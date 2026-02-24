-- Project Ike Surface Records
-- Owned surfaces for Tim Mitchell / TJMConsulting
--
-- Run with: psql -f scripts/sql/seed_surfaces.sql
-- Or: python scripts/run_sql.py scripts/sql/seed_surfaces.sql

-- GitHub profile (primary for source ingestion)
INSERT INTO surface (id, platform, surface_type, direction, constraints, metadata) VALUES
('github-timjmitchell', 'github', 'profile', 'bidirectional',
 '{"formats": ["markdown", "code", "json", "yaml"]}',
 '{"username": "timjmitchell", "organization": "TJMConsulting"}')
ON CONFLICT (id) DO UPDATE SET
 metadata = EXCLUDED.metadata,
 constraints = EXCLUDED.constraints,
 updated_at = now;

-- WordPress site
INSERT INTO surface (id, platform, surface_type, direction, constraints, metadata) VALUES
('wordpress-timjmitchell', 'wordpress', 'site', 'bidirectional',
 '{"formats": ["html", "markdown"], "max_post_size_bytes": 1000000}',
 '{"site_url": "https://www.timjmitchell.com", "site_name": "Tim J Mitchell"}')
ON CONFLICT (id) DO UPDATE SET
 metadata = EXCLUDED.metadata,
 constraints = EXCLUDED.constraints,
 updated_at = now;

-- LinkedIn profile
INSERT INTO surface (id, platform, surface_type, direction, constraints, metadata) VALUES
('linkedin-timjmitchell', 'linkedin', 'profile', 'publish',
 '{"max_post_length": 3000, "formats": ["text", "markdown"]}',
 '{"profile_url": "https://linkedin.com/in/timjmitchell"}')
ON CONFLICT (id) DO UPDATE SET
 metadata = EXCLUDED.metadata,
 constraints = EXCLUDED.constraints,
 updated_at = now;

-- Surface addresses

-- GitHub public profile
INSERT INTO surface_address (surface_id, kind, uri, active) VALUES
('github-timjmitchell', 'public', 'https://github.com/timjmitchell', true)
ON CONFLICT (surface_id, kind, uri) DO NOTHING;

-- GitHub API endpoint
INSERT INTO surface_address (surface_id, kind, uri, active) VALUES
('github-timjmitchell', 'api', 'https://api.github.com/users/timjmitchell', true)
ON CONFLICT (surface_id, kind, uri) DO NOTHING;

-- WordPress public site
INSERT INTO surface_address (surface_id, kind, uri, active) VALUES
('wordpress-timjmitchell', 'public', 'https://www.timjmitchell.com', true)
ON CONFLICT (surface_id, kind, uri) DO NOTHING;

-- WordPress API
INSERT INTO surface_address (surface_id, kind, uri, active) VALUES
('wordpress-timjmitchell', 'api', 'https://www.timjmitchell.com/wp-json/wp/v2', true)
ON CONFLICT (surface_id, kind, uri) DO NOTHING;

-- LinkedIn profile
INSERT INTO surface_address (surface_id, kind, uri, active) VALUES
('linkedin-timjmitchell', 'public', 'https://linkedin.com/in/timjmitchell', true)
ON CONFLICT (surface_id, kind, uri) DO NOTHING;
