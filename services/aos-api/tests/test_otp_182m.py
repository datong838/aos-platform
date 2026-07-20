"""182m — OTP send/verify + gate member add when required."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.membership import reset_membership_store, seed_dev_defaults
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api.org_invites import reset_org_invites_store
from aos_api.orgs import reset_org_store, seed_dev_orgs
from aos_api.otp import reset_otp_store
from aos_api.workspace_isolation import reset_items
from aos_api.workspaces_catalog import reset_workspace_catalog, seed_dev_workspaces
from aos_api import mock_data


@pytest.fixture()
def api_client(monkeypatch):
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    reset_otp_store()
    reset_membership_store()
    seed_dev_defaults()
    reset_org_store()
    seed_dev_orgs()
    reset_workspace_catalog()
    seed_dev_workspaces()
    reset_org_invites_store()
    reset_items()
    monkeypatch.setenv("AOS_TWA_STORE", "memory")
    monkeypatch.setenv("AOS_OTP_REQUIRED", "1")
    monkeypatch.setenv("AOS_OTP_DEV_CODE", "654321")
    monkeypatch.setenv("AOS_OTP_FORCE_DEV", "1")
    os.environ["AOS_LITELLM_FALLBACK"] = "mock"
    os.environ["AOS_AUTH_ALLOW_DEV"] = "1"
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


def test_otp_send_verify_and_add_member(api_client):
    h = _auth()
    send = api_client.post(
        "/v1/otp/send",
        headers=h,
        json={"channel": "email", "to": "new.user@acme.example", "purpose": "invite"},
    )
    assert send.status_code == 200, send.text
    otp_id = send.json()["otpId"]
    assert send.json().get("devCode") == "654321"
    bad = api_client.post(
        "/v1/otp/verify",
        headers=h,
        json={"otpId": otp_id, "code": "000000"},
    )
    assert bad.status_code == 400
    # re-send because bad verify shouldn't consume on wrong code - check our impl
    # wrong code raises before consume — good
    ver = api_client.post(
        "/v1/otp/verify",
        headers=h,
        json={"otpId": otp_id, "code": "654321"},
    )
    assert ver.status_code == 200, ver.text
    ticket = ver.json()["ticket"]
    denied = api_client.post(
        "/v1/workspaces/dev-project/members",
        headers=h,
        json={"email": "new.user@acme.example", "role": "viewer"},
    )
    assert denied.status_code == 400
    ok = api_client.post(
        "/v1/workspaces/dev-project/members",
        headers=h,
        json={
            "email": "new.user@acme.example",
            "role": "viewer",
            "otpTicket": ticket,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["email"] == "new.user@acme.example"


def test_otp_off_allows_email_add(monkeypatch):
    monkeypatch.setenv("AOS_OTP_REQUIRED", "0")
    reset_otp_store()
    reset_membership_store()
    seed_dev_defaults()
    reset_org_store()
    seed_dev_orgs()
    reset_workspace_catalog()
    seed_dev_workspaces()
    os.environ["AOS_AUTH_ALLOW_DEV"] = "1"
    app = create_app()
    with TestClient(app) as c:
        h = _auth()
        r = c.post(
            "/v1/workspaces/dev-project/members",
            headers=h,
            json={"email": "free@acme.example", "role": "viewer"},
        )
        assert r.status_code == 200, r.text
