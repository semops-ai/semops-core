#!/usr/bin/env python3
"""
Sync PostgreSQL concept and pattern graphs to Neo4j.

This script synchronizes concepts and patterns from PostgreSQL (source of truth)
to Neo4j for graph-based classification and analysis.

Usage:
 python scripts/sync_neo4j.py # Full sync
 python scripts/sync_neo4j.py --diff # Only sync changes since last sync
 python scripts/sync_neo4j.py --clear # Clear Neo4j and do full sync

Neo4j enables:
 - graph-orphan-v1: Find concepts with no path to approved core
 - graph-cluster-v1: Community detection for topic grouping
 - graph-hierarchy-v1: SKOS consistency validation
 - graph-centrality-v1: PageRank-style importance scoring
"""

import os
import sys
from datetime import datetime
from typing import Any

import psycopg
from neo4j import GraphDatabase
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
 """Configuration from environment variables."""

 # PostgreSQL (ADR-0010)
 semops_db_host: str = "localhost"
 semops_db_port: int = 5434
 semops_db_name: str = "postgres"
 semops_db_user: str = "postgres"
 semops_db_password: str = "postgres"

 # Neo4j
 neo4j_uri: str = "bolt://localhost:7687"
 neo4j_user: str = "" # Empty for no auth
 neo4j_password: str = ""

 class Config:
 env_file = ".env"
 extra = "ignore"


def get_pg_connection(settings: Settings) -> psycopg.Connection:
 """Create PostgreSQL connection."""
 return psycopg.connect(
 host=settings.semops_db_host,
 port=settings.semops_db_port,
 dbname=settings.semops_db_name,
 user=settings.semops_db_user,
 password=settings.semops_db_password,
 )


def get_neo4j_driver(settings: Settings) -> Any:
 """Create Neo4j driver."""
 auth = None
 if settings.neo4j_user and settings.neo4j_password:
 auth = (settings.neo4j_user, settings.neo4j_password)
 return GraphDatabase.driver(settings.neo4j_uri, auth=auth)


def clear_neo4j(driver: Any) -> None:
 """Clear all nodes and relationships from Neo4j."""
 with driver.session as session:
 session.run("MATCH (n) DETACH DELETE n")
 print("Cleared Neo4j database")


def create_constraints(driver: Any) -> None:
 """Create Neo4j constraints and indexes."""
 constraints = [
 "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
 "CREATE CONSTRAINT pattern_id IF NOT EXISTS FOR (p:Pattern) REQUIRE p.id IS UNIQUE",
 ]
 indexes = [
 "CREATE INDEX concept_provenance IF NOT EXISTS FOR (c:Concept) ON (c.provenance)",
 "CREATE INDEX concept_approval IF NOT EXISTS FOR (c:Concept) ON (c.approval_status)",
 "CREATE INDEX pattern_provenance IF NOT EXISTS FOR (p:Pattern) ON (p.provenance)",
 ]

 with driver.session as session:
 for constraint in constraints:
 try:
 session.run(constraint)
 except Exception as e:
 if "already exists" not in str(e).lower:
 print(f"Warning: {e}")

 for index in indexes:
 try:
 session.run(index)
 except Exception as e:
 if "already exists" not in str(e).lower:
 print(f"Warning: {e}")

 print("Created Neo4j constraints and indexes")


def sync_concepts(pg_conn: psycopg.Connection, driver: Any) -> int:
 """Sync concepts from PostgreSQL to Neo4j."""
 with pg_conn.cursor as cur:
 cur.execute("""
 SELECT id, preferred_label, definition, provenance, approval_status,
 alt_labels, created_at, updated_at
 FROM concept
 """)
 concepts = cur.fetchall

 count = 0
 with driver.session as session:
 for row in concepts:
 concept_id, label, definition, provenance, status, alt_labels, created, updated = row
 session.run(
 """
 MERGE (c:Concept {id: $id})
 SET c.preferred_label = $label,
 c.definition = $definition,
 c.provenance = $provenance,
 c.approval_status = $status,
 c.alt_labels = $alt_labels,
 c.created_at = $created,
 c.updated_at = $updated,
 c.synced_at = datetime
 """,
 id=concept_id,
 label=label,
 definition=definition,
 provenance=provenance,
 status=status,
 alt_labels=alt_labels or [],
 created=created.isoformat if created else None,
 updated=updated.isoformat if updated else None,
 )
 count += 1

 print(f"Synced {count} concepts")
 return count


def sync_concept_edges(pg_conn: psycopg.Connection, driver: Any) -> int:
 """Sync concept edges (SKOS relationships) from PostgreSQL to Neo4j."""
 with pg_conn.cursor as cur:
 cur.execute("""
 SELECT src_id, dst_id, predicate
 FROM concept_edge
 """)
 edges = cur.fetchall

 count = 0
 with driver.session as session:
 # Clear existing edges first (simpler than diffing)
 session.run("MATCH (:Concept)-[r:BROADER|NARROWER|RELATED]->(:Concept) DELETE r")

 for src_id, dst_id, predicate in edges:
 # Map SKOS predicates to Neo4j relationship types
 rel_type = predicate.upper # BROADER, NARROWER, RELATED

 session.run(
 f"""
 MATCH (src:Concept {{id: $src_id}})
 MATCH (dst:Concept {{id: $dst_id}})
 MERGE (src)-[:{rel_type}]->(dst)
 """,
 src_id=src_id,
 dst_id=dst_id,
 )
 count += 1

 print(f"Synced {count} concept edges")
 return count


def sync_patterns(pg_conn: psycopg.Connection, driver: Any) -> int:
 """Sync patterns from PostgreSQL to Neo4j."""
 with pg_conn.cursor as cur:
 cur.execute("""
 SELECT id, preferred_label, definition, provenance,
 alt_labels, metadata, created_at, updated_at
 FROM pattern
 """)
 patterns = cur.fetchall

 count = 0
 with driver.session as session:
 for row in patterns:
 pattern_id, label, definition, provenance, alt_labels, metadata, created, updated = row
 session.run(
 """
 MERGE (p:Pattern {id: $id})
 SET p.preferred_label = $label,
 p.definition = $definition,
 p.provenance = $provenance,
 p.alt_labels = $alt_labels,
 p.created_at = $created,
 p.updated_at = $updated,
 p.synced_at = datetime
 """,
 id=pattern_id,
 label=label,
 definition=definition,
 provenance=provenance,
 alt_labels=alt_labels or [],
 created=created.isoformat if created else None,
 updated=updated.isoformat if updated else None,
 )
 count += 1

 print(f"Synced {count} patterns")
 return count


def sync_pattern_edges(pg_conn: psycopg.Connection, driver: Any) -> int:
 """Sync pattern edges from PostgreSQL to Neo4j."""
 with pg_conn.cursor as cur:
 cur.execute("""
 SELECT src_id, dst_id, predicate, strength
 FROM pattern_edge
 """)
 edges = cur.fetchall

 count = 0
 with driver.session as session:
 # Clear existing pattern edges
 session.run(
 "MATCH (:Pattern)-[r:BROADER|NARROWER|RELATED|ADOPTS|EXTENDS|MODIFIES]->(:Pattern) DELETE r"
 )

 for src_id, dst_id, predicate, strength in edges:
 rel_type = predicate.upper
 session.run(
 f"""
 MATCH (src:Pattern {{id: $src_id}})
 MATCH (dst:Pattern {{id: $dst_id}})
 MERGE (src)-[r:{rel_type}]->(dst)
 SET r.strength = $strength
 """,
 src_id=src_id,
 dst_id=dst_id,
 strength=float(strength) if strength else 1.0,
 )
 count += 1

 print(f"Synced {count} pattern edges")
 return count


def create_graph_projection(driver: Any) -> None:
 """Create GDS graph projection for algorithms."""
 with driver.session as session:
 # Drop existing projection if exists
 try:
 session.run("CALL gds.graph.drop('concept-graph', false)")
 except Exception:
 pass

 # Create new projection for concepts
 try:
 session.run("""
 CALL gds.graph.project(
 'concept-graph',
 'Concept',
 {
 BROADER: {orientation: 'UNDIRECTED'},
 NARROWER: {orientation: 'UNDIRECTED'},
 RELATED: {orientation: 'UNDIRECTED'}
 }
 )
 """)
 print("Created GDS graph projection 'concept-graph'")
 except Exception as e:
 print(f"Warning: Could not create concept graph projection: {e}")

 # Create projection for patterns
 try:
 session.run("CALL gds.graph.drop('pattern-graph', false)")
 except Exception:
 pass

 try:
 session.run("""
 CALL gds.graph.project(
 'pattern-graph',
 'Pattern',
 {
 BROADER: {orientation: 'UNDIRECTED'},
 NARROWER: {orientation: 'UNDIRECTED'},
 RELATED: {orientation: 'UNDIRECTED'},
 ADOPTS: {orientation: 'UNDIRECTED'},
 EXTENDS: {orientation: 'UNDIRECTED'},
 MODIFIES: {orientation: 'UNDIRECTED'}
 }
 )
 """)
 print("Created GDS graph projection 'pattern-graph'")
 except Exception as e:
 print(f"Warning: Could not create pattern graph projection: {e}")


def print_stats(driver: Any) -> None:
 """Print graph statistics."""
 with driver.session as session:
 # Pattern counts
 result = session.run("MATCH (p:Pattern) RETURN count(p) as count")
 pattern_count = result.single["count"]

 result = session.run(
 "MATCH (:Pattern)-[r]->(:Pattern) RETURN count(r) as count"
 )
 pattern_edge_count = result.single["count"]

 result = session.run("""
 MATCH (p:Pattern)
 WHERE NOT (p)-[]-(:Pattern)
 RETURN count(p) as count
 """)
 orphan_pattern_count = result.single["count"]

 print("\n--- Graph Statistics ---")
 print(f"Patterns: {pattern_count} ({orphan_pattern_count} orphans)")
 print(f"Pattern edges: {pattern_edge_count}")


def main -> None:
 """Main sync function."""
 import argparse

 parser = argparse.ArgumentParser(description="Sync concept graph to Neo4j")
 parser.add_argument("--clear", action="store_true", help="Clear Neo4j before sync")
 parser.add_argument("--diff", action="store_true", help="Only sync changes (not implemented)")
 args = parser.parse_args

 if args.diff:
 print("Diff sync not yet implemented, doing full sync")

 settings = Settings

 print(f"Connecting to PostgreSQL at {settings.semops_db_host}:{settings.semops_db_port}")
 print(f"Connecting to Neo4j at {settings.neo4j_uri}")

 pg_conn = get_pg_connection(settings)
 driver = get_neo4j_driver(settings)

 try:
 if args.clear:
 clear_neo4j(driver)

 create_constraints(driver)

 # Phase 2: concept table removed — only sync patterns
 # sync_concepts(pg_conn, driver)
 # sync_concept_edges(pg_conn, driver)
 sync_patterns(pg_conn, driver)
 sync_pattern_edges(pg_conn, driver)
 create_graph_projection(driver)
 print_stats(driver)

 print(f"\nSync completed at {datetime.now.isoformat}")

 finally:
 pg_conn.close
 driver.close


if __name__ == "__main__":
 main
