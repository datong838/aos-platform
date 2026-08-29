from datetime import datetime, timezone

from aos_api.db import connect
from aos_api.routers import wave_ext
from aos_api.tenant_scope import TenantScope


def test_code_repository_catalog_contains_only_current_verifiable_repo(client, auth_headers) -> None:
    response = client.get("/v1/code-repositories", headers=auth_headers)
    assert response.status_code == 200
    names = [item["name"] for item in response.json()["repos"]]
    assert names == ["aos-platform"]
    assert "okf-sample" not in response.text
    repo = response.json()["repos"][0]
    assert repo["branch"]
    assert repo["commitCount"] > 0
    assert any(item["path"] == "apps" and item["type"] == "dir" for item in repo["files"])
    assert all("/" not in item["path"] for item in repo["files"])


def test_data_lineage_uses_chinese_business_names_and_keeps_technical_refs_in_meta(
    client, auth_headers
) -> None:
    response = client.get("/v1/data-lineage/graph", headers=auth_headers)
    assert response.status_code == 200
    nodes = response.json()["nodes"]
    assert len(nodes) in (36, 37)
    order = next(item for item in nodes if item["id"] == "ot-Order")
    assert order["name"] == "订单"
    assert order["meta"]["description"] == "业务对象 · 订单主表"
    assert order["meta"]["targetOt"] == "Order"
    sources = [item for item in nodes if item["type"] == "source"]
    if sources:
        source = sources[0]
        assert source["name"] == "栖月汇微商城数据源"
        assert "niushop" not in source["name"].lower()
        assert source["meta"]["connectorId"]


def test_data_health_does_not_manufacture_consistency_or_fourteen_day_trend(client, auth_headers) -> None:
    response = client.get("/v1/data-health/summary", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["consistency"] is None
    assert 0 <= body["timeliness"] <= 1
    assert 1 <= len(body["trend"]) <= 14
    assert all(rule["name"].endswith("当前数据可用性") for rule in body["rules"])
    assert all(rule["actual"] == (1.0 if rule["status"] == "passing" else 0.0) for rule in body["rules"])


def test_build_list_prefers_latest_persisted_schedule_run(client, auth_headers) -> None:
    scope = TenantScope("dev-org", "dev-project")
    with connect(scope) as conn:
        conn.execute(
            """
            INSERT INTO meta_source
              (id, type, status, org_id, project_id, props, updated_at)
            VALUES ('r41-current-source','file','registered',%s,%s,'{}'::jsonb,NOW())
            ON CONFLICT (org_id, project_id, id) DO NOTHING
            """,
            scope.key,
        )
        conn.commit()

    created = client.post(
        "/v1/pipelines",
        headers=auth_headers,
        json={
            "id": "r41-current-build",
            "sourceId": "r41-current-source",
            "target": "dataset",
            "name": "当前运行记录验证",
            "objectTypeHint": "Order",
        },
    )
    assert created.status_code == 200
    pipeline_id = created.json()["id"]
    schedule_id = f"r41-{pipeline_id}"
    now = datetime.now(timezone.utc)
    with connect(scope) as conn:
        conn.execute(
            """
            INSERT INTO meta_schedule
              (id, cron, pipeline_id, enabled, name, org_id, project_id, props, updated_at)
            VALUES (%s,'0 2 * * *',%s,TRUE,'R41 current run',%s,%s,'{}'::jsonb,NOW())
            ON CONFLICT (org_id, project_id, id) DO UPDATE SET pipeline_id=EXCLUDED.pipeline_id
            """,
            (schedule_id, pipeline_id, *scope.key),
        )
        conn.execute(
            """
            INSERT INTO meta_schedule_run
              (id, org_id, project_id, schedule_id, scheduled_for, trigger, status,
               started_at, finished_at, duration_ms, rows_written, executor_id)
            VALUES (%s,%s,%s,%s,%s,'cron','succeeded',%s,%s,1200,936,'ec-live-v1')
            """,
            (f"run-{schedule_id}", *scope.key, schedule_id, now, now, now),
        )
        conn.commit()

    pipeline_cache = next(
        item for item in wave_ext._pipelines.values() if item.get("id") == pipeline_id
    )
    pipeline_cache["lastBuild"] = {
        "id": f"seed-build-{pipeline_id}",
        "status": "SUCCEEDED",
        "startedAt": now.timestamp() + 86_400,
        "finishedAt": now.timestamp() + 86_400,
    }

    response = client.get("/v1/builds", headers=auth_headers)
    assert response.status_code == 200
    build = next(item for item in response.json()["items"] if item["pipelineId"] == pipeline_id)
    assert build["rowsWritten"] == 936
    assert build["status"] == "SUCCEEDED"
    assert isinstance(build["pipelineId"], str)
    syncs = client.get("/v1/syncs", headers=auth_headers)
    assert syncs.status_code == 200
    synced = next(item for item in syncs.json()["items"] if item["id"] == f"run-{schedule_id}")
    assert synced["rowsSynced"] == 936
    assert synced["pipelineId"] == pipeline_id


def test_build_list_hides_decommissioned_pipeline(client, auth_headers, monkeypatch) -> None:
    scope = TenantScope("dev-org", "dev-project")
    monkeypatch.setitem(
        wave_ext._pipelines,
        "retired-r41-pipeline",
        {
            "id": "retired-r41-pipeline",
            "name": None,
            "status": "decommissioned",
            "orgId": scope.org_id,
            "projectId": scope.project_id,
            "lastBuild": {"id": "seed-build-retired-r41-pipeline", "status": "SUCCEEDED"},
        },
    )
    response = client.get("/v1/builds", headers=auth_headers)
    assert response.status_code == 200
    assert "retired-r41-pipeline" not in response.text


def test_media_metadata_changes_are_real_and_tenant_scoped(client, auth_headers) -> None:
    created = client.post(
        "/v1/media-sets",
        headers=auth_headers,
        json={"name": "当前媒体验证.txt", "contentType": "text/plain"},
    )
    assert created.status_code == 200
    rid = created.json()["rid"]

    updated = client.patch(
        f"/v1/media-sets/{rid}",
        headers=auth_headers,
        json={"category": "document", "tags": ["经营资料", "经营资料", ""]},
    )
    assert updated.status_code == 200
    assert updated.json()["category"] == "document"
    assert updated.json()["tags"] == ["经营资料"]

    deleted = client.delete(f"/v1/media-sets/{rid}", headers=auth_headers)
    assert deleted.status_code == 200
    listed = client.get("/v1/media-sets", headers=auth_headers)
    assert rid not in listed.text
