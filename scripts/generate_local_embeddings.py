#!/usr/bin/env python3
"""
Generate embeddings using local Ollama models.

Uses nomic-embed-text (768 dimensions) via Ollama API.
Stores in embedding_local column (separate from OpenAI embeddings).

Usage:
 python scripts/generate_local_embeddings.py
 python scripts/generate_local_embeddings.py --regenerate
 python scripts/generate_local_embeddings.py --concept-id semantic-coherence
 python scripts/generate_local_embeddings.py --dry-run

Requirements:
 - Ollama running with nomic-embed-text model
 - PostgreSQL with pgvector and embedding_local column
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Configuration
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIMENSIONS = 768


def get_concepts(regenerate: bool = False, concept_id: str | None = None) -> list[dict]:
 """Fetch concepts from database."""
 if concept_id:
 where_clause = f"WHERE id = '{concept_id}'"
 elif regenerate:
 where_clause = ""
 else:
 where_clause = "WHERE embedding_local IS NULL"

 sql = f"""
 SELECT id, preferred_label, definition
 FROM concept
 {where_clause}
 ORDER BY id;
 """

 result = subprocess.run(
 ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres",
 "-t", "-A", "-F", "|", "-c", sql],
 capture_output=True,
 text=True
 )

 if result.returncode != 0:
 print(f"Error fetching concepts: {result.stderr}", file=sys.stderr)
 return []

 concepts = []
 for line in result.stdout.strip.split("\n"):
 if line:
 parts = line.split("|")
 if len(parts) >= 3:
 concepts.append({
 "id": parts[0],
 "preferred_label": parts[1],
 "definition": parts[2]
 })

 return concepts


def generate_embedding_ollama(text: str) -> list[float] | None:
 """Generate embedding using Ollama API."""
 try:
 result = subprocess.run(
 [
 "curl", "-s", f"{OLLAMA_HOST}/api/embeddings",
 "-H", "Content-Type: application/json",
 "-d", json.dumps({"model": EMBEDDING_MODEL, "prompt": text})
 ],
 capture_output=True,
 text=True,
 timeout=30
 )

 if result.returncode != 0:
 print(f"Curl error: {result.stderr}", file=sys.stderr)
 return None

 response = json.loads(result.stdout)
 if "embedding" not in response:
 print(f"No embedding in response: {result.stdout[:200]}", file=sys.stderr)
 return None

 return response["embedding"]

 except subprocess.TimeoutExpired:
 print("Timeout generating embedding", file=sys.stderr)
 return None
 except json.JSONDecodeError as e:
 print(f"JSON decode error: {e}", file=sys.stderr)
 return None


def update_embedding(concept_id: str, embedding: list[float]) -> bool:
 """Update the embedding_local column for a concept."""
 embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
 escaped_id = concept_id.replace("'", "''")

 sql = f"UPDATE concept SET embedding_local = '{embedding_str}'::vector WHERE id = '{escaped_id}';"

 result = subprocess.run(
 ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres", "-c", sql],
 capture_output=True,
 text=True
 )

 if result.returncode != 0:
 print(f"Error updating {concept_id}: {result.stderr}", file=sys.stderr)
 return False

 return True


def main:
 parser = argparse.ArgumentParser(description="Generate local embeddings for concepts")
 parser.add_argument(
 "--regenerate",
 action="store_true",
 help="Regenerate all embeddings (not just missing)",
 )
 parser.add_argument(
 "--concept-id",
 type=str,
 help="Process specific concept by ID",
 )
 parser.add_argument(
 "--dry-run",
 action="store_true",
 help="Show what would be done without making changes",
 )
 args = parser.parse_args

 print(f"Local Embedding Generator")
 print(f"Model: {EMBEDDING_MODEL} ({EMBEDDING_DIMENSIONS} dimensions)")
 print(f"Ollama: {OLLAMA_HOST}")
 print("=" * 50)

 # Verify Ollama is running
 try:
 result = subprocess.run(
 ["curl", "-s", f"{OLLAMA_HOST}/api/tags"],
 capture_output=True,
 text=True,
 timeout=5
 )
 if result.returncode != 0:
 print("Error: Ollama not responding", file=sys.stderr)
 sys.exit(1)
 except subprocess.TimeoutExpired:
 print("Error: Ollama connection timeout", file=sys.stderr)
 sys.exit(1)

 # Get concepts
 concepts = get_concepts(args.regenerate, args.concept_id)
 print(f"Found {len(concepts)} concepts to embed")

 if not concepts:
 print("No concepts to process")
 return 0

 if args.dry_run:
 print("\nDRY RUN - no changes will be made\n")
 for c in concepts[:10]:
 text = f"{c['preferred_label']}: {c['definition']}"
 print(f" {c['id']}: {len(text)} chars")
 if len(concepts) > 10:
 print(f" ... and {len(concepts) - 10} more")
 return 0

 # Process concepts
 success_count = 0
 error_count = 0

 for i, concept in enumerate(concepts, 1):
 concept_id = concept["id"]
 label = concept["preferred_label"]
 definition = concept["definition"]

 text = f"{label}: {definition}"

 print(f"[{i}/{len(concepts)}] {concept_id}...", end=" ", flush=True)

 embedding = generate_embedding_ollama(text)

 if embedding is None:
 print("FAILED (embedding)")
 error_count += 1
 continue

 if len(embedding) != EMBEDDING_DIMENSIONS:
 print(f"FAILED (wrong dims: {len(embedding)})")
 error_count += 1
 continue

 if update_embedding(concept_id, embedding):
 print("OK")
 success_count += 1
 else:
 print("FAILED (db)")
 error_count += 1

 print
 print("=" * 50)
 print(f"Success: {success_count}")
 print(f"Errors: {error_count}")
 print(f"Total: {len(concepts)}")

 return 0 if error_count == 0 else 1


if __name__ == "__main__":
 sys.exit(main)
