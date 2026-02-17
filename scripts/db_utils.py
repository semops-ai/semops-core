"""
Shared database utilities for SemOps scripts.

Provides a single get_db_connection() function that replaces the duplicated
implementations across the scripts/ and api/ directories.

Connection resolution order:
  1. SEMOPS_DB_* env vars (preferred)
  2. POSTGRES_* env vars (legacy fallback)
  3. Hardcoded defaults (localhost:5434/postgres)

The .env file at the repo root is loaded automatically; env vars already
set in the environment take precedence.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg


def load_env() -> None:
    """Load .env file into os.environ. Existing env vars take precedence."""
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                if key not in os.environ:
                    os.environ[key] = value


def get_db_connection(
    *,
    autocommit: bool = False,
    schema: str | None = None,
) -> psycopg.Connection:
    """
    Get a psycopg3 connection to the SemOps PostgreSQL database.

    Args:
        autocommit: If True, set connection to autocommit mode (for read-only).
        schema: If provided, SET search_path on the connection.
                Defaults to SEMOPS_DB_SCHEMA env var if set and not 'public'.

    Resolution order for each parameter:
        SEMOPS_DB_HOST     > POSTGRES_HOST     > "localhost"
        SEMOPS_DB_PORT     > POSTGRES_PORT     > "5434"
        SEMOPS_DB_NAME     > POSTGRES_DB       > "postgres"
        SEMOPS_DB_USER     > POSTGRES_USER     > "postgres"
        SEMOPS_DB_PASSWORD > POSTGRES_PASSWORD > "postgres"
    """
    load_env()

    host = os.environ.get("SEMOPS_DB_HOST") or os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("SEMOPS_DB_PORT") or os.environ.get("POSTGRES_PORT", "5434")
    db = os.environ.get("SEMOPS_DB_NAME") or os.environ.get("POSTGRES_DB", "postgres")
    user = os.environ.get("SEMOPS_DB_USER") or os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("SEMOPS_DB_PASSWORD") or os.environ.get("POSTGRES_PASSWORD", "postgres")

    # Docker-internal hostname won't resolve from host machine.
    if host == "db":
        host = "localhost"

    conn = psycopg.connect(f"postgresql://{user}:{password}@{host}:{port}/{db}")

    if autocommit:
        conn.autocommit = True

    target_schema = schema or os.environ.get("SEMOPS_DB_SCHEMA")
    if target_schema and target_schema != "public":
        conn.execute(f"SET search_path TO {target_schema}, public")

    return conn
