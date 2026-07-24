"""185w — Data OS metadata persist roundtrip (no demo seed on product surface)."""
from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

from aos_api import data_os_store as dos
from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.membership import reset_membership_store, seed_dev_defaults
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api.orgs import reset_org_store, seed_dev_orgs
from aos_api.routers import wave_ext
from aos_api import mock_data


@pytest.fixture()
def api_client():
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    reset_membership_store()
    seed_dev_defaults()
    reset_org_store()
    seed_dev_orgs()
    os.environ.pop("AOS_DEMO_DATA_SEED", None)
    for k in ("AGNES_API_KEY", "AGNES_BASE_URL", "AOS_LITELLM_URL"):
        os.environ.pop(k, None)
    os.environ["AOS_LITELLM_FALLBACK"] = "mock"
    wave_ext.clear_demo_data_surface()
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth():
    tok = issue_dev_token(subject="alice", org_id="dev-org", project_id="dev-project")
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_product_surface_has_no_demo_source(api_client):
    r = api_client.get("/v1/sources", headers=_auth())
    assert r.status_code == 200
    ids = {i["id"] for i in r.json()["items"]}
    assert "demo-file-wo" not in ids


def test_source_pipeline_persist_roundtrip(api_client):
    sid = f"src-persist-{int(time.time())}"
    pid = f"pipe-persist-{int(time.time())}"
    r = api_client.post(
        "/v1/sources",
        headers=_auth(),
        json={"id": sid, "type": "file"},
    )
    assert r.status_code == 200, r.text

    r2 = api_client.post(
        "/v1/pipelines",
        headers=_auth(),
        json={
            "id": pid,
            "sourceId": sid,
            "target": "dataset",
            "name": "persist-pipe",
            "displayName": "持久化探针",
        },
    )
    assert r2.status_code == 200, r2.text
    ds_rid = r2.json().get("datasetRid")
    assert ds_rid

    loaded = dos.load_all()
    assert sid in loaded["connectors"]
    assert pid in loaded["pipelines"]
    assert ds_rid in loaded["datasets"]

    # simulate boot reload
    wave_ext._connectors.clear()
    wave_ext._pipelines.clear()
    wave_ext._datasets.clear()
    dos.boot_data_os(wave_ext)
    assert sid in wave_ext._connectors
    assert pid in wave_ext._pipelines
    assert ds_rid in wave_ext._datasets
    assert "demo-file-wo" not in wave_ext._connectors

    # cleanup probe rows
    dos.delete_source(sid)
    dos.delete_pipeline(pid)
    dos.delete_dataset(ds_rid)


def _auth_org(org: str, project: str = "dev-project"):
    tok = issue_dev_token(subject="alice", org_id=org, project_id=project)
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": org,
        "X-Project-Id": project,
    }


def test_sources_list_filtered_by_org(api_client):
    """185w v1.2 · stamped source only visible to its org."""
    from aos_api.orgs import ensure_org
    from aos_api.membership import upsert_member
    from aos_api.workspaces_catalog import ensure_workspace

    ensure_org("org-filter-a", name="Filter A")
    ensure_org("org-filter-b", name="Filter B")
    ensure_workspace("org-filter-a", "dev-project")
    ensure_workspace("org-filter-b", "dev-project")
    upsert_member("org-filter-a", "dev-project", "alice", "owner", actor_id="alice")
    upsert_member("org-filter-b", "dev-project", "alice", "owner", actor_id="alice")

    sa = f"src-oa-{int(time.time())}"
    sb = f"src-ob-{int(time.time())}"
    assert (
        api_client.post(
            "/v1/sources",
            headers=_auth_org("org-filter-a"),
            json={"id": sa, "type": "file"},
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            "/v1/sources",
            headers=_auth_org("org-filter-b"),
            json={"id": sb, "type": "file"},
        ).status_code
        == 200
    )

    ids_a = {i["id"] for i in api_client.get("/v1/sources", headers=_auth_org("org-filter-a")).json()["items"]}
    ids_b = {i["id"] for i in api_client.get("/v1/sources", headers=_auth_org("org-filter-b")).json()["items"]}
    assert sa in ids_a and sb not in ids_a
    assert sb in ids_b and sa not in ids_b

    dos.delete_source(sa)
    dos.delete_source(sb)
    from aos_api.db import connect

    with connect() as conn:
        for oid in ("org-filter-a", "org-filter-b"):
            conn.execute("DELETE FROM meta_membership WHERE org_id=%s", (oid,))
            conn.execute("DELETE FROM meta_workspace WHERE org_id=%s", (oid,))
            conn.execute("DELETE FROM meta_org WHERE id=%s", (oid,))
        conn.commit()
