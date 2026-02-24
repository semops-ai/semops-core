#!/usr/bin/env python3
"""
Source-based ingestion pipeline for Project Ike.

Ingests content from configured sources (GitHub repos, etc.) into the entity catalog
with LLM-powered semantic classification.

Usage:
 # Ingest from configured source
 python scripts/ingest_from_source.py --source project-ike-private

 # Dry run (show what would be done)
 python scripts/ingest_from_source.py --source project-ike-private --dry-run

 # Skip LLM classification
 python scripts/ingest_from_source.py --source project-ike-private --no-llm

 # List available sources
 python scripts/ingest_from_source.py --list
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(override=False)

import psycopg
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from chunker import Chunk, chunk_markdown
from db_utils import get_db_connection
from entity_builder import EntityBuilder, LLMClassification
from github_fetcher import GitHubFetcher
from lineage import LineageTracker, OperationType
from source_config import SourceConfig, list_sources, load_source_config


console = Console


def classify_content(
 content: str,
 config: SourceConfig,
) -> Optional[LLMClassification]:
 """
 Classify content using LLM if enabled.

 Args:
 content: Markdown content
 config: Source configuration

 Returns:
 LLMClassification or None if classification disabled
 """
 if not config.llm_classify.enabled:
 return None

 from llm_classifier import LLMClassifier

 try:
 classifier = LLMClassifier(model=config.llm_classify.model)
 return classifier.classify(content)
 except Exception as e:
 console.print(f"[yellow]Warning: LLM classification failed: {e}[/yellow]")
 return None


def ingest_entity(
 entity: dict,
 conn: psycopg.Connection,
 dry_run: bool = False,
) -> bool:
 """
 Insert or update entity in database.

 Args:
 entity: Entity dictionary
 conn: Database connection
 dry_run: If True, don't actually insert

 Returns:
 True if successful
 """
 if dry_run:
 return True

 cursor = conn.cursor

 try:
 # Use upsert (ON CONFLICT UPDATE)
 cursor.execute(
 """
 INSERT INTO entity (
 id, entity_type, asset_type, title, version,
 filespec, attribution, metadata,
 created_at, updated_at
 ) VALUES (
 %(id)s, %(entity_type)s, %(asset_type)s, %(title)s, %(version)s,
 %(filespec)s, %(attribution)s, %(metadata)s,
 %(created_at)s, %(updated_at)s
 )
 ON CONFLICT (id) DO UPDATE SET
 title = EXCLUDED.title,
 filespec = EXCLUDED.filespec,
 attribution = EXCLUDED.attribution,
 metadata = EXCLUDED.metadata,
 updated_at = EXCLUDED.updated_at
 """,
 {
 "id": entity["id"],
 "entity_type": entity.get("entity_type", "content"),
 "asset_type": entity["asset_type"],
 "title": entity["title"],
 "version": entity["version"],
 "filespec": json.dumps(entity["filespec"]),
 "attribution": json.dumps(entity["attribution"]),
 "metadata": json.dumps(entity["metadata"]),
 "created_at": entity["created_at"],
 "updated_at": entity["updated_at"],
 },
 )
 return True

 except Exception as e:
 console.print(f"[red]Database error: {e}[/red]")
 return False


def ingest_chunks(
 entity_id: str,
 content: str,
 source_file: str,
 corpus: str | None,
 content_type: str | None,
 conn: psycopg.Connection,
 openai_client,
 dry_run: bool = False,
) -> int:
 """
 Chunk content and insert into document_chunk table with OpenAI embeddings.

 Args:
 entity_id: Parent entity ID (FK)
 content: Raw markdown content to chunk
 source_file: Source file path/URI
 corpus: Corpus tag from entity metadata
 content_type: Content type from entity metadata
 conn: Database connection
 openai_client: OpenAI client for embeddings
 dry_run: If True, don't write

 Returns:
 Number of chunks inserted
 """
 chunks = chunk_markdown(content)
 if not chunks or dry_run:
 return len(chunks)

 cursor = conn.cursor

 # Delete existing chunks for this entity (idempotent re-ingestion)
 cursor.execute(
 "DELETE FROM document_chunk WHERE entity_id = %s",
 (entity_id,),
 )

 from generate_embeddings import EMBEDDING_MODEL, EMBEDDING_DIMENSIONS

 for chunk in chunks:
 # Generate embedding via OpenAI
 try:
 resp = openai_client.embeddings.create(
 model=EMBEDDING_MODEL,
 input=chunk.content,
 dimensions=EMBEDDING_DIMENSIONS,
 )
 embedding = resp.data[0].embedding
 except Exception:
 embedding = None

 cursor.execute(
 """
 INSERT INTO document_chunk (
 source_file, heading_hierarchy, content,
 chunk_index, total_chunks, char_count, approx_tokens,
 embedding, entity_id, corpus, content_type
 ) VALUES (
 %(source_file)s, %(hierarchy)s, %(content)s,
 %(chunk_index)s, %(total_chunks)s, %(char_count)s, %(approx_tokens)s,
 %(embedding)s, %(entity_id)s, %(corpus)s, %(content_type)s
 )
 """,
 {
 "source_file": source_file,
 "hierarchy": chunk.heading_hierarchy,
 "content": chunk.content,
 "chunk_index": chunk.chunk_index,
 "total_chunks": chunk.total_chunks,
 "char_count": chunk.char_count,
 "approx_tokens": chunk.approx_tokens,
 "embedding": embedding,
 "entity_id": entity_id,
 "corpus": corpus,
 "content_type": content_type,
 },
 )

 return len(chunks)


def materialize_edges_neo4j(
 entity: dict,
) -> int:
 """
 Write entity and its detected_edges to Neo4j.

 Args:
 entity: Entity dictionary with metadata containing detected_edges

 Returns:
 Number of edges materialized
 """
 import subprocess

 metadata = entity.get("metadata", {})
 edges = metadata.get("detected_edges", [])
 entity_id = entity["id"]
 title = entity.get("title", "")
 corpus = metadata.get("corpus", "")
 ct = metadata.get("content_type", "")

 # Create/update source node
 cypher = (
 f"MERGE (n:Entity {{id: '{entity_id}'}}) "
 f"SET n.title = '{_neo4j_escape(title)}', "
 f"n.corpus = '{_neo4j_escape(corpus)}', "
 f"n.content_type = '{_neo4j_escape(ct)}'"
 )
 _run_cypher(cypher)

 count = 0
 for edge in edges:
 target = edge.get("target_concept", "")
 predicate = edge.get("predicate", "related_to").upper.replace(" ", "_")
 strength = edge.get("strength", 0.5)
 rationale = _neo4j_escape(edge.get("rationale", ""))

 if not target:
 continue

 cypher = (
 f"MERGE (s:Entity {{id: '{entity_id}'}}) "
 f"MERGE (t:Concept {{id: '{target}'}}) "
 f"MERGE (s)-[r:{predicate}]->(t) "
 f"SET r.strength = {strength}, r.rationale = '{rationale}'"
 )
 _run_cypher(cypher)
 count += 1

 return count


def _neo4j_escape(s: str) -> str:
 """Escape single quotes for Neo4j Cypher."""
 return s.replace("\\", "\\\\").replace("'", "\\'")


NEO4J_URL = os.environ.get("NEO4J_URL", "http://localhost:7474")


def _run_cypher(cypher: str) -> bool:
 """Execute a Cypher statement against Neo4j HTTP API."""
 import subprocess

 result = subprocess.run(
 [
 "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
 "-H", "Content-Type: application/json",
 "-d", json.dumps({"statements": [{"statement": cypher}]}),
 f"{NEO4J_URL}/db/neo4j/tx/commit",
 ],
 capture_output=True,
 text=True,
 timeout=10,
 )
 return result.stdout.strip == "200"


def run_ingestion(
 source_name: str,
 dry_run: bool = False,
 no_llm: bool = False,
 verbose: bool = False,
) -> int:
 """
 Run the full ingestion pipeline for a source.

 Args:
 source_name: Name of source configuration
 dry_run: If True, don't write to database
 no_llm: If True, skip LLM classification
 verbose: If True, show detailed output

 Returns:
 Exit code (0 = success)
 """
 console.print
 console.print("[bold]Project Ike Source Ingestion[/bold]")
 console.print("=" * 40)
 console.print

 # Load configuration
 try:
 config = load_source_config(source_name)
 console.print(f"[green]Loaded source:[/green] {config.name}")
 console.print(f" GitHub: {config.github.owner}/{config.github.repo}")
 console.print(f" Base path: {config.github.base_path or '(root)'}")
 console.print(f" LLM classification: {'disabled' if no_llm else 'enabled'}")
 console.print
 except FileNotFoundError as e:
 console.print(f"[red]Error: {e}[/red]")
 return 1

 # Override LLM config if --no-llm
 if no_llm:
 config.llm_classify.enabled = False

 # Initialize fetcher
 try:
 fetcher = GitHubFetcher(
 config.github.owner,
 config.github.repo,
 config.github.branch,
 )
 except RuntimeError as e:
 console.print(f"[red]Error: {e}[/red]")
 return 1

 # List files to ingest
 console.print("[bold]Discovering files...[/bold]")
 try:
 files = fetcher.list_files(
 config.github.base_path,
 extensions=config.github.file_extensions,
 include_dirs=config.github.include_directories or None,
 exclude_patterns=config.github.exclude_patterns or None,
 )
 console.print(f"Found {len(files)} files to ingest")
 console.print
 except RuntimeError as e:
 console.print(f"[red]Error listing files: {e}[/red]")
 return 1

 if not files:
 console.print("[yellow]No files found to ingest[/yellow]")
 return 0

 # Connect to database
 conn = None
 if not dry_run:
 try:
 conn = get_db_connection
 conn.autocommit = False
 except Exception as e:
 console.print(f"[red]Database connection failed: {e}[/red]")
 return 1

 # Initialize OpenAI client for chunk embeddings
 openai_client = None
 if not dry_run:
 try:
 api_key = os.environ.get("OPENAI_API_KEY")
 if api_key:
 from openai import OpenAI
 openai_client = OpenAI(api_key=api_key)
 except Exception as e:
 console.print(f"[yellow]Warning: OpenAI client init failed (chunks won't get embeddings): {e}[/yellow]")

 # Process files
 builder = EntityBuilder(config)
 results = []
 total_chunks = 0
 total_edges = 0

 console.print("[bold]Processing files...[/bold]")

 # Wrap pipeline in lineage tracker for provenance
 tracker = LineageTracker(
 source_name=source_name,
 run_type="manual",
 agent_name="ingest_from_source",
 source_config={
 "github": f"{config.github.owner}/{config.github.repo}",
 "base_path": config.github.base_path,
 "llm_enabled": config.llm_classify.enabled,
 "file_count": len(files),
 },
 ) if not dry_run else None

 with tracker if tracker else open(os.devnull):
 with Progress(
 SpinnerColumn,
 TextColumn("[progress.description]{task.description}"),
 console=console,
 transient=True,
 ) as progress:
 task = progress.add_task("Processing...", total=len(files))

 for file_path in files:
 progress.update(task, description=f"Processing {Path(file_path).name}...")

 try:
 # Fetch file
 fetched = fetcher.fetch_file(file_path)

 # Build entity
 classification = None
 if config.llm_classify.enabled:
 classification = classify_content(fetched.content, config)

 entity = builder.build(fetched, classification)

 # Insert into database
 success = ingest_entity(entity, conn, dry_run=dry_run)

 # Emit lineage episodes
 if tracker and success:
 with tracker.track_operation(
 operation=OperationType.INGEST,
 target_type="entity",
 target_id=entity["id"],
 ) as episode:
 episode.set_agent_info(name="ingest_from_source")
 episode.metadata = {"file_path": file_path, "title": entity["title"]}

 if classification is not None:
 with tracker.track_operation(
 operation=OperationType.CLASSIFY,
 target_type="entity",
 target_id=entity["id"],
 ) as episode:
 episode.set_agent_info(
 name="llm_classifier",
 model=config.llm_classify.model,
 )
 if hasattr(classification, "coherence_score") and classification.coherence_score:
 episode.coherence_score = classification.coherence_score
 if classification.detected_edges:
 for edge in classification.detected_edges:
 episode.add_detected_edge(
 predicate=edge.get("predicate", "related_to"),
 target_id=edge.get("target_concept", ""),
 strength=edge.get("strength", 0.5),
 rationale=edge.get("rationale", ""),
 )

 # Chunk content and insert with embeddings
 chunk_count = 0
 if success and openai_client:
 try:
 chunk_count = ingest_chunks(
 entity_id=entity["id"],
 content=fetched.content,
 source_file=file_path,
 corpus=entity["metadata"].get("corpus"),
 content_type=entity["metadata"].get("content_type"),
 conn=conn,
 openai_client=openai_client,
 dry_run=dry_run,
 )
 total_chunks += chunk_count
 except Exception as e:
 console.print(f"[yellow]Chunking failed for {entity['id']}: {e}[/yellow]")

 # Materialize graph edges to Neo4j
 edge_count = 0
 if success and not dry_run:
 try:
 edge_count = materialize_edges_neo4j(entity)
 total_edges += edge_count
 except Exception as e:
 console.print(f"[yellow]Graph materialization failed for {entity['id']}: {e}[/yellow]")

 results.append({
 "file": file_path,
 "entity_id": entity["id"],
 "title": entity["title"],
 "classified": classification is not None,
 "success": success,
 "chunks": chunk_count,
 "edges": edge_count,
 "concept_ownership": (
 classification.concept_ownership if classification else None
 ),
 "content_type": (
 classification.content_type if classification else None
 ),
 })

 except Exception as e:
 console.print(f"[red]Error processing {file_path}: {e}[/red]")
 results.append({
 "file": file_path,
 "entity_id": None,
 "title": None,
 "classified": False,
 "success": False,
 "error": str(e),
 })

 progress.advance(task)

 # Commit transaction
 if conn and not dry_run:
 try:
 conn.commit
 except Exception as e:
 console.print(f"[red]Commit failed: {e}[/red]")
 conn.rollback
 return 1
 finally:
 conn.close

 # Print results table
 console.print
 table = Table(title="Ingestion Results")
 table.add_column("Entity ID", style="cyan")
 table.add_column("Title", max_width=40)
 table.add_column("Type", style="magenta")
 table.add_column("Chunks", justify="right")
 table.add_column("Edges", justify="right")
 table.add_column("Status", justify="center")

 for r in results:
 if r["success"]:
 status = "[green]OK[/green]"
 else:
 status = "[red]FAIL[/red]"

 table.add_row(
 r.get("entity_id") or "-",
 (r.get("title") or "-")[:40],
 r.get("content_type") or "-",
 str(r.get("chunks", 0)),
 str(r.get("edges", 0)),
 status,
 )

 console.print(table)

 # Summary
 successful = sum(1 for r in results if r["success"])
 failed = len(results) - successful
 classified = sum(1 for r in results if r.get("classified"))

 console.print
 if dry_run:
 console.print(f"[yellow]DRY RUN:[/yellow] Would ingest {successful} entities")
 else:
 console.print(f"[green]Successfully ingested:[/green] {successful}")

 if failed:
 console.print(f"[red]Failed:[/red] {failed}")

 if classified:
 console.print(f"[blue]LLM classified:[/blue] {classified}")

 if total_chunks:
 console.print(f"[blue]Chunks created:[/blue] {total_chunks}")

 if total_edges:
 console.print(f"[blue]Graph edges:[/blue] {total_edges}")

 console.print

 return 0 if failed == 0 else 1


def main:
 """Main entry point."""
 parser = argparse.ArgumentParser(
 description="Ingest content from configured sources into Project Ike"
 )
 parser.add_argument(
 "--source",
 type=str,
 help="Source configuration name (e.g., 'project-ike-private')",
 )
 parser.add_argument(
 "--list",
 action="store_true",
 help="List available source configurations",
 )
 parser.add_argument(
 "--dry-run",
 action="store_true",
 help="Show what would be done without writing to database",
 )
 parser.add_argument(
 "--no-llm",
 action="store_true",
 help="Skip LLM classification",
 )
 parser.add_argument(
 "--verbose",
 "-v",
 action="store_true",
 help="Show detailed output",
 )

 args = parser.parse_args

 if args.list:
 sources = list_sources
 if sources:
 console.print("[bold]Available sources:[/bold]")
 for source in sources:
 console.print(f" - {source}")
 else:
 console.print("[yellow]No source configurations found in config/sources/[/yellow]")
 return 0

 if not args.source:
 parser.print_help
 return 1

 return run_ingestion(
 args.source,
 dry_run=args.dry_run,
 no_llm=args.no_llm,
 verbose=args.verbose,
 )


if __name__ == "__main__":
 sys.exit(main)
