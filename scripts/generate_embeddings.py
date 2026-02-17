#!/usr/bin/env python3
"""
Embedding generation for SemOps entities.

Generates OpenAI embeddings for entity content and stores them in pgvector.

Usage:
    # Generate embeddings for all entities without them
    python scripts/generate_embeddings.py

    # Regenerate all embeddings
    python scripts/generate_embeddings.py --regenerate

    # Process specific entity
    python scripts/generate_embeddings.py --entity-id semantic-operations

    # Dry run
    python scripts/generate_embeddings.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from openai import OpenAI
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

sys.path.insert(0, str(Path(__file__).parent))
from db_utils import get_db_connection
from search import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL

console = Console()


def get_openai_client() -> OpenAI:
    """Get OpenAI client."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment")
    return OpenAI(api_key=api_key)


def build_embedding_text(entity: dict) -> str:
    """
    Build text for embedding from entity metadata.

    Combines title, summary, and concept information for rich embeddings.
    """
    parts = []

    # Title
    if entity.get("title"):
        parts.append(f"Title: {entity['title']}")

    # Summary from metadata
    metadata = entity.get("metadata") or {}
    if metadata.get("summary"):
        parts.append(f"Summary: {metadata['summary']}")

    # Content type
    if metadata.get("content_type"):
        parts.append(f"Type: {metadata['content_type']}")

    # Primary concept
    if metadata.get("primary_concept"):
        parts.append(f"Concept: {metadata['primary_concept']}")

    # Subject areas
    if metadata.get("subject_area"):
        areas = metadata["subject_area"]
        if isinstance(areas, list):
            parts.append(f"Subject areas: {', '.join(areas)}")

    # Broader concepts
    if metadata.get("broader_concepts"):
        concepts = metadata["broader_concepts"]
        if isinstance(concepts, list):
            parts.append(f"Broader concepts: {', '.join(concepts)}")

    # Narrower concepts
    if metadata.get("narrower_concepts"):
        concepts = metadata["narrower_concepts"]
        if isinstance(concepts, list):
            parts.append(f"Narrower concepts: {', '.join(concepts)}")

    return "\n".join(parts)


def generate_embedding(client: OpenAI, text: str) -> list[float]:
    """Generate embedding for text using OpenAI API."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding


def get_entities_to_embed(
    conn: psycopg.Connection,
    regenerate: bool = False,
    entity_id: str | None = None,
) -> list[dict]:
    """Get entities that need embeddings."""
    cursor = conn.cursor()

    if entity_id:
        cursor.execute(
            """
            SELECT id, title, metadata
            FROM entity
            WHERE id = %s
            """,
            (entity_id,),
        )
    elif regenerate:
        cursor.execute(
            """
            SELECT id, title, metadata
            FROM entity
            ORDER BY id
            """
        )
    else:
        cursor.execute(
            """
            SELECT id, title, metadata
            FROM entity
            WHERE embedding IS NULL
            ORDER BY id
            """
        )

    rows = cursor.fetchall()
    return [{"id": r[0], "title": r[1], "metadata": r[2]} for r in rows]


def update_embedding(
    conn: psycopg.Connection,
    entity_id: str,
    embedding: list[float],
) -> None:
    """Update entity with embedding."""
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE entity
        SET embedding = %s::vector
        WHERE id = %s
        """,
        (embedding, entity_id),
    )


def main():
    parser = argparse.ArgumentParser(description="Generate embeddings for entities")
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate all embeddings (not just missing)",
    )
    parser.add_argument(
        "--entity-id",
        type=str,
        help="Process specific entity by ID",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    console.print()
    console.print("[bold]SemOps Embedding Generator[/bold]")
    console.print("=" * 40)
    console.print()

    # Initialize clients
    try:
        openai_client = get_openai_client()
        conn = get_db_connection()
        conn.autocommit = False
    except Exception as e:
        console.print(f"[red]Initialization failed: {e}[/red]")
        return 1

    # Get entities to process
    entities = get_entities_to_embed(conn, args.regenerate, args.entity_id)
    console.print(f"Found {len(entities)} entities to embed")
    console.print()

    if not entities:
        console.print("[green]All entities already have embeddings[/green]")
        return 0

    if args.dry_run:
        console.print("[yellow]DRY RUN - no changes will be made[/yellow]")
        console.print()
        for e in entities[:10]:
            text = build_embedding_text(e)
            console.print(f"[cyan]{e['id']}[/cyan]: {len(text)} chars")
        if len(entities) > 10:
            console.print(f"... and {len(entities) - 10} more")
        return 0

    # Process entities
    success_count = 0
    error_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Generating embeddings...", total=len(entities))

        for entity in entities:
            progress.update(task, description=f"Embedding {entity['id']}...")

            try:
                # Build text for embedding
                text = build_embedding_text(entity)

                if not text.strip():
                    console.print(f"[yellow]Skipping {entity['id']}: no text[/yellow]")
                    continue

                # Generate embedding
                embedding = generate_embedding(openai_client, text)

                # Update database
                update_embedding(conn, entity["id"], embedding)
                success_count += 1

            except Exception as e:
                console.print(f"[red]Error for {entity['id']}: {e}[/red]")
                error_count += 1

            progress.advance(task)

    # Commit
    try:
        conn.commit()
    except Exception as e:
        console.print(f"[red]Commit failed: {e}[/red]")
        conn.rollback()
        return 1
    finally:
        conn.close()

    # Summary
    console.print()
    console.print(f"[green]Successfully embedded:[/green] {success_count}")
    if error_count:
        console.print(f"[red]Errors:[/red] {error_count}")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
