"""Field-level Marking ∪ FGA bearer — scheme 65."""

from aos_api.auth import Principal
from aos_api.db import connect, ensure_inherit_openfga_seed, init_schema
from aos_api.errors import ApiError
from aos_api.marking import ensure_field_writes, redact_props
import pytest


def _headers(client, *, subject: str, markings: list[str]):
    tok = client.post(
        "/v1/auth/token",
        json={
            "grantType": "dev",
            "subject": subject,
            "roles": ["developer"],
            "markings": markings,
        },
    )
    assert tok.status_code == 200
    return {
        "Authorization": f"Bearer {tok.json()['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_public_still_redacts_internal_cost(client, monkeypatch):
    monkeypatch.setenv("AOS_AUTHZ_MARKING_BEARER", "1")
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="public-user", markings=["public"])
    r = client.get("/v1/objects/WorkOrder/wo-1001", headers=h)
    assert r.status_code == 200
    assert "internalCost" not in r.json()
    assert "internalCost" in (r.json().get("_redactedFields") or [])


def test_field_bearer_sees_internal_cost(client, monkeypatch):
    monkeypatch.setenv("AOS_AUTHZ_MARKING_BEARER", "1")
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="field-bearer", markings=["public"])
    r = client.get("/v1/objects/WorkOrder/wo-1001", headers=h)
    assert r.status_code == 200
    assert r.json().get("internalCost") == 1280
    assert "internalCost" not in (r.json().get("_redactedFields") or [])


def test_field_bearer_disabled_redacts(client, monkeypatch):
    monkeypatch.setenv("AOS_AUTHZ_MARKING_BEARER", "0")
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="field-bearer", markings=["public"])
    r = client.get("/v1/objects/WorkOrder/wo-1001", headers=h)
    assert r.status_code == 200
    assert "internalCost" not in r.json()


def test_redact_props_with_bearer_conn(monkeypatch):
    monkeypatch.setenv("AOS_AUTHZ_MARKING_BEARER", "1")
    init_schema()
    ensure_inherit_openfga_seed()
    p = Principal(
        subject="field-bearer",
        org_id="o",
        project_id="p",
        roles=["developer"],
        markings=["public"],
    )
    defs = [
        {"name": "title", "type": "string"},
        {"name": "internalCost", "type": "number", "requiredMarkings": ["secret"]},
    ]
    with connect() as conn:
        visible, redacted = redact_props(
            p,
            {"title": "t", "internalCost": 99},
            defs,
            conn=conn,
        )
    assert visible["internalCost"] == 99
    assert redacted == []


def test_ensure_field_writes_via_bearer(monkeypatch):
    monkeypatch.setenv("AOS_AUTHZ_MARKING_BEARER", "1")
    init_schema()
    ensure_inherit_openfga_seed()
    p = Principal(
        subject="field-bearer",
        org_id="o",
        project_id="p",
        roles=["developer"],
        markings=["public"],
    )
    defs = [{"name": "internalCost", "requiredMarkings": ["secret"]}]
    with connect() as conn:
        ensure_field_writes(p, {"internalCost": 1}, defs, conn=conn)


def test_ensure_field_writes_still_forbidden_without_bearer(monkeypatch):
    monkeypatch.setenv("AOS_AUTHZ_MARKING_BEARER", "1")
    p = Principal(
        subject="nobody",
        org_id="o",
        project_id="p",
        roles=["developer"],
        markings=["public"],
    )
    defs = [{"name": "internalCost", "requiredMarkings": ["secret"]}]
    with connect() as conn:
        with pytest.raises(ApiError) as ei:
            ensure_field_writes(p, {"internalCost": 1}, defs, conn=conn)
    assert ei.value.code == "FORBIDDEN"
