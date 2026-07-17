"""OpenFGA production model — scheme 61."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aos_api import openfga as fga
from aos_api.db import connect, ensure_inherit_openfga_seed, init_schema
from aos_api.errors import ApiError


ROOT = Path(__file__).resolve().parents[3]
MODEL_JSON = ROOT / "deploy" / "dev" / "openfga" / "model.json"


def test_model_json_has_prod_types():
    raw = json.loads(MODEL_JSON.read_text(encoding="utf-8"))
    types = {t["type"] for t in raw["type_definitions"]}
    assert types == {"user", "organization", "project", "object", "marking"}
    obj = next(t for t in raw["type_definitions"] if t["type"] == "object")
    assert set(obj["relations"].keys()) == {"viewer", "editor", "owner"}


def test_key_helpers():
    assert fga.organization_key("dev-org") == "organization:dev-org"
    assert fga.project_key("dev-project") == "project:dev-project"
    assert fga.marking_key("restricted") == "marking:restricted"
    assert fga.object_key("WorkOrder", "wo-1") == "object:WorkOrder:wo-1"


def test_validate_relation_unknown():
    with pytest.raises(ApiError) as ei:
        fga.validate_relation("superadmin")
    assert ei.value.code == "AUTHZ_RELATION_UNKNOWN"
    assert ei.value.status_code == 400


def test_model_and_status_payload(client, auth_headers, monkeypatch):
    monkeypatch.delenv("AOS_OPENFGA_API_URL", raising=False)
    m = client.get("/v1/authz/model", headers=auth_headers)
    assert m.status_code == 200
    body = m.json()
    assert body["modelVersion"] == "aos-prod-v1"
    type_names = {t["type"] for t in body["types"]}
    assert "organization" in type_names
    assert "marking" in type_names

    st = client.get("/v1/authz/status", headers=auth_headers)
    assert st.status_code == 200
    assert st.json()["modelVersion"] == "aos-prod-v1"
    assert "object" in st.json()["types"]


def test_write_unknown_relation_400(client, auth_headers):
    r = client.post(
        "/v1/authz/tuples",
        headers=auth_headers,
        json={
            "user": "user:x",
            "relation": "godmode",
            "object": "object:WorkOrder:x",
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == "AUTHZ_RELATION_UNKNOWN"


def test_local_editor_implies_viewer(monkeypatch):
    monkeypatch.delenv("AOS_OPENFGA_API_URL", raising=False)
    init_schema()
    ensure_inherit_openfga_seed()
    obj = "object:WorkOrder:wo-editor-demo"
    with connect() as conn:
        fga.write_tuple(conn, "user:editor-only", "editor", obj)
        conn.commit()
        assert fga.check(conn, "user:editor-only", "viewer", obj) is True
        assert fga.check(conn, "user:other", "viewer", obj) is False


def test_local_org_member_tuple(monkeypatch):
    monkeypatch.delenv("AOS_OPENFGA_API_URL", raising=False)
    init_schema()
    with connect() as conn:
        fga.write_tuple(conn, "user:alice", "member", "organization:acme")
        conn.commit()
        assert fga.check(conn, "user:alice", "member", "organization:acme") is True
        assert fga.check(conn, "user:bob", "member", "organization:acme") is False
