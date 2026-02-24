#!/usr/bin/env python3
"""
Document ingestion pipeline using Docling for Project Ike.

Processes documents (PDF, DOCX, PPTX, etc.) through Docling,
chunks the content, generates embeddings, and stores in PostgreSQL.

Based on: https://github.com/coleam00/ottomator-agents/tree/main/docling-rag-agent

Usage:
 # Process a single file
 python scripts/docling_ingest.py /path/to/document.pdf

 # Process all files in a directory
 python scripts/docling_ingest.py /path/to/docs/ --recursive

 # Dry run
 python scripts/docling_ingest.py /path/to/docs/ --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Optional

import httpx
import psycopg
from openai import OpenAI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

sys.path.insert(0, str(Path(__file__).parent))
from db_utils import get_db_connection

console = Console

# Configuration
DOCLING_URL = os.environ.get("DOCLING_URL", "http://localhost:5001")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
CHUNK_SIZE = 1000 # characters
CHUNK_OVERLAP = 200 # characters


def get_openai_client -> OpenAI:
 """Get OpenAI client."""
 api_key = os.environ.get("OPENAI_API_KEY")
 if not api_key:
 raise ValueError("OPENAI_API_KEY not set in environment")
 return OpenAI(api_key=api_key)


def process_with_docling(file_path: Path) -> str:
 """
 Process document through Docling API.

 Args:
 file_path: Path to document file

 Returns:
 Extracted text as markdown
 """
 with open(file_path, "rb") as f:
 files = {"file": (file_path.name, f)}
 response = httpx.post(
 f"{DOCLING_URL}/v1/convert/file",
 files=files,
 timeout=300.0, # 5 min timeout for large docs
 )

 if response.status_code != 200:
 raise RuntimeError(f"Docling API error: {response.status_code} - {response.text}")

 result = response.json
 # Docling returns markdown in the 'md' field
 return result.get("md", result.get("text", ""))


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
 """
 Split text into overlapping chunks.

 Args:
 text: Text to chunk
 chunk_size: Target chunk size in characters
 overlap: Overlap between chunks

 Returns:
 List of text chunks
 """
 if len(text) <= chunk_size:
 return [text]

 chunks = []
 start = 0

 while start < len(text):
 end = start + chunk_size

 # Try to break at sentence boundary
 if end < len(text):
 # Look for sentence end (.!?) followed by space or newline
 for i in range(end, max(start + chunk_size // 2, 0), -1):
 if text[i] in ".!?" and (i + 1 >= len(text) or text[i + 1] in " \n"):
 end = i + 1
 break

 chunk = text[start:end].strip
 if chunk:
 chunks.append(chunk)

 start = end - overlap

 return chunks


def generate_embedding(client: OpenAI, text: str) -> list[float]:
 """Generate embedding for text using OpenAI API."""
 response = client.embeddings.create(
 model=EMBEDDING_MODEL,
 input=text,
 dimensions=EMBEDDING_DIMENSIONS,
 )
 return response.data[0].embedding


def derive_entity_id(file_path: Path) -> str:
 """Derive entity ID from file path."""
 name = file_path.stem.lower
 # Convert to kebab-case
 name = re.sub(r"[^a-z0-9]+", "-", name)
 name = re.sub(r"-+", "-", name).strip("-")
 return f"doc-{name}"


def compute_file_hash(file_path: Path) -> str:
 """Compute SHA256 hash of file."""
 sha256 = hashlib.sha256
 with open(file_path, "rb") as f:
 for chunk in iter(lambda: f.read(8192), b""):
 sha256.update(chunk)
 return sha256.hexdigest


def ingest_document(
 file_path: Path,
 conn: psycopg.Connection,
 openai_client: OpenAI,
 dry_run: bool = False,
) -> dict:
 """
 Ingest a single document into the database.

 Args:
 file_path: Path to document
 conn: Database connection
 openai_client: OpenAI client
 dry_run: If True, don't write to database

 Returns:
 Result dictionary with ingestion details
 """
 entity_id = derive_entity_id(file_path)
 file_hash = compute_file_hash(file_path)

 result = {
 "file": str(file_path),
 "entity_id": entity_id,
 "chunks": 0,
 "success": False,
 "error": None,
 }

 try:
 # Process through Docling
 console.print(f" Processing with Docling...", style="dim")
 markdown_text = process_with_docling(file_path)

 if not markdown_text.strip:
 result["error"] = "No text extracted"
 return result

 # Chunk the text
 chunks = chunk_text(markdown_text)
 result["chunks"] = len(chunks)

 if dry_run:
 result["success"] = True
 return result

 cursor = conn.cursor

 # Create or update entity
 cursor.execute(
 """
 INSERT INTO entity (
 id, asset_type, title, version, visibility,
 approval_status, provenance, filespec, attribution, metadata
 ) VALUES (
 %(id)s, 'file', %(title)s, '1.0', 'private',
 'pending', '3p',
 %(filespec)s::jsonb,
 %(attribution)s::jsonb,
 %(metadata)s::jsonb
 )
 ON CONFLICT (id) DO UPDATE SET
 title = EXCLUDED.title,
 filespec = EXCLUDED.filespec,
 metadata = EXCLUDED.metadata,
 updated_at = now
 """,
 {
 "id": entity_id,
 "title": file_path.stem,
 "filespec": f'{{"$schema": "filespec_v1", "uri": "file://{file_path}", "format": "{file_path.suffix[1:]}", "hash": "sha256:{file_hash}", "size_bytes": {file_path.stat.st_size}}}',
 "attribution": '{"$schema": "attribution_v2", "platform": "local"}',
 "metadata": f'{{"$schema": "content_metadata_v1", "content_type": "document", "media_type": "text", "word_count": {len(markdown_text.split)}}}',
 },
 )

 # Generate embedding from full text (or summary)
 # Use first chunk + title for entity embedding
 embed_text = f"Title: {file_path.stem}\n\n{chunks[0]}"
 embedding = generate_embedding(openai_client, embed_text[:8000])

 cursor.execute(
 "UPDATE entity SET embedding = %s::vector WHERE id = %s",
 (embedding, entity_id),
 )

 result["success"] = True

 except Exception as e:
 result["error"] = str(e)

 return result


def find_documents(path: Path, recursive: bool = False) -> list[Path]:
 """Find processable documents in path."""
 supported_extensions = {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".md", ".txt"}

 if path.is_file:
 if path.suffix.lower in supported_extensions:
 return [path]
 return []

 if recursive:
 files = list(path.rglob("*"))
 else:
 files = list(path.glob("*"))

 return [f for f in files if f.is_file and f.suffix.lower in supported_extensions]


def main:
 parser = argparse.ArgumentParser(description="Ingest documents using Docling")
 parser.add_argument("path", type=str, help="File or directory to process")
 parser.add_argument(
 "--recursive",
 "-r",
 action="store_true",
 help="Recursively process directories",
 )
 parser.add_argument(
 "--dry-run",
 action="store_true",
 help="Show what would be done without making changes",
 )
 args = parser.parse_args

 console.print
 console.print("[bold]Docling Document Ingestion[/bold]")
 console.print("=" * 40)
 console.print

 path = Path(args.path)
 if not path.exists:
 console.print(f"[red]Path not found: {path}[/red]")
 return 1

 # Find documents
 documents = find_documents(path, args.recursive)
 if not documents:
 console.print("[yellow]No supported documents found[/yellow]")
 return 0

 console.print(f"Found {len(documents)} documents to process")
 console.print

 if args.dry_run:
 console.print("[yellow]DRY RUN - no changes will be made[/yellow]")
 console.print

 # Initialize clients
 try:
 openai_client = get_openai_client
 conn = get_db_connection
 conn.autocommit = False
 except Exception as e:
 console.print(f"[red]Initialization failed: {e}[/red]")
 return 1

 # Process documents
 results = []

 with Progress(
 SpinnerColumn,
 TextColumn("[progress.description]{task.description}"),
 console=console,
 transient=True,
 ) as progress:
 task = progress.add_task("Processing...", total=len(documents))

 for doc_path in documents:
 progress.update(task, description=f"Processing {doc_path.name}...")

 result = ingest_document(doc_path, conn, openai_client, args.dry_run)
 results.append(result)

 if result["success"]:
 console.print(f"[green]OK[/green] {doc_path.name} ({result['chunks']} chunks)")
 else:
 console.print(f"[red]FAIL[/red] {doc_path.name}: {result['error']}")

 progress.advance(task)

 # Commit
 if not args.dry_run:
 try:
 conn.commit
 except Exception as e:
 console.print(f"[red]Commit failed: {e}[/red]")
 conn.rollback
 return 1
 finally:
 conn.close

 # Summary
 console.print
 success = sum(1 for r in results if r["success"])
 failed = len(results) - success

 if args.dry_run:
 console.print(f"[yellow]Would process:[/yellow] {success} documents")
 else:
 console.print(f"[green]Successfully processed:[/green] {success}")

 if failed:
 console.print(f"[red]Failed:[/red] {failed}")

 return 0 if failed == 0 else 1


if __name__ == "__main__":
 sys.exit(main)
