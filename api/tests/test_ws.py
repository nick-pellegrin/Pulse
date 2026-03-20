"""Tests for WS /ws/pipelines/{id}/graph.

Uses TestClient's websocket_connect() which runs inside the same event loop
as all other test requests, so asyncpg connections stay valid.

Tests cover:
  - graph_snapshot on connect (shape, field names, content)
  - error message for nonexistent pipeline
  - snapshot content matches REST GET /pipelines/{id}/graph
  - live_simulator integration: graph_update broadcast after a run
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


# ── graph_snapshot on connect ──────────────────────────────────────────────────

def test_ws_connects_and_receives_snapshot(client: TestClient, jaffle: dict) -> None:
    with client.websocket_connect(f"/ws/pipelines/{jaffle['id']}/graph") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "graph_snapshot"


def test_ws_snapshot_pipeline_id(client: TestClient, jaffle: dict) -> None:
    with client.websocket_connect(f"/ws/pipelines/{jaffle['id']}/graph") as ws:
        msg = ws.receive_json()
    assert msg["pipeline_id"] == jaffle["id"]


def test_ws_snapshot_pipeline_name(client: TestClient, jaffle: dict) -> None:
    with client.websocket_connect(f"/ws/pipelines/{jaffle['id']}/graph") as ws:
        msg = ws.receive_json()
    assert msg["pipeline_name"] == jaffle["name"]


def test_ws_snapshot_has_timestamp(client: TestClient, jaffle: dict) -> None:
    with client.websocket_connect(f"/ws/pipelines/{jaffle['id']}/graph") as ws:
        msg = ws.receive_json()
    assert "timestamp" in msg
    assert msg["timestamp"]


def test_ws_snapshot_node_count(client: TestClient, jaffle: dict) -> None:
    with client.websocket_connect(f"/ws/pipelines/{jaffle['id']}/graph") as ws:
        msg = ws.receive_json()
    assert len(msg["nodes"]) == 12


def test_ws_snapshot_edge_count(client: TestClient, jaffle: dict) -> None:
    with client.websocket_connect(f"/ws/pipelines/{jaffle['id']}/graph") as ws:
        msg = ws.receive_json()
    assert len(msg["edges"]) == 12


def test_ws_snapshot_node_fields(client: TestClient, jaffle: dict) -> None:
    with client.websocket_connect(f"/ws/pipelines/{jaffle['id']}/graph") as ws:
        msg = ws.receive_json()
    node = msg["nodes"][0]
    for field in ("id", "external_id", "name", "node_type", "state",
                  "last_run_at", "last_run_status", "anomaly_count"):
        assert field in node, f"Missing node field: {field}"


def test_ws_snapshot_edge_fields(client: TestClient, jaffle: dict) -> None:
    with client.websocket_connect(f"/ws/pipelines/{jaffle['id']}/graph") as ws:
        msg = ws.receive_json()
    edge = msg["edges"][0]
    for field in ("id", "source_node_id", "target_node_id"):
        assert field in edge, f"Missing edge field: {field}"


def test_ws_snapshot_node_states_valid(client: TestClient, jaffle: dict) -> None:
    valid_states = {"healthy", "failed", "running", "drifting", "stale"}
    with client.websocket_connect(f"/ws/pipelines/{jaffle['id']}/graph") as ws:
        msg = ws.receive_json()
    for node in msg["nodes"]:
        assert node["state"] in valid_states


def test_ws_snapshot_matches_rest_graph(client: TestClient, jaffle: dict) -> None:
    """WS snapshot node states must match GET /pipelines/{id}/graph."""
    rest = client.get(f"/pipelines/{jaffle['id']}/graph").json()
    rest_states = {n["id"]: n["state"] for n in rest["nodes"]}

    with client.websocket_connect(f"/ws/pipelines/{jaffle['id']}/graph") as ws:
        snap = ws.receive_json()
    ws_states = {n["id"]: n["state"] for n in snap["nodes"]}

    assert ws_states == rest_states


def test_ws_snapshot_all_three_pipelines(
    client: TestClient, jaffle: dict, payments: dict, ml: dict
) -> None:
    for pipeline, expected_nodes in [(jaffle, 12), (payments, 28), (ml, 45)]:
        with client.websocket_connect(f"/ws/pipelines/{pipeline['id']}/graph") as ws:
            msg = ws.receive_json()
        assert msg["type"] == "graph_snapshot"
        assert len(msg["nodes"]) == expected_nodes


# ── error handling ─────────────────────────────────────────────────────────────

def test_ws_nonexistent_pipeline_returns_error(
    client: TestClient, nonexistent_id: str
) -> None:
    with client.websocket_connect(f"/ws/pipelines/{nonexistent_id}/graph") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "error"
    assert "Pipeline not found" in msg["detail"]


# ── live simulator integration ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_live_simulator_broadcasts_graph_update(
    client: TestClient, jaffle: dict
) -> None:
    """Trigger the live simulator directly and verify graph_update is broadcast."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from pulse_api.config import settings
    from pulse_api.services.live_simulator import _simulate_run
    from pulse_api.services.ws_manager import manager

    pipeline_id = uuid.UUID(jaffle["id"])
    received: list[dict] = []

    class _FakeWS:
        async def send_json(self, msg: dict) -> None:
            received.append(msg)

    fake_ws = _FakeWS()
    manager._connections[pipeline_id].append(fake_ws)  # type: ignore[attr-defined]

    # NullPool engine so the connection is created fresh in the current event loop
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            await _simulate_run(pipeline_id, session)
    finally:
        manager.disconnect(pipeline_id, fake_ws)  # type: ignore[arg-type]
        await engine.dispose()

    assert len(received) > 0, "Expected at least one graph_update broadcast"

    for msg in received:
        assert msg["type"] == "graph_update"
        assert msg["pipeline_id"] == str(pipeline_id)
        assert "timestamp" in msg
        assert len(msg["nodes"]) == 1  # each update is a single-node delta
        node = msg["nodes"][0]
        for field in ("id", "state", "last_run_at", "last_run_status", "anomaly_count"):
            assert field in node, f"Missing update node field: {field}"
        assert node["state"] in {"healthy", "failed", "running", "drifting", "stale", "skipped"}


@pytest.mark.anyio
async def test_live_simulator_no_op_without_subscribers() -> None:
    """run_live_simulation should return immediately if no clients are connected."""
    from pulse_api.services.live_simulator import run_live_simulation
    from pulse_api.services.ws_manager import manager

    # Ensure no subscribers for any pipeline
    original = dict(manager._connections)  # type: ignore[attr-defined]
    manager._connections.clear()  # type: ignore[attr-defined]
    try:
        # Should complete without error and without hitting the DB
        await run_live_simulation()
    finally:
        manager._connections.update(original)  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_ws_manager_connect_disconnect() -> None:
    """ConnectionManager tracks connections correctly."""
    from pulse_api.services.ws_manager import ConnectionManager

    cm = ConnectionManager()
    pid = uuid.uuid4()

    class _FakeWS:
        async def accept(self) -> None:
            pass

        async def send_json(self, msg: dict) -> None:
            pass

    ws = _FakeWS()
    await cm.connect(pid, ws)  # type: ignore[arg-type]
    assert pid in cm.subscribed_pipeline_ids()

    cm.disconnect(pid, ws)  # type: ignore[arg-type]
    assert pid not in cm.subscribed_pipeline_ids()


@pytest.mark.anyio
async def test_ws_manager_broadcast_prunes_dead_connections() -> None:
    """Dead connections (send_json raises) are pruned from the manager."""
    from pulse_api.services.ws_manager import ConnectionManager

    cm = ConnectionManager()
    pid = uuid.uuid4()

    class _DeadWS:
        async def accept(self) -> None:
            pass

        async def send_json(self, msg: dict) -> None:
            raise RuntimeError("connection closed")

    ws = _DeadWS()
    await cm.connect(pid, ws)  # type: ignore[arg-type]
    assert pid in cm.subscribed_pipeline_ids()

    await cm.broadcast(pid, {"type": "test"})

    # Dead connection should have been pruned
    assert not cm._connections.get(pid)  # type: ignore[attr-defined]
