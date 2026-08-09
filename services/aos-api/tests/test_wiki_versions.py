"""93 · wiki version snapshots on approve."""


def test_wiki_version_list_empty_ok(client, auth_headers):
    r = client.get("/v1/wiki/WorkOrder/wo-1001/versions", headers=auth_headers)
    assert r.status_code == 200
    assert "items" in r.json()


def test_wiki_version_snapshot_on_approve(client, auth_headers):
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
    assert appr.status_code == 200, appr.text

    after = client.get("/v1/wiki/WorkOrder/wo-1001/versions", headers=auth_headers)
    assert after.status_code == 200
    items = after.json()["items"]
    assert items
    assert items[0].get("draftId") == did
    if previous_latest_id is not None:
        assert items[0]["id"] > previous_latest_id

    vid = items[0]["id"]
    one = client.get(f"/v1/wiki/WorkOrder/wo-1001/versions/{vid}", headers=auth_headers)
    assert one.status_code == 200
    # Versions are immutable pre-write snapshots used for rollback/diff.  The
    # approved body stays on the current page rather than being duplicated as
    # a historical version.
    assert one.json()["body"] == previous_body
    current = client.get("/v1/wiki/WorkOrder/wo-1001", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["body"]["summary"] == "ver-test-summary"
