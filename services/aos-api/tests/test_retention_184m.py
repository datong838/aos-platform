"""184m — Insight TTL archive + retention job."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from aos_api.db import connect, init_schema
from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api import mock_data
from aos_api import ttl_job
from aos_api.retention_jobs import FORGET_DENY, archive_one, ensure_lifecycle_schema


@pytest.fixture()
def api():
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    ttl_job.reset_insight_store()
    try:
        init_schema()
    except Exception as exc:
        pytest.skip(f"PG unavailable: {exc}")
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth() -> dict[str, str]:
    tok = issue_dev_token(subject="alice", org_id="dev-org", project_id="dev-project")
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_ttl_dry_run_and_archive(api, monkeypatch):
    monkeypatch.setenv("AOS_INSIGHT_TTL_DAYS", "30")
    h = _auth()
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    created = api.post(
        "/v1/aip/insights/backfill",
        headers=h,
        json={"objectType": "InsightNote", "objectId": "ins-obj-1", "createdAt": old},
    )
    assert created.status_code == 200, created.text
    dry = api.post("/v1/ops/ttl/run", headers=h, json={"dryRun": True})
    assert dry.status_code == 200
    assert dry.json()["dryRun"] is True
    assert dry.json()["candidateCount"] >= 1
    run = api.post("/v1/ops/ttl/run", headers=h, json={"dryRun": False})
    assert run.status_code == 200
    assert run.json()["archivedCount"] >= 1
    st = api.get("/v1/ops/ttl/status", headers=h)
    assert st.status_code == 200
    assert st.json()["archived"] >= 1
    gh = api.get("/v1/ontology/graph-health", headers=h)
    assert gh.status_code == 200
    assert "archiveCandidates" in gh.json()["metrics"]


def test_forget_denied_for_core_types():
    try:
        init_schema()
        ensure_lifecycle_schema()
    except Exception as exc:
        pytest.skip(f"PG unavailable: {exc}")
    with connect() as conn:
        with pytest.raises(ValueError):
            archive_one(
                conn,
                object_type="WorkOrder",
                object_id="wo-x",
                reason="test",
                ttl=90,
                status="forgotten",
            )
    assert "WorkOrder" in FORGET_DENY
