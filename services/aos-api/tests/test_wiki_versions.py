"""93 · wiki version snapshots on approve."""


def test_wiki_version_list_empty_ok(client, auth_headers):
    r = client.get("/v1/wiki/WorkOrder/wo-1001/versions", headers=auth_headers)
    assert r.status_code == 200
    assert "items" in r.json()


def test_wiki_version_snapshot_on_approve(client, auth_headers):
    cur = client.get("/v1/wiki/WorkOrder/wo-1001", headers=auth_headers)
    assert cur.status_code == 200
    old_summary = (cur.json().get("body") or {}).get("summary")

    before = client.get("/v1/wiki/WorkOrder/wo-1001/versions", headers=auth_headers).json()["items"]

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
    assert len(items) >= len(before) + 1
    if old_summary is not None:
        assert any(i.get("summary") == old_summary for i in items)

    vid = items[0]["id"]
    one = client.get(f"/v1/wiki/WorkOrder/wo-1001/versions/{vid}", headers=auth_headers)
    assert one.status_code == 200
    assert "body" in one.json()
