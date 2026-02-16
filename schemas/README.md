# Phase 1 Schema Documentation

## Overview

The Phase 1 schema implements a **DDD-inspired semantic operations system** with a clear separation between:

- **Concrete reality** (what you physically have)
- **Abstract semantics** (what it represents)
- **Relationships** (how things connect)

## Core Design Principles

### 1. Asset Type (Concrete)

All entities have one of two concrete `asset_type` values:

- **`file`** - You possess the actual file/content
- **`link`** - External reference to content you don't possess

```sql
asset_type text not null check (asset_type in ('file', 'link'))
```

### 2. Content Type (Abstract)

The semantic "what is it" lives in flexible JSONB `metadata.content_type`:

- `research_paper`
- `blog_post`
- `educational_video`
- `transcript`
- `quote`
- `concept_definition`
- `technical_guide`
- etc. (extensible without schema changes)

### 3. Typed JSONB Fields

Three flexible JSONB fields use versioned schemas:

#### `filespec` (WHERE is it?)
Schema: `filespec_v1.json`
```json
{
  "$schema": "filespec_v1",
  "uri": "file:///papers/attention.pdf",
  "format": "pdf",
  "hash": "sha256:abc123...",
  "mime_type": "application/pdf",
  "size_bytes": 2500000
}
```

#### `attribution` (WHO made it?)
Schema: `attribution_v2.json` (Dublin Core aligned)
```json
{
  "$schema": "attribution_v2",
  "creator": ["Vaswani et al"],
  "publisher": "Google Brain",
  "rights": "Apache-2.0",
  "platform": "arxiv",
  "original_source": "https://arxiv.org/abs/1706.03762"
}
```

#### `metadata` (WHAT is it?)
Schema: `content_metadata_v1.json`
```json
{
  "$schema": "content_metadata_v1",
  "content_type": "research_paper",
  "media_type": "document",
  "subject_area": ["AI/ML", "NLP"],
  "word_count": 15000
}
```

## Example: YouTube Video → Transcript → Quote

```sql
-- 1. YouTube link (you don't have the video)
INSERT INTO entity VALUES (
  'yt-transformers-explained',
  'link',                    -- asset_type
  'Understanding Transformers',
  '1.0',
  'public',
  'published',
  '3p',
  '{"$schema":"filespec_v1","uri":"https://youtube.com/watch?v=abc","platform":"youtube"}',
  '{"$schema":"attribution_v2","platform":"youtube","creator":["Dr. Smith"]}',
  '{"$schema":"content_metadata_v1","content_type":"educational_video","media_type":"video"}',
  now(), now(), '2024-01-15'
);

-- 2. Transcript file (you have this)
INSERT INTO entity VALUES (
  'transcript-transformers',
  'file',                    -- asset_type
  'Transcript: Understanding Transformers',
  '1.0',
  'private',
  'draft',
  'derived',
  '{"$schema":"filespec_v1","uri":"file:///transcripts/transformers.txt","format":"text"}',
  '{"$schema":"attribution_v2"}',
  '{"$schema":"content_metadata_v1","content_type":"transcript","media_type":"text"}',
  now(), now(), null
);

-- 3. Quote file (you have this)
INSERT INTO entity VALUES (
  'quote-attention-001',
  'file',                    -- asset_type
  'Key insight about attention',
  '1.0',
  'public',
  'published',
  'derived',
  '{"$schema":"filespec_v1","uri":"file:///quotes/quote-001.txt"}',
  '{"$schema":"attribution_v2"}',
  '{"$schema":"content_metadata_v1","content_type":"quote","media_type":"text","text":"Attention allows..."}',
  now(), now(), now()
);

-- Edges showing lineage
INSERT INTO edge VALUES ('entity', 'transcript-transformers', 'entity', 'yt-transformers-explained', 'derived_from', 1.0, '{}', now());
INSERT INTO edge VALUES ('entity', 'quote-attention-001', 'entity', 'transcript-transformers', 'derived_from', 1.0, '{}', now());
```

## Query Examples

### Find all files of a certain content type
```sql
SELECT * FROM entity
WHERE asset_type = 'file'
AND metadata->>'content_type' = 'research_paper';
```

### Find all YouTube videos
```sql
SELECT * FROM entity
WHERE asset_type = 'link'
AND attribution->>'platform' = 'youtube';
```

### Find all PDFs
```sql
SELECT * FROM entity
WHERE asset_type = 'file'
AND filespec->>'format' = 'pdf';
```

### Trace lineage of a quote back to original source
```sql
WITH RECURSIVE lineage AS (
  SELECT dst_id, src_id FROM edge
  WHERE src_id = 'quote-attention-001' AND predicate = 'derived_from'
  UNION
  SELECT e.dst_id, e.src_id FROM edge e
  JOIN lineage l ON e.src_id = l.dst_id
  WHERE e.predicate = 'derived_from'
)
SELECT * FROM entity WHERE id IN (SELECT dst_id FROM lineage);
```

## Schema Versioning

- Current version: **4.0.0**
- Major change: Simplified `content_kind` → `asset_type` with only `file|link`
- Abstract types moved to `metadata.content_type`

## JSON Schema Validation

Schema definitions in:
- `/schemas/filespec/filespec_v1.json`
- `/schemas/attribution/attribution_v2.json`
- `/schemas/metadata/content_metadata_v1.json`

Use these for validation before inserting entities.

## Key Benefits

✅ **Concrete schema** - Only two asset types
✅ **Flexible abstractions** - Add new content_types without migrations
✅ **Graph-based lineage** - Automatic provenance via edges
✅ **Business rules in code** - Not in complex DB constraints
✅ **Future-proof** - Easy to migrate JSONB → columns if needed
✅ **Queryable** - GIN indexes on JSONB for fast queries

---

## Related Documentation

- **[UBIQUITOUS_LANGUAGE.md](UBIQUITOUS_LANGUAGE.md)** - Canonical definitions of all schema terms, enums, and value objects
- **[phase2-schema.sql](phase2-schema.sql)** - Current database schema implementation
- **[SCHEMA_REFERENCE.md](SCHEMA_REFERENCE.md)** - Column specs, JSONB schemas, constraints
- **[SCHEMA_CHANGELOG.md](SCHEMA_CHANGELOG.md)** - Schema evolution history
