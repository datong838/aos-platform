"""115 · TA.6 analytics governance: redaction · export deny · lineage."""


def _public_headers(client):
    tok = client.post(
        "/v1/auth/token",
        json={
            "grantType": "dev",
            "subject": "public-user-ta6",
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


def _secret_headers(client):
    tok = client.post(
        "/v1/auth/token",
        json={
            "grantType": "dev",
            "subject": "secret-user-ta6",
            "roles": ["developer"],
            "markings": ["public", "secret"],
        },
    )
    assert tok.status_code == 200
    return {
        "Authorization": f"Bearer {tok.json()['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_objects_list_governance_redacts_public(client):
    r = client.post(
        "/v1/analytics/objects/list",
        headers=_public_headers(client),
        json={"objectType": "WorkOrder", "limit": 20},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["governance"]["exportPolicy"] == "deny-if-redacted"
    assert "internalCost" in (body["governance"].get("redactedFieldUnion") or [])
    for row in body["rows"]:
        if row.get("id") == "wo-1001":
            assert "internalCost" not in row
            assert "internalCost" in (row.get("_redactedFields") or [])


def test_export_forbidden_when_redacted(client):
    r = client.post(
        "/v1/analytics/export",
        headers=_public_headers(client),
        json={"objectType": "WorkOrder", "format": "json", "limit": 20},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "ANALYTICS_EXPORT_FORBIDDEN"


def test_export_ok_with_secret_marking(client):
    r = client.post(
        "/v1/analytics/export",
        headers=_secret_headers(client),
        json={"objectType": "WorkOrder", "format": "json", "limit": 20},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "ta6-export"
    assert body["total"] >= 1
    assert not (body.get("governance") or {}).get("redactedFieldUnion")


def test_lineage_lists_after_approve(client, auth_headers):
    prop = client.post(
        "/v1/analytics/writeback/propose",
        headers={**auth_headers, "Idempotency-Key": "ta6-lin-p"},
        json={
            "objectType": "WorkOrder",
            "objectId": "wo-1001",
            "proposed": {"reason": "ta6-lineage", "status": "closed"},
        },
    )
    assert prop.status_code == 201
    draft_id = prop.json()["id"]
    appr = client.post(
        f"/v1/aip/drafts/{draft_id}/approve",
        headers={
            **auth_headers,
            "Idempotency-Key": "ta6-lin-a",
            "X-Allow-Conflicts": "1",
        },
    )
    assert appr.status_code == 200, appr.text
    lin = client.get(
        "/v1/analytics/lineage",
        headers=auth_headers,
        params={"objectType": "WorkOrder", "objectId": "wo-1001", "limit": 5},
    )
    assert lin.status_code == 200
    body = lin.json()
    assert body["mode"] == "ta6-lineage"
    assert body["items"]
    assert any(i.get("draftId") == draft_id for i in body["items"])
