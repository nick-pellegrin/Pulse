"""Generates time-series metric rows from simulated node_run data.

Two metric types written per successful node_run:
  row_count   — base_row_count ± 8% Gaussian noise
  duration_ms — base_duration_ms ± 15% Gaussian noise

Anomaly injections override metric values for specific nodes on specific days.
The anomaly detector (Phase 5) will discover these deviations from baseline.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from pulse_api.services.synthetic.dag_builder import AnomalyInjection, NodeDefinition


def generate_metrics(
    node_run_dicts: list[dict],
    node_def_by_db_id: dict[uuid.UUID, NodeDefinition],
    anomaly_injections: list[AnomalyInjection],
    node_id_map: dict[str, uuid.UUID],  # external_id → db UUID
    sim_start: datetime,
    rng: random.Random,
) -> list[dict]:
    """Generate metric rows for all successful node_runs.

    Returns dicts ready for bulk insert into the metrics table.
    """
    # Build anomaly override lookup: (node_db_id, metric_name) → {day_idx: multiplier}
    anomaly_overrides: dict[tuple[uuid.UUID, str], dict[int, float]] = {}
    for inj in anomaly_injections:
        node_db_id = node_id_map.get(inj.node_external_id)
        if node_db_id is None:
            continue
        key = (node_db_id, inj.metric_name)
        if key not in anomaly_overrides:
            anomaly_overrides[key] = {}
        for day in range(inj.day_start, inj.day_end + 1):
            anomaly_overrides[key][day] = inj.value_multiplier

    sim_start_naive = sim_start.replace(tzinfo=None)
    metric_dicts: list[dict] = []

    for run in node_run_dicts:
        if run["status"] != "success":
            continue

        node_db_id: uuid.UUID | None = run["node_id"]
        if node_db_id is None:
            continue
        node_def = node_def_by_db_id.get(node_db_id)
        if node_def is None:
            continue

        run_time: datetime = run["started_at"]
        day_idx = (run_time.replace(tzinfo=None) - sim_start_naive).days

        for metric_name, base_value, noise_sigma in (
            ("row_count", float(node_def.base_row_count), 0.08),
            ("duration_ms", float(node_def.base_duration_ms), 0.15),
        ):
            multiplier = anomaly_overrides.get((node_db_id, metric_name), {}).get(day_idx, 1.0)
            noisy = base_value * rng.gauss(1.0, noise_sigma)
            value = max(0.0, noisy * multiplier)

            metric_dicts.append(
                {
                    "time": run_time,
                    "node_id": node_db_id,
                    "metric_name": metric_name,
                    "value": value,
                }
            )

    return metric_dicts


def generate_anomaly_records(
    anomaly_injections: list[AnomalyInjection],
    node_id_map: dict[str, uuid.UUID],
    node_def_by_ext_id: dict[str, NodeDefinition],
    sim_start: datetime,
) -> list[dict]:
    """Create anomaly records for each day of each injected anomaly.

    Returns dicts ready for bulk insert into the anomalies table.
    """
    anomaly_dicts: list[dict] = []
    start_utc = sim_start.replace(tzinfo=timezone.utc)

    for inj in anomaly_injections:
        node_db_id = node_id_map.get(inj.node_external_id)
        node_def = node_def_by_ext_id.get(inj.node_external_id)
        if node_db_id is None or node_def is None:
            continue

        base = (
            float(node_def.base_row_count)
            if inj.metric_name == "row_count"
            else float(node_def.base_duration_ms)
        )
        expected = base
        observed = base * inj.value_multiplier

        noise_sigma = 0.08 if inj.metric_name == "row_count" else 0.15
        std_estimate = max(base * noise_sigma, 1.0)
        z_score = (observed - expected) / std_estimate

        for day in range(inj.day_start, inj.day_end + 1):
            detected_at = start_utc + timedelta(days=day, hours=6)
            anomaly_dicts.append(
                {
                    "id": uuid.uuid4(),
                    "node_id": node_db_id,
                    "pipeline_run_id": None,
                    "detected_at": detected_at,
                    "metric_name": inj.metric_name,
                    "observed_value": observed,
                    "expected_value": expected,
                    "z_score": z_score,
                    "severity": inj.severity,
                    "description": inj.description,
                    "resolved_at": None,
                    "metadata": None,
                }
            )

    return anomaly_dicts
