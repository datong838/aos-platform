"""93 · wiki version snapshots on approve."""


def test_wiki_version_list_empty_ok(client, auth_headers):
    r = client.get("/v1/wiki/WorkOrder/wo-1001/versions", headers=auth_headers)
    assert r.status_code == 200
    assert "items" in r.json()


def test_legacy_wiki_approve_is_closed_without_mutating_versions(client, auth_headers):
    cur = client.get("/v1/wiki/WorkOrder/wo-1001", headers=auth_headers)
    assert cur.status_code == 200
    previous_body = cur.json()["body"]
    before = client.get("/v1/wiki/WorkOrder/wo-1001/versions", headers=auth_headers).json()["items"]
    previous_latest_id = before[0]["id"] if before else None

    draft = client.post(
        "/v1/aip/drafts",
        headers=auth_headers,
        json={
            "actionTypeId": "UpdateWikiCard",
            "objectType": "WorkOrder",
            "objectId": "wo-1001",
            "proposed": {
                "wikiBody": {
                    "summary": "ver-test-summary",
                    "fields": {"sla": "4h"},
                }
            },
            "title": "wiki version selftest",
        },
    )
    assert draft.status_code in (200, 201), draft.text
    did = draft.json()["id"]

    appr = client.post(f"/v1/aip/drafts/{did}/approve", headers=auth_headers)
    assert appr.status_code == 410, appr.text

    after = client.get("/v1/wiki/WorkOrder/wo-1001/versions", headers=auth_headers)
    assert after.status_code == 200
    items = after.json()["items"]
    assert (items[0]["id"] if items else None) == previous_latest_id
    current = client.get("/v1/wiki/WorkOrder/wo-1001", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["body"] == previous_body
