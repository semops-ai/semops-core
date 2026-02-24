#!/usr/bin/env python3
"""
Semantic search for the Project SemOps knowledge base using pgvector.

Searches entities, document chunks, or both (hybrid) with optional filtering.

Usage:
 # Chunk search (default — passage-level retrieval)
 python scripts/semantic_search.py "What is semantic coherence?"

 # Entity search
 python scripts/semantic_search.py "domain patterns" --mode entities

 # Hybrid search (entities + top chunks per entity)
 python scripts/semantic_search.py "architecture decisions" --mode hybrid

 # Filter by corpus
 python scripts/semantic_search.py "AI transformation" --corpus core_kb research_ai

 # Filter by content type
 python scripts/semantic_search.py "architecture decisions" --mode entities --content-type adr

 # Filter by lifecycle stage (entity mode only)
 python scripts/semantic_search.py "draft concepts" --mode entities --lifecycle-stage draft

 # Limit results and show details
 python scripts/semantic_search.py "domain driven design" --limit 5 --verbose
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from openai import OpenAI
from rich.console import Console
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))
from db_utils import get_db_connection
from search import (
 EMBEDDING_DIMENSIONS,
 EMBEDDING_MODEL,
 search_chunks,
 search_entities,
 search_hybrid,
)

console = Console


def get_openai_client -> OpenAI:
 """Get OpenAI client."""
 api_key = os.environ.get("OPENAI_API_KEY")
 if not api_key:
 raise ValueError("OPENAI_API_KEY not set in environment")
 return OpenAI(api_key=api_key)


def generate_query_embedding(client: OpenAI, query: str) -> list[float]:
 """Generate embedding for search query."""
 response = client.embeddings.create(
 model=EMBEDDING_MODEL,
 input=query,
 dimensions=EMBEDDING_DIMENSIONS,
 )
 return response.data[0].embedding


# ---------------------------------------------------------------------------
# Display formatters
# ---------------------------------------------------------------------------


def display_entity_results(results: list[dict], verbose: bool = False) -> None:
 """Display entity search results as a Rich table."""
 if not results:
 console.print("[yellow]No entity results found[/yellow]")
 return

 table = Table(title=f"Top {len(results)} Entity Results")
 table.add_column("Score", justify="right", style="green")
 table.add_column("ID", style="cyan")
 table.add_column("Title", max_width=40)
 table.add_column("Corpus", style="yellow")
 table.add_column("Type", style="magenta")
 table.add_column("Owner")

 for r in results:
 table.add_row(
 f"{r['similarity']:.3f}",
 r["id"],
 (r["title"] or "-")[:40],
 r["corpus"] or "-",
 r["content_type"] or "-",
 r["ownership"] or "-",
 )

 console.print(table)

 if verbose:
 console.print
 console.print("[bold]Summaries:[/bold]")
 for r in results[:5]:
 if r["summary"]:
 console.print(f"\n[cyan]{r['id']}[/cyan]:")
 console.print(f" {r['summary'][:200]}...")


def display_chunk_results(results: list[dict], verbose: bool = False) -> None:
 """Display chunk search results as a Rich table."""
 if not results:
 console.print("[yellow]No chunk results found[/yellow]")
 return

 table = Table(title=f"Top {len(results)} Chunk Results")
 table.add_column("Score", justify="right", style="green")
 table.add_column("Entity", style="cyan", max_width=30)
 table.add_column("Source", max_width=25)
 table.add_column("Heading", max_width=35)
 table.add_column("Corpus", style="yellow")
 table.add_column("Chunk", justify="right", style="dim")

 for r in results:
 heading = " > ".join(r["heading_hierarchy"][-2:]) if r["heading_hierarchy"] else "-"
 source = (r["source_file"] or "").split("/")[-1] or "-"
 chunk_info = f"{r['chunk_index']}/{r['total_chunks']}" if r["total_chunks"] else "-"

 table.add_row(
 f"{r['similarity']:.3f}",
 (r["entity_id"] or "-")[:30],
 source[:25],
 heading[:35],
 r["corpus"] or "-",
 chunk_info,
 )

 console.print(table)

 if verbose:
 console.print
 console.print("[bold]Content previews:[/bold]")
 for r in results[:5]:
 if r["content"]:
 heading = " > ".join(r["heading_hierarchy"]) if r["heading_hierarchy"] else "(root)"
 console.print(f"\n[cyan]{r['entity_id']}[/cyan] [{heading}]:")
 console.print(f" {r['content'][:200]}...")


def display_hybrid_results(results: list[dict], verbose: bool = False) -> None:
 """Display hybrid search results."""
 if not results:
 console.print("[yellow]No hybrid results found[/yellow]")
 return

 total_chunks = sum(len(r["chunks"]) for r in results)
 console.print(f"[bold]Hybrid Results:[/bold] {len(results)} entities, {total_chunks} chunks")
 console.print

 for r in results:
 entity = r["entity"]
 chunks = r["chunks"]

 console.print(
 f"[bold cyan]{entity['id']}[/bold cyan] "
 f"[green]({entity['similarity']:.3f})[/green] "
 f"— {entity['title'] or '(untitled)'}"
 )

 if not chunks:
 console.print(" [dim]No chunks found[/dim]")
 else:
 for c in chunks:
 hierarchy = c["heading_hierarchy"]
 heading = " > ".join(hierarchy[-2:]) if hierarchy else "(root)"
 console.print(f" [green]{c['similarity']:.3f}[/green] [dim]{heading}[/dim]")
 if verbose and c["content"]:
 console.print(f" {c['content'][:150]}...")

 console.print


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main:
 parser = argparse.ArgumentParser(
 description="Semantic search for the SemOps knowledge base",
 )
 parser.add_argument("query", type=str, help="Search query")
 parser.add_argument(
 "--mode",
 choices=["chunks", "entities", "hybrid"],
 default="chunks",
 help="Search mode (default: chunks)",
 )
 parser.add_argument(
 "--limit",
 type=int,
 default=10,
 help="Maximum results to return",
 )
 parser.add_argument(
 "--corpus",
 nargs="+",
 help="Filter by corpus (e.g., core_kb, deployment, research_ai)",
 )
 parser.add_argument(
 "--content-type",
 nargs="+",
 help="Filter by content type (e.g., concept, pattern, adr)",
 )
 parser.add_argument(
 "--lifecycle-stage",
 nargs="+",
 help="Filter by lifecycle stage (entity mode only)",
 )
 parser.add_argument(
 "--verbose",
 "-v",
 action="store_true",
 help="Show detailed output including content previews",
 )
 args = parser.parse_args

 console.print
 console.print(f"[bold]Searching ({args.mode}):[/bold] {args.query}")
 if args.corpus:
 console.print(f"[dim]Corpus filter: {', '.join(args.corpus)}[/dim]")
 if args.content_type:
 console.print(f"[dim]Content type filter: {', '.join(args.content_type)}[/dim]")
 if args.lifecycle_stage:
 if args.mode != "entities":
 console.print("[yellow]Warning: --lifecycle-stage only applies to entity mode[/yellow]")
 else:
 console.print(f"[dim]Lifecycle stage filter: {', '.join(args.lifecycle_stage)}[/dim]")
 console.print

 try:
 openai_client = get_openai_client
 conn = get_db_connection
 except Exception as e:
 console.print(f"[red]Initialization failed: {e}[/red]")
 return 1

 try:
 query_embedding = generate_query_embedding(openai_client, args.query)
 except Exception as e:
 console.print(f"[red]Failed to generate query embedding: {e}[/red]")
 return 1

 if args.mode == "entities":
 results = search_entities(
 conn,
 query_embedding,
 limit=args.limit,
 corpus=args.corpus,
 content_type=args.content_type,
 lifecycle_stage=args.lifecycle_stage,
 )
 display_entity_results(results, verbose=args.verbose)

 elif args.mode == "chunks":
 results = search_chunks(
 conn,
 query_embedding,
 limit=args.limit,
 corpus=args.corpus,
 content_max_chars=500,
 )
 display_chunk_results(results, verbose=args.verbose)

 elif args.mode == "hybrid":
 results = search_hybrid(
 conn,
 query_embedding,
 entity_limit=min(args.limit, 10),
 corpus=args.corpus,
 content_max_chars=500,
 )
 display_hybrid_results(results, verbose=args.verbose)

 conn.close
 return 0


if __name__ == "__main__":
 sys.exit(main)
