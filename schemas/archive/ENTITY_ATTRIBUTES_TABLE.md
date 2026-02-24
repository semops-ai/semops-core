# Entity (Aggregate Root) - Attribute Type Classification

## Complete Attribute Breakdown (Lines 17-29)

| Attribute | Type Category | Specific Type | Description | Example Value |
|-----------|---------------|---------------|-------------|---------------|
| `id` | Identity | String (kebab-case) | Unique identifier for the entity | `"blog-post-semantic-ops-2024"` |
| `asset_type` | Enum | AssetType | Concrete type indicating if you possess the content or reference it | `"file"` or `"link"` |
| `title` | Primitive | String | Human-readable title | `"Introduction to Semantic Operations"` |
| `version` | Primitive | String (semantic versioning) | Version number for iteration tracking | `"1.0"`, `"1.1"`, `"2.0"` |
| `provenance` | Enum | ProvenanceType | Who created THIS artifact | `"1p"`, `"2p"`, or `"3p"` |
| `status` | Enum | Status | Current lifecycle state | `"draft"`, `"published"`, or `"archived"` |
| `visibility` | Enum | Visibility | Access level | `"public"` or `"private"` |
| `filespec` | Value Object | FileSpec (JSONB: filespec_v1) | Physical location and file properties | `{"$schema": "filespec_v1", "uri": "...", "format": "pdf", ...}` |
| `attribution` | Value Object | Attribution (JSONB: attribution_v2) | Authorship and provenance details (Dublin Core aligned) | `{"$schema": "attribution_v2", "creator": [...], ...}` |
| `metadata` | Value Object | ContentMetadata (JSONB: content_metadata_v1) | Semantic content metadata (W3C SKOS-based) | `{"$schema": "content_metadata_v1", "semantic_type": "concept", ...}` |
| `created_at` | Timestamp | DateTime | When entity was created | `2024-11-07T10:30:00Z` |
| `updated_at` | Timestamp | DateTime | When entity was last modified | `2024-11-15T14:22:00Z` |
| `published_at` | Timestamp | DateTime (Optional) | When status became 'published' | `2024-11-10T09:00:00Z` or `null` |

## Type Category Definitions

### Identity
- **Purpose**: Uniquely identifies this entity instance
- **Characteristics**: Required, unique across all entities
- **Equality**: Two entities are the same if they have the same ID

### Primitive
- **Purpose**: Simple, atomic values
- **Characteristics**: Built-in types (string, number, boolean)
- **Examples**: `title: str`, `word_count: int`, `is_featured: bool`

### Enum
- **Purpose**: Constrained set of allowed values with business meaning
- **Characteristics**: Fixed set of valid options, type-safe
- **Immutability**: Enums themselves are immutable, but entity can change which enum value it holds
- **Examples**: Status, Provenance Type, Asset Type

### Value Object
- **Purpose**: Composite domain concept with multiple related attributes
- **Characteristics**:
 - Multiple fields grouped together
 - Immutable (replace entire object to change)
 - No identity of its own
 - Compared by all attribute values
- **Examples**:
 - FileSpec (uri + format + hash + size)
 - Attribution (authors + license + platform)
 - ContentMetadata (W3C SKOS-based semantic metadata)

### Timestamp
- **Purpose**: Track entity lifecycle events
- **Characteristics**: Special datetime primitives for temporal tracking
- **Common patterns**: `created_at`, `updated_at`, `deleted_at`, `published_at`

## DDD Pattern Summary

```python
class Entity(BaseModel):
 # 1. IDENTITY (1 required)
 id: str

 # 2. PRIMITIVES (0 or more)
 title: str
 version: str

 # 3. ENUMS (0 or more)
 asset_type: AssetType
 provenance: ProvenanceType
 status: Status
 visibility: Visibility

 # 4. VALUE OBJECTS (0 or more)
 filespec: FileSpec
 attribution: Attribution
 metadata: ContentMetadata

 # 5. TIMESTAMPS (typically 2+)
 created_at: datetime
 updated_at: datetime
 published_at: Optional[datetime]
```

## Key Distinctions

### Primitive vs Enum
- **Primitive**: Any value of that type (`title: str` can be any string)
- **Enum**: Only specific allowed values (`status: Status` can only be `"draft"`, `"published"`, or `"archived"`)

### Enum vs Value Object
- **Enum**: Single scalar value from constrained set (`"1p"`)
- **Value Object**: Composite object with multiple fields (`{"uri": "...", "format": "pdf", "hash": "..."}`)

### Value Object vs Entity
- **Value Object**: No identity, immutable, compared by values
- **Entity**: Has ID, mutable, compared by identity

---

**This table clarifies the precise DDD type of each attribute in the Entity aggregate root.**
