#!/usr/bin/env python3
"""
Test script for Episode-Centric Provenance infrastructure.

Prerequisites:
    1. Start services: docker compose up -d
    2. Apply migration: psql -h localhost -U postgres -f schemas/migrations/001_episode_provenance.sql

Usage:
    python scripts/lineage/test_lineage.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lineage import LineageTracker, OperationType, emit_lineage
from lineage.decorators import add_context_pattern, set_coherence_score, add_detected_edge


def test_tracker_context_manager():
    """Test LineageTracker as context manager."""
    print("\n=== Test: LineageTracker context manager ===")

    with LineageTracker(
        source_name="test-source",
        run_type="manual",
        agent_name="test_lineage.py",
    ) as tracker:
        print(f"Run ID: {tracker.run_id}")

        # Test track_operation context manager
        with tracker.track_operation(
            operation=OperationType.INGEST,
            target_type="entity",
            target_id="test-entity-001",
        ) as episode:
            episode.add_context_pattern("skos")
            episode.add_context_pattern("ddd")
            episode.coherence_score = 0.85
            episode.set_agent_info(
                name="test_ingest",
                version="1.0.0",
                model="gpt-4o-mini",
            )
            print(f"Episode ID: {episode.id}")

        # Test classification episode
        with tracker.track_operation(
            operation=OperationType.CLASSIFY,
            target_type="entity",
            target_id="test-entity-001",
        ) as episode:
            episode.add_context_pattern("semantic-operations")
            episode.coherence_score = 0.92
            episode.add_detected_edge(
                predicate="derived_from",
                target_id="test-entity-000",
                strength=0.8,
                rationale="Content appears to build on previous entity",
            )
            print(f"Classification Episode ID: {episode.id}")

    print("Run completed successfully!")
    return True


@emit_lineage(
    operation=OperationType.CLASSIFY,
    target_id_param="entity_id",
    agent_name="mock_classifier",
    agent_version="1.0.0",
)
def mock_classify(entity_id: str, content: str) -> dict:
    """Mock classification function with lineage decorator."""
    # In a real classifier, this would do LLM calls
    add_context_pattern("skos")
    add_context_pattern("prov-o")
    set_coherence_score(0.88)
    add_detected_edge(
        predicate="related_to",
        target_id="some-pattern",
        strength=0.7,
        rationale="Semantic similarity detected",
    )
    return {"classification": "approved", "confidence": 0.88}


def test_decorator():
    """Test emit_lineage decorator."""
    print("\n=== Test: @emit_lineage decorator ===")

    # This should create a standalone episode
    result = mock_classify(entity_id="test-entity-002", content="Test content")
    print(f"Classification result: {result}")
    print("Decorator test completed!")
    return True


def test_decorator_with_tracker():
    """Test decorator within a tracker context."""
    print("\n=== Test: Decorator within tracker context ===")

    with LineageTracker(
        source_name="decorator-test",
        run_type="manual",
        agent_name="test_lineage.py",
    ) as tracker:
        from lineage.decorators import LineageContext
        LineageContext.set_tracker(tracker)

        try:
            result = mock_classify(entity_id="test-entity-003", content="Test content 2")
            print(f"Classification result: {result}")
        finally:
            LineageContext.clear()

    print("Decorator with tracker test completed!")
    return True


def verify_data():
    """Verify data was written to the database."""
    print("\n=== Verifying data in database ===")

    import psycopg
    from pydantic_settings import BaseSettings

    class Settings(BaseSettings):
        postgres_host: str = "localhost"
        postgres_port: int = 5432
        postgres_db: str = "postgres"
        postgres_user: str = "postgres"
        postgres_password: str = "postgres"

        class Config:
            env_file = ".env"
            extra = "ignore"

    settings = Settings()

    conn = psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )

    with conn.cursor() as cur:
        # Check runs
        cur.execute("SELECT COUNT(*) FROM ingestion_run")
        run_count = cur.fetchone()[0]
        print(f"Ingestion runs: {run_count}")

        # Check episodes
        cur.execute("SELECT COUNT(*) FROM ingestion_episode")
        episode_count = cur.fetchone()[0]
        print(f"Ingestion episodes: {episode_count}")

        # Show recent episodes
        cur.execute("""
            SELECT e.id, e.operation, e.target_type, e.target_id, e.coherence_score, r.source_name
            FROM ingestion_episode e
            LEFT JOIN ingestion_run r ON e.run_id = r.id
            ORDER BY e.created_at DESC
            LIMIT 5
        """)
        print("\nRecent episodes:")
        for row in cur.fetchall():
            print(f"  {row[0][:8]}... | {row[1]:15} | {row[2]:8} | {row[3]:20} | score={row[4]} | source={row[5]}")

    conn.close()
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Episode-Centric Provenance Infrastructure Test")
    print("=" * 60)

    try:
        test_tracker_context_manager()
        test_decorator()
        test_decorator_with_tracker()
        verify_data()

        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
