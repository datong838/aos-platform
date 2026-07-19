"""184m — Insight TTL soft-archive."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from aos_api import ttl_job
from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api import mock_data


@pytest.fixture()
def api(monkeypatch):
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    ttl_job.reset_insight_store()
    monkeypatch.setenv("AOS_INSIGHT_TTL_DAYS", "30")
    monkeypatch.setenv("AOS_TWA_STORE", "memory")
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "1")
    monkeypatch.setenv("AOS_LITELLM_FALLBACK", "mock")
    app = create_app()
    with TestClient(app) as c:
        yield c


def _h() -> dict[str, str]:
    tok = issue_dev_token(subject="alice", org_id="dev-org", project_id="dev-project")
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_ttl_archives_old_insight(api):
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    r = api.post(
        "/v1/aip/insights/backfill",
        headers=_h(),
        json={"objectId": "wo-old", "createdAt": old, "text": "stale"},
    )
    assert r.status_code == 200, r.text
    iid = r.json()["id"]
    st = api.get("/v1/ops/ttl/status", headers=_h())
    assert st.status_code == 200
    assert st.json()["archiveCandidates"] >= 1
    run = api.post("/v1/ops/ttl/run", headers=_h(), json={"dryRun": False})
    assert run.status_code == 200, run.text
    assert run.json()["archivedCount"] >= 1
    assert iid in run.json()["archivedIds"]
    listed = api.get("/v1/aip/insights", headers=_h(), params={"status": "archived"})
    assert listed.status_code == 200
    assert any(i["id"] == iid for i in listed.json()["items"])


def test_ttl_fresh_insight_not_archived(api):
    r = api.post(
        "/v1/aip/insights/backfill",
        headers=_h(),
        json={"objectId": "wo-new", "text": "fresh"},
    )
    assert r.status_code == 200
    iid = r.json()["id"]
    run = api.post("/v1/ops/ttl/run", headers=_h(), json={})
    assert run.status_code == 200
    assert iid not in run.json()["archivedIds"]


def test_graph_health_archive_candidates(api):
    old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    api.post(
        "/v1/aip/insights/backfill",
        headers=_h(),
        json={"createdAt": old, "text": "cand"},
    )
    gh = api.get("/v1/ontology/graph-health", headers=_h())
    assert gh.status_code == 200, gh.text
    assert gh.json()["metrics"]["archiveCandidates"] >= 1
    assert "archivePreview" in gh.json()
