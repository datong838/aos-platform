"""TWA.8 — storage / vector / wiki tenant prefix gates."""
from __future__ import annotations

import base64
import os

import pytest
from fastapi.testclient import TestClient

from aos_api.errors import ApiError
from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.metrics import reset_metrics
from aos_api.object_store import object_key_for
from aos_api.oidc import issue_dev_token
from aos_api.tenant_prefix import (
    assert_object_key_tenant,
    migrate_prefix_dry_run,
    scoped_collection_name,
    tenant_key_prefix,
    wiki_space_id,
)
from aos_api import mock_data


@pytest.fixture()
def api_client(monkeypatch):
    """No-PG client for media/vector prefix gates."""
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    monkeypatch.setenv("AOS_S3_DISABLED", "1")
    monkeypatch.setenv("AOS_LITELLM_FALLBACK", "mock")
    for k in (
        "AGNES_API_KEY",
        "AGNES_BASE_URL",
        "AOS_LITELLM_URL",
    ):
        os.environ.pop(k, None)
    app = create_app()
    with TestClient(app) as c:
        yield c


def _headers(org: str, project: str, subject: str = "alice"):
    tok = issue_dev_token(subject=subject, org_id=org, project_id=project)
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": org,
        "X-Project-Id": project,
        "Content-Type": "application/json",
    }


def test_prefix_builders():
    assert tenant_key_prefix("dev-org", "dev-project") == "dev-org/dev-project/"
    assert wiki_space_id("dev-org", "dev-project") == "wiki:dev-org:dev-project"
    k = object_key_for(
        "ri.mediaset.x",
        "a.bin",
        org_id="org-a",
        project_id="prj-1",
    )
    assert k.startswith("org-a/prj-1/mediasets/")
    assert_object_key_tenant(k, "org-a", "prj-1")
    with pytest.raises(ApiError) as ei:
        assert_object_key_tenant(k, "org-a", "prj-2")
    assert ei.value.status_code == 403


def test_scoped_collection_rejects_foreign():
    c = scoped_collection_name("org-a", "prj-1", "orders")
    assert c == "org-a__prj-1__orders"
    assert scoped_collection_name("org-a", "prj-1", c) == c
    with pytest.raises(ApiError) as ei:
        scoped_collection_name("org-a", "prj-1", "org-b__prj-9__orders")
    assert ei.value.status_code == 403


def test_migrate_prefix_dry_run():
    report = migrate_prefix_dry_run(
        [
            "org-a/prj-1/mediasets/x",
            "mediasets/legacy",
            "org-b/prj-2/y",
        ],
        "org-a",
        "prj-1",
    )
    assert report["okCount"] == 1
    assert report["missingCount"] == 2
    assert "mediasets/legacy" in report["missingSample"]


def test_media_isolated_by_workspace(api_client):
    h1 = _headers("org-a", "prj-1")
    h2 = _headers("org-a", "prj-2")
    r = api_client.post(
        "/v1/media-sets",
        headers=h1,
        json={
            "name": "a.bin",
            "bytesBase64": base64.b64encode(b"hello").decode(),
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["orgId"] == "org-a"
    assert body["projectId"] == "prj-1"
    if body.get("objectKey"):
        assert body["objectKey"].startswith("org-a/prj-1/")

    listed2 = api_client.get("/v1/media-sets", headers=h2)
    assert listed2.status_code == 200
    assert all(i.get("rid") != body["rid"] for i in listed2.json().get("items", []))

    cross = api_client.get(f"/v1/media-sets/{body['rid']}", headers=h2)
    assert cross.status_code == 404


def test_vector_collection_foreign_rejected(api_client):
    h = _headers("org-a", "prj-1")
    r = api_client.post(
        "/v1/aip/vector-index/upsert",
        headers=h,
        json={
            "collection": "org-b__other__leak",
            "documents": [{"id": "1", "text": "hi"}],
            "replace": True,
        },
    )
    assert r.status_code == 403
