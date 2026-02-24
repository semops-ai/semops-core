#!/usr/bin/env python3
"""
LLM classifier for Project Ike ingestion pipeline.

Uses Anthropic's Claude API to classify markdown documents into
schema-compliant semantic metadata.

Based on validated experiment results showing 100% consistency
across runs (experiments/llm-classification-test).

Usage:
 from llm_classifier import LLMClassifier
 from entity_builder import LLMClassification

 classifier = LLMClassifier(api_key="sk-ant-...")
 result = classifier.classify(markdown_content)
"""

from __future__ import annotations

import json
import os
from typing import Optional

from entity_builder import LLMClassification


CLASSIFICATION_SYSTEM_PROMPT = """You are a content classifier for the Project Ike knowledge management system.

Classify the given markdown document and return a JSON object with these fields:

1. content_type: One of: article, guide, framework, principle, pattern, definition, methodology, tutorial
2. primary_concept: The main concept this document establishes or documents, as a kebab-case ID (e.g., "semantic-operations", "domain-driven-design")
3. broader_concepts: Array of parent/broader concept IDs that this concept falls under (kebab-case)
4. narrower_concepts: Array of child/narrower concept IDs that are subtopics of this concept (kebab-case)
5. subject_area: Array from: "AI/ML", "Knowledge Management", "Domain-Driven Design", "Data Architecture", "Software Engineering", "First Principles"
6. summary: A 1-2 sentence abstract of the document's content
7. concept_ownership: One of:
 - "1p" if this concept was coined/invented by the document author (Tim Mitchell / Project Ike)
 - "2p" if this is an adapted/customized version of an existing concept
 - "3p" if this is an industry-standard concept created by others (e.g., DDD, SKOS, PROV-O)
8. detected_edges: Array of objects representing relationships this document has to other concepts. Each object has:
 - "predicate": One of "derived_from", "cites", "related_to", "extends", "contradicts"
 - "target_concept": The kebab-case concept ID of the related concept
 - "strength": Float 0.0-1.0 indicating relationship strength
 - "rationale": Brief explanation of why this relationship exists

IMPORTANT: Return ONLY valid JSON, no explanation or markdown code blocks."""


class LLMClassifier:
 """
 Classifies markdown content using Claude API.

 Attributes:
 model: Claude model to use (default: claude-sonnet-4-20250514)
 max_content_length: Max content length to send (truncated if longer)
 """

 def __init__(
 self,
 api_key: Optional[str] = None,
 model: str = "claude-sonnet-4-20250514",
 max_content_length: int = 8000,
 ):
 """
 Initialize classifier.

 Args:
 api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
 model: Model to use for classification
 max_content_length: Max content length to send
 """
 self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
 if not self.api_key:
 raise ValueError("ANTHROPIC_API_KEY not provided or set in environment")

 self.model = model
 self.max_content_length = max_content_length
 self._client = None

 @property
 def client(self):
 """Lazy-load Anthropic client."""
 if self._client is None:
 import anthropic

 self._client = anthropic.Anthropic(api_key=self.api_key)
 return self._client

 def classify(self, content: str) -> LLMClassification:
 """
 Classify markdown content.

 Args:
 content: Markdown document content

 Returns:
 LLMClassification with extracted semantic metadata

 Raises:
 RuntimeError: If API call fails or response is invalid
 """
 # Truncate if needed
 truncated = content[: self.max_content_length]

 try:
 response = self.client.messages.create(
 model=self.model,
 max_tokens=1024,
 system=CLASSIFICATION_SYSTEM_PROMPT,
 messages=[{"role": "user", "content": f"Classify this document:\n\n{truncated}"}],
 )

 response_text = response.content[0].text.strip

 # Handle potential markdown code blocks
 if response_text.startswith("```"):
 lines = response_text.split("\n")
 response_text = "\n".join(lines[1:-1])

 data = json.loads(response_text)

 return LLMClassification(
 content_type=data.get("content_type", ""),
 primary_concept=data.get("primary_concept", ""),
 broader_concepts=data.get("broader_concepts"),
 narrower_concepts=data.get("narrower_concepts"),
 subject_area=data.get("subject_area"),
 summary=data.get("summary", ""),
 concept_ownership=data.get("concept_ownership", ""),
 detected_edges=data.get("detected_edges"),
 )

 except json.JSONDecodeError as e:
 raise RuntimeError(f"Failed to parse LLM response as JSON: {e}")
 except Exception as e:
 raise RuntimeError(f"LLM classification failed: {e}")


if __name__ == "__main__":
 import sys

 if len(sys.argv) < 2:
 print("Usage: python llm_classifier.py <markdown_file>")
 sys.exit(1)

 file_path = sys.argv[1]
 with open(file_path) as f:
 content = f.read

 classifier = LLMClassifier
 result = classifier.classify(content)

 print(f"Content Type: {result.content_type}")
 print(f"Primary Concept: {result.primary_concept}")
 print(f"Broader Concepts: {result.broader_concepts}")
 print(f"Narrower Concepts: {result.narrower_concepts}")
 print(f"Subject Area: {result.subject_area}")
 print(f"Summary: {result.summary}")
 print(f"Concept Ownership: {result.concept_ownership}")
 print(f"Detected Edges: {result.detected_edges}")
