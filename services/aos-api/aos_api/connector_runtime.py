"""Connector Host runtime dispatch — scheme 100 · 对齐 20 §3.1 / 97 · 201m REST."""
from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib import error as urlerror
from urllib import request as urlrequest

from aos_api.connector_registry import assert_type_installed, list_connector_plugins
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.connector_runtime")

Handler = Callable[..., dict[str, Any]]


def _rest_url() -> str:
    return (os.environ.get("AOS_REST_CONNECTOR_URL") or "").strip()


def _rest_token() -> str:
    return (os.environ.get("AOS_REST_CONNECTOR_TOKEN") or "").strip()


def rest_mock_mode() -> bool:
    return (os.environ.get("AOS_REST_CONNECTOR_MOCK") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def rest_configured() -> bool:
    return bool(_rest_url()) or rest_mock_mode()


def _rest_http_get() -> dict[str, Any]:
    if rest_mock_mode() and not _rest_url():
        return {
            "ok": True,
            "mode": "mock",
            "status": 200,
            "url": "mock://rest",
            "sample": [{"id": "rest-mock-1", "title": "REST mock", "status": "open"}],
            "pluginId": "rest-generic",
        }
    url = _rest_url()
    if not url:
        raise ApiError(
            code="CONNECTOR_STUB",
            message="rest-generic requires AOS_REST_CONNECTOR_URL or AOS_REST_CONNECTOR_MOCK=1",
            status_code=501,
            details={"pluginId": "rest-generic", "op": "probe"},
        )
    headers = {"Accept": "application/json"}
    tok = _rest_token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urlrequest.Request(url, headers=headers, method="GET")
    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            status = int(resp.status)
            raw = resp.read().decode("utf-8", errors="replace")[:2000]
    except (urlerror.URLError, TimeoutError, ValueError) as exc:
        raise ApiError(
            code="CONNECTOR_UPSTREAM",
            message=f"rest upstream failed: {exc}",
            status_code=502,
        ) from None
    sample: Any = None
    try:
        sample = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        sample = {"raw": raw[:200]}
    return {
        "ok": 200 <= status < 300,
        "mode": "http",
        "status": status,
        "url": url,
        "sample": sample,
        "pluginId": "rest-generic",
    }


def _rest_health(**_: Any) -> dict[str, Any]:
    if not rest_configured():
        raise ApiError(
            code="CONNECTOR_STUB",
            message="rest-generic requires AOS_REST_CONNECTOR_URL or AOS_REST_CONNECTOR_MOCK=1",
            status_code=501,
            details={"pluginId": "rest-generic", "op": "health"},
        )
    out = _rest_http_get()
    return {
        "ok": out.get("ok"),
        "mode": out.get("mode") or "http",
        "configured": True,
        "url": out.get("url"),
        "status": out.get("status"),
        "pluginId": "rest-generic",
    }


def _rest_probe(*, limit: int = 5, **_: Any) -> dict[str, Any]:
    _ = limit
    if not rest_configured():
        raise ApiError(
            code="CONNECTOR_STUB",
            message="rest-generic requires AOS_REST_CONNECTOR_URL or AOS_REST_CONNECTOR_MOCK=1",
            status_code=501,
            details={"pluginId": "rest-generic", "op": "probe"},
        )
    return _rest_http_get()


def _rest_ingest(
    *,
    object_type: str = "WorkOrder",
    limit: int = 100,
    mapping: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """217m — REST sample → upsert obj_instance."""
    import uuid

    from aos_api.db import connect

    if not rest_configured():
        raise ApiError(
            code="CONNECTOR_STUB",
            message="rest-generic requires AOS_REST_CONNECTOR_URL or AOS_REST_CONNECTOR_MOCK=1",
            status_code=501,
            details={"pluginId": "rest-generic", "op": "ingest"},
        )
    probed = _rest_http_get()
    raw = probed.get("sample")
    rows: list[dict[str, Any]] = []
    if isinstance(raw, list):
        rows = [r for r in raw if isinstance(r, dict)][: max(1, int(limit or 100))]
    elif isinstance(raw, dict):
        rows = [raw]
    if rest_mock_mode() and not rows:
        rows = [{"id": f"rest-mock-{uuid.uuid4().hex[:8]}", "title": "REST mock ingest", "status": "open"}]

    written = 0
    ids: list[str] = []
    with connect() as conn:
        for row in rows:
            oid = str(row.get("id") or row.get("object_id") or f"rest-{uuid.uuid4().hex[:8]}")
            props = {k: v for k, v in row.items() if k not in {"id", "object_id"}}
            if mapping:
                props = {mapping.get(k, k): v for k, v in props.items()}
            conn.execute(
                """
                INSERT INTO obj_instance (object_type, object_id, props)
                VALUES (%s,%s,%s::jsonb)
                ON CONFLICT (object_type, object_id)
                DO UPDATE SET props = EXCLUDED.props
                """,
                (object_type, oid, json.dumps(props, ensure_ascii=False)),
            )
            written += 1
            ids.append(oid)
        conn.commit()
    log.info("rest_ingest written=%s objectType=%s mode=%s", written, object_type, probed.get("mode"))
    return {
        "ok": True,
        "mode": probed.get("mode") or "http",
        "written": written,
        "objectType": object_type,
        "objectIds": ids,
        "pluginId": "rest-generic",
        "source": {"url": probed.get("url")},
    }


def _mysql_probe(
    *,
    limit: int = 5,
    object_type: str = "WorkOrder",
    table: str | None = None,
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    from aos_api.mysql_connector import probe

    return probe(
        limit=limit,
        object_type=object_type,
        table=table,
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )


def _mysql_ingest(
    *,
    object_type: str = "WorkOrder",
    limit: int = 0,
    mapping: dict[str, Any] | None = None,
    table: str | None = None,
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
    include_all: bool = False,
    id_field: str | None = None,
    auto_create_object_type: bool = False,
    org_id: str | None = None,
    project_id: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    from aos_api.mysql_connector import ingest

    return ingest(
        object_type=object_type,
        limit=limit,
        mapping=mapping,
        table=table,
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        include_all=include_all,
        id_field=id_field,
        auto_create_object_type=auto_create_object_type,
        org_id=org_id,
        project_id=project_id,
    )


def _mysql_health(**_: Any) -> dict[str, Any]:
    r = _mysql_probe(limit=1)
    return {
        "ok": r.get("ok"),
        "mode": r.get("mode"),
        "host": r.get("host"),
        "port": r.get("port"),
        "database": r.get("database"),
        "table": r.get("table"),
        "rowsSampled": r.get("rowsSampled"),
        "passwordRef": r.get("passwordRef"),
        "driver": r.get("driver"),
        "detail": r.get("detail"),
        "pluginId": "jdbc-mysql",
    }


def _file_local_root() -> str:
    return (os.environ.get("AOS_FILE_LOCAL_ROOT") or "").strip()


def file_local_mock_mode() -> bool:
    return (os.environ.get("AOS_FILE_LOCAL_MOCK") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def file_local_configured() -> bool:
    if file_local_mock_mode():
        return True
    root = _file_local_root()
    return bool(root) and os.path.isdir(root)


def _file_local_probe(*, limit: int = 5, **_: Any) -> dict[str, Any]:
    if file_local_mock_mode() and not (_file_local_root() and os.path.isdir(_file_local_root())):
        return {
            "ok": True,
            "mode": "mock",
            "root": "mock://file-local",
            "sample": ["mock-a.txt", "mock-b.csv"],
            "pluginId": "file-local",
        }
    root = _file_local_root()
    if not root or not os.path.isdir(root):
        raise ApiError(
            code="CONNECTOR_STUB",
            message="file-local requires AOS_FILE_LOCAL_ROOT or AOS_FILE_LOCAL_MOCK=1",
            status_code=501,
            details={"pluginId": "file-local", "op": "probe"},
        )
    names: list[str] = []
    try:
        for name in sorted(os.listdir(root)):
            if name.startswith("."):
                continue
            names.append(name)
            if len(names) >= max(1, int(limit or 5)):
                break
    except OSError as exc:
        raise ApiError(
            code="CONNECTOR_UPSTREAM",
            message=f"file-local list failed: {exc}",
            status_code=502,
        ) from None
    return {
        "ok": True,
        "mode": "local",
        "root": root,
        "sample": names,
        "pluginId": "file-local",
    }


def _file_local_health(**_: Any) -> dict[str, Any]:
    if not file_local_configured():
        raise ApiError(
            code="CONNECTOR_STUB",
            message="file-local requires AOS_FILE_LOCAL_ROOT or AOS_FILE_LOCAL_MOCK=1",
            status_code=501,
            details={"pluginId": "file-local", "op": "health"},
        )
    out = _file_local_probe(limit=3)
    return {
        "ok": True,
        "mode": out.get("mode") or "local",
        "configured": True,
        "root": out.get("root"),
        "sampleCount": len(out.get("sample") or []),
        "pluginId": "file-local",
    }


def _file_local_ingest(
    *,
    object_type: str = "WorkOrder",
    limit: int = 100,
    mapping: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """217m — file names → upsert obj_instance."""
    import uuid

    from aos_api.db import connect

    if not file_local_configured():
        raise ApiError(
            code="CONNECTOR_STUB",
            message="file-local requires AOS_FILE_LOCAL_ROOT or AOS_FILE_LOCAL_MOCK=1",
            status_code=501,
            details={"pluginId": "file-local", "op": "ingest"},
        )
    _ = mapping
    probed = _file_local_probe(limit=limit)
    names = [str(n) for n in (probed.get("sample") or [])][: max(1, int(limit or 100))]
    if not names and file_local_mock_mode():
        names = [f"mock-{uuid.uuid4().hex[:6]}.txt"]

    written = 0
    ids: list[str] = []
    with connect() as conn:
        for name in names:
            oid = f"file-{name}".replace("/", "_")[:64]
            props = {"title": name, "filename": name, "source": "file-local", "status": "open"}
            conn.execute(
                """
                INSERT INTO obj_instance (object_type, object_id, props)
                VALUES (%s,%s,%s::jsonb)
                ON CONFLICT (object_type, object_id)
                DO UPDATE SET props = EXCLUDED.props
                """,
                (object_type, oid, json.dumps(props, ensure_ascii=False)),
            )
            written += 1
            ids.append(oid)
        conn.commit()
    log.info("file_local_ingest written=%s mode=%s", written, probed.get("mode"))
    return {
        "ok": True,
        "mode": probed.get("mode") or "local",
        "written": written,
        "objectType": object_type,
        "objectIds": ids,
        "pluginId": "file-local",
        "source": {"root": probed.get("root")},
    }


def _file_object_store_health(**_: Any) -> dict[str, Any]:
    from aos_api import object_store as ostore

    cfg = ostore.get_config()
    if not cfg.enabled:
        raise ApiError(
            code="CONNECTOR_STUB",
            message="file-object-store requires S3/MinIO config (not AOS_S3_DISABLED)",
            status_code=501,
            details={"pluginId": "file-object-store", "op": "health"},
        )
    probe = ostore.health_probe()
    return {
        "ok": bool(probe.get("ok")),
        "mode": "s3",
        "configured": True,
        "endpoint": probe.get("endpoint"),
        "bucket": probe.get("bucket"),
        "detail": probe.get("detail"),
        "pluginId": "file-object-store",
    }


def _file_object_store_probe(*, limit: int = 5, **_: Any) -> dict[str, Any]:
    from aos_api import object_store as ostore

    cfg = ostore.get_config()
    if not cfg.enabled:
        raise ApiError(
            code="CONNECTOR_STUB",
            message="file-object-store requires S3/MinIO config (not AOS_S3_DISABLED)",
            status_code=501,
            details={"pluginId": "file-object-store", "op": "probe"},
        )
    try:
        keys = ostore.list_keys_with_prefix(prefix="", cfg=cfg)[: max(1, int(limit or 5))]
    except Exception as exc:  # noqa: BLE001
        raise ApiError(
            code="CONNECTOR_UPSTREAM",
            message=f"object-store list failed: {exc}",
            status_code=502,
        ) from None
    return {
        "ok": True,
        "mode": "s3",
        "sample": keys,
        "bucket": cfg.bucket,
        "pluginId": "file-object-store",
    }


def _pg_health(**_: Any) -> dict[str, Any]:
    from aos_api import pg_connector as pg

    if not pg.configured():
        raise ApiError(
            code="CONNECTOR_STUB",
            message="jdbc-postgres requires AOS_PG_CONNECTOR_DSN|HOST or AOS_PG_CONNECTOR_MOCK=1",
            status_code=501,
            details={"pluginId": "jdbc-postgres", "op": "health"},
        )
    return pg.health()


def _pg_probe(*, limit: int = 5, object_type: str = "WorkOrder", **_: Any) -> dict[str, Any]:
    from aos_api import pg_connector as pg

    if not pg.configured():
        raise ApiError(
            code="CONNECTOR_STUB",
            message="jdbc-postgres requires AOS_PG_CONNECTOR_DSN|HOST or AOS_PG_CONNECTOR_MOCK=1",
            status_code=501,
            details={"pluginId": "jdbc-postgres", "op": "probe"},
        )
    return pg.probe(limit=limit, object_type=object_type)


def _pg_ingest(
    *,
    object_type: str = "WorkOrder",
    limit: int = 100,
    mapping: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    from aos_api import pg_connector as pg

    if not pg.configured():
        raise ApiError(
            code="CONNECTOR_STUB",
            message="jdbc-postgres requires AOS_PG_CONNECTOR_DSN|HOST or AOS_PG_CONNECTOR_MOCK=1",
            status_code=501,
            details={"pluginId": "jdbc-postgres", "op": "ingest"},
        )
    return pg.ingest(object_type=object_type, limit=limit, mapping=mapping)


def _mssql_health(**_: Any) -> dict[str, Any]:
    from aos_api import mssql_connector as ms

    if not ms.configured():
        raise ApiError(
            code="CONNECTOR_STUB",
            message="jdbc-sqlserver requires AOS_MSSQL_CONNECTOR_HOST|DSN or AOS_MSSQL_CONNECTOR_MOCK=1",
            status_code=501,
            details={"pluginId": "jdbc-sqlserver", "op": "health"},
        )
    return ms.health()


def _mssql_probe(*, limit: int = 5, object_type: str = "WorkOrder", **_: Any) -> dict[str, Any]:
    from aos_api import mssql_connector as ms

    if not ms.configured():
        raise ApiError(
            code="CONNECTOR_STUB",
            message="jdbc-sqlserver requires AOS_MSSQL_CONNECTOR_HOST|DSN or AOS_MSSQL_CONNECTOR_MOCK=1",
            status_code=501,
            details={"pluginId": "jdbc-sqlserver", "op": "probe"},
        )
    return ms.probe(limit=limit, object_type=object_type)


def _mssql_ingest(
    *,
    object_type: str = "WorkOrder",
    limit: int = 100,
    mapping: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    from aos_api import mssql_connector as ms

    if not ms.configured():
        raise ApiError(
            code="CONNECTOR_STUB",
            message="jdbc-sqlserver requires AOS_MSSQL_CONNECTOR_HOST|DSN or AOS_MSSQL_CONNECTOR_MOCK=1",
            status_code=501,
            details={"pluginId": "jdbc-sqlserver", "op": "ingest"},
        )
    return ms.ingest(object_type=object_type, limit=limit, mapping=mapping)


# pluginId → op → handler（新增 live 连接器只加表项，不改 Host 路由）
_HANDLERS: dict[str, dict[str, Handler]] = {
    "jdbc-mysql": {
        "health": _mysql_health,
        "probe": _mysql_probe,
        "ingest": _mysql_ingest,
    },
    "rest-generic": {
        "health": _rest_health,
        "probe": _rest_probe,
        "ingest": _rest_ingest,
    },
    "file-local": {
        "health": _file_local_health,
        "probe": _file_local_probe,
        "ingest": _file_local_ingest,
    },
    "file-object-store": {
        "health": _file_object_store_health,
        "probe": _file_object_store_probe,
    },
    "jdbc-postgres": {
        "health": _pg_health,
        "probe": _pg_probe,
        "ingest": _pg_ingest,
    },
    "jdbc-sqlserver": {
        "health": _mssql_health,
        "probe": _mssql_probe,
        "ingest": _mssql_ingest,
    },
}

# 旧厂商路径别名
_ALIASES = {
    "mysql": "jdbc-mysql",
}


def resolve_plugin_id(raw: str) -> str:
    return _ALIASES.get((raw or "").strip(), (raw or "").strip())


def _plugin_meta(plugin_id: str) -> dict[str, Any] | None:
    for it in list_connector_plugins().get("items") or []:
        if it.get("id") == plugin_id:
            return it
    return None


def dispatch(plugin_id_raw: str, op: str, **kwargs: Any) -> dict[str, Any]:
    """按已安装插件分发 health/probe/ingest。"""
    plugin_id = resolve_plugin_id(plugin_id_raw)
    try:
        plugin_id = assert_type_installed(plugin_id)
    except KeyError as exc:
        raise ApiError(code="UNKNOWN_CONNECTOR", message=str(exc), status_code=400) from None
    except PermissionError as exc:
        raise ApiError(code="PLUGIN_NOT_INSTALLED", message=str(exc), status_code=400) from None

    meta = _plugin_meta(plugin_id) or {}
    handlers = _HANDLERS.get(plugin_id)
    if not handlers or op not in handlers:
        runtime = meta.get("runtime") or "stub"
        raise ApiError(
            code="CONNECTOR_STUB",
            message=f"connector plugin {plugin_id} has no live {op} handler (runtime={runtime})",
            status_code=501,
            details={"pluginId": plugin_id, "op": op, "runtime": runtime},
        )
    log.info("connector_dispatch plugin=%s op=%s", plugin_id, op)
    out = handlers[op](**kwargs)
    if isinstance(out, dict) and "pluginId" not in out:
        out = {**out, "pluginId": plugin_id}
    return out
