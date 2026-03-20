"""Live pipeline run simulator.

Called by APScheduler every 30 seconds. Picks a random pipeline that has
active WebSocket subscribers, simulates one complete run node-by-node, and
broadcasts a graph_update after each node run completes.

If no clients are connected the function returns immediately (no-op).
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import insert, select

from pulse_api.database import AsyncSessionLocal
from pulse_api.models.pipeline import Node, Pipeline
from pulse_api.models.run import NodeRun, PipelineRun
from pulse_api.services.node_state import compute_node_states
from pulse_api.services.synthetic.dag_builder import PIPELINE_DEFINITIONS
from pulse_api.services.synthetic.run_simulator import _build_parent_map, _topo_sort
from pulse_api.services.ws_manager import manager

_rng = random.Random()


async def run_live_simulation() -> None:
    """Entry point called by APScheduler. No-op when no clients are connected."""
    subscribed = manager.subscribed_pipeline_ids()
    if not subscribed:
        return

    pipeline_id = _rng.choice(list(subscribed))
    async with AsyncSessionLocal() as session:
        await _simulate_run(pipeline_id, session)


async def _simulate_run(pipeline_id: uuid.UUID, session) -> None:  # type: ignore[type-arg]
    pipeline = await session.get(Pipeline, pipeline_id)
    if pipeline is None:
        return

    pipeline_def = next(
        (pd for pd in PIPELINE_DEFINITIONS if pd.slug == pipeline.slug), None
    )
    if pipeline_def is None:
        return

    nodes = (
        await session.execute(select(Node).where(Node.pipeline_id == pipeline_id))
    ).scalars().all()
    if not nodes:
        return

    node_id_map: dict[str, uuid.UUID] = {n.external_id: n.id for n in nodes}
    topo_order = _topo_sort(pipeline_def.nodes, pipeline_def.edges)
    parents = _build_parent_map(pipeline_def.edges)
    node_def_map = {n.external_id: n for n in pipeline_def.nodes}

    now = datetime.now(timezone.utc)
    pipeline_run_id = uuid.uuid4()
    pipeline_status = "success"
    node_statuses: dict[str, str] = {}

    for ext_id in topo_order:
        node_def = node_def_map.get(ext_id)
        if node_def is None:
            continue
        node_db_id = node_id_map.get(ext_id)
        if node_db_id is None:
            continue

        node_parents = parents.get(ext_id, [])
        any_parent_failed = any(
            node_statuses.get(p) in ("failed", "skipped") for p in node_parents
        )

        if any_parent_failed:
            status = "skipped"
            duration_ms = None
            error: str | None = "Skipped due to upstream failure"
        elif _rng.random() < node_def.failure_rate:
            status = "failed"
            pipeline_status = "failed"
            duration_ms = max(1, int(node_def.base_duration_ms * _rng.uniform(0.2, 0.6)))
            error = None
        else:
            status = "success"
            duration_ms = max(1, int(node_def.base_duration_ms * _rng.gauss(1.0, 0.15)))
            error = None

        node_statuses[ext_id] = status
        completed_at = now + timedelta(milliseconds=duration_ms) if duration_ms else now

        await session.execute(
            insert(NodeRun),
            {
                "id": uuid.uuid4(),
                "pipeline_run_id": pipeline_run_id,
                "node_id": node_db_id,
                "started_at": now,
                "completed_at": completed_at,
                "status": status,
                "duration_ms": duration_ms,
                "rows_processed": None,
                "error_message": error,
            },
        )
        await session.commit()

        # Broadcast graph_update with the new state of this node
        node_states = await compute_node_states(session, [node_db_id], pipeline_id)
        info = node_states[node_db_id]
        await manager.broadcast(
            pipeline_id,
            {
                "type": "graph_update",
                "pipeline_id": str(pipeline_id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "nodes": [
                    {
                        "id": str(node_db_id),
                        "state": info.state,
                        "last_run_at": info.last_run_at.isoformat() if info.last_run_at else None,
                        "last_run_status": info.last_run_status,
                        "anomaly_count": info.anomaly_count,
                    }
                ],
            },
        )

    # Persist the pipeline run record
    await session.execute(
        insert(PipelineRun),
        {
            "id": pipeline_run_id,
            "pipeline_id": pipeline_id,
            "started_at": now,
            "completed_at": datetime.now(timezone.utc),
            "status": pipeline_status,
            "triggered_by": "live_simulation",
            "metadata": None,
        },
    )
    await session.commit()
