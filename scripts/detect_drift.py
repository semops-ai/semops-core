#!/usr/bin/env python3
"""
Detect semantic drift in documents by comparing embeddings.

Compares current document embeddings against stored versions to identify
when content has changed significantly enough to warrant re-indexing.

Usage:
 python scripts/detect_drift.py # Check all documents
 python scripts/detect_drift.py --threshold 0.15 # Custom threshold
 python scripts/detect_drift.py --file path/to.md # Check specific file
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMBEDDING_MODEL = "nomic-embed-text"

# Drift threshold: cosine distance above this indicates significant change
DEFAULT_DRIFT_THRESHOLD = 0.10 # ~90% similarity


def generate_embedding(text: str) -> list[float] | None:
 """Generate embedding using Ollama."""
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
 return None

 response = json.loads(result.stdout)
 return response.get("embedding")

 except (subprocess.TimeoutExpired, json.JSONDecodeError):
 return None


def compute_content_hash(content: str) -> str:
 """Compute SHA256 hash of content."""
 return hashlib.sha256(content.encode).hexdigest[:16]


def strip_yaml_frontmatter(content: str) -> str:
 """Remove YAML frontmatter from markdown."""
 if content.startswith("---"):
 end = content.find("---", 3)
 if end != -1:
 return content[end + 3:].lstrip
 return content


def get_stored_chunks(source_file: str) -> list[dict]:
 """Get stored chunks for a source file."""
 escaped = source_file.replace("'", "''")

 sql = f"""
 SELECT json_agg(row_to_json(t)) FROM (
 SELECT
 id,
 heading_hierarchy,
 LEFT(content, 500) as content,
 chunk_index
 FROM document_chunk
 WHERE source_file LIKE '%{escaped}'
 ORDER BY chunk_index
 ) t;
 """

 result = subprocess.run(
 ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres",
 "-t", "-A", "-c", sql],
 capture_output=True,
 text=True
 )

 if result.returncode != 0:
 return []

 try:
 data = json.loads(result.stdout.strip)
 return data if data else []
 except json.JSONDecodeError:
 return []


def compute_similarity(embedding1: list[float], embedding2: list[float]) -> float:
 """Compute cosine similarity between two embeddings."""
 # Format embeddings for pgvector comparison
 e1_str = "[" + ",".join(str(x) for x in embedding1) + "]"
 e2_str = "[" + ",".join(str(x) for x in embedding2) + "]"

 sql = f"""
 SELECT 1 - ('{e1_str}'::vector <=> '{e2_str}'::vector) as similarity;
 """

 result = subprocess.run(
 ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres",
 "-t", "-A", "-c", sql],
 capture_output=True,
 text=True
 )

 if result.returncode != 0 or not result.stdout.strip:
 return 0.0

 try:
 return float(result.stdout.strip)
 except ValueError:
 return 0.0


def check_chunk_drift(
 chunk_id: int,
 new_content: str,
 threshold: float
) -> dict:
 """
 Check if a chunk has drifted from its stored embedding.

 Returns dict with drift analysis.
 """
 # Get stored embedding
 sql = f"SELECT embedding FROM document_chunk WHERE id = {chunk_id};"

 result = subprocess.run(
 ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres",
 "-t", "-A", "-c", sql],
 capture_output=True,
 text=True
 )

 if result.returncode != 0 or not result.stdout.strip:
 return {"error": "Could not fetch stored embedding"}

 # Generate new embedding
 new_embedding = generate_embedding(new_content)
 if new_embedding is None:
 return {"error": "Could not generate new embedding"}

 # Parse stored embedding and compute similarity
 stored_str = result.stdout.strip
 # pgvector returns [x,y,z] format
 try:
 stored_vals = stored_str.strip("[]").split(",")
 stored_embedding = [float(x) for x in stored_vals]
 except (ValueError, AttributeError):
 return {"error": "Could not parse stored embedding"}

 similarity = compute_similarity(new_embedding, stored_embedding)
 drift = 1.0 - similarity

 return {
 "similarity": similarity,
 "drift": drift,
 "has_drifted": drift > threshold,
 "threshold": threshold
 }


def detect_document_drift(
 doc_path: Path,
 threshold: float
) -> dict:
 """
 Detect drift for all chunks of a document.

 Compares current file content against stored embeddings.
 """
 if not doc_path.exists:
 return {"error": f"File not found: {doc_path}"}

 # Get stored chunks
 stored_chunks = get_stored_chunks(str(doc_path))
 if not stored_chunks:
 return {"status": "no_stored_chunks", "needs_indexing": True}

 # Read current content
 current_content = doc_path.read_text
 current_content = strip_yaml_frontmatter(current_content)
 current_hash = compute_content_hash(current_content)

 # Get the stored content from first chunk to compare like-for-like
 first_chunk = stored_chunks[0]
 stored_content = first_chunk.get("content", "")

 # Use same length as stored chunk for fair comparison
 sample_length = len(stored_content)
 sample_content = current_content[:sample_length]
 new_embedding = generate_embedding(sample_content)

 if new_embedding is None:
 return {"error": "Could not generate embedding for current content"}

 # Get stored embedding for first chunk
 chunk_id = first_chunk["id"]
 drift_result = check_chunk_drift(chunk_id, sample_content, threshold)

 return {
 "file": str(doc_path),
 "stored_chunks": len(stored_chunks),
 "content_hash": current_hash,
 **drift_result
 }


def main:
 parser = argparse.ArgumentParser(description="Detect semantic drift in documents")
 parser.add_argument(
 "--threshold",
 type=float,
 default=DEFAULT_DRIFT_THRESHOLD,
 help=f"Drift threshold (default: {DEFAULT_DRIFT_THRESHOLD})"
 )
 parser.add_argument(
 "--file",
 type=str,
 help="Check specific file"
 )
 parser.add_argument(
 "--docs-path",
 type=str,
 help="Path to docs folder to check"
 )
 args = parser.parse_args

 print("Semantic Drift Detection")
 print(f"Threshold: {args.threshold} ({(1-args.threshold)*100:.0f}% similarity required)")
 print("=" * 60)

 if args.file:
 # Check single file
 doc_path = Path(args.file)
 result = detect_document_drift(doc_path, args.threshold)
 print(f"\n{doc_path.name}:")
 if "error" in result:
 print(f" Error: {result['error']}")
 elif result.get("needs_indexing"):
 print(" Status: Not indexed (needs initial indexing)")
 else:
 sim_pct = result.get("similarity", 0) * 100
 drift_pct = result.get("drift", 0) * 100
 status = "DRIFTED" if result.get("has_drifted") else "OK"
 print(f" Similarity: {sim_pct:.1f}%")
 print(f" Drift: {drift_pct:.1f}%")
 print(f" Status: {status}")
 return

 if args.docs_path:
 docs_path = Path(args.docs_path)
 if not docs_path.exists:
 print(f"Error: {docs_path} does not exist", file=sys.stderr)
 sys.exit(1)

 md_files = list(docs_path.glob("*.md"))
 md_files = [f for f in md_files if f.name.lower != "readme.md"]
 else:
 # Default: check all indexed documents
 sql = """
 SELECT DISTINCT source_file FROM document_chunk ORDER BY source_file;
 """
 result = subprocess.run(
 ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres",
 "-t", "-A", "-c", sql],
 capture_output=True,
 text=True
 )

 if result.returncode != 0:
 print("Error querying indexed documents", file=sys.stderr)
 sys.exit(1)

 md_files = [Path(f.strip) for f in result.stdout.strip.split("\n") if f.strip]

 print(f"\nChecking {len(md_files)} documents...\n")

 drifted = []
 ok = []
 errors = []

 for doc_path in md_files:
 result = detect_document_drift(doc_path, args.threshold)
 name = doc_path.name if hasattr(doc_path, 'name') else str(doc_path).split('/')[-1]

 if "error" in result:
 errors.append((name, result["error"]))
 print(f" {name}: ERROR - {result['error']}")
 elif result.get("needs_indexing"):
 errors.append((name, "Not indexed"))
 print(f" {name}: NOT INDEXED")
 else:
 sim_pct = result.get("similarity", 0) * 100
 if result.get("has_drifted"):
 drifted.append((name, sim_pct))
 print(f" {name}: DRIFTED ({sim_pct:.1f}% similar)")
 else:
 ok.append((name, sim_pct))
 print(f" {name}: OK ({sim_pct:.1f}% similar)")

 print
 print("=" * 60)
 print(f"OK: {len(ok)}")
 print(f"Drifted: {len(drifted)}")
 print(f"Errors: {len(errors)}")

 if drifted:
 print("\nDocuments needing re-indexing:")
 for name, sim in drifted:
 print(f" - {name} ({sim:.1f}% similar)")

 return 0 if not drifted else 1


if __name__ == "__main__":
 sys.exit(main)
