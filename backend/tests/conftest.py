"""Session-scoped Postgres container via testcontainers.

Starts Postgres 16 with pg_stat_statements enabled.  Integration tests are
skipped automatically when Docker is not reachable.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

HERE = Path(__file__).parent.parent  # backend/

# ---------------------------------------------------------------------------
# Docker guard
# ---------------------------------------------------------------------------
try:
    import docker as _docker

    _docker.from_env().ping()
    _DOCKER_OK = True
except Exception:
    _DOCKER_OK = False

skip_no_docker = pytest.mark.skipif(not _DOCKER_OK, reason="Docker not reachable")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_container():
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer(
        image="postgres:16-alpine",
        username="test",
        password="test",
        dbname="testdb",
    )
    container.with_command(
        "postgres"
        " -c shared_preload_libraries=pg_stat_statements"
        " -c pg_stat_statements.track=all"
        " -c pg_stat_statements.max=10000"
    )
    with container as c:
        yield c


@pytest.fixture(scope="session")
def db_url(pg_container) -> str:
    raw = pg_container.get_connection_url()
    return raw.replace("psycopg2", "psycopg")


@pytest.fixture(scope="session")
def test_engine(db_url: str):
    engine = create_engine(db_url, pool_pre_ping=True, future=True)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_stat_statements"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS plantrace"))

    env = {**os.environ, "DATABASE_URL": db_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(HERE),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade failed:\n{result.stdout}\n{result.stderr}")

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Plain session that commits normally; caller cleans up."""
    with Session(test_engine, autoflush=False, expire_on_commit=False) as sess:
        yield sess
