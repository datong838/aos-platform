"""113 · TA.4 analytics read (objects/list · get · dataset preview · sql)."""

from aos_api.tenant_scope import TenantScope


TEST_SCOPE = TenantScope("dev-org", "dev-project")


def test_objects_list_workorder(client, auth_headers):
    r = client.post(
        "/v1/analytics/objects/list",
        headers=auth_headers,
        json={"objectType": "WorkOrder", "limit": 10},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "ta4-read"
    assert body["kind"] == "objectType"
    assert body["objectType"] == "WorkOrder"
    assert "columns" in body and "rows" in body
    assert body["total"] == len(body["rows"])
    assert body["total"] >= 1


def test_objects_get(client, auth_headers):
    listed = client.post(
        "/v1/analytics/objects/list",
        headers=auth_headers,
        json={"objectType": "WorkOrder", "limit": 1},
    ).json()
    oid = listed["rows"][0]["id"]
    g = client.post(
        "/v1/analytics/objects/get",
        headers=auth_headers,
        json={"objectType": "WorkOrder", "objectId": oid},
    )
    assert g.status_code == 200
    body = g.json()
    assert body["kind"] == "object"
    assert body["total"] == 1
    assert body["rows"][0]["id"] == oid


def test_dataset_preview_via_hint(client, auth_headers):
    from aos_api.routers import wave_ext

    rid = "ri.dataset.ta4-113"
    wave_ext._datasets[wave_ext._resource_key(TEST_SCOPE, rid)] = {
        "rid": rid,
        "name": "ta4-hint",
        "objectTypeHint": "WorkOrder",
        "status": "READY",
        "orgId": TEST_SCOPE.org_id,
        "projectId": TEST_SCOPE.project_id,
    }
    r = client.post(
        "/v1/analytics/datasets/preview",
        headers=auth_headers,
        json={"datasetRid": rid, "limit": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "dataset"
    assert body["source"] == "dataset-hint"
    assert body["total"] >= 1


def test_dataset_preview_no_hint_empty_ok(client, auth_headers):
    from aos_api.routers import wave_ext

    rid = "ri.dataset.ta4-empty"
    wave_ext._datasets[wave_ext._resource_key(TEST_SCOPE, rid)] = {
        "rid": rid,
        "name": "meta-only",
        "status": "READY",
        "orgId": TEST_SCOPE.org_id,
        "projectId": TEST_SCOPE.project_id,
    }
    r = client.post(
        "/v1/analytics/datasets/preview",
        headers=auth_headers,
        json={"datasetRid": rid},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert "objectTypeHint" in (body.get("detail") or "")


def test_dataset_preview_get_is_read_only_browser_contract(client, auth_headers):
    from aos_api.routers import wave_ext

    rid = "ri.dataset.ta4-get"
    wave_ext._datasets[wave_ext._resource_key(TEST_SCOPE, rid)] = {
        "rid": rid,
        "name": "get-preview",
        "status": "READY",
        "orgId": TEST_SCOPE.org_id,
        "projectId": TEST_SCOPE.project_id,
    }
    r = client.get(
        "/v1/analytics/datasets/preview",
        headers=auth_headers,
        params={"datasetRid": rid, "limit": 10},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["datasetRid"] == rid
    assert body["kind"] == "dataset"
    assert body["source"] == "dataset-meta"


def test_sql_select_1(client, auth_headers):
    r = client.post(
        "/v1/analytics/sql/preview",
        headers=auth_headers,
        json={"sql": "select 1", "limit": 10},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == [{"v": 1}]
    assert body["source"] == "sql-literal"


def test_sql_select_star_with_object_type(client, auth_headers):
    r = client.post(
        "/v1/analytics/sql/preview",
        headers=auth_headers,
        json={"sql": "select *", "objectType": "WorkOrder", "limit": 5},
    )
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_sql_forbidden_dml(client, auth_headers):
    r = client.post(
        "/v1/analytics/sql/preview",
        headers=auth_headers,
        json={"sql": "delete from WorkOrder"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "ANALYTICS_SQL_FORBIDDEN"


def test_sql_unsupported(client, auth_headers):
    r = client.post(
        "/v1/analytics/sql/preview",
        headers=auth_headers,
        json={"sql": "select count(*) from WorkOrder"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "ANALYTICS_SQL_UNSUPPORTED"
