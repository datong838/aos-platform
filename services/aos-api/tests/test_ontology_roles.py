"""W1-17 · Ontology 角色体系单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.ontology_roles import (
    OntologyRoleStore,
    Permission,
    Role,
)

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}


def _new_store() -> OntologyRoleStore:
    return OntologyRoleStore()


# --- 引擎：assign/revoke --- #

def test_assign_and_get():
    s = _new_store()
    s.assign("WorkOrder", "user:alice", Role.OWNER, "admin")
    roles = s.get_roles("WorkOrder")
    assert len(roles) == 1
    assert roles[0].role == Role.OWNER


def test_assign_upsert():
    s = _new_store()
    s.assign("WorkOrder", "user:alice", Role.VIEWER)
    s.assign("WorkOrder", "user:alice", Role.OWNER)
    roles = s.get_roles("WorkOrder")
    assert len(roles) == 1
    assert roles[0].role == Role.OWNER


def test_revoke_existing():
    s = _new_store()
    s.assign("WorkOrder", "user:alice", Role.VIEWER)
    assert s.revoke("WorkOrder", "user:alice") is True
    assert s.get_roles("WorkOrder") == []


def test_revoke_idempotent():
    s = _new_store()
    assert s.revoke("WorkOrder", "user:ghost") is False


def test_assign_bad_role():
    s = _new_store()
    with pytest.raises(Exception):
        s.assign("WorkOrder", "user:alice", "bogus")


# --- 引擎：check_permission --- #

def test_check_owner_all_permissions():
    s = _new_store()
    s.assign("WorkOrder", "user:alice", Role.OWNER)
    for p in Permission:
        assert s.check_permission("WorkOrder", "user:alice", p) is True


def test_check_editor():
    s = _new_store()
    s.assign("WorkOrder", "user:bob", Role.EDITOR)
    assert s.check_permission("WorkOrder", "user:bob", Permission.WRITE_DATA) is True
    assert s.check_permission("WorkOrder", "user:bob", Permission.DELETE_DATA) is False
    assert s.check_permission("WorkOrder", "user:bob", Permission.ADMIN) is False


def test_check_viewer():
    s = _new_store()
    s.assign("WorkOrder", "user:carol", Role.VIEWER)
    assert s.check_permission("WorkOrder", "user:carol", Permission.READ_DATA) is True
    assert s.check_permission("WorkOrder", "user:carol", Permission.WRITE_META) is False
    assert s.check_permission("WorkOrder", "user:carol", Permission.WRITE_DATA) is False


def test_check_discoverer():
    s = _new_store()
    s.assign("WorkOrder", "user:dave", Role.DISCOVERER)
    assert s.check_permission("WorkOrder", "user:dave", Permission.READ_META) is True
    assert s.check_permission("WorkOrder", "user:dave", Permission.READ_DATA) is False
    assert s.check_permission("WorkOrder", "user:dave", Permission.WRITE_DATA) is False


def test_check_unauthorized():
    s = _new_store()
    assert s.check_permission("WorkOrder", "user:ghost", Permission.READ_META) is False


def test_check_wrong_object_type():
    s = _new_store()
    s.assign("WorkOrder", "user:alice", Role.OWNER)
    assert s.check_permission("Invoice", "user:alice", Permission.READ_META) is False


# --- 引擎：list --- #

def test_list_principals():
    s = _new_store()
    s.assign("WorkOrder", "user:alice", Role.OWNER)
    s.assign("WorkOrder", "group:devs", Role.EDITOR)
    principals = s.list_principals("WorkOrder")
    assert principals["user:alice"] == "owner"
    assert principals["group:devs"] == "editor"


def test_get_assignments_for_principal():
    s = _new_store()
    s.assign("WorkOrder", "user:alice", Role.OWNER)
    s.assign("Invoice", "user:alice", Role.VIEWER)
    assignments = s.get_assignments_for("user:alice")
    assert len(assignments) == 2
    types = {a.object_type for a in assignments}
    assert types == {"WorkOrder", "Invoice"}


def test_list_permissions():
    s = _new_store()
    perms = s.list_permissions()
    assert "read_meta" in perms
    assert "admin" in perms
    assert len(perms) == 6


# --- API --- #

@pytest.fixture()
def client(monkeypatch):
    fresh = OntologyRoleStore()
    monkeypatch.setattr("aos_api.routers.ontology_roles.get_store", lambda: fresh)
    return TestClient(create_app())


def test_api_assign(client):
    resp = client.post("/v1/ontology/roles/assign", json={
        "object_type": "WorkOrder", "principal": "user:alice",
        "role": "owner", "granted_by": "admin"}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["role"] == "owner"


def test_api_revoke(client):
    client.post("/v1/ontology/roles/assign", json={
        "object_type": "WorkOrder", "principal": "user:alice", "role": "owner"}, headers=_H)
    resp = client.delete(
        "/v1/ontology/roles/assign?object_type=WorkOrder&principal=user:alice", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["revoked"] is True


def test_api_list_roles(client):
    client.post("/v1/ontology/roles/assign", json={
        "object_type": "WorkOrder", "principal": "user:alice", "role": "owner"}, headers=_H)
    resp = client.get("/v1/ontology/roles/WorkOrder", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["assignments"]) == 1


def test_api_check_owner(client):
    client.post("/v1/ontology/roles/assign", json={
        "object_type": "WorkOrder", "principal": "user:alice", "role": "owner"}, headers=_H)
    resp = client.post("/v1/ontology/roles/check", json={
        "object_type": "WorkOrder", "principal": "user:alice",
        "permission": "admin"}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["allowed"] is True


def test_api_check_unauthorized(client):
    resp = client.post("/v1/ontology/roles/check", json={
        "object_type": "WorkOrder", "principal": "user:ghost",
        "permission": "read_meta"}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["allowed"] is False


def test_api_list_permissions(client):
    resp = client.get("/v1/ontology/roles/permissions/list", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["permissions"]) == 6


def test_api_principal_assignments(client):
    client.post("/v1/ontology/roles/assign", json={
        "object_type": "WorkOrder", "principal": "user:alice", "role": "owner"}, headers=_H)
    resp = client.get("/v1/ontology/roles/principals/user:alice", headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["assignments"]) == 1


def test_api_check_viewer_cannot_write(client):
    client.post("/v1/ontology/roles/assign", json={
        "object_type": "WorkOrder", "principal": "user:bob", "role": "viewer"}, headers=_H)
    resp = client.post("/v1/ontology/roles/check", json={
        "object_type": "WorkOrder", "principal": "user:bob",
        "permission": "write_data"}, headers=_H)
    assert resp.json()["allowed"] is False
