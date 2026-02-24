#!/usr/bin/env python3
"""
Run the tiered classifier pipeline on pending concepts.

Pipeline order:
1. RuleBasedClassifier - Fast validation rules
2. EmbeddingClassifier - Semantic similarity
3. GraphClassifier - Structural analysis

Usage:
 python3 scripts/run_classifiers.py [--tier TIER] [--limit N]

Arguments:
 --tier: Run specific tier only (rules, embedding, graph, all)
 --limit: Limit number of concepts to classify
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists:
 import os
 with open(env_path) as f:
 for line in f:
 line = line.strip
 if line and not line.startswith("#") and "=" in line:
 key, value = line.split("=", 1)
 os.environ.setdefault(key.strip, value.strip)


def get_pending_concepts -> list[dict]:
 """Fetch pending concepts from PostgreSQL."""
 sql = """
 SELECT id, preferred_label, definition, provenance
 FROM concept
 WHERE approval_status = 'pending'
 ORDER BY id;
 """
 result = subprocess.run(
 ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres",
 "-t", "-A", "-F", "| ||", "-c", sql],
 capture_output=True,
 text=True
 )

 if result.returncode != 0:
 print(f"Error: {result.stderr}", file=sys.stderr)
 return []

 concepts = []
 for line in result.stdout.strip.split("\n"):
 if line:
 parts = line.split("| ||")
 if len(parts) >= 4:
 concepts.append({
 "id": parts[0],
 "preferred_label": parts[1],
 "definition": parts[2],
 "provenance": parts[3]
 })
 return concepts


def check_relationships(concept_id: str) -> bool:
 """Check if concept has SKOS relationships."""
 sql = f"""
 SELECT EXISTS (
 SELECT 1 FROM concept_edge
 WHERE src_id = '{concept_id}' OR dst_id = '{concept_id}'
 );
 """
 result = subprocess.run(
 ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres",
 "-t", "-A", "-c", sql],
 capture_output=True,
 text=True
 )
 return result.stdout.strip == "t"


def classify_concept_rules(concept: dict) -> dict:
 """Run rule-based classification on a concept."""
 issues = []
 scores = {}

 definition = concept.get("definition", "")
 preferred_label = concept.get("preferred_label", "")

 # Completeness score
 completeness = 0.0
 if preferred_label:
 completeness += 0.3
 else:
 issues.append("Missing preferred_label")

 if definition:
 completeness += 0.4
 else:
 issues.append("Missing definition")

 # Format validation
 format_valid = True
 if definition:
 if len(definition) < 20:
 issues.append("Definition too short (<20 chars)")
 format_valid = False
 if len(definition) > 2000:
 issues.append("Definition too long (>2000 chars)")
 format_valid = False

 # Relationship check
 has_relationships = check_relationships(concept["id"])
 if has_relationships:
 completeness += 0.3
 else:
 issues.append("No SKOS relationships")

 # Promotion ready
 promotion_ready = completeness >= 0.7 and format_valid and len(issues) <= 1

 return {
 "classifier_id": "rule-completeness-v1",
 "scores": {
 "completeness": round(completeness, 2),
 "format_valid": format_valid,
 "has_relationships": has_relationships,
 "promotion_ready": promotion_ready
 },
 "labels": {"issues": issues},
 "confidence": 1.0,
 "rationale": f"Issues: {'; '.join(issues)}" if issues else "All rules passed"
 }


def save_classification(concept_id: str, result: dict) -> bool:
 """Save classification result to database."""
 import uuid
 classification_id = str(uuid.uuid4)

 scores_json = json.dumps(result["scores"]).replace("'", "''")
 labels_json = json.dumps(result["labels"]).replace("'", "''")
 rationale = (result.get("rationale") or "").replace("'", "''")

 sql = f"""
 INSERT INTO classification (
 id, target_type, target_id, classifier_id, classifier_version,
 scores, labels, confidence, rationale
 ) VALUES (
 '{classification_id}', 'concept', '{concept_id}', '{result["classifier_id"]}', '1.0.0',
 '{scores_json}'::jsonb, '{labels_json}'::jsonb, {result.get("confidence", 1.0)}, '{rationale}'
 ) ON CONFLICT (target_type, target_id, classifier_id, classifier_version)
 DO UPDATE SET scores = EXCLUDED.scores, labels = EXCLUDED.labels,
 rationale = EXCLUDED.rationale;
 """

 result = subprocess.run(
 ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres", "-c", sql],
 capture_output=True,
 text=True
 )
 return result.returncode == 0


def run_rules_classifier(concepts: list[dict]) -> dict:
 """Run rule-based classifier on all concepts."""
 print(f"\n=== Rule-Based Classifier ===")
 print(f"Processing {len(concepts)} concepts...\n")

 results = {"passed": 0, "failed": 0, "issues": {}}

 for concept in concepts:
 result = classify_concept_rules(concept)

 if save_classification(concept["id"], result):
 if result["scores"]["promotion_ready"]:
 results["passed"] += 1
 status = "✓"
 else:
 results["failed"] += 1
 status = "✗"
 # Track issue types
 for issue in result["labels"]["issues"]:
 results["issues"][issue] = results["issues"].get(issue, 0) + 1

 print(f" {status} {concept['id']}: completeness={result['scores']['completeness']}")
 else:
 print(f" ! Error saving {concept['id']}")

 return results


def run_embedding_classifier(concepts: list[dict]) -> dict:
 """Run embedding-based classifier (similarity analysis)."""
 print(f"\n=== Embedding Classifier ===")
 print(f"Processing {len(concepts)} concepts...\n")

 # Get all embeddings for similarity comparison
 sql = """
 SELECT id, embedding
 FROM concept
 WHERE embedding IS NOT NULL;
 """
 result = subprocess.run(
 ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres",
 "-t", "-A", "-F", "| ||", "-c", sql],
 capture_output=True,
 text=True
 )

 if "embedding" not in result.stdout:
 print(" Embeddings available, running similarity analysis...")

 # For each concept, find most similar concepts
 results = {"analyzed": 0, "duplicates": 0, "orphans": 0}

 for concept in concepts:
 # Find top 5 similar concepts
 sql = f"""
 SELECT c2.id, c2.preferred_label,
 1 - (c1.embedding <=> c2.embedding) as similarity
 FROM concept c1, concept c2
 WHERE c1.id = '{concept["id"]}'
 AND c2.id != c1.id
 AND c2.embedding IS NOT NULL
 ORDER BY c1.embedding <=> c2.embedding
 LIMIT 5;
 """
 sim_result = subprocess.run(
 ["docker", "exec", "supabase-db", "psql", "-U", "postgres", "-d", "postgres",
 "-t", "-A", "-F", "| ||", "-c", sql],
 capture_output=True,
 text=True
 )

 similarities = []
 max_similarity = 0.0
 most_similar = None

 for line in sim_result.stdout.strip.split("\n"):
 if line:
 parts = line.split("| ||")
 if len(parts) >= 3:
 sim = float(parts[2])
 similarities.append(sim)
 if sim > max_similarity:
 max_similarity = sim
 most_similar = parts[0]

 avg_similarity = sum(similarities) / len(similarities) if similarities else 0

 # Classify based on similarity
 is_duplicate = max_similarity > 0.95
 is_orphan = max_similarity < 0.5
 coherent = avg_similarity >= 0.5

 if is_duplicate:
 results["duplicates"] += 1
 status = "⚠ DUPLICATE"
 elif is_orphan:
 results["orphans"] += 1
 status = "⚠ ORPHAN"
 else:
 status = "✓"

 results["analyzed"] += 1

 # Save result
 embed_result = {
 "classifier_id": "embedding-similarity-v1",
 "scores": {
 "max_similarity": round(max_similarity, 3),
 "avg_similarity": round(avg_similarity, 3),
 "is_duplicate": is_duplicate,
 "is_orphan": is_orphan,
 "coherent": coherent
 },
 "labels": {"most_similar": most_similar},
 "confidence": 0.9,
 "rationale": f"Most similar to {most_similar} ({max_similarity:.3f})"
 }
 save_classification(concept["id"], embed_result)

 print(f" {status} {concept['id']}: max_sim={max_similarity:.3f} avg={avg_similarity:.3f}")

 return results


def run_graph_classifier(concepts: list[dict]) -> dict:
 """Run graph-based classifier (Neo4j structural analysis)."""
 print(f"\n=== Graph Classifier ===")
 print(f"Processing {len(concepts)} concepts...\n")

 results = {"analyzed": 0, "hubs": 0, "isolated": 0}

 for concept in concepts:
 # Get degree (in + out edges) from Neo4j
 cypher = f"""
 MATCH (c:Concept {{id: '{concept["id"]}'}})
 OPTIONAL MATCH (c)-[r]-
 RETURN count(r) as degree
 """

 result = subprocess.run(
 ["docker", "exec", "ike-neo4j", "cypher-shell", "-u", "neo4j", "-p", "password", cypher],
 capture_output=True,
 text=True
 )

 degree = 0
 for line in result.stdout.strip.split("\n"):
 if line and line.isdigit:
 degree = int(line)
 break

 # Get broader/narrower counts
 cypher_broader = f"""
 MATCH (c:Concept {{id: '{concept["id"]}'}})-[:BROADER]->(b)
 RETURN count(b) as broader_count
 """
 broader_result = subprocess.run(
 ["docker", "exec", "ike-neo4j", "cypher-shell", "-u", "neo4j", "-p", "password", cypher_broader],
 capture_output=True,
 text=True
 )

 broader_count = 0
 for line in broader_result.stdout.strip.split("\n"):
 if line and line.isdigit:
 broader_count = int(line)
 break

 cypher_narrower = f"""
 MATCH (c:Concept {{id: '{concept["id"]}'}})<-[:BROADER]-(n)
 RETURN count(n) as narrower_count
 """
 narrower_result = subprocess.run(
 ["docker", "exec", "ike-neo4j", "cypher-shell", "-u", "neo4j", "-p", "password", cypher_narrower],
 capture_output=True,
 text=True
 )

 narrower_count = 0
 for line in narrower_result.stdout.strip.split("\n"):
 if line and line.isdigit:
 narrower_count = int(line)
 break

 # Classify
 is_hub = narrower_count >= 3
 is_isolated = degree == 0
 is_leaf = degree > 0 and narrower_count == 0

 if is_hub:
 results["hubs"] += 1
 status = "★ HUB"
 elif is_isolated:
 results["isolated"] += 1
 status = "⚠ ISOLATED"
 elif is_leaf:
 status = "○ leaf"
 else:
 status = "✓"

 results["analyzed"] += 1

 # Save result
 graph_result = {
 "classifier_id": "graph-structure-v1",
 "scores": {
 "degree": degree,
 "broader_count": broader_count,
 "narrower_count": narrower_count,
 "is_hub": is_hub,
 "is_leaf": is_leaf,
 "is_isolated": is_isolated
 },
 "labels": {"role": "hub" if is_hub else ("leaf" if is_leaf else "intermediate")},
 "confidence": 1.0,
 "rationale": f"Degree={degree}, {narrower_count} narrower concepts"
 }
 save_classification(concept["id"], graph_result)

 print(f" {status} {concept['id']}: degree={degree} broader={broader_count} narrower={narrower_count}")

 return results


def print_summary(rules_results: dict, embed_results: dict, graph_results: dict):
 """Print classification summary."""
 print("\n" + "="*60)
 print("CLASSIFICATION SUMMARY")
 print("="*60)

 print(f"\nRule-Based Classifier:")
 print(f" Passed: {rules_results['passed']}")
 print(f" Failed: {rules_results['failed']}")
 if rules_results.get('issues'):
 print(f" Common issues:")
 for issue, count in sorted(rules_results['issues'].items, key=lambda x: -x[1]):
 print(f" - {issue}: {count}")

 print(f"\nEmbedding Classifier:")
 print(f" Analyzed: {embed_results['analyzed']}")
 print(f" Potential duplicates: {embed_results['duplicates']}")
 print(f" Potential orphans: {embed_results['orphans']}")

 print(f"\nGraph Classifier:")
 print(f" Analyzed: {graph_results['analyzed']}")
 print(f" Hubs (≥3 narrower): {graph_results['hubs']}")
 print(f" Isolated (no edges): {graph_results['isolated']}")

 print("\n" + "="*60)


def main:
 parser = argparse.ArgumentParser(description="Run classifier pipeline")
 parser.add_argument("--tier", choices=["rules", "embedding", "graph", "all"],
 default="all", help="Which classifier tier to run")
 parser.add_argument("--limit", type=int, help="Limit number of concepts")
 args = parser.parse_args

 concepts = get_pending_concepts
 if args.limit:
 concepts = concepts[:args.limit]

 print(f"Found {len(concepts)} pending concepts")

 rules_results = {"passed": 0, "failed": 0, "issues": {}}
 embed_results = {"analyzed": 0, "duplicates": 0, "orphans": 0}
 graph_results = {"analyzed": 0, "hubs": 0, "isolated": 0}

 if args.tier in ("rules", "all"):
 rules_results = run_rules_classifier(concepts)

 if args.tier in ("embedding", "all"):
 embed_results = run_embedding_classifier(concepts)

 if args.tier in ("graph", "all"):
 graph_results = run_graph_classifier(concepts)

 print_summary(rules_results, embed_results, graph_results)


if __name__ == "__main__":
 main
