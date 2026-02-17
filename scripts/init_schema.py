#!/usr/bin/env python3
"""
Initialize Phase 1 Schema

This script initializes the Phase 1 schema (Entity, Edge, Surface, Delivery)
in the Supabase PostgreSQL database.

Usage:
    python scripts/init_schema.py
"""

import os
import sys
import time
import psycopg2
from pathlib import Path

def load_env():
    """Load required environment variables from .env file."""
    env_file = Path(".env")
    if not env_file.exists():
        print("✗ Error: .env file not found!")
        sys.exit(1)

    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()

    # Check required variables
    required = ['POSTGRES_PASSWORD', 'POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 'POSTGRES_USER']
    missing = [var for var in required if var not in env_vars]

    if missing:
        print(f"✗ Error: Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    return env_vars

def wait_for_postgres(config, max_attempts=30):
    """Wait for PostgreSQL to be ready."""
    print("⏳ Waiting for PostgreSQL to be ready...")

    for attempt in range(max_attempts):
        try:
            conn = psycopg2.connect(**config)
            conn.close()
            print("✓ PostgreSQL is ready!")
            return True
        except psycopg2.OperationalError:
            if attempt < max_attempts - 1:
                print(f"  Attempt {attempt + 1}/{max_attempts}: waiting...")
                time.sleep(2)
            else:
                print(f"✗ Failed to connect after {max_attempts} attempts")
                return False

    return False

def run_schema(conn, schema_path):
    """Run the Phase 1 schema SQL file."""
    print(f"\n📄 Loading schema from {schema_path}...")

    if not schema_path.exists():
        print(f"✗ Error: Schema file not found at {schema_path}")
        sys.exit(1)

    with open(schema_path) as f:
        schema_sql = f.read()

    try:
        cursor = conn.cursor()

        print("⚙️  Running Phase 1 schema...")
        cursor.execute(schema_sql)
        conn.commit()

        print("✓ Phase 1 schema installed successfully!")

        # Verify tables
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('entity', 'edge', 'surface', 'surface_address', 'delivery', 'schema_version')
            ORDER BY table_name
        """)

        tables = cursor.fetchall()
        print("\n📊 Tables created:")
        for table in tables:
            print(f"  ✓ {table[0]}")

        # Show schema version
        cursor.execute("""
            SELECT version, description, applied_at
            FROM schema_version
            ORDER BY applied_at DESC
            LIMIT 1
        """)

        version_info = cursor.fetchone()
        if version_info:
            print(f"\n📌 Schema Version: {version_info[0]}")
            print(f"   {version_info[1]}")
            print(f"   Applied: {version_info[2]}")

        cursor.close()
        return True

    except Exception as e:
        print(f"✗ Error running schema: {e}")
        conn.rollback()
        return False

def show_examples():
    """Show example queries and next steps."""
    print("\n" + "="*70)
    print("🎉 Schema Initialization Complete!")
    print("="*70)

    print("\n💡 Quick Test Queries (run in Supabase Studio SQL Editor):")
    print("-" * 70)

    print("""
-- Check schema version
SELECT * FROM schema_version;

-- List all tables
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- Create your first entity (a concept)
INSERT INTO entity (
  id, content_kind, title, visibility, status, provenance,
  filespec, attribution, metadata
) VALUES (
  'concept-semantic-ops',
  'concept',
  'Semantic Operations',
  'public',
  'published',
  '1p',
  '{"type":"concept_v1","location":"./concepts/semantic-ops.md"}'::jsonb,
  '{"type":"attribution_v1","primary_author":"Your Name"}'::jsonb,
  '{}'::jsonb
);

-- View your new entity
SELECT id, content_kind, title, status FROM entity;
""")

    print("\n🚀 Next Steps:")
    print("  1. Open Supabase Studio: http://localhost:8000")
    print("  2. Navigate to Table Editor and explore the schema")
    print("  3. Try the example queries in the SQL Editor")
    print("  4. Check out schemas/phase1-schema.sql for more examples")
    print("  5. Build n8n workflows to populate your knowledge graph")

    print("\n📚 Documentation:")
    print("  • Phase 1 Schema: ./schemas/phase1-schema.sql")
    print("  • Ubiquitous Language: ./schemas/UBIQUITOUS_LANGUAGE.md")
    print("  • DDD Architecture: ./docs/DDD_arch.md")
    print("\n")

def main():
    print("="*70)
    print("SemOps - Phase 1 Schema Initialization")
    print("="*70)
    print()

    # Load environment
    env = load_env()

    # Database config
    db_config = {
        'host': env.get('POSTGRES_HOST', 'localhost'),
        'port': int(env.get('POSTGRES_PORT', 5432)),
        'database': env.get('POSTGRES_DB', 'postgres'),
        'user': env.get('POSTGRES_USER', 'postgres'),
        'password': env['POSTGRES_PASSWORD']
    }

    # Wait for PostgreSQL
    if not wait_for_postgres(db_config):
        print("\n💡 Troubleshooting:")
        print("  1. Make sure services are running: docker compose ps")
        print("  2. Check logs: docker logs ike-semops-db-1")
        print("  3. Start services: python scripts/start.py")
        sys.exit(1)

    # Connect
    print("\n🔌 Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(**db_config)
        print("✓ Connected to PostgreSQL")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)

    # Run schema
    schema_path = Path("schemas/phase1-schema.sql")
    success = run_schema(conn, schema_path)

    # Cleanup
    conn.close()

    if success:
        show_examples()
        sys.exit(0)
    else:
        print("\n✗ Schema initialization failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
