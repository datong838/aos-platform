"""202m / 203m / 204m — W8 file connectors · member quota · install drill."""
from __future__ import annotations

import os
from pathlib import Path

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
from aos_api.person_identity import reset_person_store, seed_dev_persons
from aos_api.provisioning import reset_provisioning_store
from aos_api.workspaces_catalog import reset_workspace_catalog, seed_dev_workspaces

ROOT = Path(__file__).resolve().parents[3]
CI = ROOT / "scripts" / "ci"


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
    reset_provisioning_store()
    reset_person_store()
    seed_dev_persons()
    os.environ["AOS_TWA_STORE"] = "memory"
    os.environ["AOS_AUTH_ALLOW_DEV"] = "1"
    os.environ["AOS_OTP_REQUIRED"] = "0"
    os.environ.pop("AOS_FILE_LOCAL_ROOT", None)
    os.environ.pop("AOS_MAX_MEMBERS_PER_ORG", None)
    os.environ["AOS_S3_DISABLED"] = "1"
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth(org="dev-org", subject="alice", roles=None):
    tok = issue_dev_token(
        subject=subject,
        org_id=org,
        project_id="dev-project",
        roles=roles or ["owner", "platform_admin"],
    )
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": org,
        "X-Project-Id": "dev-project",
    }


def test_202m_file_local_without_root_501(client):
    client.post("/v1/connector-plugins/file-local/install", headers=_auth())
    r = client.get("/v1/connectors/file-local/health", headers=_auth())
    assert r.status_code == 501
    assert r.json()["code"] == "CONNECTOR_STUB"


def test_202m_file_local_with_root_ok(client, tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    monkeypatch.setenv("AOS_FILE_LOCAL_ROOT", str(tmp_path))
    client.post("/v1/connector-plugins/file-local/install", headers=_auth())
    h = client.get("/v1/connectors/file-local/health", headers=_auth())
    assert h.status_code == 200, h.text
    assert h.json()["mode"] == "local"
    p = client.post(
        "/v1/connectors/file-local/probe",
        headers=_auth(),
        json={"limit": 5},
    )
    assert p.status_code == 200
    assert "a.txt" in p.json()["sample"]


def test_202m_file_object_store_disabled_501(client):
    client.post("/v1/connector-plugins/file-object-store/install", headers=_auth())
    r = client.get("/v1/connectors/file-object-store/health", headers=_auth())
    assert r.status_code == 501
    assert r.json()["code"] == "CONNECTOR_STUB"


def test_203m_member_quota_exceeded(client):
    ops = _auth("dev-org", "ops-admin", ["platform_admin"])
    prov = client.post(
        "/v1/ops/tenants",
        headers=ops,
        json={
            "orgId": "quota-org",
            "orgName": "Quota Org",
            "ownerSubject": "quota-owner",
            "quota": {"maxMembers": 1, "maxWorkspaces": 5},
        },
    )
    assert prov.status_code == 200, prov.text
    h = _auth("quota-org", "quota-owner", ["owner", "admin"])
    # ensure workspace exists in catalog for this org
    ws = client.post(
        "/v1/workspaces",
        headers=h,
        json={"name": "默认工作区", "id": "dev-project"},
    )
    assert ws.status_code in (200, 409), ws.text
    listed = client.get("/v1/workspaces/dev-project/members", headers=h)
    assert listed.status_code == 200, listed.text
    n = len(listed.json()["items"])
    patch = client.patch(
        "/v1/ops/tenants/quota-org/quota",
        headers=ops,
        json={"maxMembers": max(1, n)},
    )
    assert patch.status_code == 200, patch.text
    add = client.post(
        "/v1/workspaces/dev-project/members",
        headers=h,
        json={"email": "extra@acme.example", "role": "viewer"},
    )
    assert add.status_code == 409, add.text
    assert add.json()["code"] == "QUOTA_EXCEEDED"


def test_204m_drill_install_package():
    import subprocess

    script = CI / "drill-install-package.sh"
    assert script.is_file()
    help_out = subprocess.run(
        ["bash", str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_out.returncode == 0
    assert "204m" in help_out.stdout or "NOT" in help_out.stdout
    drill = subprocess.run(
        ["bash", str(script), "--require-report"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert drill.returncode == 0, drill.stdout + drill.stderr
    reports = list((ROOT / "deploy" / "dev" / "_install_drill").glob("drill-*.md"))
    assert reports
    text = reports[0].read_text(encoding="utf-8")
    assert "204m" in text
    assert "正式安装包" in text or "formal" in text.lower()
