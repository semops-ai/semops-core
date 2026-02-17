#!/usr/bin/env python3
"""
Sync concepts and edges from PostgreSQL to Neo4j.

Creates nodes for concepts and relationships for edges,
enabling graph-based analysis and the GraphClassifier.

Usage:
    python3 scripts/sync_concepts_to_neo4j.py

Requires:
    - PostgreSQL with concepts loaded
    - Neo4j running (docker compose up neo4j)
"""

import subprocess
import sys
import json


NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"


def run_cypher(query: str) -> tuple[bool, str]:
    """Execute a Cypher query in Neo4j."""
    result = subprocess.run(
        [
            "docker", "exec", "ike-neo4j",
            "cypher-shell", "-u", NEO4J_USER, "-p", NEO4J_PASSWORD,
            query
        ],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout + result.stderr


def get_concepts_from_postgres() -> list[dict]:
    """Fetch all concepts from PostgreSQL."""
    sql = """
    SELECT id, preferred_label, definition, provenance, approval_status
    FROM concept
    ORDER BY id;
    """
    result = subprocess.run(
        ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-F", "|||", "-c", sql],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Error fetching concepts: {result.stderr}", file=sys.stderr)
        return []

    concepts = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split("|||")
            if len(parts) >= 5:
                concepts.append({
                    "id": parts[0],
                    "preferred_label": parts[1],
                    "definition": parts[2][:200] if len(parts[2]) > 200 else parts[2],  # Truncate for Neo4j
                    "provenance": parts[3],
                    "approval_status": parts[4]
                })
    return concepts


def get_edges_from_postgres() -> list[tuple]:
    """Fetch all concept edges from PostgreSQL."""
    sql = """
    SELECT src_id, dst_id, predicate
    FROM concept_edge
    ORDER BY src_id, dst_id;
    """
    result = subprocess.run(
        ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-F", "|||", "-c", sql],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Error fetching edges: {result.stderr}", file=sys.stderr)
        return []

    edges = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split("|||")
            if len(parts) >= 3:
                edges.append((parts[0], parts[1], parts[2]))
    return edges


def escape_neo4j(s: str) -> str:
    """Escape string for Neo4j Cypher."""
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def create_concept_node(concept: dict) -> str:
    """Generate MERGE statement for a concept node."""
    return f"""
MERGE (c:Concept {{id: '{escape_neo4j(concept["id"])}'}})
SET c.preferred_label = '{escape_neo4j(concept["preferred_label"])}',
    c.definition = '{escape_neo4j(concept["definition"])}',
    c.provenance = '{escape_neo4j(concept["provenance"])}',
    c.approval_status = '{escape_neo4j(concept["approval_status"])}';
"""


def create_edge_relationship(src_id: str, dst_id: str, predicate: str) -> str:
    """Generate MERGE statement for an edge relationship."""
    # Map predicate to Neo4j relationship type (uppercase)
    rel_type = predicate.upper()
    return f"""
MATCH (src:Concept {{id: '{escape_neo4j(src_id)}'}}), (dst:Concept {{id: '{escape_neo4j(dst_id)}'}})
MERGE (src)-[r:{rel_type}]->(dst);
"""


def main():
    print("=== Syncing concepts to Neo4j ===\n")

    # Clear existing data
    print("Clearing existing Concept nodes...")
    success, output = run_cypher("MATCH (c:Concept) DETACH DELETE c;")
    if not success:
        print(f"Warning: {output}", file=sys.stderr)

    # Get data from PostgreSQL
    concepts = get_concepts_from_postgres()
    edges = get_edges_from_postgres()

    print(f"Found {len(concepts)} concepts and {len(edges)} edges in PostgreSQL\n")

    if not concepts:
        print("No concepts to sync")
        return

    # Create concept nodes
    print("Creating concept nodes...")
    success_count = 0
    error_count = 0

    for i, concept in enumerate(concepts, 1):
        query = create_concept_node(concept)
        success, output = run_cypher(query)

        if success:
            success_count += 1
            if i % 10 == 0 or i == len(concepts):
                print(f"  Created {i}/{len(concepts)} nodes", end="\r")
        else:
            error_count += 1
            print(f"\n  Error creating {concept['id']}: {output}", file=sys.stderr)

    print(f"\nNodes: {success_count} created, {error_count} errors")

    # Create edge relationships
    print("\nCreating edge relationships...")
    edge_success = 0
    edge_error = 0

    for i, (src_id, dst_id, predicate) in enumerate(edges, 1):
        query = create_edge_relationship(src_id, dst_id, predicate)
        success, output = run_cypher(query)

        if success:
            edge_success += 1
            if i % 20 == 0 or i == len(edges):
                print(f"  Created {i}/{len(edges)} edges", end="\r")
        else:
            edge_error += 1
            # Don't print individual errors for edges (usually missing nodes)

    print(f"\nEdges: {edge_success} created, {edge_error} skipped (missing nodes)")

    # Verify
    print("\nVerifying...")
    success, output = run_cypher("MATCH (c:Concept) RETURN count(c) AS node_count;")
    print(f"  {output.strip()}")

    success, output = run_cypher("MATCH ()-[r]->() RETURN count(r) AS relationship_count;")
    print(f"  {output.strip()}")

    # Show some stats by provenance
    print("\nBy provenance:")
    success, output = run_cypher("""
MATCH (c:Concept)
RETURN c.provenance AS provenance, count(c) AS count
ORDER BY count DESC;
""")
    print(output)

    print("\n=== Sync complete ===")


if __name__ == "__main__":
    main()
