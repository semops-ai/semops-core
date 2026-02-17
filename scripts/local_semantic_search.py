#!/usr/bin/env python3
"""
Semantic search using local Ollama embeddings.

Queries the embedding_local column in concepts table.

Usage:
    python scripts/local_semantic_search.py "what is semantic coherence"
    python scripts/local_semantic_search.py "DDD patterns" --limit 10
"""

import argparse
import json
import os
import subprocess
import sys

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMBEDDING_MODEL = "nomic-embed-text"


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


def search_concepts(embedding: list[float], limit: int = 5) -> list[dict]:
    """Search concepts by embedding similarity."""
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    sql = f"""
    SELECT
        id,
        preferred_label,
        definition,
        provenance,
        1 - (embedding_local <=> '{embedding_str}'::vector) as similarity
    FROM concept
    WHERE embedding_local IS NOT NULL
    ORDER BY embedding_local <=> '{embedding_str}'::vector
    LIMIT {limit};
    """

    result = subprocess.run(
        ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Search error: {result.stderr}", file=sys.stderr)
        return []

    results = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split("|")
            if len(parts) >= 5:
                results.append({
                    "id": parts[0],
                    "label": parts[1],
                    "definition": parts[2][:100] + "..." if len(parts[2]) > 100 else parts[2],
                    "provenance": parts[3],
                    "similarity": float(parts[4])
                })

    return results


def main():
    parser = argparse.ArgumentParser(description="Semantic search over concepts")
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument("--limit", type=int, default=5, help="Number of results")
    args = parser.parse_args()

    print(f"Query: {args.query}")
    print("=" * 60)

    # Generate query embedding
    embedding = generate_embedding(args.query)
    if embedding is None:
        print("Error: Could not generate embedding", file=sys.stderr)
        sys.exit(1)

    # Search
    results = search_concepts(embedding, args.limit)

    if not results:
        print("No results found")
        return

    # Display results
    for i, r in enumerate(results, 1):
        sim_pct = r["similarity"] * 100
        prov = "1p" if r["provenance"] == "1p" else "3p"
        print(f"\n{i}. [{prov}] {r['label']} ({sim_pct:.1f}%)")
        print(f"   ID: {r['id']}")
        print(f"   {r['definition']}")


if __name__ == "__main__":
    main()
