"""Simulates pipeline run history for a given PipelineDefinition.

Produces pipeline_run and node_run dicts ready for bulk insert.
Handles topological ordering, cascading failures, and bad periods.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

from pulse_api.services.synthetic.dag_builder import NodeDefinition, PipelineDefinition


def _topo_sort(nodes: list[NodeDefinition], edges: list[tuple[str, str]]) -> list[str]:
    """Kahn's algorithm — returns external_ids in dependency order (sources first)."""
    all_ids = [n.external_id for n in nodes]
    # in_edges[node_id] = set of nodes this node depends on
    in_edges: dict[str, set[str]] = {nid: set() for nid in all_ids}
    for src, tgt in edges:
        in_edges[tgt].add(src)

    result: list[str] = []
    ready = sorted(nid for nid in all_ids if not in_edges[nid])

    while ready:
        nid = ready.pop(0)
        result.append(nid)
        for other_id in all_ids:
            if nid in in_edges[other_id]:
                in_edges[other_id].discard(nid)
                if not in_edges[other_id] and other_id not in result and other_id not in ready:
                    ready.append(other_id)
                    ready.sort()

    return result


def _build_parent_map(edges: list[tuple[str, str]]) -> dict[str, list[str]]:
    parents: dict[str, list[str]] = {}
    for src, tgt in edges:
        parents.setdefault(tgt, []).append(src)
    return parents


_ERROR_MESSAGES: dict[str, list[str]] = {
    "source": [
        "Connection timeout to source database",
        "Source table not found or access denied",
        "Upstream data feed unavailable",
    ],
    "model": [
        "dbt run error: relation does not exist",
        "Query exceeded memory limit",
        "Unique constraint violation on output table",
        "Execution time exceeded SLA threshold",
        "Null constraint violation — unexpected nulls in required column",
    ],
    "seed": [
        "Seed file not found",
        "CSV parse error in seed data",
    ],
    "test": [
        "Data freshness test failed",
        "Uniqueness test failed — duplicate primary keys detected",
        "Not-null test failed",
    ],
}


def _random_error(node_type: str, rng: random.Random) -> str:
    messages = _ERROR_MESSAGES.get(node_type, _ERROR_MESSAGES["model"])
    return rng.choice(messages)


def simulate_pipeline_runs(
    pipeline_def: PipelineDefinition,
    node_id_map: dict[str, uuid.UUID],
    pipeline_id: uuid.UUID,
    sim_start: datetime,
    num_days: int,
    rng: random.Random,
) -> tuple[list[dict], list[dict]]:
    """Simulate all runs for a pipeline over `num_days` starting at `sim_start`.

    Returns:
        (pipeline_run_dicts, node_run_dicts) — plain dicts for bulk insert.
    """
    topo_order = _topo_sort(pipeline_def.nodes, pipeline_def.edges)
    parents = _build_parent_map(pipeline_def.edges)
    node_def_map = {n.external_id: n for n in pipeline_def.nodes}

    pipeline_run_dicts: list[dict] = []
    node_run_dicts: list[dict] = []

    for day_idx in range(num_days):
        for run_hour in pipeline_def.run_hours:
            pipeline_run_id = uuid.uuid4()
            run_start = sim_start + timedelta(days=day_idx, hours=run_hour)

            in_bad_period = (
                pipeline_def.bad_period is not None
                and pipeline_def.bad_period[0] <= day_idx <= pipeline_def.bad_period[1]
            )

            node_statuses: dict[str, str] = {}
            node_end_times: dict[str, datetime] = {}
            pipeline_status = "success"

            for ext_id in topo_order:
                node_def = node_def_map[ext_id]
                node_db_id = node_id_map[ext_id]
                node_parents = parents.get(ext_id, [])

                # Node start: after the latest parent completes
                if node_parents:
                    node_start = max(
                        node_end_times.get(p, run_start) for p in node_parents
                    ) + timedelta(seconds=2)
                else:
                    node_start = run_start

                # Cascade: skip if any parent failed or was skipped
                any_parent_failed = any(
                    node_statuses.get(p) in ("failed", "skipped") for p in node_parents
                )

                if any_parent_failed:
                    status = "skipped"
                    duration_ms = None
                    rows = None
                    error = "Skipped due to upstream failure"
                    node_end = node_start
                else:
                    failure_rate = node_def.failure_rate
                    if node_def.is_flaky:
                        failure_rate *= 3.0

                    if in_bad_period:
                        multiplier = pipeline_def.bad_period_node_multipliers.get(
                            ext_id, pipeline_def.bad_period_default_multiplier
                        )
                        failure_rate *= multiplier

                    failure_rate = min(failure_rate, 0.95)

                    if rng.random() < failure_rate:
                        status = "failed"
                        pipeline_status = "failed"
                        duration_ms = max(1, int(node_def.base_duration_ms * rng.uniform(0.2, 0.6)))
                        rows = None
                        error = _random_error(node_def.node_type, rng)
                        node_end = node_start + timedelta(milliseconds=duration_ms)
                    else:
                        status = "success"
                        duration_ms = max(1, int(node_def.base_duration_ms * rng.gauss(1.0, 0.15)))
                        rows = max(0, int(node_def.base_row_count * rng.gauss(1.0, 0.08)))
                        error = None
                        node_end = node_start + timedelta(milliseconds=duration_ms)

                node_statuses[ext_id] = status
                node_end_times[ext_id] = node_end

                node_run_dicts.append(
                    {
                        "id": uuid.uuid4(),
                        "pipeline_run_id": pipeline_run_id,
                        "node_id": node_db_id,
                        "started_at": node_start,
                        "completed_at": node_end,
                        "status": status,
                        "duration_ms": duration_ms,
                        "rows_processed": rows,
                        "error_message": error,
                    }
                )

            pipeline_end = max(node_end_times.values(), default=run_start)

            pipeline_run_dicts.append(
                {
                    "id": pipeline_run_id,
                    "pipeline_id": pipeline_id,
                    "started_at": run_start,
                    "completed_at": pipeline_end,
                    "status": pipeline_status,
                    "triggered_by": "synthetic",
                    "metadata": None,
                }
            )

    return pipeline_run_dicts, node_run_dicts
