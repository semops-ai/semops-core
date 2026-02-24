-- Project Ike Phase 1 Schema
-- DDD-inspired design with W3C standards foundation:
-- - Content metadata (JSONB) based on W3C SKOS (Simple Knowledge Organization System)
-- - Edge predicates based on W3C PROV-O (Provenance Ontology)
-- See: https://www.w3.org/TR/skos-reference/ and https://www.w3.org/TR/prov-o/

-- Schema version tracking
create table if not exists schema_version (
 version text primary key,
 applied_at timestamptz default now,
 description text
);

-- Insert initial version
insert into schema_version (version, description) values
 ('5.0.0', 'Phase 1 DAM-aligned: Changed status to approval_status (pending|approved|rejected) following DAM industry standards');

-- All knowledge assets are stored as entities with concrete asset_type
-- Abstract categorization (research_paper, blog_post, etc.) lives in metadata.content_type

-- Content/artifact entity (concrete things)
create table if not exists entity (
 id text primary key, -- slug-style: blog-post-ai-adoption-2024
 asset_type text not null -- file | link (concrete: do you have it or reference it?)
 check (asset_type in ('file', 'link')),
 title text, -- human-readable title
 version text default '1.0', -- semantic versioning for iterations
 visibility text not null default 'public'
 check (visibility in ('public','private')), -- whether data is available for public consumption
 approval_status text not null default 'pending'
 check (approval_status in ('pending','approved','rejected')), -- DAM-style approval workflow
 provenance text not null default '1p'
 check (provenance in ('1p','2p','3p')), -- 1p = created by us, 2p = partner/collab, 3p = external
 filespec jsonb not null default '{}', -- typed: filespec_v1 (uri, format, hash, mime_type, size, etc)
 attribution jsonb not null default '{}', -- typed: attribution_v2 (creator, contributor, publisher, rights, agents) - Dublin Core aligned
 metadata jsonb not null default '{}', -- typed: content_metadata_v1 (W3C SKOS-based: content_type, primary_concept, broader_concepts, etc)
 created_at timestamptz not null default now,
 updated_at timestamptz not null default now,
 approved_at timestamptz -- when approval_status became 'approved'
);

-- Relationships between entities (graph structure)
-- Based on W3C PROV-O (Provenance Ontology) for provenance tracking
-- See: https://www.w3.org/TR/prov-o/
create table if not exists edge (
 src_type text not null check (src_type in ('entity','surface')),
 src_id text not null,
 dst_type text not null check (dst_type in ('entity','surface')),
 dst_id text not null,
 predicate text not null -- W3C PROV-O based: derived_from (prov:wasDerivedFrom), cites (prov:wasQuotedFrom), version_of (prov:wasRevisionOf), plus domain extensions
 check (predicate in ('derived_from','cites','version_of','part_of','documents','depends_on','related_to')),
 strength decimal(3,2) default 1.0 -- relationship strength 0.0-1.0 for ranking
 check (strength >= 0.0 and strength <= 1.0),
 metadata jsonb not null default '{}', -- edge-specific metadata (e.g., timestamps, locations within content)
 created_at timestamptz default now,
 primary key (src_type, src_id, dst_type, dst_id, predicate)
);

-- Surfaces (publication destinations and ingestion sources)
create table if not exists surface (
 id text primary key, -- slug-style: youtube-my-channel, github-my-repo
 platform text not null, -- youtube | github | wordpress | medium | linkedin | twitter | instagram
 surface_type text not null, -- channel | repo | site | publication | feed | profile
 direction text not null -- publish | ingest | bidirectional
 check (direction in ('publish','ingest','bidirectional')),
 constraints jsonb not null default '{}', -- platform limits/capabilities (max_size, formats, etc)
 metadata jsonb not null default '{}', -- typed metadata (youtube_channel_v1, github_repo_v1, etc)
 created_at timestamptz not null default now,
 updated_at timestamptz not null default now
);

-- Surface addresses (URLs and endpoints for surfaces)
create table if not exists surface_address (
 surface_id text not null references surface(id) on delete cascade,
 kind text not null, -- public | feed | api | webhook | deeplink
 uri text not null, -- the actual URL or endpoint
 active boolean not null default true,
 first_seen timestamptz default now,
 last_seen timestamptz default now,
 primary key (surface_id, kind, uri)
);

-- Deliveries (entity published to or ingested from a surface)
create table if not exists delivery (
 id text primary key, -- slug-style: delivery-blog-post-123-wordpress
 entity_id text not null references entity(id),
 surface_id text not null references surface(id),
 role text not null -- original | syndication
 check (role in ('original','syndication')),
 status text not null -- planned | queued | published | failed | removed
 check (status in ('planned','queued','published','failed','removed')),
 url text, -- where the content lives on the surface
 remote_id text, -- platform-specific ID (YouTube video ID, GitHub issue number, etc)
 field_mapping jsonb not null default '{}', -- how entity fields map to platform schema
 source_hash text, -- hash for deduplication and lineage
 published_at timestamptz,
 failed_at timestamptz,
 error_message text,
 metadata jsonb not null default '{}', -- delivery-specific metadata
 created_at timestamptz not null default now,
 updated_at timestamptz not null default now
);

-- Indexes for performance

-- Entity indexes
create index if not exists idx_entity_asset_type on entity(asset_type);
create index if not exists idx_entity_approval_status on entity(approval_status);
create index if not exists idx_entity_provenance on entity(provenance);
create index if not exists idx_entity_visibility on entity(visibility);
create index if not exists idx_entity_approved_at on entity(approved_at);
create index if not exists idx_entity_metadata on entity using gin(metadata);
create index if not exists idx_entity_filespec on entity using gin(filespec);
create index if not exists idx_entity_attribution on entity using gin(attribution);

-- Edge indexes
create index if not exists idx_edge_src on edge(src_type, src_id);
create index if not exists idx_edge_dst on edge(dst_type, dst_id);
create index if not exists idx_edge_predicate on edge(predicate);
create index if not exists idx_edge_strength on edge(strength);

-- Surface indexes
create index if not exists idx_surface_platform on surface(platform);
create index if not exists idx_surface_type on surface(surface_type);
create index if not exists idx_surface_direction on surface(direction);

-- Surface address indexes
create index if not exists idx_surface_address_active on surface_address(active);
create index if not exists idx_surface_address_kind on surface_address(kind);

-- Delivery indexes
create index if not exists idx_delivery_entity_id on delivery(entity_id);
create index if not exists idx_delivery_surface_id on delivery(surface_id);
create index if not exists idx_delivery_status on delivery(status);
create index if not exists idx_delivery_role on delivery(role);
create index if not exists idx_delivery_published_at on delivery(published_at);
create index if not exists idx_delivery_remote_id on delivery(remote_id);

-- Note: Referential integrity for polymorphic edges will be handled by:
-- 1. Application-level validation when inserting edges
-- 2. Fitness functions that check for orphaned references
-- 3. Periodic cleanup jobs if needed
-- 
-- This is a common pattern for polymorphic relationships in Postgres

-- Update triggers for updated_at
create or replace function update_updated_at_column
returns trigger as $$
begin
 new.updated_at = now;
 return new;
end;
$$ language plpgsql;

create trigger update_entity_updated_at before update on entity
 for each row execute function update_updated_at_column;

create trigger update_surface_updated_at before update on surface
 for each row execute function update_updated_at_column;

create trigger update_delivery_updated_at before update on delivery
 for each row execute function update_updated_at_column;

-- Comments for documentation
comment on table entity is 'Aggregate root - all concrete deliverables, content, and knowledge assets';
comment on table edge is 'Typed relationships between entities and surfaces';
comment on table surface is 'Publication destinations and ingestion sources (channels, repos, sites)';
comment on table surface_address is 'URLs and endpoints for surfaces';
comment on table delivery is 'Record of entity published to or ingested from a surface';

comment on column entity.asset_type is 'Concrete asset type: file (you possess it) or link (external reference). Abstract type lives in metadata.content_type';
comment on column entity.provenance is 'Origin: 1p (first party/us), 2p (partner/collab), 3p (external). Derived content is indicated by derived_from edges, not provenance value';
comment on column entity.filespec is 'Typed JSON (filespec_v1): uri, format, hash, mime_type, size_bytes, platform, etc';
comment on column entity.attribution is 'Typed JSON (attribution_v2): Dublin Core aligned - creator (dc:creator), contributor (dc:contributor), publisher (dc:publisher), rights (dc:rights), plus custom extensions: organization, platform, channel, agents, original_source, source_reference, epistemic_status (fact/synthesis/hypothesis), concept_ownership (1p/2p/3p)';
comment on column entity.metadata is 'Typed JSON (content_metadata_v1): content_type (research_paper, blog_post, etc), media_type, subject_area, tags, etc';

comment on column edge.predicate is 'Edge predicates based on W3C PROV-O (derived_from, cites, version_of), Schema.org (part_of, documents), and Project Ike domain extensions (depends_on, related_to). See UBIQUITOUS_LANGUAGE.md for complete semantics and standards mapping.';
comment on column edge.strength is 'Relationship strength 0.0-1.0 for ranking and filtering';
comment on column edge.metadata is 'Edge-specific data like timestamps, locations within content, or confidence scores';

comment on column surface.direction is 'Data flow: publish (we push content), ingest (we pull content), bidirectional (both)';
comment on column surface.constraints is 'Platform limits and capabilities (max file size, supported formats, rate limits)';

comment on column delivery.role is 'original (first publication) or syndication (republished/cross-posted)';
comment on column delivery.status is 'Lifecycle: planned → queued → published (or failed/removed)';
comment on column delivery.remote_id is 'Platform-specific identifier (YouTube video ID, GitHub issue number, etc)';

-- ============================================================================
-- DESIGN PATTERNS & EXAMPLES
-- ============================================================================

-- Pattern 1: Sub-Entities (Quotes, Clips, Transcripts from Source Content)
-- --------------------------------------------------------------------------
-- Use case: Extract a quote from a YouTube video, or a clip from a longer video
--
-- Each piece of content is its own entity with independent:
-- - Identity (unique ID)
-- - Visibility (quote can be public even if source is private)
-- - Provenance (quote is 'derived', source may be '3p')
-- - Lifecycle (quote can be published independently)
--
-- Example:
/*
-- Original 3p video (link - we don't have the video file)
INSERT INTO entity VALUES (
 'yt-link-lex-ai-safety-2024',
 'link',
 'Lex Fridman on AI Safety',
 '1.0',
 'public',
 'approved',
 '3p',
 '{"$schema":"filespec_v1","uri":"https://youtube.com/watch?v=xyz123","platform":"youtube"}',
 '{"$schema":"attribution_v2","platform":"youtube","creator":["Lex Fridman"],"channel":"Lex Fridman Podcast"}',
 '{"$schema":"content_metadata_v1","content_type":"educational_video","media_type":"video","duration_seconds":3600,"subject_area":["AI/ML","AI Safety"]}',
 now,
 now,
 '2024-01-15'
);

-- Transcript we extracted (file - we have this)
-- Provenance is 1p because WE created this derivative work (even though source is 3p)
INSERT INTO entity VALUES (
 'transcript-lex-ai-safety-2024',
 'file',
 'Transcript: Lex Fridman on AI Safety',
 '1.0',
 'private',
 'pending',
 '1p',
 '{"$schema":"filespec_v1","uri":"file:///transcripts/lex-ai-safety.txt","format":"text","hash":"sha256:abc123..."}',
 '{"$schema":"attribution_v2","agents":[{"name":"youtube-dl","role":"transcriber"}]}',
 '{"$schema":"content_metadata_v1","content_type":"transcript","media_type":"text","word_count":5000}',
 now,
 now,
 null
);

-- Extracted quote (file - we have this, can be made public)
-- Provenance is 1p because WE extracted/created this quote
INSERT INTO entity VALUES (
 'quote-ai-alignment-problem',
 'file',
 'Lex on the alignment problem',
 '1.0',
 'public',
 'approved',
 '1p',
 '{"$schema":"filespec_v1","uri":"file:///quotes/ai-alignment-001.txt","format":"text"}',
 '{"$schema":"attribution_v2"}',
 '{"$schema":"content_metadata_v1","content_type":"quote","media_type":"text","text":"The alignment problem is fundamentally about...","timestamp":"00:20:34"}',
 now,
 now,
 now
);

-- Link transcript to video
INSERT INTO edge VALUES (
 'entity', 'transcript-lex-ai-safety-2024',
 'entity', 'yt-link-lex-ai-safety-2024',
 'derived_from',
 1.0,
 '{}',
 now
);

-- Link quote to transcript
INSERT INTO edge VALUES (
 'entity', 'quote-ai-alignment-problem',
 'entity', 'transcript-lex-ai-safety-2024',
 'derived_from',
 1.0,
 '{"timestamp":"00:20:34"}', -- edge metadata: where in the transcript
 now
);
*/

-- Pattern 2: Attribution with Multiple Parties (YouTube Channel + Person)
-- ------------------------------------------------------------------------
-- Use typed metadata in attribution field until Phase 3 (Party entities)
-- Attribution v2 aligns with Dublin Core metadata standard
--
-- Example attribution_v2 metadata:
/*
{
 "$schema": "attribution_v2",
 "creator": ["Lex Fridman"],
 "publisher": "Lex Fridman Media",
 "rights": "All Rights Reserved",
 "platform": "youtube",
 "channel": "Lex Fridman Podcast",
 "original_source": "https://youtube.com/watch?v=xyz123",
 "publication_date": "2024-01-15"
}
*/

-- Pattern 3: Content Hierarchy (Link → File → File)
-- -----------------------------------------------------------
/*
entity('yt-link-xyz') [asset_type='link', provenance='3p', visibility='public']
 ↓ derived_from (edge)
entity('transcript-xyz') [asset_type='file', provenance='1p', visibility='private'] -- 1p because YOU created the transcript
 ↓ derived_from (edge)
entity('quote-1') [asset_type='file', provenance='1p', visibility='public'] -- 1p because YOU extracted it
entity('quote-2') [asset_type='file', provenance='1p', visibility='public'] -- 1p because YOU extracted it

Note: The 'derived_from' relationship is captured in edges, not in provenance.
 Provenance indicates WHO created THIS specific artifact (the transcript, the quote).
*/

-- Pattern 4: Publishing Workflow (Entity → Surface via Delivery)
-- --------------------------------------------------------------
/*
-- Create entity (blog post file)
INSERT INTO entity VALUES ('blog-post-ai-trends-2024', 'file', ...);

-- Create surface (WordPress site)
INSERT INTO surface VALUES ('wordpress-mysite', 'wordpress', 'site', 'publish', ...);

-- Plan delivery
INSERT INTO delivery VALUES (
 'delivery-blog-post-ai-trends-wordpress',
 'blog-post-ai-trends-2024',
 'wordpress-mysite',
 'original',
 'planned',
 NULL, -- url not known yet
 NULL, -- remote_id not known yet
 '{}', -- field mapping
 NULL, -- source_hash
 NULL, -- not published yet
 NULL,
 NULL,
 '{}',
 now,
 now
);

-- After successful publish, update delivery
UPDATE delivery SET
 status = 'published',
 url = 'https://mysite.com/blog/ai-trends-2024',
 remote_id = '12345', -- WordPress post ID
 published_at = now
WHERE id = 'delivery-blog-post-ai-trends-wordpress';
*/

-- Pattern 5: Invariants & Business Rules
-- ---------------------------------------
-- 1. Derived entities MUST have at least one 'derived_from' edge
-- 2. At most one delivery with role='original' per entity
-- 3. Cannot deliver private entity to public surface
-- 4. Once approval_status='approved', certain fields become immutable
-- 5. Entities with approval_status='pending' should not have delivery records
--
-- These are enforced via:
-- - Application-level validation
-- - Fitness functions (CI tests)
-- - Database constraints where possible