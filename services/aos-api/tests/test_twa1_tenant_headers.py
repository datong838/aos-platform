"""TWA.1 — R-ISO-01 tenant header harden (claim vs X-Org-Id / X-Project-Id)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.auth import bind_tenant_ids, resolve_principal
from aos_api.errors import ApiError
from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api import mock_data


@pytest.fixture()
def api_client():
    """Auth-only client — no PG (TWA.1 HTTP paths only hit /v1/me)."""
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_bind_mismatch_project_forbidden():
    with pytest.raises(ApiError) as ei:
        bind_tenant_ids(
            claim_org="org-a",
            claim_project="prj-1",
            header_org="org-a",
            header_project="prj-forged",
            allow_header_fallback=False,
        )
    assert ei.value.status_code == 403
    assert ei.value.code == "AUTH_TENANT_MISMATCH"


def test_bind_mismatch_org_forbidden():
    with pytest.raises(ApiError) as ei:
        bind_tenant_ids(
            claim_org="org-a",
            claim_project="prj-1",
            header_org="org-forged",
            header_project="prj-1",
            allow_header_fallback=True,
        )
    assert ei.value.status_code == 403
    assert ei.value.code == "AUTH_TENANT_MISMATCH"


def test_bind_claim_wins_when_headers_match():
    org, project = bind_tenant_ids(
        claim_org="org-a",
        claim_project="prj-1",
        header_org="org-a",
        header_project="prj-1",
        allow_header_fallback=False,
    )
    assert org == "org-a"
    assert project == "prj-1"


def test_bind_prod_requires_claims_ignores_header_only():
    with pytest.raises(ApiError) as ei:
        bind_tenant_ids(
            claim_org=None,
            claim_project=None,
            header_org="spoof-org",
            header_project="spoof-prj",
            allow_header_fallback=False,
        )
    assert ei.value.status_code == 401
    assert ei.value.code == "AUTH_TENANT_CLAIM_REQUIRED"


def test_bind_dev_header_fallback():
    org, project = bind_tenant_ids(
        claim_org=None,
        claim_project=None,
        header_org="h-org",
        header_project="h-prj",
        allow_header_fallback=True,
    )
    assert org == "h-org"
    assert project == "h-prj"


def test_jwt_forged_project_header_rejected(api_client):
    tok = issue_dev_token(subject="alice", org_id="org-a", project_id="prj-1")
    r = api_client.get(
        "/v1/me",
        headers={
            "Authorization": f"Bearer {tok['accessToken']}",
            "X-Org-Id": "org-a",
            "X-Project-Id": "prj-forged",
        },
    )
    assert r.status_code == 403
    body = r.json()
    assert body["code"] == "AUTH_TENANT_MISMATCH"
    assert "traceId" in body


def test_jwt_matching_headers_ok(api_client):
    tok = issue_dev_token(subject="alice", org_id="org-a", project_id="prj-1")
    r = api_client.get(
        "/v1/me",
        headers={
            "Authorization": f"Bearer {tok['accessToken']}",
            "X-Org-Id": "org-a",
            "X-Project-Id": "prj-1",
        },
    )
    assert r.status_code == 200
    me = r.json()
    assert me["orgId"] == "org-a"
    assert me["projectId"] == "prj-1"


def test_jwt_no_headers_uses_claims(api_client):
    tok = issue_dev_token(subject="bob", org_id="org-b", project_id="prj-b")
    r = api_client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {tok['accessToken']}"},
    )
    assert r.status_code == 200
    assert r.json()["projectId"] == "prj-b"


def test_prod_rejects_dev_and_header_spoof_path(api_client, monkeypatch):
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "0")
    r = api_client.get(
        "/v1/me",
        headers={
            "Authorization": "Bearer dev",
            "X-Project-Id": "anything",
        },
    )
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_DEV_DISABLED"


def test_resolve_principal_unit_mismatch():
    tok = issue_dev_token(subject="u", org_id="o1", project_id="p1")["accessToken"]
    with pytest.raises(ApiError) as ei:
        resolve_principal(
            token=tok,
            header_org="o1",
            header_project="p-evil",
        )
    assert ei.value.code == "AUTH_TENANT_MISMATCH"
