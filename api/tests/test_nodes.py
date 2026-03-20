"""Tests for GET /nodes/{id}/metrics."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_metrics_status(client: TestClient, jaffle_node: dict) -> None:
    resp = client.get(f"/nodes/{jaffle_node['id']}/metrics?metric=row_count")
    assert resp.status_code == 200


def test_metrics_404_unknown_node(client: TestClient, nonexistent_id: str) -> None:
    resp = client.get(f"/nodes/{nonexistent_id}/metrics?metric=row_count")
    assert resp.status_code == 404


def test_metrics_invalid_uuid_rejected(client: TestClient) -> None:
    assert client.get("/nodes/not-a-uuid/metrics?metric=row_count").status_code == 422


def test_metrics_response_fields(client: TestClient, jaffle_node: dict) -> None:
    body = client.get(f"/nodes/{jaffle_node['id']}/metrics?metric=row_count").json()
    assert "node_id" in body
    assert "metric_name" in body
    assert "window" in body
    assert "points" in body


def test_metrics_node_id_matches(client: TestClient, jaffle_node: dict) -> None:
    body = client.get(f"/nodes/{jaffle_node['id']}/metrics?metric=row_count").json()
    assert body["node_id"] == jaffle_node["id"]


def test_metrics_metric_name_matches(client: TestClient, jaffle_node: dict) -> None:
    body = client.get(f"/nodes/{jaffle_node['id']}/metrics?metric=duration_ms").json()
    assert body["metric_name"] == "duration_ms"


def test_metrics_default_window_7d(client: TestClient, jaffle_node: dict) -> None:
    body = client.get(f"/nodes/{jaffle_node['id']}/metrics?metric=row_count").json()
    assert body["window"] == "7d"


def test_metrics_window_1d(client: TestClient, jaffle_node: dict) -> None:
    body = client.get(f"/nodes/{jaffle_node['id']}/metrics?metric=row_count&window=1d").json()
    assert body["window"] == "1d"
    # 1d window should have fewer points than 7d
    points_1d = len(body["points"])
    points_7d = len(client.get(
        f"/nodes/{jaffle_node['id']}/metrics?metric=row_count&window=7d"
    ).json()["points"])
    assert points_1d <= points_7d


def test_metrics_window_30d(client: TestClient, jaffle_node: dict) -> None:
    body = client.get(f"/nodes/{jaffle_node['id']}/metrics?metric=row_count&window=30d").json()
    assert body["window"] == "30d"
    assert len(body["points"]) > 0


def test_metrics_window_90d(client: TestClient, jaffle_node: dict) -> None:
    body = client.get(f"/nodes/{jaffle_node['id']}/metrics?metric=row_count&window=90d").json()
    assert body["window"] == "90d"
    assert len(body["points"]) > 0


def test_metrics_invalid_window_rejected(client: TestClient, jaffle_node: dict) -> None:
    resp = client.get(f"/nodes/{jaffle_node['id']}/metrics?metric=row_count&window=bad")
    assert resp.status_code == 422
    assert "Invalid window" in resp.json()["detail"]


def test_metrics_missing_metric_param_rejected(client: TestClient, jaffle_node: dict) -> None:
    resp = client.get(f"/nodes/{jaffle_node['id']}/metrics")
    assert resp.status_code == 422


def test_metrics_points_have_time_and_value(client: TestClient, jaffle_node: dict) -> None:
    points = client.get(
        f"/nodes/{jaffle_node['id']}/metrics?metric=row_count&window=7d"
    ).json()["points"]
    assert len(points) > 0
    for pt in points:
        assert "time" in pt
        assert "value" in pt


def test_metrics_points_ordered_ascending(client: TestClient, jaffle_node: dict) -> None:
    points = client.get(
        f"/nodes/{jaffle_node['id']}/metrics?metric=row_count&window=90d"
    ).json()["points"]
    times = [pt["time"] for pt in points]
    assert times == sorted(times)


def test_metrics_row_count_values_positive(client: TestClient, jaffle_node: dict) -> None:
    points = client.get(
        f"/nodes/{jaffle_node['id']}/metrics?metric=row_count&window=90d"
    ).json()["points"]
    for pt in points:
        assert pt["value"] >= 0


def test_metrics_duration_ms_available(client: TestClient, jaffle_node: dict) -> None:
    resp = client.get(f"/nodes/{jaffle_node['id']}/metrics?metric=duration_ms&window=90d")
    assert resp.status_code == 200
    assert len(resp.json()["points"]) > 0


def test_metrics_unknown_metric_returns_empty(client: TestClient, jaffle_node: dict) -> None:
    body = client.get(
        f"/nodes/{jaffle_node['id']}/metrics?metric=nonexistent_metric&window=90d"
    ).json()
    assert body["points"] == []
