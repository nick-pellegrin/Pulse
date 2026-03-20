"""Tests for anomaly endpoints:
  GET /anomalies
  GET /pipelines/{id}/anomalies
"""
from __future__ import annotations

from fastapi.testclient import TestClient


# ── GET /anomalies ─────────────────────────────────────────────────────────────

def test_list_anomalies_status(client: TestClient, seed_data: dict) -> None:  # noqa: ARG001
    assert client.get("/anomalies").status_code == 200


def test_list_anomalies_response_fields(client: TestClient) -> None:
    body = client.get("/anomalies").json()
    assert "anomalies" in body
    assert "total" in body


def test_list_anomalies_total_positive(client: TestClient) -> None:
    body = client.get("/anomalies").json()
    assert body["total"] > 0


def test_list_anomalies_default_limit_50(client: TestClient) -> None:
    body = client.get("/anomalies").json()
    assert len(body["anomalies"]) <= 50


def test_anomaly_fields(client: TestClient) -> None:
    anomalies = client.get("/anomalies?limit=1").json()["anomalies"]
    assert len(anomalies) == 1
    a = anomalies[0]
    for field in ("id", "node_id", "pipeline_run_id", "detected_at",
                  "metric_name", "observed_value", "expected_value",
                  "z_score", "severity", "description", "resolved_at"):
        assert field in a, f"Missing anomaly field: {field}"


def test_anomaly_severity_is_valid(client: TestClient) -> None:
    anomalies = client.get("/anomalies?limit=50").json()["anomalies"]
    valid = {"low", "medium", "high", "critical"}
    for a in anomalies:
        assert a["severity"] in valid, f"Invalid severity: {a['severity']}"


def test_filter_unresolved(client: TestClient) -> None:
    body = client.get("/anomalies?resolved=false").json()
    assert body["total"] > 0
    for a in body["anomalies"]:
        assert a["resolved_at"] is None


def test_filter_resolved(client: TestClient) -> None:
    # Seeded data may or may not have resolved anomalies; just check the filter works
    body = client.get("/anomalies?resolved=true").json()
    for a in body["anomalies"]:
        assert a["resolved_at"] is not None


def test_filter_severity_critical(client: TestClient) -> None:
    body = client.get("/anomalies?severity=critical").json()
    for a in body["anomalies"]:
        assert a["severity"] == "critical"


def test_filter_severity_high(client: TestClient) -> None:
    body = client.get("/anomalies?severity=high").json()
    for a in body["anomalies"]:
        assert a["severity"] == "high"


def test_filter_combined_unresolved_and_severity(client: TestClient) -> None:
    body = client.get("/anomalies?resolved=false&severity=critical").json()
    for a in body["anomalies"]:
        assert a["resolved_at"] is None
        assert a["severity"] == "critical"


def test_pagination_limit(client: TestClient) -> None:
    body = client.get("/anomalies?limit=2").json()
    assert len(body["anomalies"]) <= 2


def test_pagination_max_limit(client: TestClient) -> None:
    body = client.get("/anomalies?limit=200").json()
    assert len(body["anomalies"]) <= 200


def test_pagination_limit_above_max_rejected(client: TestClient) -> None:
    assert client.get("/anomalies?limit=201").status_code == 422


def test_pagination_negative_limit_rejected(client: TestClient) -> None:
    assert client.get("/anomalies?limit=0").status_code == 422


def test_pagination_negative_offset_rejected(client: TestClient) -> None:
    assert client.get("/anomalies?offset=-1").status_code == 422


def test_pagination_offset(client: TestClient) -> None:
    all_body = client.get("/anomalies?limit=50").json()
    page2 = client.get("/anomalies?limit=3&offset=3").json()
    if len(all_body["anomalies"]) >= 6:
        assert page2["anomalies"] == all_body["anomalies"][3:6]


def test_total_consistent_with_filter(client: TestClient) -> None:
    unresolved = client.get("/anomalies?resolved=false").json()["total"]
    resolved = client.get("/anomalies?resolved=true").json()["total"]
    total = client.get("/anomalies").json()["total"]
    assert unresolved + resolved == total


def test_anomalies_ordered_by_detected_at_desc(client: TestClient) -> None:
    anomalies = client.get("/anomalies?limit=50").json()["anomalies"]
    times = [a["detected_at"] for a in anomalies]
    assert times == sorted(times, reverse=True)


# ── GET /pipelines/{id}/anomalies ─────────────────────────────────────────────

def test_pipeline_anomalies_status(client: TestClient, jaffle: dict) -> None:
    assert client.get(f"/pipelines/{jaffle['id']}/anomalies").status_code == 200


def test_pipeline_anomalies_response_fields(client: TestClient, jaffle: dict) -> None:
    body = client.get(f"/pipelines/{jaffle['id']}/anomalies").json()
    assert "anomalies" in body
    assert "total" in body


def test_pipeline_anomalies_sum_equals_global(
    client: TestClient, jaffle: dict, payments: dict, ml: dict
) -> None:
    global_total = client.get("/anomalies").json()["total"]
    per_pipeline = sum(
        client.get(f"/pipelines/{p['id']}/anomalies").json()["total"]
        for p in (jaffle, payments, ml)
    )
    assert per_pipeline == global_total


def test_pipeline_anomalies_filter_severity(client: TestClient, jaffle: dict) -> None:
    body = client.get(f"/pipelines/{jaffle['id']}/anomalies?severity=critical").json()
    for a in body["anomalies"]:
        assert a["severity"] == "critical"


def test_pipeline_anomalies_filter_unresolved(client: TestClient, jaffle: dict) -> None:
    body = client.get(f"/pipelines/{jaffle['id']}/anomalies?resolved=false").json()
    for a in body["anomalies"]:
        assert a["resolved_at"] is None


def test_pipeline_anomalies_limit(client: TestClient, jaffle: dict) -> None:
    body = client.get(f"/pipelines/{jaffle['id']}/anomalies?limit=1").json()
    assert len(body["anomalies"]) <= 1


def test_pipeline_anomalies_invalid_uuid(client: TestClient, nonexistent_id: str) -> None:
    # Non-existent pipeline returns 0 anomalies (no pipeline guard on this endpoint)
    body = client.get(f"/pipelines/{nonexistent_id}/anomalies").json()
    assert body["total"] == 0


def test_pipeline_anomalies_limit_above_max_rejected(client: TestClient, jaffle: dict) -> None:
    assert client.get(f"/pipelines/{jaffle['id']}/anomalies?limit=201").status_code == 422
