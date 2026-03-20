"""Node state computation — derived at query time, never persisted.

State priority (highest wins):
  running  → a node_run with status='running' exists
  failed   → most recent node_run has status='failed'
  drifting → unresolved anomaly exists for this node
  stale    → time since last successful run > 2× pipeline cadence
  healthy  → default when all checks pass
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pulse_api.models.metric import Anomaly
from pulse_api.models.run import NodeRun, PipelineRun


@dataclass
class NodeStateInfo:
    state: str  # 'healthy' | 'failed' | 'running' | 'drifting' | 'stale'
    last_run_at: datetime | None
    last_run_status: str | None
    anomaly_count: int


async def _pipeline_cadence(session: AsyncSession, pipeline_id: uuid.UUID) -> timedelta:
    """Estimate run cadence from the last 20 pipeline runs. Defaults to 24h."""
    rows = (
        await session.execute(
            select(PipelineRun.started_at)
            .where(PipelineRun.pipeline_id == pipeline_id)
            .order_by(PipelineRun.started_at.desc())
            .limit(20)
        )
    ).fetchall()

    timestamps = [r[0] for r in rows]
    if len(timestamps) < 2:
        return timedelta(hours=24)

    intervals = [timestamps[i] - timestamps[i + 1] for i in range(len(timestamps) - 1)]
    return sum(intervals, timedelta()) / len(intervals)


async def compute_node_states(
    session: AsyncSession,
    node_ids: list[uuid.UUID],
    pipeline_id: uuid.UUID,
) -> dict[uuid.UUID, NodeStateInfo]:
    if not node_ids:
        return {}

    now = datetime.now(timezone.utc)

    # ── Latest node run per node (any status) ─────────────────────────────────
    rn_latest = func.row_number().over(
        partition_by=NodeRun.node_id,
        order_by=NodeRun.started_at.desc(),
    ).label("rn")
    latest_subq = (
        select(NodeRun.node_id, NodeRun.status, NodeRun.started_at, rn_latest)
        .where(NodeRun.node_id.in_(node_ids))
        .subquery()
    )
    latest_rows = (
        await session.execute(
            select(latest_subq.c.node_id, latest_subq.c.status, latest_subq.c.started_at)
            .where(latest_subq.c.rn == 1)
        )
    ).fetchall()
    latest: dict[uuid.UUID, tuple[str, datetime]] = {
        r.node_id: (r.status, r.started_at) for r in latest_rows
    }

    # ── Last successful run per node ──────────────────────────────────────────
    rn_success = func.row_number().over(
        partition_by=NodeRun.node_id,
        order_by=NodeRun.started_at.desc(),
    ).label("rn")
    success_subq = (
        select(NodeRun.node_id, NodeRun.started_at, rn_success)
        .where(
            and_(
                NodeRun.node_id.in_(node_ids),
                NodeRun.status == "success",
            )
        )
        .subquery()
    )
    success_rows = (
        await session.execute(
            select(success_subq.c.node_id, success_subq.c.started_at)
            .where(success_subq.c.rn == 1)
        )
    ).fetchall()
    last_success: dict[uuid.UUID, datetime] = {
        r.node_id: r.started_at for r in success_rows
    }

    # ── Unresolved anomaly counts per node ────────────────────────────────────
    anomaly_rows = (
        await session.execute(
            select(Anomaly.node_id, func.count().label("cnt"))
            .where(
                and_(
                    Anomaly.node_id.in_(node_ids),
                    Anomaly.resolved_at.is_(None),
                )
            )
            .group_by(Anomaly.node_id)
        )
    ).fetchall()
    anomaly_counts: dict[uuid.UUID, int] = {r.node_id: r.cnt for r in anomaly_rows}

    # ── Pipeline cadence for stale threshold ──────────────────────────────────
    cadence = await _pipeline_cadence(session, pipeline_id)
    stale_threshold = cadence * 2

    # ── Derive per-node state ─────────────────────────────────────────────────
    result: dict[uuid.UUID, NodeStateInfo] = {}
    for node_id in node_ids:
        node_latest = latest.get(node_id)
        node_last_success = last_success.get(node_id)
        anomaly_count = anomaly_counts.get(node_id, 0)

        if node_latest is None:
            state = "stale"
        else:
            status, _run_at = node_latest
            if status == "running":
                state = "running"
            elif status == "failed":
                state = "failed"
            elif anomaly_count > 0:
                state = "drifting"
            elif node_last_success is None or (now - node_last_success) > stale_threshold:
                state = "stale"
            else:
                state = "healthy"

        result[node_id] = NodeStateInfo(
            state=state,
            last_run_at=node_latest[1] if node_latest else None,
            last_run_status=node_latest[0] if node_latest else None,
            anomaly_count=anomaly_count,
        )

    return result
