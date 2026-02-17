#!/usr/bin/env python3
"""
Materialize entity edges into Neo4j graph.

Reads detected_edges from entity metadata in Supabase and creates
nodes + relationships in Neo4j. Safe to re-run (uses MERGE).

Usage:
    python scripts/materialize_graph.py
    python scripts/materialize_graph.py --dry-run
    python scripts/materialize_graph.py --clear
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

sys.path.insert(0, str(Path(__file__).parent))
from db_utils import get_db_connection

console = Console()

NEO4J_URL = os.environ.get("NEO4J_URL", "http://localhost:7474")


def neo4j_escape(s: str) -> str:
    """Escape for Cypher."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def run_cypher(cypher: str) -> dict | None:
    """Execute Cypher via HTTP API."""
    try:
        result = subprocess.run(
            [
                "curl", "-s",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({"statements": [{"statement": cypher}]}),
                f"{NEO4J_URL}/db/neo4j/tx/commit",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return json.loads(result.stdout) if result.returncode == 0 else None
    except Exception:
        return None


def clear_graph() -> None:
    """Delete all nodes and relationships."""
    run_cypher("MATCH (n) DETACH DELETE n")
    console.print("[yellow]Cleared all nodes and relationships from Neo4j[/yellow]")


def main():
    parser = argparse.ArgumentParser(description="Materialize entity edges to Neo4j")
    parser.add_argument("--dry-run", action="store_true", help="Show counts without writing")
    parser.add_argument("--clear", action="store_true", help="Clear graph before materializing")
    args = parser.parse_args()

    console.print()
    console.print("[bold]Neo4j Graph Materialization[/bold]")
    console.print("=" * 40)
    console.print()

    # Check Neo4j connectivity
    health = run_cypher("RETURN 1")
    if health is None:
        console.print("[red]Cannot connect to Neo4j at {NEO4J_URL}[/red]")
        return 1

    if args.clear and not args.dry_run:
        clear_graph()

    # Get entities with edges
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, title, metadata
        FROM entity
        WHERE metadata->'detected_edges' IS NOT NULL
          AND jsonb_array_length(metadata->'detected_edges') > 0
        ORDER BY id
        """
    )
    entities = cursor.fetchall()
    conn.close()

    console.print(f"Found {len(entities)} entities with detected edges")

    if args.dry_run:
        total_edges = 0
        for _, _, metadata in entities:
            edges = (metadata or {}).get("detected_edges", [])
            total_edges += len(edges)
        console.print(f"Would create {len(entities)} entity nodes and {total_edges} edges")
        return 0

    # Materialize
    node_count = 0
    edge_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Materializing...", total=len(entities))

        for entity_id, title, metadata in entities:
            progress.update(task, description=f"Processing {entity_id}...")
            metadata = metadata or {}
            corpus = metadata.get("corpus", "")
            ct = metadata.get("content_type", "")

            # Create entity node
            cypher = (
                f"MERGE (n:Entity {{id: '{entity_id}'}}) "
                f"SET n.title = '{neo4j_escape(title or '')}', "
                f"n.corpus = '{neo4j_escape(corpus)}', "
                f"n.content_type = '{neo4j_escape(ct)}'"
            )
            run_cypher(cypher)
            node_count += 1

            # Create edges
            for edge in metadata.get("detected_edges", []):
                target = edge.get("target_concept", "")
                predicate = edge.get("predicate", "related_to").upper().replace(" ", "_")
                strength = edge.get("strength", 0.5)
                rationale = neo4j_escape(edge.get("rationale", ""))

                if not target:
                    continue

                cypher = (
                    f"MERGE (s:Entity {{id: '{entity_id}'}}) "
                    f"MERGE (t:Concept {{id: '{target}'}}) "
                    f"MERGE (s)-[r:{predicate}]->(t) "
                    f"SET r.strength = {strength}, r.rationale = '{rationale}'"
                )
                run_cypher(cypher)
                edge_count += 1

            progress.advance(task)

    console.print()
    console.print(f"[green]Entity nodes created/updated:[/green] {node_count}")
    console.print(f"[green]Edges materialized:[/green] {edge_count}")

    # Show graph stats
    result = run_cypher("MATCH (n) RETURN count(n) as nodes")
    if result and result.get("results"):
        total = result["results"][0]["data"][0]["row"][0]
        console.print(f"[blue]Total graph nodes:[/blue] {total}")

    result = run_cypher("MATCH ()-[r]->() RETURN count(r) as rels")
    if result and result.get("results"):
        total = result["results"][0]["data"][0]["row"][0]
        console.print(f"[blue]Total graph relationships:[/blue] {total}")

    console.print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
