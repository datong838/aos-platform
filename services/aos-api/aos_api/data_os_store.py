"""Data OS metadata store — Source/Pipeline/Dataset/Sync/Schedule (185w)."""
from __future__ import annotations

import json
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger

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
        if rid in wave_ext_module._datasets:
            del wave_ext_module._datasets[rid]
            removed["datasets"].append(rid)
        wave_ext_module._dataset_history.pop(rid, None)
    for sid in DEMO_SURFACE_IDS["syncs"]:
        if sid in wave_ext_module._syncs:
            del wave_ext_module._syncs[sid]
            removed["syncs"].append(sid)
    for sch in DEMO_SURFACE_IDS["schedules"]:
        if sch in wave_ext_module._schedules:
            del wave_ext_module._schedules[sch]
            removed["schedules"].append(sch)
    before = len(wave_ext_module._dlq)
    wave_ext_module._dlq[:] = [
        d
        for d in wave_ext_module._dlq
        if not (isinstance(d, dict) and str(d.get("id", "")).startswith(_DEMO_DLQ_PREFIX))
    ]
    removed["dlq"] = before - len(wave_ext_module._dlq)
    log.info("data_os_demo_purged %s", removed)
    return {"ok": True, "removed": removed}


def ensure_data_os_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_source (
              id TEXT PRIMARY KEY,
              type TEXT NOT NULL DEFAULT 'file',
              status TEXT NOT NULL DEFAULT 'registered',
              plugin_id TEXT,
              org_id TEXT NOT NULL DEFAULT 'dev-org',
              project_id TEXT NOT NULL DEFAULT 'dev-project',
              props JSONB NOT NULL DEFAULT '{}'::jsonb,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_pipeline (
              id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL,
              target TEXT NOT NULL DEFAULT 'dataset',
              dataset_rid TEXT,
              name TEXT,
              object_type_hint TEXT,
              last_build JSONB NOT NULL DEFAULT '{}'::jsonb,
              props JSONB NOT NULL DEFAULT '{}'::jsonb,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_dataset (
              rid TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              display_name TEXT,
              pipeline_id TEXT,
              source_id TEXT,
              status TEXT NOT NULL DEFAULT 'READY',
              object_type_hint TEXT,
              created_at DOUBLE PRECISION,
              updated_at DOUBLE PRECISION,
              props JSONB NOT NULL DEFAULT '{}'::jsonb
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_sync (
              id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'SUCCEEDED',
              rows_synced INTEGER NOT NULL DEFAULT 0,
              started_at DOUBLE PRECISION,
              finished_at DOUBLE PRECISION,
              props JSONB NOT NULL DEFAULT '{}'::jsonb,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_schedule (
              id TEXT PRIMARY KEY,
              cron TEXT NOT NULL DEFAULT '0 * * * *',
              pipeline_id TEXT,
              enabled BOOLEAN NOT NULL DEFAULT TRUE,
              name TEXT,
              ingest JSONB,
              last_run JSONB,
              org_id TEXT,
              project_id TEXT,
              props JSONB NOT NULL DEFAULT '{}'::jsonb,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_dataset_history (
              id BIGSERIAL PRIMARY KEY,
              dataset_rid TEXT NOT NULL,
              payload JSONB NOT NULL DEFAULT '{}'::jsonb,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS phase5_pipeline_graph (
              pipeline_id TEXT PRIMARY KEY,
              payload JSONB NOT NULL,
              revision BIGINT NOT NULL DEFAULT 1,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()
    _schema_ready = True
    log.info("data_os_schema_ready")


def persist_source(item: dict[str, Any]) -> None:
    ensure_data_os_schema()
    props = {k: v for k, v in item.items() if k not in {"id", "type", "status", "pluginId", "orgId", "projectId"}}
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO meta_source (id, type, status, plugin_id, org_id, project_id, props, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,NOW())
            ON CONFLICT (id) DO UPDATE SET
              type=EXCLUDED.type, status=EXCLUDED.status, plugin_id=EXCLUDED.plugin_id,
              org_id=EXCLUDED.org_id, project_id=EXCLUDED.project_id, props=EXCLUDED.props,
              updated_at=NOW()
            """,
            (
                item["id"],
                item.get("type") or "file",
                item.get("status") or "registered",
                item.get("pluginId"),
                item.get("orgId") or "dev-org",
                item.get("projectId") or "dev-project",
                json.dumps(props, ensure_ascii=False, default=str),
            ),
        )
        conn.commit()


def persist_pipeline(item: dict[str, Any]) -> None:
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
    if item.get("orgId"):
        props["orgId"] = item["orgId"]
    if item.get("projectId"):
        props["projectId"] = item["projectId"]
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO meta_pipeline
              (id, source_id, target, dataset_rid, name, object_type_hint, last_build, props, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,NOW())
            ON CONFLICT (id) DO UPDATE SET
              source_id=EXCLUDED.source_id, target=EXCLUDED.target, dataset_rid=EXCLUDED.dataset_rid,
              name=EXCLUDED.name, object_type_hint=EXCLUDED.object_type_hint,
              last_build=EXCLUDED.last_build, props=EXCLUDED.props, updated_at=NOW()
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
            ),
        )
        conn.commit()


def persist_phase5_pipeline_graph(payload: dict[str, Any]) -> dict[str, Any]:
    """Atomically persist one complete Phase5 graph and return the committed snapshot."""
    ensure_data_os_schema()
    pipeline_id = str(payload.get("pipeline_id") or "").strip()
    if not pipeline_id:
        raise ValueError("pipeline graph requires pipeline_id")
    node_ids = {str(node.get("id") or "") for node in payload.get("nodes") or []}
    edge_ids = {str(edge.get("id") or "") for edge in payload.get("edges") or []}
    encoded = json.dumps(payload, ensure_ascii=False, default=str)
    with connect() as conn:
        # Serialize graph writers across processes so nested node/edge ids keep one owner.
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (228301,))
        rows = conn.execute(
            "SELECT pipeline_id, payload FROM phase5_pipeline_graph WHERE pipeline_id<>%s FOR UPDATE",
            (pipeline_id,),
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
            INSERT INTO phase5_pipeline_graph (pipeline_id, payload, revision, updated_at)
            VALUES (%s,%s::jsonb,1,NOW())
            ON CONFLICT (pipeline_id) DO UPDATE SET
              payload=EXCLUDED.payload,
              revision=phase5_pipeline_graph.revision+1,
              updated_at=NOW()
            RETURNING payload, revision
            """,
            (pipeline_id, encoded),
        ).fetchone()
        conn.commit()
    committed = dict(row["payload"] or {})
    committed["revision"] = int(row["revision"])
    committed["persisted"] = True
    committed["demo"] = False
    return committed


def load_phase5_pipeline_graph(pipeline_id: str) -> dict[str, Any] | None:
    """Load one committed graph snapshot from the shared metadata store."""
    ensure_data_os_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT payload, revision FROM phase5_pipeline_graph WHERE pipeline_id=%s",
            (pipeline_id,),
        ).fetchone()
    if row is None:
        return None
    payload = dict(row["payload"] or {})
    payload["revision"] = int(row["revision"])
    payload["persisted"] = True
    payload["demo"] = False
    return payload


def delete_phase5_pipeline_graph(pipeline_id: str) -> None:
    """Delete one explicitly identified graph; never truncate shared graph data."""
    ensure_data_os_schema()
    with connect() as conn:
        conn.execute("DELETE FROM phase5_pipeline_graph WHERE pipeline_id=%s", (pipeline_id,))
        conn.commit()


def persist_dataset(item: dict[str, Any]) -> None:
    ensure_data_os_schema()
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
    if item.get("orgId"):
        props["orgId"] = item["orgId"]
    if item.get("projectId"):
        props["projectId"] = item["projectId"]
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO meta_dataset
              (rid, name, display_name, pipeline_id, source_id, status, object_type_hint,
               created_at, updated_at, props)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (rid) DO UPDATE SET
              name=EXCLUDED.name, display_name=EXCLUDED.display_name,
              pipeline_id=EXCLUDED.pipeline_id, source_id=EXCLUDED.source_id,
              status=EXCLUDED.status, object_type_hint=EXCLUDED.object_type_hint,
              updated_at=EXCLUDED.updated_at, props=EXCLUDED.props
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
            ),
        )
        conn.commit()


def persist_sync(item: dict[str, Any]) -> None:
    ensure_data_os_schema()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO meta_sync
              (id, source_id, status, rows_synced, started_at, finished_at, props, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,'{}'::jsonb,NOW())
            ON CONFLICT (id) DO UPDATE SET
              source_id=EXCLUDED.source_id, status=EXCLUDED.status,
              rows_synced=EXCLUDED.rows_synced, started_at=EXCLUDED.started_at,
              finished_at=EXCLUDED.finished_at, updated_at=NOW()
            """,
            (
                item["id"],
                item.get("sourceId") or "",
                item.get("status") or "SUCCEEDED",
                int(item.get("rowsSynced") or 0),
                item.get("startedAt"),
                item.get("finishedAt"),
            ),
        )
        conn.commit()


def persist_schedule(item: dict[str, Any]) -> None:
    ensure_data_os_schema()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO meta_schedule
              (id, cron, pipeline_id, enabled, name, ingest, last_run, org_id, project_id, props, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,'{}'::jsonb,NOW())
            ON CONFLICT (id) DO UPDATE SET
              cron=EXCLUDED.cron, pipeline_id=EXCLUDED.pipeline_id, enabled=EXCLUDED.enabled,
              name=EXCLUDED.name, ingest=EXCLUDED.ingest, last_run=EXCLUDED.last_run,
              org_id=EXCLUDED.org_id, project_id=EXCLUDED.project_id, updated_at=NOW()
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
                item.get("orgId"),
                item.get("projectId"),
            ),
        )
        conn.commit()


def persist_dataset_history(dataset_rid: str, entries: list[dict[str, Any]]) -> None:
    ensure_data_os_schema()
    with connect() as conn:
        conn.execute("DELETE FROM meta_dataset_history WHERE dataset_rid=%s", (dataset_rid,))
        for e in entries:
            conn.execute(
                """
                INSERT INTO meta_dataset_history (dataset_rid, payload)
                VALUES (%s,%s::jsonb)
                """,
                (dataset_rid, json.dumps(e, ensure_ascii=False, default=str)),
            )
        conn.commit()


def delete_source(source_id: str) -> None:
    ensure_data_os_schema()
    with connect() as conn:
        conn.execute("DELETE FROM meta_source WHERE id=%s", (source_id,))
        conn.commit()


def delete_pipeline(pipeline_id: str) -> None:
    ensure_data_os_schema()
    with connect() as conn:
        conn.execute("DELETE FROM meta_pipeline WHERE id=%s", (pipeline_id,))
        conn.commit()


def delete_dataset(rid: str) -> None:
    ensure_data_os_schema()
    with connect() as conn:
        conn.execute("DELETE FROM meta_dataset_history WHERE dataset_rid=%s", (rid,))
        conn.execute("DELETE FROM meta_dataset WHERE rid=%s", (rid,))
        conn.commit()


def delete_sync(sync_id: str) -> None:
    ensure_data_os_schema()
    with connect() as conn:
        conn.execute("DELETE FROM meta_sync WHERE id=%s", (sync_id,))
        conn.commit()


def delete_schedule(schedule_id: str) -> None:
    ensure_data_os_schema()
    with connect() as conn:
        conn.execute("DELETE FROM meta_schedule WHERE id=%s", (schedule_id,))
        conn.commit()


def load_all() -> dict[str, Any]:
    """Return dicts suitable for wave_ext memory maps."""
    ensure_data_os_schema()
    out: dict[str, Any] = {
        "connectors": {},
        "pipelines": {},
        "datasets": {},
        "syncs": {},
        "schedules": {},
        "dataset_history": {},
    }
    with connect() as conn:
        for r in conn.execute("SELECT * FROM meta_source").fetchall():
            item = dict(r.get("props") or {})
            item.update(
                {
                    "id": r["id"],
                    "type": r["type"],
                    "status": r["status"],
                    "pluginId": r["plugin_id"],
                    "orgId": r["org_id"],
                    "projectId": r["project_id"],
                }
            )
            out["connectors"][r["id"]] = item
        for r in conn.execute("SELECT * FROM meta_pipeline").fetchall():
            props = dict(r.get("props") or {})
            item = {
                "id": r["id"],
                "sourceId": r["source_id"],
                "target": r["target"],
                "datasetRid": r["dataset_rid"],
                "name": r["name"],
                "objectTypeHint": r["object_type_hint"],
                "lastBuild": r["last_build"] or {},
                "orgId": props.pop("orgId", None),
                "projectId": props.pop("projectId", None),
            }
            item.update(props)
            out["pipelines"][r["id"]] = item
        for r in conn.execute("SELECT * FROM meta_dataset").fetchall():
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
                "orgId": props.pop("orgId", None),
                "projectId": props.pop("projectId", None),
            }
            item.update(props)
            out["datasets"][r["rid"]] = item
        for r in conn.execute("SELECT * FROM meta_sync").fetchall():
            out["syncs"][r["id"]] = {
                "id": r["id"],
                "sourceId": r["source_id"],
                "status": r["status"],
                "rowsSynced": r["rows_synced"],
                "startedAt": r["started_at"],
                "finishedAt": r["finished_at"],
            }
        for r in conn.execute("SELECT * FROM meta_schedule").fetchall():
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
            "SELECT dataset_rid, payload FROM meta_dataset_history ORDER BY id"
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
    """Load into wave_ext maps; strip demo surface unless AOS_DEMO_DATA_SEED=1."""
    ensure_data_os_schema()
    data = load_all()
    wave_ext_module._connectors.clear()
    wave_ext_module._connectors.update(data["connectors"])
    wave_ext_module._pipelines.clear()
    wave_ext_module._pipelines.update(data["pipelines"])
    wave_ext_module._datasets.clear()
    wave_ext_module._datasets.update(data["datasets"])
    wave_ext_module._syncs.clear()
    wave_ext_module._syncs.update(data["syncs"])
    wave_ext_module._schedules.clear()
    wave_ext_module._schedules.update(data["schedules"])
    wave_ext_module._dataset_history.clear()
    wave_ext_module._dataset_history.update(data["dataset_history"])
    # Always purge known demo ids from runtime + PG (product surface)
    cleared = purge_demo_surface(wave_ext_module)
    for sid in cleared.get("removed", {}).get("sources") or []:
        delete_source(sid)
    for pid in cleared.get("removed", {}).get("pipelines") or []:
        delete_pipeline(pid)
    for rid in cleared.get("removed", {}).get("datasets") or []:
        delete_dataset(rid)
    for sid in cleared.get("removed", {}).get("syncs") or []:
        delete_sync(sid)
    for sch in cleared.get("removed", {}).get("schedules") or []:
        delete_schedule(sch)
    log.info("data_os_booted demo_cleared=%s", cleared.get("removed"))
