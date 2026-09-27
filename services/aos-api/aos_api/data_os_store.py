"""Data OS metadata store — Source/Pipeline/Dataset/Sync/Schedule (185w)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from aos_api.db import connect, connect_read_only
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.data-os")

_schema_ready = False

DEMO_SURFACE_IDS: dict[str, tuple[str, ...]] = {
    "sources": ("demo-file-wo",),
    "pipelines": ("demo-pipe-wo",),
    "datasets": ("ri.dataset.demo-workorder",),
    "syncs": ("sync-demo-wo",),
    "schedules": ("demo-sch-wo",),
}
"""已知 demo 专用 id 清单。``boot_data_os`` 启动时强制从产品 surface 清除。"""

_DEMO_DLQ_PREFIX = "dlq-demo"


def purge_demo_surface(wave_ext_module: Any) -> dict[str, Any]:
    """从 wave_ext 内存数据面清除已知 demo 条目（产品 surface 反 demo 守门）。

    替代原 ``wave_ext.clear_demo_data_surface``，把"反 demo 清理"职责收敛到 data_os 层，
    生产代码不再反向依赖 wave_ext 的 demo 函数。
    """
    removed: dict[str, Any] = {
        "sources": [],
        "pipelines": [],
        "datasets": [],
        "syncs": [],
        "schedules": [],
        "dlq": 0,
    }
    for sid in DEMO_SURFACE_IDS["sources"]:
        if sid in wave_ext_module._connectors:
            del wave_ext_module._connectors[sid]
            removed["sources"].append(sid)
    for pid in DEMO_SURFACE_IDS["pipelines"]:
        if pid in wave_ext_module._pipelines:
            del wave_ext_module._pipelines[pid]
            removed["pipelines"].append(pid)
    for rid in DEMO_SURFACE_IDS["datasets"]:
        dataset_keys = [
            key
            for key in wave_ext_module._datasets
            if (key[2] if isinstance(key, tuple) and len(key) == 3 else key) == rid
        ]
        if dataset_keys:
            for key in dataset_keys:
                wave_ext_module._datasets.pop(key, None)
                wave_ext_module._dataset_history.pop(key, None)
            removed["datasets"].append(rid)
    for sid in DEMO_SURFACE_IDS["syncs"]:
        if sid in wave_ext_module._syncs:
            del wave_ext_module._syncs[sid]
            removed["syncs"].append(sid)
    for sch in DEMO_SURFACE_IDS["schedules"]:
        if sch in wave_ext_module._schedules:
            del wave_ext_module._schedules[sch]
            removed["schedules"].append(sch)
    before = len(wave_ext_module._dlq)
    kept_dlq = {
        key: item
        for key, item in wave_ext_module._dlq.items()
        if not str(item.get("id", "")).startswith(_DEMO_DLQ_PREFIX)
    }
    wave_ext_module._dlq.clear()
    wave_ext_module._dlq.update(kept_dlq)
    removed["dlq"] = before - len(wave_ext_module._dlq)
    log.info("data_os_demo_purged %s", removed)
    return {"ok": True, "removed": removed}


def ensure_data_os_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    expected_primary_keys = {
        "meta_source": ["org_id", "project_id", "id"],
        "meta_pipeline": ["org_id", "project_id", "id"],
        "meta_dataset": ["org_id", "project_id", "rid"],
        "meta_dataset_history": ["org_id", "project_id", "id"],
        "meta_sync": ["org_id", "project_id", "id"],
        "meta_schedule": ["org_id", "project_id", "id"],
        "phase5_pipeline_graph": ["org_id", "project_id", "pipeline_id"],
    }
    with connect() as conn:
        rows = conn.execute(
            "SELECT table_name, array_agg(column_name::text ORDER BY ordinal_position) "
            "FILTER (WHERE column_name IN ('org_id','project_id')) AS scope_columns "
            "FROM information_schema.columns WHERE table_schema='public' "
            "AND table_name=ANY(%s) GROUP BY table_name",
            (list(expected_primary_keys),),
        ).fetchall()
        present = {str(row["table_name"]): list(row["scope_columns"] or []) for row in rows}
        pk_rows = conn.execute(
            "SELECT c.relname AS table_name, "
            "array_agg(a.attname::text ORDER BY k.ordinality) AS columns "
            "FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid "
            "JOIN unnest(p.conkey) WITH ORDINALITY k(attnum, ordinality) ON TRUE "
            "JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.attnum "
            "WHERE p.contype='p' AND c.relnamespace='public'::regnamespace "
            "AND c.relname=ANY(%s) GROUP BY c.relname",
            (list(expected_primary_keys),),
        ).fetchall()
        primary_keys = {
            str(row["table_name"]): list(row["columns"] or []) for row in pk_rows
        }
    invalid = sorted(
        table
        for table, expected in expected_primary_keys.items()
        if present.get(table) != ["org_id", "project_id"]
        or primary_keys.get(table) != expected
    )
    if invalid:
        raise RuntimeError(
            "Data OS schema is not at TI-4 D7 contract; run Alembic upgrade: "
            + ", ".join(invalid)
        )
    _schema_ready = True
    log.info("data_os_schema_ready")


def _assert_scoped_upsert(row: Any, *, resource: str, resource_id: str) -> None:
    if row is None:
        raise ApiError(
            code="TENANT_SCOPE_CONFLICT",
            message=f"{resource} id belongs to another or unresolved tenant",
            status_code=409,
            details={"resource": resource, "id": resource_id},
        )


def _require_scope(scope: TenantScope | None) -> TenantScope:
    if not isinstance(scope, TenantScope):
        raise ApiError(
            code="TENANT_SCOPE_REQUIRED",
            message="Data OS mutation requires TenantScope",
            status_code=400,
        )
    return scope


def persist_source(
    scope: TenantScope, item: dict[str, Any], *,
    merge_existing: bool = False, replace_fields: tuple[str, ...] = (),
    expected_configuration_revision: str | None = None,
    registration_key: str | None = None,
) -> dict[str, Any]:
    scope = _require_scope(scope)
    ensure_data_os_schema()
    if registration_key is not None and (not registration_key or len(registration_key) > 160):
        raise ApiError(code="SOURCE_REGISTRATION_KEY_INVALID", message="登记幂等键无效", status_code=400)
    request_hash = hashlib.sha256(json.dumps(
        {"item": item, "expectedConfigurationRevision": expected_configuration_revision},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
    ).encode("utf-8")).hexdigest() if registration_key is not None else None
    props = {k: v for k, v in item.items() if k not in {"id", "type", "status", "pluginId", "orgId", "projectId", "configurationRevision"}}
    with connect(scope) as conn:
        if registration_key is not None:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                         (json.dumps(["source-registration-key", *scope.key, registration_key]),))
            existing_receipt = conn.execute(
                "SELECT request_hash,response_metadata FROM source_registration_receipt "
                "WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
                (*scope.key, registration_key),
            ).fetchone()
            if existing_receipt is not None:
                if existing_receipt["request_hash"] != request_hash:
                    raise ApiError(code="SOURCE_REGISTRATION_KEY_CONFLICT",
                                   message="登记幂等键已用于不同请求", status_code=409)
                return dict(existing_receipt["response_metadata"])
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                     (json.dumps(["source-registration", *scope.key, item["id"]]),))
        if replace_fields or expected_configuration_revision is not None:
            current = conn.execute(
                "SELECT configuration_revision FROM meta_source WHERE org_id=%s AND project_id=%s AND id=%s FOR UPDATE",
                (*scope.key, item["id"]),
            ).fetchone()
            actual = str(current["configuration_revision"]) if current else None
            if actual != expected_configuration_revision:
                raise ApiError(code="SOURCE_CONFIGURATION_CONFLICT",
                    message="数据源配置已变化，请重新读取后再修改", status_code=409)
        row = conn.execute(
            """
            INSERT INTO meta_source (id, type, status, plugin_id, org_id, project_id, props, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,NOW())
            ON CONFLICT (org_id, project_id, id) DO UPDATE SET
              type=EXCLUDED.type, status=EXCLUDED.status, plugin_id=EXCLUDED.plugin_id,
              props=CASE WHEN %s THEN (meta_source.props - %s::text[]) || EXCLUDED.props
                         ELSE EXCLUDED.props END,
              updated_at=NOW()
            WHERE meta_source.org_id=EXCLUDED.org_id
              AND meta_source.project_id=EXCLUDED.project_id
              AND (NOT %s OR meta_source.type=EXCLUDED.type)
            RETURNING *
            """,
            (
                item["id"],
                item.get("type") or "file",
                item.get("status") or "registered",
                item.get("pluginId"),
                scope.org_id,
                scope.project_id,
                json.dumps(props, ensure_ascii=False, default=str),
                merge_existing, list(replace_fields), merge_existing,
            ),
        ).fetchone()
        _assert_scoped_upsert(row, resource="source", resource_id=str(item["id"]))
        result = {**dict(row["props"]), "id": row["id"], "type": row["type"],
                  "status": row["status"], "pluginId": row["plugin_id"],
                  "orgId": row["org_id"], "projectId": row["project_id"],
                  "configurationRevision": str(row["configuration_revision"])}
        if registration_key is not None:
            public_fields = {"id", "type", "status", "pluginId", "orgId", "projectId",
                             "configurationRevision", "runtimeMode", "name", "displayName",
                             "description", "siteId", "connector_type"}
            metadata = {key: value for key, value in result.items() if key in public_fields}
            conn.execute(
                "INSERT INTO source_registration_receipt "
                "(org_id,project_id,idempotency_key,request_hash,source_id,configuration_revision,response_metadata) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                (*scope.key, registration_key, request_hash, item["id"],
                 row["configuration_revision"], json.dumps(metadata, ensure_ascii=False, default=str)),
            )
        conn.commit()
        return result


def load_source_registration_receipt(scope: TenantScope, source_id: str, key: str) -> dict[str, Any] | None:
    """Read the original public response by exact key; never load source secrets."""
    scope = _require_scope(scope)
    with connect_read_only(scope) as conn:
        row = conn.execute(
            "SELECT source_id,configuration_revision,response_metadata FROM source_registration_receipt "
            "WHERE org_id=%s AND project_id=%s AND idempotency_key=%s AND source_id=%s",
            (*scope.key, key, source_id),
        ).fetchone()
    if row is None:
        return None
    return {"sourceId": row["source_id"],
            "configurationRevision": str(row["configuration_revision"]),
            "responseMetadata": dict(row["response_metadata"])}


def persist_pipeline(scope: TenantScope, item: dict[str, Any]) -> None:
    scope = _require_scope(scope)
    ensure_data_os_schema()
    props = {
        k: v
        for k, v in item.items()
        if k
        not in {
            "id",
            "sourceId",
            "target",
            "datasetRid",
            "name",
            "displayName",
            "objectTypeHint",
            "lastBuild",
            "orgId",
            "projectId",
        }
    }
    with connect(scope) as conn:
        row = conn.execute(
            """
            INSERT INTO meta_pipeline
              (id, source_id, target, dataset_rid, name, object_type_hint,
               last_build, props, org_id, project_id, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,NOW())
            ON CONFLICT (org_id, project_id, id) DO UPDATE SET
              source_id=EXCLUDED.source_id, target=EXCLUDED.target, dataset_rid=EXCLUDED.dataset_rid,
              name=EXCLUDED.name, object_type_hint=EXCLUDED.object_type_hint,
              last_build=EXCLUDED.last_build, props=EXCLUDED.props, updated_at=NOW()
            WHERE meta_pipeline.org_id=EXCLUDED.org_id
              AND meta_pipeline.project_id=EXCLUDED.project_id
            RETURNING id
            """,
            (
                item["id"],
                item.get("sourceId") or "",
                item.get("target") or "dataset",
                item.get("datasetRid"),
                item.get("name") or item.get("displayName"),
                item.get("objectTypeHint"),
                json.dumps(item.get("lastBuild") or {}, ensure_ascii=False, default=str),
                json.dumps(props, ensure_ascii=False, default=str),
                *scope.key,
            ),
        ).fetchone()
        _assert_scoped_upsert(row, resource="pipeline", resource_id=str(item["id"]))
        conn.commit()


def register_pipeline(scope: TenantScope, *, pipeline_id: str, source_id: str,
                      source_configuration_revision: str, dataset_rid: str,
                      name: str, idempotency_key: str) -> dict[str, Any]:
    """Register a first pipeline, its dataset and the original outcome atomically."""
    scope = _require_scope(scope)
    ensure_data_os_schema()
    if not idempotency_key or len(idempotency_key) > 160:
        raise ApiError(code="PIPELINE_REGISTRATION_KEY_INVALID", message="管道登记幂等键无效", status_code=400)
    request_hash = hashlib.sha256(json.dumps({
        "pipelineId": pipeline_id, "sourceId": source_id,
        "sourceConfigurationRevision": source_configuration_revision,
        "datasetRid": dataset_rid, "name": name,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    with connect(scope) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                     (json.dumps(["pipeline-registration-key", *scope.key, idempotency_key]),))
        receipt = conn.execute(
            "SELECT request_hash,response_metadata FROM pipeline_registration_receipt "
            "WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
            (*scope.key, idempotency_key),
        ).fetchone()
        if receipt is not None:
            if receipt["request_hash"] != request_hash:
                raise ApiError(code="PIPELINE_REGISTRATION_KEY_CONFLICT",
                    message="幂等键已用于不同管道请求", status_code=409)
            return dict(receipt["response_metadata"])
        for identity in sorted((f"pipeline:{pipeline_id}", f"dataset:{dataset_rid}")):
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                         (json.dumps(["pipeline-registration", *scope.key, identity]),))
        source = conn.execute(
            "SELECT configuration_revision FROM meta_source "
            "WHERE org_id=%s AND project_id=%s AND id=%s FOR SHARE",
            (*scope.key, source_id),
        ).fetchone()
        if source is None or str(source["configuration_revision"]) != source_configuration_revision:
            raise ApiError(code="PIPELINE_SOURCE_CONFIGURATION_CHANGED",
                message="来源不存在或配置修订已变化，请重新读取", status_code=409)
        if conn.execute("SELECT 1 FROM meta_pipeline WHERE org_id=%s AND project_id=%s AND id=%s",
                        (*scope.key, pipeline_id)).fetchone() is not None:
            raise ApiError(code="PIPELINE_ID_CONFLICT", message="管道 ID 已存在", status_code=409)
        if conn.execute("SELECT 1 FROM meta_dataset WHERE org_id=%s AND project_id=%s AND rid=%s",
                        (*scope.key, dataset_rid)).fetchone() is not None:
            raise ApiError(code="PIPELINE_DATASET_CONFLICT", message="输出数据集 ID 已存在", status_code=409)
        conn.execute("""INSERT INTO meta_pipeline
            (id,source_id,target,dataset_rid,name,object_type_hint,last_build,props,org_id,project_id,updated_at)
            VALUES (%s,%s,'dataset',%s,%s,NULL,'{}'::jsonb,'{}'::jsonb,%s,%s,NOW())""",
            (pipeline_id,source_id,dataset_rid,name,*scope.key))
        conn.execute("""INSERT INTO meta_dataset
            (rid,name,display_name,pipeline_id,source_id,status,object_type_hint,
             created_at,updated_at,props,org_id,project_id)
            VALUES (%s,%s,%s,%s,%s,'PENDING',NULL,extract(epoch from clock_timestamp()),
                    extract(epoch from clock_timestamp()),'{}'::jsonb,%s,%s)""",
            (dataset_rid,name,name,pipeline_id,source_id,*scope.key))
        metadata = {"id": pipeline_id, "sourceId": source_id, "target": "dataset",
                    "datasetRid": dataset_rid, "name": name,
                    "sourceConfigurationRevision": source_configuration_revision,
                    "orgId": scope.org_id, "projectId": scope.project_id}
        conn.execute("""INSERT INTO pipeline_registration_receipt
            (org_id,project_id,idempotency_key,request_hash,pipeline_id,source_id,
             source_configuration_revision,dataset_rid,response_metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s::uuid,%s,%s::jsonb)""",
            (*scope.key,idempotency_key,request_hash,pipeline_id,source_id,
             source_configuration_revision,dataset_rid,json.dumps(metadata,ensure_ascii=False)))
        conn.commit()
        return metadata


def load_pipeline_registration_receipt(scope: TenantScope, pipeline_id: str,
                                       key: str) -> dict[str, Any] | None:
    """Read the original public result without accessing any source data."""
    scope = _require_scope(scope)
    with connect_read_only(scope) as conn:
        row = conn.execute(
            "SELECT response_metadata FROM pipeline_registration_receipt "
            "WHERE org_id=%s AND project_id=%s AND pipeline_id=%s AND idempotency_key=%s",
            (*scope.key,pipeline_id,key),
        ).fetchone()
    return dict(row["response_metadata"]) if row is not None else None


def persist_phase5_pipeline_graph(
    scope: TenantScope, payload: dict[str, Any]
) -> dict[str, Any]:
    """Atomically persist one complete Phase5 graph and return the committed snapshot."""
    scope = _require_scope(scope)
    ensure_data_os_schema()
    pipeline_id = str(payload.get("pipeline_id") or "").strip()
    if not pipeline_id:
        raise ValueError("pipeline graph requires pipeline_id")
    node_ids = {str(node.get("id") or "") for node in payload.get("nodes") or []}
    edge_ids = {str(edge.get("id") or "") for edge in payload.get("edges") or []}
    encoded = json.dumps(payload, ensure_ascii=False, default=str)
    with connect(scope) as conn:
        # Serialize graph writers across processes so nested node/edge ids keep one owner.
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (228301,))
        rows = conn.execute(
            "SELECT pipeline_id, payload FROM phase5_pipeline_graph "
            "WHERE org_id=%s AND project_id=%s AND pipeline_id<>%s FOR UPDATE",
            (*scope.key, pipeline_id),
        ).fetchall()
        for row in rows:
            other_id = str(row["pipeline_id"])
            other = dict(row.get("payload") or {})
            other_nodes = {str(node.get("id") or "") for node in other.get("nodes") or []}
            other_edges = {str(edge.get("id") or "") for edge in other.get("edges") or []}
            duplicate_nodes = sorted(node_ids & other_nodes)
            if duplicate_nodes:
                raise ValueError(
                    f"node id belongs to another pipeline: {duplicate_nodes[0]} ({other_id})"
                )
            duplicate_edges = sorted(edge_ids & other_edges)
            if duplicate_edges:
                raise ValueError(
                    f"edge id belongs to another pipeline: {duplicate_edges[0]} ({other_id})"
                )
        row = conn.execute(
            """
            INSERT INTO phase5_pipeline_graph
              (pipeline_id, payload, revision, org_id, project_id, updated_at)
            VALUES (%s,%s::jsonb,1,%s,%s,NOW())
            ON CONFLICT (org_id, project_id, pipeline_id) DO UPDATE SET
              payload=EXCLUDED.payload,
              revision=phase5_pipeline_graph.revision+1,
              updated_at=NOW()
            WHERE phase5_pipeline_graph.org_id=EXCLUDED.org_id
              AND phase5_pipeline_graph.project_id=EXCLUDED.project_id
            RETURNING payload, revision
            """,
            (pipeline_id, encoded, *scope.key),
        ).fetchone()
        _assert_scoped_upsert(row, resource="pipeline_graph", resource_id=pipeline_id)
        conn.commit()
    committed = dict(row["payload"] or {})
    committed["revision"] = int(row["revision"])
    committed["persisted"] = True
    committed["demo"] = False
    return committed


def load_phase5_pipeline_graph_catalog(scope: TenantScope) -> list[dict[str, Any]]:
    """Read saved graph identities without exposing node configuration or activating them."""
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        rows = conn.execute(
            "SELECT pipeline_id, payload->>'name' AS name, "
            "payload->>'pipeline_type' AS pipeline_type, "
            "payload->>'write_mode' AS write_mode "
            "FROM phase5_pipeline_graph WHERE org_id=%s AND project_id=%s "
            "ORDER BY pipeline_id",
            scope.key,
        ).fetchall()
    return [
        {"id": row["pipeline_id"], "name": row["name"] or row["pipeline_id"],
         "pipeline_type": row["pipeline_type"] or "ETL",
         "write_mode": row["write_mode"] or "SNAPSHOT",
         "status": "draft", "execution_mode": "disabled", "persisted": True,
         "orgId": scope.org_id, "projectId": scope.project_id}
        for row in rows
    ]


def load_phase5_pipeline_graph(
    scope: TenantScope, pipeline_id: str
) -> dict[str, Any] | None:
    """Load one committed graph snapshot from the shared metadata store."""
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        row = conn.execute(
            "SELECT payload, revision FROM phase5_pipeline_graph "
            "WHERE pipeline_id=%s AND org_id=%s AND project_id=%s",
            (pipeline_id, *scope.key),
        ).fetchone()
    if row is None:
        return None
    payload = dict(row["payload"] or {})
    payload["revision"] = int(row["revision"])
    payload["persisted"] = True
    payload["demo"] = False
    return payload


def delete_phase5_pipeline_graph(scope: TenantScope, pipeline_id: str) -> None:
    """Delete one explicitly identified graph; never truncate shared graph data."""
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        conn.execute(
            "DELETE FROM phase5_pipeline_graph "
            "WHERE pipeline_id=%s AND org_id=%s AND project_id=%s",
            (pipeline_id, *scope.key),
        )
        conn.commit()


def persist_dataset(
    scope: TenantScope, item: dict[str, Any], *,
    history_entries: list[dict[str, Any]] | None = None,
) -> None:
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        _persist_dataset_in_transaction(conn,scope,item,history_entries=history_entries)
        conn.commit()


def _persist_dataset_in_transaction(conn, scope: TenantScope, item: dict[str, Any], *,
                                    history_entries: list[dict[str, Any]] | None = None) -> None:
    """Existing Dataset owner SQL, with commit retained by the caller."""
    scope = _require_scope(scope)
    props = {
        k: v
        for k, v in item.items()
        if k
        not in {
            "rid",
            "name",
            "displayName",
            "pipelineId",
            "sourceId",
            "status",
            "objectTypeHint",
            "createdAt",
            "updatedAt",
            "orgId",
            "projectId",
        }
    }
    row = conn.execute(
        """
        INSERT INTO meta_dataset
          (rid, name, display_name, pipeline_id, source_id, status, object_type_hint,
           created_at, updated_at, props, org_id, project_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
        ON CONFLICT (org_id, project_id, rid) DO UPDATE SET
          name=EXCLUDED.name, display_name=EXCLUDED.display_name,
          pipeline_id=EXCLUDED.pipeline_id, source_id=EXCLUDED.source_id,
          status=EXCLUDED.status, object_type_hint=EXCLUDED.object_type_hint,
          updated_at=EXCLUDED.updated_at, props=EXCLUDED.props
        WHERE meta_dataset.org_id=EXCLUDED.org_id
          AND meta_dataset.project_id=EXCLUDED.project_id
        RETURNING rid
        """,
        (
            item["rid"],
            item.get("name") or item["rid"],
            item.get("displayName"),
            item.get("pipelineId"),
            item.get("sourceId"),
            item.get("status") or "READY",
            item.get("objectTypeHint"),
            item.get("createdAt"),
            item.get("updatedAt"),
            json.dumps(props, ensure_ascii=False, default=str),
            *scope.key,
        ),
    ).fetchone()
    _assert_scoped_upsert(row, resource="dataset", resource_id=str(item["rid"]))
    if history_entries is not None:
        _replace_dataset_history(conn, scope, str(item["rid"]), history_entries)


def persist_sync(scope: TenantScope, item: dict[str, Any]) -> None:
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        row = conn.execute(
            """
            INSERT INTO meta_sync
              (id, source_id, status, rows_synced, started_at, finished_at,
               props, org_id, project_id, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,'{}'::jsonb,%s,%s,NOW())
            ON CONFLICT (org_id, project_id, id) DO UPDATE SET
              source_id=EXCLUDED.source_id, status=EXCLUDED.status,
              rows_synced=EXCLUDED.rows_synced, started_at=EXCLUDED.started_at,
              finished_at=EXCLUDED.finished_at, updated_at=NOW()
            WHERE meta_sync.org_id=EXCLUDED.org_id
              AND meta_sync.project_id=EXCLUDED.project_id
            RETURNING id
            """,
            (
                item["id"],
                item.get("sourceId") or "",
                item.get("status") or "SUCCEEDED",
                int(item.get("rowsSynced") or 0),
                item.get("startedAt"),
                item.get("finishedAt"),
                *scope.key,
            ),
        ).fetchone()
        _assert_scoped_upsert(row, resource="sync", resource_id=str(item["id"]))
        conn.commit()


def persist_schedule(scope: TenantScope, item: dict[str, Any]) -> None:
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        row = conn.execute(
            """
            INSERT INTO meta_schedule
              (id, cron, pipeline_id, enabled, name, ingest, last_run, org_id, project_id, props, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,'{}'::jsonb,NOW())
            ON CONFLICT (org_id, project_id, id) DO UPDATE SET
              cron=EXCLUDED.cron, pipeline_id=EXCLUDED.pipeline_id, enabled=EXCLUDED.enabled,
              name=EXCLUDED.name, ingest=EXCLUDED.ingest, last_run=EXCLUDED.last_run,
              updated_at=NOW()
            WHERE meta_schedule.org_id=EXCLUDED.org_id
              AND meta_schedule.project_id=EXCLUDED.project_id
            RETURNING id
            """,
            (
                item["id"],
                item.get("cron") or "0 * * * *",
                item.get("pipelineId"),
                bool(item.get("enabled", True)),
                item.get("name"),
                json.dumps(item.get("ingest"), ensure_ascii=False, default=str)
                if item.get("ingest") is not None
                else None,
                json.dumps(item.get("lastRun"), ensure_ascii=False, default=str)
                if item.get("lastRun") is not None
                else None,
                *scope.key,
            ),
        ).fetchone()
        _assert_scoped_upsert(row, resource="schedule", resource_id=str(item["id"]))
        conn.commit()


def persist_schedule_configuration(
    scope: TenantScope, item: dict[str, Any]
) -> dict[str, Any] | None:
    """Persist control-plane fields without taking ownership of ``last_run``.

    Schedule execution owns ``last_run``.  A configuration edit can carry a
    stale cached copy, so the conflict path deliberately preserves the value
    already committed by the executor and returns it for cache publication.
    """
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        row = conn.execute(
            """
            INSERT INTO meta_schedule
              (id, cron, pipeline_id, enabled, name, ingest, last_run,
               org_id, project_id, props, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,'{}'::jsonb,NOW())
            ON CONFLICT (org_id, project_id, id) DO UPDATE SET
              cron=EXCLUDED.cron, pipeline_id=EXCLUDED.pipeline_id,
              enabled=EXCLUDED.enabled, name=EXCLUDED.name,
              ingest=EXCLUDED.ingest, updated_at=NOW()
            WHERE meta_schedule.org_id=EXCLUDED.org_id
              AND meta_schedule.project_id=EXCLUDED.project_id
            RETURNING last_run
            """,
            (
                item["id"],
                item.get("cron") or "0 * * * *",
                item.get("pipelineId"),
                bool(item.get("enabled", True)),
                item.get("name"),
                json.dumps(item.get("ingest"), ensure_ascii=False, default=str)
                if item.get("ingest") is not None
                else None,
                json.dumps(item.get("lastRun"), ensure_ascii=False, default=str)
                if item.get("lastRun") is not None
                else None,
                *scope.key,
            ),
        ).fetchone()
        _assert_scoped_upsert(row, resource="schedule", resource_id=str(item["id"]))
        conn.commit()
    return row["last_run"]


def persist_dataset_history(
    scope: TenantScope, dataset_rid: str, entries: list[dict[str, Any]]
) -> None:
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        _replace_dataset_history(conn, scope, dataset_rid, entries)
        conn.commit()


def _replace_dataset_history(conn, scope: TenantScope, dataset_rid: str, entries: list[dict[str, Any]]) -> None:
    conn.execute(
        "DELETE FROM meta_dataset_history "
        "WHERE dataset_rid=%s AND org_id=%s AND project_id=%s",
        (dataset_rid, *scope.key),
    )
    for e in entries:
        conn.execute(
            """
            INSERT INTO meta_dataset_history
              (dataset_rid, payload, org_id, project_id)
            VALUES (%s,%s::jsonb,%s,%s)
            """,
            (
                dataset_rid,
                json.dumps(e, ensure_ascii=False, default=str),
                *scope.key,
            ),
        )


def delete_source(scope: TenantScope, source_id: str) -> None:
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        conn.execute(
            "DELETE FROM meta_source WHERE id=%s AND org_id=%s AND project_id=%s",
            (source_id, *scope.key),
        )
        conn.commit()


def delete_pipeline(scope: TenantScope, pipeline_id: str) -> None:
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        conn.execute(
            "DELETE FROM meta_pipeline WHERE id=%s AND org_id=%s AND project_id=%s",
            (pipeline_id, *scope.key),
        )
        conn.commit()


def delete_dataset(scope: TenantScope, rid: str) -> None:
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        conn.execute(
            "DELETE FROM meta_dataset_history "
            "WHERE dataset_rid=%s AND org_id=%s AND project_id=%s",
            (rid, *scope.key),
        )
        conn.execute(
            "DELETE FROM meta_dataset "
            "WHERE rid=%s AND org_id=%s AND project_id=%s",
            (rid, *scope.key),
        )
        conn.commit()


def delete_sync(scope: TenantScope, sync_id: str) -> None:
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        conn.execute(
            "DELETE FROM meta_sync WHERE id=%s AND org_id=%s AND project_id=%s",
            (sync_id, *scope.key),
        )
        conn.commit()


def delete_schedule(scope: TenantScope, schedule_id: str) -> None:
    scope = _require_scope(scope)
    ensure_data_os_schema()
    with connect(scope) as conn:
        conn.execute(
            "DELETE FROM meta_schedule "
            "WHERE id=%s AND org_id=%s AND project_id=%s",
            (schedule_id, *scope.key),
        )
        conn.commit()


def load_source_metadata(scope: TenantScope) -> list[dict[str, Any]]:
    """Read current public source metadata without loading connection secrets."""
    scope = _require_scope(scope)
    ensure_data_os_schema()
    keys = ["name", "displayName", "description", "siteId", "runtimeMode", "connector_type"]
    with connect(scope) as conn:
        rows = conn.execute(
            """SELECT id,type,status,plugin_id,org_id,project_id,configuration_revision,
                 (SELECT COALESCE(jsonb_object_agg(key,value),'{}'::jsonb)
                    FROM jsonb_each(props) WHERE key=ANY(%s::text[])) AS metadata
               FROM meta_source WHERE org_id=%s AND project_id=%s ORDER BY id""",
            (keys, *scope.key),
        ).fetchall()
        return [{**dict(row["metadata"]), "id": row["id"], "type": row["type"],
                 "status": row["status"], "pluginId": row["plugin_id"],
                 "orgId": row["org_id"], "projectId": row["project_id"],
                 "configurationRevision": str(row["configuration_revision"])} for row in rows]


def load_all(scope: TenantScope) -> dict[str, Any]:
    """Return one tenant's Data OS projection for wave_ext memory maps."""
    scope = _require_scope(scope)
    ensure_data_os_schema()
    out: dict[str, Any] = {
        "connectors": {},
        "pipelines": {},
        "datasets": {},
        "syncs": {},
        "schedules": {},
        "dataset_history": {},
    }
    with connect(scope) as conn:
        params = scope.key
        for r in conn.execute(
            "SELECT * FROM meta_source WHERE org_id=%s AND project_id=%s", params
        ).fetchall():
            item = dict(r.get("props") or {})
            item.update(
                {
                    "id": r["id"],
                    "type": r["type"],
                    "status": r["status"],
                    "pluginId": r["plugin_id"],
                    "orgId": r["org_id"],
                    "projectId": r["project_id"],
                    "configurationRevision": str(r["configuration_revision"]),
                }
            )
            out["connectors"][r["id"]] = item
        for r in conn.execute(
            "SELECT * FROM meta_pipeline WHERE org_id=%s AND project_id=%s", params
        ).fetchall():
            props = dict(r.get("props") or {})
            item = {
                "id": r["id"],
                "sourceId": r["source_id"],
                "target": r["target"],
                "datasetRid": r["dataset_rid"],
                "name": r["name"],
                "objectTypeHint": r["object_type_hint"],
                "lastBuild": r["last_build"] or {},
                "orgId": r["org_id"],
                "projectId": r["project_id"],
            }
            item.update(props)
            out["pipelines"][r["id"]] = item
        for r in conn.execute(
            "SELECT * FROM meta_dataset WHERE org_id=%s AND project_id=%s", params
        ).fetchall():
            props = dict(r.get("props") or {})
            item = {
                "rid": r["rid"],
                "name": r["name"],
                "displayName": r["display_name"],
                "pipelineId": r["pipeline_id"],
                "sourceId": r["source_id"],
                "status": r["status"],
                "objectTypeHint": r["object_type_hint"],
                "createdAt": r["created_at"],
                "updatedAt": r["updated_at"],
                "orgId": r["org_id"],
                "projectId": r["project_id"],
            }
            item.update(props)
            out["datasets"][r["rid"]] = item
        for r in conn.execute(
            "SELECT * FROM meta_sync WHERE org_id=%s AND project_id=%s", params
        ).fetchall():
            out["syncs"][r["id"]] = {
                "id": r["id"],
                "sourceId": r["source_id"],
                "status": r["status"],
                "rowsSynced": r["rows_synced"],
                "startedAt": r["started_at"],
                "finishedAt": r["finished_at"],
                "orgId": r["org_id"],
                "projectId": r["project_id"],
            }
        for r in conn.execute(
            "SELECT * FROM meta_schedule WHERE org_id=%s AND project_id=%s", params
        ).fetchall():
            out["schedules"][r["id"]] = {
                "id": r["id"],
                "cron": r["cron"],
                "pipelineId": r["pipeline_id"],
                "enabled": r["enabled"],
                "name": r["name"],
                "ingest": r["ingest"],
                "lastRun": r["last_run"],
                "orgId": r["org_id"],
                "projectId": r["project_id"],
            }
        for r in conn.execute(
            "SELECT dataset_rid, payload FROM meta_dataset_history "
            "WHERE org_id=%s AND project_id=%s ORDER BY id",
            params,
        ).fetchall():
            rid = r["dataset_rid"]
            out["dataset_history"].setdefault(rid, []).append(r["payload"] or {})
    log.info(
        "data_os_load sources=%s pipelines=%s datasets=%s syncs=%s schedules=%s",
        len(out["connectors"]),
        len(out["pipelines"]),
        len(out["datasets"]),
        len(out["syncs"]),
        len(out["schedules"]),
    )
    return out


def boot_data_os(wave_ext_module: Any) -> None:
    """Reset Data OS runtime cache; request scope performs the lazy load."""
    wave_ext_module._connectors.clear()
    wave_ext_module._pipelines.clear()
    wave_ext_module._datasets.clear()
    wave_ext_module._syncs.clear()
    wave_ext_module._schedules.clear()
    wave_ext_module._dataset_history.clear()
    loaded_scopes = getattr(wave_ext_module, "_data_os_loaded_scopes", None)
    if loaded_scopes is not None:
        loaded_scopes.clear()
    cleared = purge_demo_surface(wave_ext_module)
    log.info(
        "data_os_booted mode=lazy_scoped demo_surface_cleared=%s physical_delete=deferred",
        cleared.get("removed"),
    )
