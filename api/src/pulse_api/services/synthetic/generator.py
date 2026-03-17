"""Orchestrates synthetic data generation and bulk-inserts into the database.

Entry point: seed_database(session) — idempotent, clears existing synthetic
data before writing fresh records.

Generates:
  - 3 pipelines (12, 28, 45 nodes respectively)
  - 90 days of run history at each pipeline's configured schedule
  - row_count and duration_ms metrics per successful node run
  - Pre-baked anomaly records for the injected deviations
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from pulse_api.models.metric import Anomaly, Metric
from pulse_api.models.pipeline import Edge, Node, Pipeline
from pulse_api.models.run import NodeRun, PipelineRun
from pulse_api.services.synthetic.dag_builder import PIPELINE_DEFINITIONS, PipelineDefinition
from pulse_api.services.synthetic.metric_simulator import generate_anomaly_records, generate_metrics
from pulse_api.services.synthetic.run_simulator import simulate_pipeline_runs

_CHUNK = 1_000  # rows per bulk-insert batch
_SIM_DAYS = 90


@dataclass
class SeedResult:
    pipelines_created: int = 0
    node_runs_created: int = 0
    metrics_created: int = 0
    anomalies_created: int = 0
    duration_seconds: float = 0.0
    message: str = "Database seeded successfully"
    pipeline_names: list[str] = field(default_factory=list)


def _chunks(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


async def _seed_pipeline(
    session: AsyncSession,
    pipeline_def: PipelineDefinition,
    sim_start: datetime,
    rng: random.Random,
) -> tuple[int, int, int]:
    """Seed one pipeline. Returns (node_run_count, metric_count, anomaly_count)."""

    # ── Create pipeline ───────────────────────────────────────────────────────
    pipeline = Pipeline(
        name=pipeline_def.name,
        slug=pipeline_def.slug,
        description=pipeline_def.description,
        source_type=pipeline_def.source_type,
    )
    session.add(pipeline)
    await session.flush()  # populate pipeline.id

    # ── Create nodes ──────────────────────────────────────────────────────────
    nodes: list[Node] = []
    for nd in pipeline_def.nodes:
        node = Node(
            pipeline_id=pipeline.id,
            external_id=nd.external_id,
            name=nd.name,
            node_type=nd.node_type,
        )
        session.add(node)
        nodes.append(node)
    await session.flush()  # populate node.id for all nodes

    node_id_map = {n.external_id: n.id for n in nodes}

    # ── Create edges ──────────────────────────────────────────────────────────
    node_by_ext = {n.external_id: n for n in nodes}
    for src_ext, tgt_ext in pipeline_def.edges:
        session.add(
            Edge(
                pipeline_id=pipeline.id,
                source_node_id=node_by_ext[src_ext].id,
                target_node_id=node_by_ext[tgt_ext].id,
            )
        )
    await session.flush()

    # ── Simulate runs ─────────────────────────────────────────────────────────
    pipeline_run_dicts, node_run_dicts = simulate_pipeline_runs(
        pipeline_def, node_id_map, pipeline.id, sim_start, _SIM_DAYS, rng
    )

    for chunk in _chunks(pipeline_run_dicts, _CHUNK):
        await session.execute(insert(PipelineRun), chunk)

    for chunk in _chunks(node_run_dicts, _CHUNK):
        await session.execute(insert(NodeRun), chunk)

    # ── Generate metrics ──────────────────────────────────────────────────────
    node_def_by_db_id = {node_id_map[nd.external_id]: nd for nd in pipeline_def.nodes}
    node_def_by_ext = {nd.external_id: nd for nd in pipeline_def.nodes}

    metric_dicts = generate_metrics(
        node_run_dicts,
        node_def_by_db_id,
        pipeline_def.anomaly_injections,
        node_id_map,
        sim_start,
        rng,
    )

    for chunk in _chunks(metric_dicts, _CHUNK):
        await session.execute(insert(Metric), chunk)

    # ── Create pre-baked anomaly records ──────────────────────────────────────
    anomaly_dicts = generate_anomaly_records(
        pipeline_def.anomaly_injections,
        node_id_map,
        node_def_by_ext,
        sim_start,
    )

    if anomaly_dicts:
        await session.execute(insert(Anomaly), anomaly_dicts)

    return len(node_run_dicts), len(metric_dicts), len(anomaly_dicts)


async def seed_database(session: AsyncSession) -> SeedResult:
    """Clear existing synthetic data and seed three fresh pipelines.

    Uses a fixed RNG seed (42) so results are deterministic across runs.
    Idempotent — safe to call multiple times.
    """
    t0 = time.monotonic()
    rng = random.Random(42)

    # sim_start is 90 days ago at midnight UTC
    sim_start = (datetime.now(timezone.utc) - timedelta(days=_SIM_DAYS)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # ── Clear existing synthetic data (CASCADE removes all child records) ─────
    await session.execute(delete(Pipeline).where(Pipeline.source_type == "synthetic"))
    await session.commit()

    result = SeedResult()

    for pipeline_def in PIPELINE_DEFINITIONS:
        node_runs, metrics, anomalies = await _seed_pipeline(
            session, pipeline_def, sim_start, rng
        )
        await session.commit()

        result.pipelines_created += 1
        result.node_runs_created += node_runs
        result.metrics_created += metrics
        result.anomalies_created += anomalies
        result.pipeline_names.append(pipeline_def.name)

    result.duration_seconds = round(time.monotonic() - t0, 2)
    return result
