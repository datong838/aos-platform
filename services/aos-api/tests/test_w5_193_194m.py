"""193m / 194m — invite QR + members CSV import."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aos_api import mock_data
from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.membership import reset_membership_store, seed_dev_defaults
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api.org_invites import reset_org_invites_store
from aos_api.orgs import reset_org_store, seed_dev_orgs
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
    reset_org_invites_store()
    for k in ("AGNES_API_KEY", "AGNES_BASE_URL", "AOS_LITELLM_URL"):
        os.environ.pop(k, None)
    os.environ["AOS_LITELLM_FALLBACK"] = "mock"
    os.environ["AOS_OTP_REQUIRED"] = "0"
    os.environ.pop("AOS_MEMBERS_IMPORT_MAX", None)
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


def test_193m_invite_qr_requires_origin(client):
    inv = client.post(
        "/v1/orgs/dev-org/invites",
        headers=_auth(),
        json={"role": "viewer", "projectId": "dev-project"},
    )
    assert inv.status_code == 200, inv.text
    token = inv.json()["token"]
    bad = client.get(f"/v1/org-invites/{token}/qr", headers=_auth())
    assert bad.status_code == 400


def test_193m_invite_qr_svg_ok(client):
    inv = client.post(
        "/v1/orgs/dev-org/invites",
        headers=_auth(),
        json={"role": "viewer", "projectId": "dev-project"},
    )
    assert inv.status_code == 200, inv.text
    token = inv.json()["token"]
    path = inv.json()["invitePath"]
    qr = client.get(
        f"/v1/org-invites/{token}/qr",
        headers=_auth(),
        params={"origin": "http://localhost:5173"},
    )
    assert qr.status_code == 200, qr.text
    body = qr.json()
    assert body["invitePath"] == path
    assert body["inviteUrl"] == f"http://localhost:5173{path}"
    assert "<svg" in body["svg"].lower()
    assert path in body["inviteUrl"]


def test_193m_invite_qr_unknown_token(client):
    r = client.get(
        "/v1/org-invites/no-such-token/qr",
        headers=_auth(),
        params={"origin": "http://localhost:5173"},
    )
    assert r.status_code == 404


def test_194m_members_import_csv_ok(client):
    csv_body = "email,phone,displayName,role\nimp1@acme.example,,Importer One,viewer\n,13800138000,Phone User,editor\n"
    r = client.post(
        "/v1/workspaces/dev-project/members/import",
        headers=_auth(),
        json={"csv": csv_body, "defaultRole": "viewer"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["imported"] == 2
    listed = client.get("/v1/workspaces/dev-project/members", headers=_auth())
    assert listed.status_code == 200
    labels = " ".join(
        str(m.get("email") or "") + " " + str(m.get("phone") or "")
        for m in listed.json()["items"]
    )
    assert "imp1@acme.example" in labels
    assert "13800138000" in labels or "138" in labels


def test_194m_members_import_bad_row_isolated(client):
    csv_body = "email,role\nok2@acme.example,viewer\n,badrole\n"
    r = client.post(
        "/v1/workspaces/dev-project/members/import",
        headers=_auth(),
        json={"csv": csv_body},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] >= 1
    assert body["errors"]


def test_194m_members_import_max_rows(client, monkeypatch):
    monkeypatch.setenv("AOS_MEMBERS_IMPORT_MAX", "2")
    lines = ["email,role"] + [f"u{i}@acme.example,viewer" for i in range(5)]
    r = client.post(
        "/v1/workspaces/dev-project/members/import",
        headers=_auth(),
        json={"csv": "\n".join(lines)},
    )
    assert r.status_code == 400
    assert "too many" in r.json()["message"].lower() or "too many" in r.text.lower()
