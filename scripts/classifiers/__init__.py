"""
Classifiers for semantic coherence evaluation.

This module provides classifiers that evaluate concepts and entities,
writing results to the classification table for the promotion workflow.

Classifier Types:
 - RuleBasedClassifier: Deterministic validation (completeness, format)
 - EmbeddingClassifier: Semantic similarity using pgvector
 - LLMClassifier: Quality scoring with rationale using Claude/GPT
 - GraphClassifier: Graph-based analysis using Neo4j

Usage:
 from scripts.classifiers import RuleBasedClassifier, EmbeddingClassifier

 # Run rule-based classification on all pending concepts
 classifier = RuleBasedClassifier
 classifier.classify_pending_concepts

 # Run embedding-based coherence check
 embedding_classifier = EmbeddingClassifier
 embedding_classifier.classify_pending_concepts

 # Run graph-based classification (requires Neo4j sync first)
 from scripts.classifiers import GraphClassifier
 graph_classifier = GraphClassifier
 graph_classifier.run_graph_algorithms # PageRank, community detection
 graph_classifier.classify_all_concepts
"""

from .base import BaseClassifier, ClassificationResult
from .embedding import EmbeddingClassifier
from .embedding_local import LocalEmbeddingClassifier
from .graph import GraphClassifier
from .llm import LLMClassifier
from .rules import RuleBasedClassifier

__all__ = [
 "BaseClassifier",
 "ClassificationResult",
 "RuleBasedClassifier",
 "EmbeddingClassifier",
 "LocalEmbeddingClassifier",
 "LLMClassifier",
 "GraphClassifier",
]
