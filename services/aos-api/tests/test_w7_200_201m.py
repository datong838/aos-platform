"""200m / 201m — account linking + REST connector optional HTTP."""
from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from aos_api import mock_data
from aos_api.account_link import reset_account_links
from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.membership import reset_membership_store, seed_dev_defaults
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api.orgs import reset_org_store, seed_dev_orgs
from aos_api.person_identity import reset_person_store, seed_dev_persons, resolve_member_identity
from aos_api.workspaces_catalog import reset_workspace_catalog, seed_dev_workspaces


@pytest.fixture()
def client():
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    reset_membership_store()
    seed_dev_defaults()
    reset_org_store()
    seed_dev_orgs()
    reset_workspace_catalog()
    seed_dev_workspaces()
    reset_person_store()
    seed_dev_persons()
    reset_account_links()
    for k in ("AGNES_API_KEY", "AGNES_BASE_URL", "AOS_LITELLM_URL"):
        os.environ.pop(k, None)
    os.environ["AOS_LITELLM_FALLBACK"] = "mock"
    os.environ["AOS_OTP_REQUIRED"] = "0"
    os.environ.pop("AOS_REST_CONNECTOR_URL", None)
    os.environ.pop("AOS_REST_CONNECTOR_TOKEN", None)
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth(subject: str = "alice") -> dict[str, str]:
    tok = issue_dev_token(subject=subject, org_id="dev-org", project_id="dev-project")
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_200m_account_link_and_resolve(client):
    r = client.post(
        "/v1/me/account-links",
        headers=_auth("alice"),
        json={"email": "link-alice@acme.example"},
    )
    assert r.status_code == 200, r.text
    link = r.json()["link"]
    assert link["subject"] == "alice"
    assert link["email"] == "link-alice@acme.example"
    listed = client.get("/v1/me/account-links", headers=_auth("alice"))
    assert listed.status_code == 200
    assert any(i["id"] == link["id"] for i in listed.json()["items"])
    ident = resolve_member_identity(email="link-alice@acme.example")
    assert ident["subject"] == "alice"
    assert ident["kind"] == "linked"


def test_201m_rest_connector_without_url_501(client):
    client.post("/v1/connector-plugins/rest-generic/install", headers=_auth())
    r = client.get("/v1/connectors/rest-generic/health", headers=_auth())
    assert r.status_code == 501
    assert r.json()["code"] == "CONNECTOR_STUB"


def test_201m_rest_connector_with_url_ok(client, monkeypatch):
    from urllib import request as urlrequest

    monkeypatch.setenv("AOS_REST_CONNECTOR_URL", "http://rest.test/data")

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"items": [{"id": 1}]}).encode("utf-8")

    monkeypatch.setattr(urlrequest, "urlopen", lambda *a, **k: _Resp())
    client.post("/v1/connector-plugins/rest-generic/install", headers=_auth())
    h = client.get("/v1/connectors/rest-generic/health", headers=_auth())
    assert h.status_code == 200, h.text
    assert h.json()["mode"] == "http"
    assert h.json()["configured"] is True
    p = client.post(
        "/v1/connectors/rest-generic/probe",
        headers=_auth(),
        json={"limit": 1},
    )
    assert p.status_code == 200, p.text
    assert p.json()["ok"] is True
    assert p.json()["sample"]["items"][0]["id"] == 1
