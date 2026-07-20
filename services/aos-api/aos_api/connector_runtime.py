"""Connector Host runtime dispatch — scheme 100 · 对齐 20 §3.1 / 97."""
from __future__ import annotations

from typing import Any, Callable

from aos_api.connector_registry import assert_type_installed, list_connector_plugins
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.connector_runtime")

Handler = Callable[..., dict[str, Any]]


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
    limit: int = 100,
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


# pluginId → op → handler（新增 live 连接器只加表项，不改 Host 路由）
_HANDLERS: dict[str, dict[str, Handler]] = {
    "jdbc-mysql": {
        "health": _mysql_health,
        "probe": _mysql_probe,
        "ingest": _mysql_ingest,
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
