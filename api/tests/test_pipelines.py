"""Tests for pipeline endpoints:
  GET /pipelines
  GET /pipelines/{id}/graph
  GET /pipelines/{id}/runs
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


# ── GET /pipelines ─────────────────────────────────────────────────────────────

def test_list_pipelines_status(client: TestClient, seed_data: dict) -> None:  # noqa: ARG001
    assert client.get("/pipelines").status_code == 200


def test_list_pipelines_returns_three(client: TestClient, pipelines: list[dict]) -> None:  # noqa: ARG001
    resp = client.get("/pipelines")
    assert len(resp.json()["pipelines"]) == 3


def test_list_pipelines_slugs(client: TestClient) -> None:
    resp = client.get("/pipelines")
    slugs = {p["slug"] for p in resp.json()["pipelines"]}
    assert slugs == {"jaffle-shop-analytics", "payments-pipeline", "ml-feature-store"}


def test_pipeline_summary_fields(jaffle: dict) -> None:
    for field in ("id", "name", "slug", "description", "source_type",
                  "node_count", "healthy_count", "failed_count",
                  "drifting_count", "stale_count", "running_count", "created_at"):
        assert field in jaffle, f"Missing field: {field}"


def test_pipeline_node_counts(jaffle: dict, payments: dict, ml: dict) -> None:
    assert jaffle["node_count"] == 12
    assert payments["node_count"] == 28
    assert ml["node_count"] == 45


def test_pipeline_state_counts_sum_to_node_count(jaffle: dict) -> None:
    total = (jaffle["healthy_count"] + jaffle["failed_count"] +
             jaffle["drifting_count"] + jaffle["stale_count"] +
             jaffle["running_count"])
    assert total == jaffle["node_count"]


def test_pipeline_source_type_synthetic(pipelines: list[dict]) -> None:
    for p in pipelines:
        assert p["source_type"] == "synthetic"


# ── GET /pipelines/{id}/graph ──────────────────────────────────────────────────

def test_graph_status(client: TestClient, jaffle: dict) -> None:
    assert client.get(f"/pipelines/{jaffle['id']}/graph").status_code == 200


def test_graph_404_unknown_pipeline(client: TestClient, nonexistent_id: str) -> None:
    assert client.get(f"/pipelines/{nonexistent_id}/graph").status_code == 404


def test_graph_response_fields(jaffle_graph: dict, jaffle: dict) -> None:
    assert jaffle_graph["pipeline_id"] == jaffle["id"]
    assert jaffle_graph["pipeline_name"] == "Jaffle Shop Analytics"
    assert "nodes" in jaffle_graph
    assert "edges" in jaffle_graph


def test_graph_node_count(jaffle_graph: dict) -> None:
    assert len(jaffle_graph["nodes"]) == 12


def test_graph_has_edges(jaffle_graph: dict) -> None:
    assert len(jaffle_graph["edges"]) > 0


def test_graph_node_fields(jaffle_node: dict) -> None:
    for field in ("id", "external_id", "name", "node_type", "state",
                  "last_run_at", "last_run_status", "anomaly_count"):
        assert field in jaffle_node, f"Missing node field: {field}"


def test_graph_node_states_are_valid(jaffle_graph: dict) -> None:
    valid = {"healthy", "failed", "running", "drifting", "stale"}
    for node in jaffle_graph["nodes"]:
        assert node["state"] in valid, f"Invalid state: {node['state']}"


def test_graph_edge_fields(jaffle_graph: dict) -> None:
    edge = jaffle_graph["edges"][0]
    assert "id" in edge
    assert "source_node_id" in edge
    assert "target_node_id" in edge


def test_graph_all_three_pipelines(client: TestClient, jaffle: dict, payments: dict, ml: dict) -> None:
    for pipeline, expected_nodes in [(jaffle, 12), (payments, 28), (ml, 45)]:
        resp = client.get(f"/pipelines/{pipeline['id']}/graph")
        assert resp.status_code == 200
        assert len(resp.json()["nodes"]) == expected_nodes


# ── GET /pipelines/{id}/runs ───────────────────────────────────────────────────

def test_runs_status(client: TestClient, jaffle: dict) -> None:
    assert client.get(f"/pipelines/{jaffle['id']}/runs").status_code == 200


def test_runs_404_unknown_pipeline(client: TestClient, nonexistent_id: str) -> None:
    assert client.get(f"/pipelines/{nonexistent_id}/runs").status_code == 404


def test_runs_response_fields(client: TestClient, jaffle: dict) -> None:
    body = client.get(f"/pipelines/{jaffle['id']}/runs").json()
    assert "pipeline_id" in body
    assert "runs" in body
    assert "total" in body


def test_runs_total_is_90(client: TestClient, jaffle: dict) -> None:
    body = client.get(f"/pipelines/{jaffle['id']}/runs").json()
    assert body["total"] == 90


def test_runs_default_limit_50(client: TestClient, jaffle: dict) -> None:
    body = client.get(f"/pipelines/{jaffle['id']}/runs").json()
    assert len(body["runs"]) == 50


def test_runs_custom_limit(client: TestClient, jaffle: dict) -> None:
    body = client.get(f"/pipelines/{jaffle['id']}/runs?limit=10").json()
    assert len(body["runs"]) == 10


def test_runs_limit_max_200(client: TestClient, jaffle: dict) -> None:
    body = client.get(f"/pipelines/{jaffle['id']}/runs?limit=200").json()
    assert len(body["runs"]) <= 200


def test_runs_limit_above_max_rejected(client: TestClient, jaffle: dict) -> None:
    assert client.get(f"/pipelines/{jaffle['id']}/runs?limit=201").status_code == 422


def test_runs_limit_zero_rejected(client: TestClient, jaffle: dict) -> None:
    assert client.get(f"/pipelines/{jaffle['id']}/runs?limit=0").status_code == 422


def test_runs_negative_offset_rejected(client: TestClient, jaffle: dict) -> None:
    assert client.get(f"/pipelines/{jaffle['id']}/runs?offset=-1").status_code == 422


def test_runs_ordered_descending(client: TestClient, jaffle: dict) -> None:
    runs = client.get(f"/pipelines/{jaffle['id']}/runs?limit=5").json()["runs"]
    times = [r["started_at"] for r in runs]
    assert times == sorted(times, reverse=True)


def test_runs_pagination_offset(client: TestClient, jaffle: dict) -> None:
    all_runs = client.get(f"/pipelines/{jaffle['id']}/runs?limit=90").json()["runs"]
    page2 = client.get(f"/pipelines/{jaffle['id']}/runs?limit=10&offset=10").json()["runs"]
    assert page2 == all_runs[10:20]


def test_runs_pipeline_id_matches(client: TestClient, jaffle: dict) -> None:
    body = client.get(f"/pipelines/{jaffle['id']}/runs").json()
    assert body["pipeline_id"] == jaffle["id"]


def test_runs_each_has_required_fields(client: TestClient, jaffle: dict) -> None:
    runs = client.get(f"/pipelines/{jaffle['id']}/runs?limit=5").json()["runs"]
    for run in runs:
        for field in ("id", "pipeline_id", "started_at", "status", "triggered_by"):
            assert field in run, f"Missing run field: {field}"


def test_runs_payments_has_more_than_jaffle(client: TestClient, jaffle: dict, payments: dict) -> None:
    j_total = client.get(f"/pipelines/{jaffle['id']}/runs").json()["total"]
    p_total = client.get(f"/pipelines/{payments['id']}/runs").json()["total"]
    assert p_total > j_total


def test_runs_invalid_uuid_rejected(client: TestClient) -> None:
    assert client.get("/pipelines/not-a-uuid/runs").status_code == 422
