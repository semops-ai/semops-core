#!/usr/bin/env python3
"""
Markdown chunker for the unified ingestion pipeline.

Splits markdown content by heading into chunks suitable for RAG retrieval.
Ported from chunk_markdown_docs.py — this module is imported by ingest_from_source.py
rather than run standalone.

Chunking strategy:
- Split by markdown headings (##, ###, etc.)
- Skip YAML frontmatter
- If section exceeds token limit, split with overlap
- Preserve heading hierarchy in metadata
"""

from __future__ import annotations

import re
from dataclasses import dataclass


DEFAULT_MAX_TOKENS = 512
DEFAULT_OVERLAP_TOKENS = 50


@dataclass
class Chunk:
 """A chunk of document content with heading context."""

 heading_hierarchy: list[str]
 content: str
 chunk_index: int # 0 if not split, 1+ if section was split
 total_chunks: int # 1 if not split, N if section was split
 char_count: int
 approx_tokens: int


def estimate_tokens(text: str) -> int:
 """Rough token estimate: ~4 chars per token for English."""
 return len(text) // 4


def strip_yaml_frontmatter(content: str) -> str:
 """Remove YAML frontmatter from markdown."""
 if content.startswith("---"):
 end = content.find("---", 3)
 if end != -1:
 return content[end + 3 :].lstrip
 return content


def _parse_headings(content: str) -> list[tuple[int, str, str]]:
 """
 Parse markdown into sections by heading.

 Returns:
 List of (heading_level, heading_text, section_content) tuples.
 """
 lines = content.split("\n")
 sections: list[tuple[int, str, str]] = []
 current_level = 0
 current_heading = ""
 current_content: list[str] = []

 for line in lines:
 heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
 if heading_match:
 if current_content or current_heading:
 sections.append(
 (current_level, current_heading, "\n".join(current_content).strip)
 )
 current_level = len(heading_match.group(1))
 current_heading = heading_match.group(2)
 current_content = []
 else:
 current_content.append(line)

 if current_content or current_heading:
 sections.append(
 (current_level, current_heading, "\n".join(current_content).strip)
 )

 return sections


def _build_heading_hierarchy(
 sections: list[tuple[int, str, str]], current_idx: int
) -> list[str]:
 """Build the heading hierarchy path for a given section."""
 current_level, current_heading, _ = sections[current_idx]
 hierarchy = [current_heading] if current_heading else []

 for i in range(current_idx - 1, -1, -1):
 level, heading, _ = sections[i]
 if level < current_level and heading:
 hierarchy.insert(0, heading)
 current_level = level

 return hierarchy


def _split_long_section(
 content: str, max_tokens: int, overlap_tokens: int
) -> list[str]:
 """Split a long section into overlapping chunks."""
 if estimate_tokens(content) <= max_tokens:
 return [content]

 chunks: list[str] = []
 words = content.split
 chars_per_token = 4
 max_chars = max_tokens * chars_per_token
 overlap_chars = overlap_tokens * chars_per_token

 current_chunk: list[str] = []
 current_chars = 0

 for word in words:
 word_chars = len(word) + 1
 if current_chars + word_chars > max_chars and current_chunk:
 chunks.append(" ".join(current_chunk))
 overlap_words: list[str] = []
 overlap_count = 0
 for w in reversed(current_chunk):
 if overlap_count + len(w) + 1 > overlap_chars:
 break
 overlap_words.insert(0, w)
 overlap_count += len(w) + 1
 current_chunk = overlap_words
 current_chars = overlap_count

 current_chunk.append(word)
 current_chars += word_chars

 if current_chunk:
 chunks.append(" ".join(current_chunk))

 return chunks


def chunk_markdown(
 content: str,
 max_tokens: int = DEFAULT_MAX_TOKENS,
 overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
 """
 Chunk markdown content by heading structure.

 Args:
 content: Raw markdown content (may include YAML frontmatter).
 max_tokens: Maximum approximate tokens per chunk.
 overlap_tokens: Overlap tokens when splitting long sections.

 Returns:
 List of Chunk objects with heading hierarchy and content.
 """
 content = strip_yaml_frontmatter(content)
 sections = _parse_headings(content)
 chunks: list[Chunk] = []

 for idx, (_level, _heading, section_content) in enumerate(sections):
 if not section_content.strip:
 continue

 hierarchy = _build_heading_hierarchy(sections, idx)
 sub_chunks = _split_long_section(section_content, max_tokens, overlap_tokens)

 for i, sub_content in enumerate(sub_chunks):
 chunks.append(
 Chunk(
 heading_hierarchy=hierarchy,
 content=sub_content,
 chunk_index=i,
 total_chunks=len(sub_chunks),
 char_count=len(sub_content),
 approx_tokens=estimate_tokens(sub_content),
 )
 )

 return chunks
