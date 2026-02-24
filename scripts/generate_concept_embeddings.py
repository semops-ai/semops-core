#!/usr/bin/env python3
"""
Generate embeddings for concepts in PostgreSQL using OpenAI API.

Reads concepts from the database, generates embeddings via OpenAI's
text-embedding-3-small model, and updates the embedding column.

Usage:
 python scripts/generate_concept_embeddings.py

Requires:
 - OPENAI_API_KEY in .env
 - PostgreSQL with concepts loaded
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists:
 with open(env_path) as f:
 for line in f:
 line = line.strip
 if line and not line.startswith("#") and "=" in line:
 key, value = line.split("=", 1)
 os.environ.setdefault(key.strip, value.strip)

import subprocess
import json

# OpenAI API configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def get_concepts_without_embeddings -> list[dict]:
 """Fetch concepts that don't have embeddings yet."""
 sql = """
 SELECT id, preferred_label, definition
 FROM concept
 WHERE embedding IS NULL
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


def generate_embedding(text: str) -> list[float] | None:
 """Generate embedding using OpenAI API via curl."""
 import subprocess
 import json

 payload = {
 "model": EMBEDDING_MODEL,
 "input": text,
 "encoding_format": "float"
 }

 result = subprocess.run(
 [
 "curl", "-s", "https://api.openai.com/v1/embeddings",
 "-H", "Content-Type: application/json",
 "-H", f"Authorization: Bearer {OPENAI_API_KEY}",
 "-d", json.dumps(payload)
 ],
 capture_output=True,
 text=True
 )

 if result.returncode != 0:
 print(f"Curl error: {result.stderr}", file=sys.stderr)
 return None

 try:
 response = json.loads(result.stdout)
 if "error" in response:
 print(f"OpenAI API error: {response['error']}", file=sys.stderr)
 return None
 return response["data"][0]["embedding"]
 except (json.JSONDecodeError, KeyError, IndexError) as e:
 print(f"Error parsing response: {e}", file=sys.stderr)
 print(f"Response: {result.stdout[:500]}", file=sys.stderr)
 return None


def update_concept_embedding(concept_id: str, embedding: list[float]) -> bool:
 """Update the embedding column for a concept."""
 # Format embedding as PostgreSQL vector literal
 embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

 # Escape the concept_id for SQL
 escaped_id = concept_id.replace("'", "''")

 sql = f"UPDATE concept SET embedding = '{embedding_str}'::vector WHERE id = '{escaped_id}';"

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
 if not OPENAI_API_KEY:
 print("Error: OPENAI_API_KEY not found in environment", file=sys.stderr)
 sys.exit(1)

 print(f"Using model: {EMBEDDING_MODEL}")

 # Get concepts without embeddings
 concepts = get_concepts_without_embeddings
 print(f"Found {len(concepts)} concepts without embeddings")

 if not concepts:
 print("No concepts to process")
 return

 # Process each concept
 success_count = 0
 error_count = 0

 for i, concept in enumerate(concepts, 1):
 concept_id = concept["id"]
 label = concept["preferred_label"]
 definition = concept["definition"]

 # Create text for embedding: "Label: Definition"
 text = f"{label}: {definition}"

 print(f"[{i}/{len(concepts)}] Processing: {concept_id}...", end=" ", flush=True)

 # Generate embedding
 embedding = generate_embedding(text)

 if embedding is None:
 print("FAILED (API error)")
 error_count += 1
 continue

 # Update database
 if update_concept_embedding(concept_id, embedding):
 print("OK")
 success_count += 1
 else:
 print("FAILED (DB error)")
 error_count += 1

 print(f"\n=== Summary ===")
 print(f"Success: {success_count}")
 print(f"Errors: {error_count}")
 print(f"Total: {len(concepts)}")


if __name__ == "__main__":
 main
