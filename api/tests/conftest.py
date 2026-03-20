"""Shared test fixtures.

seed_data is session-scoped (seeds the DB once per test session).
Data-fetching fixtures (pipelines, jaffle, etc.) are function-scoped so they
re-query after test_dev.py calls /dev/seed again mid-session.

# ── Async DB access in tests ───────────────────────────────────────────────────
# pytest-anyio creates a NEW asyncio event loop for each async test function.
# asyncpg binds each connection to the event loop that was active when the
# connection was opened. The module-level engine in database.py opens its pool
# connections in the event loop of the first request that touches it (typically
# the TestClient's internal loop). When an async test then runs in a *different*
# loop, any pooled connection from the old loop raises:
#
#   RuntimeError: Task ... got Future attached to a different loop
#   — or —
#   AttributeError: 'NoneType' object has no attribute 'send'  (closed loop)
#
# The fix used throughout this test suite: any @pytest.mark.anyio test (or
# fixture) that needs direct DB access must create its own engine with
# NullPool inside the test/fixture body:
#
#   engine = create_async_engine(settings.database_url, poolclass=NullPool)
#   maker  = async_sessionmaker(engine, expire_on_commit=False)
#   async with maker() as session:
#       ...
#   await engine.dispose()
#
# NullPool means no connection is ever cached, so each session opens a fresh
# asyncpg connection in the current event loop and closes it when done.
# Tests that go through the HTTP layer (TestClient) are unaffected because
# TestClient runs its own synchronous thread with a stable event loop.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from pulse_api.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def seed_data(client: TestClient) -> dict:
    """Seed once per session; return the seed response payload."""
    resp = client.post("/dev/seed")
    assert resp.status_code == 200, f"Seed failed: {resp.text}"
    return resp.json()


@pytest.fixture
def pipelines(client: TestClient, seed_data: dict) -> list[dict]:  # noqa: ARG001
    resp = client.get("/pipelines")
    assert resp.status_code == 200
    return resp.json()["pipelines"]


@pytest.fixture
def jaffle(pipelines: list[dict]) -> dict:
    return next(p for p in pipelines if p["slug"] == "jaffle-shop-analytics")


@pytest.fixture
def payments(pipelines: list[dict]) -> dict:
    return next(p for p in pipelines if p["slug"] == "payments-pipeline")


@pytest.fixture
def ml(pipelines: list[dict]) -> dict:
    return next(p for p in pipelines if p["slug"] == "ml-feature-store")


@pytest.fixture
def jaffle_graph(client: TestClient, jaffle: dict) -> dict:
    resp = client.get(f"/pipelines/{jaffle['id']}/graph")
    assert resp.status_code == 200
    return resp.json()


@pytest.fixture
def jaffle_node(jaffle_graph: dict) -> dict:
    return jaffle_graph["nodes"][0]


@pytest.fixture(scope="session")
def nonexistent_id() -> str:
    return str(uuid.UUID(int=0))
