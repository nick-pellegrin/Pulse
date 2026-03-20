"""Unit tests for services/node_state.py.

Each test inserts minimal controlled data, asserts state, then cleans up.
Uses the real database so all SQLAlchemy window functions work correctly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from pulse_api.config import settings
from pulse_api.models.metric import Anomaly
from pulse_api.models.pipeline import Edge, Node, Pipeline
from pulse_api.models.run import NodeRun, PipelineRun
from pulse_api.services.node_state import NodeStateInfo, compute_node_states

# ── Async engine fixture ───────────────────────────────────────────────────────
# Engine is created inside the fixture so each test gets a fresh asyncpg
# connection in its own event loop (pytest-anyio creates a new loop per test).
# NullPool disables connection reuse so closed-loop connections are never reused.


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ago(**kwargs: int) -> datetime:
    return _now() - timedelta(**kwargs)


async def _make_pipeline(session: AsyncSession) -> Pipeline:
    p = Pipeline(
        name="Test Pipeline",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        source_type="synthetic",
    )
    session.add(p)
    await session.flush()
    return p


async def _make_node(session: AsyncSession, pipeline_id: uuid.UUID) -> Node:
    n = Node(
        pipeline_id=pipeline_id,
        external_id=f"node_{uuid.uuid4().hex[:8]}",
        name="Test Node",
        node_type="model",
    )
    session.add(n)
    await session.flush()
    return n


async def _make_pipeline_run(
    session: AsyncSession, pipeline_id: uuid.UUID, started_at: datetime
) -> PipelineRun:
    pr = PipelineRun(
        pipeline_id=pipeline_id,
        started_at=started_at,
        status="success",
        triggered_by="test",
    )
    session.add(pr)
    await session.flush()
    return pr


async def _make_node_run(
    session: AsyncSession,
    node_id: uuid.UUID,
    pipeline_run_id: uuid.UUID,
    status: str,
    started_at: datetime,
) -> NodeRun:
    nr = NodeRun(
        node_id=node_id,
        pipeline_run_id=pipeline_run_id,
        started_at=started_at,
        status=status,
    )
    session.add(nr)
    await session.flush()
    return nr


async def _cleanup_pipeline(session: AsyncSession, pipeline_id: uuid.UUID) -> None:
    """Delete all test data for a pipeline in dependency order."""
    # node_runs, anomalies depend on nodes which depend on pipelines
    node_ids_result = await session.execute(
        text("SELECT id FROM nodes WHERE pipeline_id = :pid"),
        {"pid": pipeline_id},
    )
    node_ids = [r[0] for r in node_ids_result]
    if node_ids:
        await session.execute(
            delete(NodeRun).where(NodeRun.node_id.in_(node_ids))
        )
        await session.execute(
            delete(Anomaly).where(Anomaly.node_id.in_(node_ids))
        )
    await session.execute(delete(PipelineRun).where(PipelineRun.pipeline_id == pipeline_id))
    await session.execute(delete(Edge).where(Edge.pipeline_id == pipeline_id))
    await session.execute(delete(Node).where(Node.pipeline_id == pipeline_id))
    await session.execute(delete(Pipeline).where(Pipeline.id == pipeline_id))
    await session.commit()


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_empty_node_ids_returns_empty(session: AsyncSession) -> None:
    result = await compute_node_states(session, [], uuid.uuid4())
    assert result == {}


@pytest.mark.anyio
async def test_node_with_no_runs_is_stale(session: AsyncSession) -> None:
    p = await _make_pipeline(session)
    n = await _make_node(session, p.id)
    await session.commit()
    try:
        result = await compute_node_states(session, [n.id], p.id)
        assert result[n.id].state == "stale"
        assert result[n.id].last_run_at is None
        assert result[n.id].last_run_status is None
        assert result[n.id].anomaly_count == 0
    finally:
        await _cleanup_pipeline(session, p.id)


@pytest.mark.anyio
async def test_healthy_state(session: AsyncSession) -> None:
    p = await _make_pipeline(session)
    n = await _make_node(session, p.id)
    # Several recent runs so cadence is ~1 hour; last run successful < 2h ago
    for i in range(5, 0, -1):
        pr = await _make_pipeline_run(session, p.id, _ago(hours=i))
        await _make_node_run(session, n.id, pr.id, "success", _ago(hours=i))
    await session.commit()
    try:
        result = await compute_node_states(session, [n.id], p.id)
        assert result[n.id].state == "healthy"
        assert result[n.id].last_run_status == "success"
        assert result[n.id].anomaly_count == 0
    finally:
        await _cleanup_pipeline(session, p.id)


@pytest.mark.anyio
async def test_running_state(session: AsyncSession) -> None:
    p = await _make_pipeline(session)
    n = await _make_node(session, p.id)
    pr = await _make_pipeline_run(session, p.id, _ago(minutes=5))
    await _make_node_run(session, n.id, pr.id, "running", _ago(minutes=5))
    await session.commit()
    try:
        result = await compute_node_states(session, [n.id], p.id)
        assert result[n.id].state == "running"
    finally:
        await _cleanup_pipeline(session, p.id)


@pytest.mark.anyio
async def test_failed_state(session: AsyncSession) -> None:
    p = await _make_pipeline(session)
    n = await _make_node(session, p.id)
    # Earlier success, then a failure
    pr1 = await _make_pipeline_run(session, p.id, _ago(hours=2))
    await _make_node_run(session, n.id, pr1.id, "success", _ago(hours=2))
    pr2 = await _make_pipeline_run(session, p.id, _ago(hours=1))
    await _make_node_run(session, n.id, pr2.id, "failed", _ago(hours=1))
    await session.commit()
    try:
        result = await compute_node_states(session, [n.id], p.id)
        assert result[n.id].state == "failed"
        assert result[n.id].last_run_status == "failed"
    finally:
        await _cleanup_pipeline(session, p.id)


@pytest.mark.anyio
async def test_drifting_state(session: AsyncSession) -> None:
    p = await _make_pipeline(session)
    n = await _make_node(session, p.id)
    # Recent successful run
    pr = await _make_pipeline_run(session, p.id, _ago(hours=1))
    await _make_node_run(session, n.id, pr.id, "success", _ago(hours=1))
    # Unresolved anomaly
    anomaly = Anomaly(
        node_id=n.id,
        detected_at=_ago(hours=1),
        metric_name="row_count",
        observed_value=0.0,
        expected_value=1000.0,
        severity="high",
    )
    session.add(anomaly)
    await session.commit()
    try:
        result = await compute_node_states(session, [n.id], p.id)
        assert result[n.id].state == "drifting"
        assert result[n.id].anomaly_count == 1
    finally:
        await _cleanup_pipeline(session, p.id)


@pytest.mark.anyio
async def test_resolved_anomaly_does_not_trigger_drifting(session: AsyncSession) -> None:
    p = await _make_pipeline(session)
    n = await _make_node(session, p.id)
    pr = await _make_pipeline_run(session, p.id, _ago(hours=1))
    await _make_node_run(session, n.id, pr.id, "success", _ago(hours=1))
    # Resolved anomaly — should not cause drifting
    anomaly = Anomaly(
        node_id=n.id,
        detected_at=_ago(hours=2),
        metric_name="row_count",
        observed_value=0.0,
        expected_value=1000.0,
        severity="high",
        resolved_at=_ago(hours=1),
    )
    session.add(anomaly)
    await session.commit()
    try:
        result = await compute_node_states(session, [n.id], p.id)
        assert result[n.id].state == "healthy"
        assert result[n.id].anomaly_count == 0
    finally:
        await _cleanup_pipeline(session, p.id)


@pytest.mark.anyio
async def test_running_takes_priority_over_anomaly(session: AsyncSession) -> None:
    p = await _make_pipeline(session)
    n = await _make_node(session, p.id)
    pr = await _make_pipeline_run(session, p.id, _ago(minutes=5))
    await _make_node_run(session, n.id, pr.id, "running", _ago(minutes=5))
    anomaly = Anomaly(
        node_id=n.id,
        detected_at=_ago(hours=1),
        metric_name="row_count",
        observed_value=0.0,
        expected_value=1000.0,
        severity="critical",
    )
    session.add(anomaly)
    await session.commit()
    try:
        result = await compute_node_states(session, [n.id], p.id)
        assert result[n.id].state == "running"
    finally:
        await _cleanup_pipeline(session, p.id)


@pytest.mark.anyio
async def test_failed_takes_priority_over_anomaly(session: AsyncSession) -> None:
    p = await _make_pipeline(session)
    n = await _make_node(session, p.id)
    pr = await _make_pipeline_run(session, p.id, _ago(hours=1))
    await _make_node_run(session, n.id, pr.id, "failed", _ago(hours=1))
    anomaly = Anomaly(
        node_id=n.id,
        detected_at=_ago(hours=1),
        metric_name="row_count",
        observed_value=0.0,
        expected_value=1000.0,
        severity="critical",
    )
    session.add(anomaly)
    await session.commit()
    try:
        result = await compute_node_states(session, [n.id], p.id)
        assert result[n.id].state == "failed"
    finally:
        await _cleanup_pipeline(session, p.id)


@pytest.mark.anyio
async def test_multiple_anomalies_counted(session: AsyncSession) -> None:
    p = await _make_pipeline(session)
    n = await _make_node(session, p.id)
    pr = await _make_pipeline_run(session, p.id, _ago(hours=1))
    await _make_node_run(session, n.id, pr.id, "success", _ago(hours=1))
    for metric in ("row_count", "duration_ms", "failure_rate"):
        session.add(Anomaly(
            node_id=n.id,
            detected_at=_ago(hours=1),
            metric_name=metric,
            observed_value=0.0,
            expected_value=100.0,
            severity="medium",
        ))
    await session.commit()
    try:
        result = await compute_node_states(session, [n.id], p.id)
        assert result[n.id].anomaly_count == 3
    finally:
        await _cleanup_pipeline(session, p.id)


@pytest.mark.anyio
async def test_multiple_nodes_returned(session: AsyncSession) -> None:
    p = await _make_pipeline(session)
    n1 = await _make_node(session, p.id)
    n2 = await _make_node(session, p.id)
    pr = await _make_pipeline_run(session, p.id, _ago(hours=1))
    await _make_node_run(session, n1.id, pr.id, "success", _ago(hours=1))
    await _make_node_run(session, n2.id, pr.id, "failed", _ago(hours=1))
    await session.commit()
    try:
        result = await compute_node_states(session, [n1.id, n2.id], p.id)
        assert len(result) == 2
        assert result[n2.id].state == "failed"
    finally:
        await _cleanup_pipeline(session, p.id)


@pytest.mark.anyio
async def test_node_state_info_fields(session: AsyncSession) -> None:
    p = await _make_pipeline(session)
    n = await _make_node(session, p.id)
    run_time = _ago(hours=1)
    pr = await _make_pipeline_run(session, p.id, run_time)
    await _make_node_run(session, n.id, pr.id, "success", run_time)
    await session.commit()
    try:
        result = await compute_node_states(session, [n.id], p.id)
        info: NodeStateInfo = result[n.id]
        assert isinstance(info.state, str)
        assert info.last_run_at is not None
        assert info.last_run_status == "success"
        assert isinstance(info.anomaly_count, int)
    finally:
        await _cleanup_pipeline(session, p.id)


@pytest.mark.anyio
async def test_stale_when_last_success_exceeds_2x_cadence(session: AsyncSession) -> None:
    p = await _make_pipeline(session)
    n = await _make_node(session, p.id)
    # 10 pipeline runs at consistent 1-hour intervals → cadence ≈ 1h, threshold ≈ 2h.
    # Node success runs only for hours 10-5 ago → last success at 5h ago.
    # 5h > 2h threshold → stale.
    prs: list[tuple[int, PipelineRun]] = []
    for i in range(10, 0, -1):
        pr = await _make_pipeline_run(session, p.id, _ago(hours=i))
        prs.append((i, pr))

    for i, pr in prs:
        if i >= 5:
            await _make_node_run(session, n.id, pr.id, "success", _ago(hours=i))

    # Most recent node run (1h ago): skipped — not failed, not running
    latest_pr = prs[-1][1]  # i=1
    await _make_node_run(session, n.id, latest_pr.id, "skipped", _ago(hours=1))
    await session.commit()
    try:
        result = await compute_node_states(session, [n.id], p.id)
        assert result[n.id].state == "stale"
    finally:
        await _cleanup_pipeline(session, p.id)
