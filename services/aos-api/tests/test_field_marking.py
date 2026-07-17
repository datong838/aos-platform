"""TX.4 field-level Marking MVP — scheme 52."""

from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.marking import ensure_field_writes, redact_props
import pytest


def test_redact_props_unit():
    p = Principal(
        subject="u",
        org_id="o",
        project_id="p",
        roles=["developer"],
        markings=["public"],
    )
    props = {"title": "t", "internalCost": 99}
    defs = [
        {"name": "title", "type": "string"},
        {"name": "internalCost", "type": "number", "requiredMarkings": ["secret"]},
    ]
    visible, redacted = redact_props(p, props, defs)
    assert "internalCost" not in visible
    assert visible["title"] == "t"
    assert redacted == ["internalCost"]


def test_ensure_field_writes_forbidden():
    p = Principal(
        subject="u",
        org_id="o",
        project_id="p",
        roles=["developer"],
        markings=["public"],
    )
    defs = [{"name": "internalCost", "requiredMarkings": ["secret"]}]
    with pytest.raises(ApiError) as ei:
        ensure_field_writes(p, {"internalCost": 1}, defs)
    assert ei.value.code == "FORBIDDEN"


def _public_headers(client):
    tok = client.post(
        "/v1/auth/token",
        json={
            "grantType": "dev",
            "subject": "public-user",
            "roles": ["developer"],
            "markings": ["public"],
        },
    )
    assert tok.status_code == 200
    return {
        "Authorization": f"Bearer {tok.json()['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_get_object_redacts_without_secret(client):
    # Bearer dev is admin (bypass) — use public-only JWT
    r = client.get("/v1/objects/WorkOrder/wo-1001", headers=_public_headers(client))
    assert r.status_code == 200
    body = r.json()
    assert body["title"]
    assert "internalCost" not in body
    assert "internalCost" in (body.get("_redactedFields") or [])


def test_get_object_visible_with_secret(client):
    tok = client.post(
        "/v1/auth/token",
        json={
            "grantType": "dev",
            "subject": "secret-user",
            "roles": ["developer"],
            "markings": ["public", "secret"],
        },
    )
    assert tok.status_code == 200
    headers = {
        "Authorization": f"Bearer {tok.json()['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    r = client.get("/v1/objects/WorkOrder/wo-1001", headers=headers)
    assert r.status_code == 200
    assert r.json().get("internalCost") == 1280
    assert not r.json().get("_redactedFields")


def test_validate_rejects_secret_field(client):
    r = client.post(
        "/v1/actions/validate",
        headers=_public_headers(client),
        json={
            "actionTypeId": "CloseWorkOrder",
            "payload": {"reason": "ok", "internalCost": 9},
        },
    )
    assert r.status_code == 403
    assert r.json()["code"] == "FORBIDDEN"


def test_object_sets_query_redacts(client):
    r = client.post(
        "/v1/object-sets/query",
        headers=_public_headers(client),
        json={"objectType": "WorkOrder", "source": "pg", "page": 1, "pageSize": 10},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    for it in items:
        if it.get("id") == "wo-1001":
            assert "internalCost" not in it
            assert "internalCost" in (it.get("_redactedFields") or [])
