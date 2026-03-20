"""Tests for POST /dev/seed."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_seed_returns_200(client: TestClient, seed_data: dict) -> None:  # noqa: ARG001
    # seed_data fixture already called it; call again to verify idempotency
    resp = client.post("/dev/seed")
    assert resp.status_code == 200


def test_seed_response_shape(client: TestClient) -> None:
    resp = client.post("/dev/seed")
    body = resp.json()
    assert "pipelines_created" in body
    assert "node_runs_created" in body
    assert "metrics_created" in body
    assert "anomalies_created" in body
    assert "duration_seconds" in body
    assert "message" in body
    assert "pipeline_names" in body


def test_seed_creates_three_pipelines(client: TestClient) -> None:
    resp = client.post("/dev/seed")
    assert resp.json()["pipelines_created"] == 3


def test_seed_pipeline_names(client: TestClient) -> None:
    resp = client.post("/dev/seed")
    names = set(resp.json()["pipeline_names"])
    assert names == {"Jaffle Shop Analytics", "Payments Pipeline", "ML Feature Store"}


def test_seed_creates_runs(client: TestClient) -> None:
    resp = client.post("/dev/seed")
    assert resp.json()["node_runs_created"] > 0


def test_seed_creates_metrics(client: TestClient) -> None:
    resp = client.post("/dev/seed")
    assert resp.json()["metrics_created"] > 0


def test_seed_creates_anomalies(client: TestClient) -> None:
    resp = client.post("/dev/seed")
    assert resp.json()["anomalies_created"] > 0


def test_seed_duration_is_positive(client: TestClient) -> None:
    resp = client.post("/dev/seed")
    assert resp.json()["duration_seconds"] > 0


def test_seed_blocked_in_production(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    import pulse_api.routers.dev as dev_module
    monkeypatch.setattr(dev_module.settings, "env", "production")
    resp = client.post("/dev/seed")
    assert resp.status_code == 404
