#!/usr/bin/env python3
"""
RAG query with confidence-based response routing.

Routes queries through semantic search with tiered confidence handling:
- High confidence (>0.8): Direct answer from retrieved context
- Medium confidence (0.6-0.8): Answer with caveats
- Low confidence (<0.6): Suggest related topics or escalate

Usage:
 python scripts/rag_query.py "what is semantic coherence"
 python scripts/rag_query.py "DDD patterns" --verbose
 python scripts/rag_query.py "explain the regression paradox" --use-llm
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "mistral"

# Confidence thresholds
HIGH_CONFIDENCE = 0.80
MEDIUM_CONFIDENCE = 0.60


class ConfidenceLevel(Enum):
 HIGH = "high"
 MEDIUM = "medium"
 LOW = "low"


@dataclass
class SearchResult:
 source: str
 content: str
 similarity: float
 hierarchy: list[str]
 result_type: str # "concept" or "chunk"


@dataclass
class QueryResponse:
 confidence_level: ConfidenceLevel
 confidence_score: float
 results: list[SearchResult]
 answer: str | None = None
 caveats: list[str] | None = None
 suggestions: list[str] | None = None


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


def search_concepts(embedding: list[float], limit: int = 3) -> list[SearchResult]:
 """Search concepts by embedding similarity."""
 embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

 sql = f"""
 SELECT json_agg(row_to_json(t)) FROM (
 SELECT
 id,
 preferred_label,
 definition,
 1 - (embedding_local <=> '{embedding_str}'::vector) as similarity
 FROM concept
 WHERE embedding_local IS NOT NULL
 ORDER BY embedding_local <=> '{embedding_str}'::vector
 LIMIT {limit}
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

 results = []
 try:
 data = json.loads(result.stdout.strip)
 if data:
 for row in data:
 results.append(SearchResult(
 source=row["id"],
 content=f"{row['preferred_label']}: {row['definition']}",
 similarity=row["similarity"],
 hierarchy=[row["preferred_label"]],
 result_type="concept"
 ))
 except json.JSONDecodeError:
 pass

 return results


def search_chunks(embedding: list[float], limit: int = 3) -> list[SearchResult]:
 """Search document chunks by embedding similarity."""
 embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

 sql = f"""
 SELECT json_agg(row_to_json(t)) FROM (
 SELECT
 source_file,
 heading_hierarchy,
 LEFT(content, 500) as content,
 1 - (embedding <=> '{embedding_str}'::vector) as similarity
 FROM document_chunk
 WHERE embedding IS NOT NULL
 ORDER BY embedding <=> '{embedding_str}'::vector
 LIMIT {limit}
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

 results = []
 try:
 data = json.loads(result.stdout.strip)
 if data:
 for row in data:
 source_name = row["source_file"].split("/")[-1] if row["source_file"] else "unknown"
 results.append(SearchResult(
 source=source_name,
 content=row["content"],
 similarity=row["similarity"],
 hierarchy=row["heading_hierarchy"] or [],
 result_type="chunk"
 ))
 except json.JSONDecodeError:
 pass

 return results


def compute_confidence(results: list[SearchResult]) -> tuple[ConfidenceLevel, float]:
 """
 Compute confidence level from search results.

 Uses the top result's similarity, with adjustments:
 - Bonus for multiple high-similarity results
 - Penalty if results are very inconsistent
 """
 if not results:
 return ConfidenceLevel.LOW, 0.0

 top_similarity = results[0].similarity

 # Compute consistency bonus/penalty
 if len(results) > 1:
 similarities = [r.similarity for r in results]
 variance = sum((s - top_similarity) ** 2 for s in similarities) / len(similarities)
 consistency_factor = 1.0 - min(variance * 10, 0.2) # Max 20% adjustment
 else:
 consistency_factor = 0.9 # Small penalty for single result

 adjusted_confidence = top_similarity * consistency_factor

 if adjusted_confidence >= HIGH_CONFIDENCE:
 return ConfidenceLevel.HIGH, adjusted_confidence
 elif adjusted_confidence >= MEDIUM_CONFIDENCE:
 return ConfidenceLevel.MEDIUM, adjusted_confidence
 else:
 return ConfidenceLevel.LOW, adjusted_confidence


def generate_llm_answer(query: str, context: str) -> str:
 """Generate answer using local LLM."""
 prompt = f"""Based on the following context, answer the question concisely.

Context:
{context}

Question: {query}

Answer:"""

 try:
 result = subprocess.run(
 [
 "curl", "-s", f"{OLLAMA_HOST}/api/generate",
 "-H", "Content-Type: application/json",
 "-d", json.dumps({
 "model": LLM_MODEL,
 "prompt": prompt,
 "stream": False
 })
 ],
 capture_output=True,
 text=True,
 timeout=60
 )

 if result.returncode != 0:
 return "Error generating response"

 response = json.loads(result.stdout)
 return response.get("response", "No response generated")

 except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
 return f"Error: {e}"


def route_query(
 query: str,
 use_llm: bool = False,
 verbose: bool = False
) -> QueryResponse:
 """
 Route a query through the RAG pipeline with confidence-based handling.
 """
 # Generate embedding
 embedding = generate_embedding(query)
 if embedding is None:
 return QueryResponse(
 confidence_level=ConfidenceLevel.LOW,
 confidence_score=0.0,
 results=[],
 answer="Error: Could not generate query embedding"
 )

 # Search both concepts and chunks
 concept_results = search_concepts(embedding, limit=3)
 chunk_results = search_chunks(embedding, limit=3)

 # Merge and sort by similarity
 all_results = concept_results + chunk_results
 all_results.sort(key=lambda r: r.similarity, reverse=True)
 top_results = all_results[:5]

 # Compute confidence
 confidence_level, confidence_score = compute_confidence(top_results)

 # Route based on confidence
 if confidence_level == ConfidenceLevel.HIGH:
 # High confidence: provide direct answer
 context = "\n\n".join([r.content for r in top_results[:3]])

 if use_llm:
 answer = generate_llm_answer(query, context)
 else:
 # Return top result as answer
 answer = top_results[0].content

 return QueryResponse(
 confidence_level=confidence_level,
 confidence_score=confidence_score,
 results=top_results,
 answer=answer
 )

 elif confidence_level == ConfidenceLevel.MEDIUM:
 # Medium confidence: answer with caveats
 context = "\n\n".join([r.content for r in top_results[:3]])

 if use_llm:
 answer = generate_llm_answer(query, context)
 else:
 answer = top_results[0].content

 caveats = [
 f"Confidence: {confidence_score:.0%}",
 "Results may be tangentially related",
 "Consider refining your query for better results"
 ]

 return QueryResponse(
 confidence_level=confidence_level,
 confidence_score=confidence_score,
 results=top_results,
 answer=answer,
 caveats=caveats
 )

 else:
 # Low confidence: suggest related topics
 suggestions = []
 if top_results:
 for r in top_results[:3]:
 if r.result_type == "concept":
 suggestions.append(f"Concept: {r.source}")
 else:
 if r.hierarchy:
 suggestions.append(f"Topic: {' > '.join(r.hierarchy[:2])}")

 return QueryResponse(
 confidence_level=confidence_level,
 confidence_score=confidence_score,
 results=top_results,
 answer=None,
 suggestions=suggestions if suggestions else [
 "No closely related content found",
 "Try rephrasing your query",
 "Consider broader or more specific terms"
 ]
 )


def main:
 parser = argparse.ArgumentParser(description="RAG query with confidence routing")
 parser.add_argument("query", type=str, help="Search query")
 parser.add_argument("--use-llm", action="store_true", help="Use LLM for answer generation")
 parser.add_argument("--verbose", action="store_true", help="Show detailed results")
 args = parser.parse_args

 print(f"Query: {args.query}")
 print("=" * 70)

 response = route_query(args.query, use_llm=args.use_llm, verbose=args.verbose)

 # Display confidence
 conf_pct = response.confidence_score * 100
 print(f"\nConfidence: {response.confidence_level.value.upper} ({conf_pct:.1f}%)")
 print("-" * 70)

 # Display based on confidence level
 if response.confidence_level == ConfidenceLevel.HIGH:
 print("\nAnswer:")
 print(f" {response.answer}")

 elif response.confidence_level == ConfidenceLevel.MEDIUM:
 print("\nAnswer (with caveats):")
 print(f" {response.answer}")
 print("\nCaveats:")
 for caveat in response.caveats or []:
 print(f" - {caveat}")

 else: # LOW
 print("\nNo confident answer found.")
 if response.suggestions:
 print("\nRelated topics to explore:")
 for suggestion in response.suggestions:
 print(f" - {suggestion}")

 # Show sources if verbose
 if args.verbose and response.results:
 print("\n" + "-" * 70)
 print("Sources:")
 for i, r in enumerate(response.results[:5], 1):
 sim_pct = r.similarity * 100
 print(f"\n{i}. [{r.result_type}] {r.source} ({sim_pct:.1f}%)")
 hierarchy = " > ".join(r.hierarchy) if r.hierarchy else "(root)"
 print(f" Path: {hierarchy}")
 content_preview = r.content[:150] + "..." if len(r.content) > 150 else r.content
 print(f" {content_preview}")


if __name__ == "__main__":
 main
