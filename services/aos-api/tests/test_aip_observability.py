"""W2-A5 — AIP observability summary/traces endpoints."""
from __future__ import annotations

from aos_api.metrics import record, reset_metrics


def test_observability_summary_requires_auth(client):
    r = client.get("/v1/aip/observability/summary")
    assert r.status_code == 401


def test_observability_traces_requires_auth(client):
    r = client.get("/v1/aip/observability/traces")
    assert r.status_code == 401


def test_observability_summary_and_traces(client, auth_headers):
    reset_metrics()
    record(method="GET", path="/v1/health", status=200, duration_ms=12.5)
    record(method="GET", path="/v1/health", status=200, duration_ms=18.0)
    record(method="POST", path="/v1/objects/WorkOrder", status=500, duration_ms=90.0)

    summary = client.get("/v1/aip/observability/summary?range=1h", headers=auth_headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body["source"] == "sampled"
    assert body["range"] == "1h"
    assert isinstance(body["kpis"], list) and len(body["kpis"]) >= 4
    assert isinstance(body["trend"], list) and len(body["trend"]) == 12
    assert body["totals"]["count"] >= 3

    traces = client.get("/v1/aip/observability/traces?limit=10", headers=auth_headers)
    assert traces.status_code == 200
    tbody = traces.json()
    assert tbody["source"] == "sampled"
    assert isinstance(tbody["items"], list)
    assert len(tbody["items"]) >= 1
    row = tbody["items"][0]
    assert "traceId" in row and "rootSpan" in row and "service" in row
    assert row["status"] in ("ok", "error")
