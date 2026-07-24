"""208m — JDBC SQL Server connector probe (optional env / mock)."""
from __future__ import annotations

import os
from typing import Any

from aos_api.env_load import load_dotenv
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.mssql-connector")
load_dotenv()


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def mock_mode() -> bool:
    return _env("AOS_MSSQL_CONNECTOR_MOCK", "").lower() in {"1", "true", "yes"}


def configured() -> bool:
    if mock_mode():
        return True
    return bool(
        _env("AOS_MSSQL_CONNECTOR_DSN")
        or _env("AOS_MSSQL_CONNECTOR_HOST")
        or _env("AOS_SQLSERVER_HOST")
    )


def probe(*, limit: int = 5, object_type: str = "WorkOrder") -> dict[str, Any]:
    if not configured():
        return {
            "ok": False,
            "mode": "stub",
            "detail": "not_configured",
            "pluginId": "jdbc-sqlserver",
        }
    if mock_mode():
        return {
            "ok": True,
            "mode": "mock",
            "mappedObjectType": object_type,
            "rowsSampled": 0,
            "sample": [],
            "driver": "mssql-mock",
            "pluginId": "jdbc-sqlserver",
            "passwordRef": "env:AOS_MSSQL_CONNECTOR_PASSWORD",
        }
    # Live path: require pymssql/pyodbc when available; else honest error mode
    host = _env("AOS_MSSQL_CONNECTOR_HOST") or _env("AOS_SQLSERVER_HOST") or "127.0.0.1"
    try:
        import pymssql  # type: ignore

        conn = pymssql.connect(
            server=host,
            user=_env("AOS_MSSQL_CONNECTOR_USER", "sa"),
            password=_env("AOS_MSSQL_CONNECTOR_PASSWORD", ""),
            database=_env("AOS_MSSQL_CONNECTOR_DATABASE", "master"),
            port=int(_env("AOS_MSSQL_CONNECTOR_PORT", "1433") or "1433"),
            login_timeout=5,
            timeout=5,
        )
        with conn.cursor(as_dict=True) as cur:
            cur.execute("SELECT 1 AS ok")
            cur.fetchone()
        conn.close()
        log.info("mssql_probe ok host=%s", host)
        return {
            "ok": True,
            "mode": "live",
            "host": host,
            "mappedObjectType": object_type,
            "rowsSampled": 0,
            "sample": [],
            "driver": "pymssql",
            "pluginId": "jdbc-sqlserver",
            "passwordRef": "env:AOS_MSSQL_CONNECTOR_PASSWORD",
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("mssql_probe_fail err=%s", exc)
        return {
            "ok": False,
            "mode": "error",
            "host": host,
            "detail": str(exc),
            "pluginId": "jdbc-sqlserver",
            "mappedObjectType": object_type,
            "rowsSampled": 0,
            "passwordRef": "env:AOS_MSSQL_CONNECTOR_PASSWORD",
        }


def health(**_: Any) -> dict[str, Any]:
    r = probe(limit=1)
    return {
        "ok": bool(r.get("ok")),
        "mode": r.get("mode"),
        "configured": configured(),
        "detail": r.get("detail"),
        "host": r.get("host"),
        "driver": r.get("driver"),
        "pluginId": "jdbc-sqlserver",
        "passwordRef": r.get("passwordRef"),
    }


DEFAULT_MAPPING = {
    "id": "id",
    "title": "title",
    "status": "status",
}


def map_row(row: dict[str, Any], mapping: dict[str, str] | None = None) -> tuple[str, dict[str, Any]]:
    import json

    m = mapping or DEFAULT_MAPPING
    oid = str(row.get(m.get("id", "id")) or row.get("id") or row.get("object_id") or "")
    if not oid:
        oid = f"mssql-{abs(hash(json.dumps(row, sort_keys=True, default=str))) % 10_000_000}"
    props: dict[str, Any] = {}
    for src_key, dst_key in (m or {}).items():
        if src_key == "id":
            continue
        if src_key in row:
            props[dst_key] = row[src_key]
    for k, v in row.items():
        if k not in props and k != m.get("id", "id"):
            props.setdefault(k, v)
    return oid, props


def ingest(
    *,
    object_type: str = "WorkOrder",
    limit: int = 100,
    mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """216m — mock or live sample → upsert obj_instance."""
    import json
    import uuid

    from aos_api.db import connect

    if not configured():
        return {
            "ok": False,
            "mode": "stub",
            "detail": "not_configured",
            "written": 0,
            "pluginId": "jdbc-sqlserver",
        }

    if mock_mode():
        oid = f"mock-mssql-{uuid.uuid4().hex[:8]}"
        props = {"title": "MSSQL mock ingest", "status": "open", "source": "jdbc-sqlserver-mock"}
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO obj_instance (object_type, object_id, props)
                VALUES (%s,%s,%s::jsonb)
                ON CONFLICT (object_type, object_id)
                DO UPDATE SET props = EXCLUDED.props
                """,
                (object_type, oid, json.dumps(props, ensure_ascii=False)),
            )
            conn.commit()
        log.info("mssql_ingest mock written=1 objectType=%s", object_type)
        return {
            "ok": True,
            "mode": "mock",
            "written": 1,
            "objectType": object_type,
            "objectIds": [oid],
            "mapping": mapping or DEFAULT_MAPPING,
            "passwordRef": "env:AOS_MSSQL_CONNECTOR_PASSWORD",
            "pluginId": "jdbc-sqlserver",
            "source": {"mode": "mock"},
        }

    probed = probe(limit=limit, object_type=object_type)
    if not probed.get("ok") or probed.get("mode") != "live":
        return {**probed, "written": 0, "pluginId": "jdbc-sqlserver"}

    written = 0
    ids: list[str] = []
    with connect() as conn:
        for row in probed.get("sample") or []:
            if not isinstance(row, dict):
                continue
            oid, props = map_row(row, mapping)
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
    log.info("mssql_ingest written=%s objectType=%s", written, object_type)
    return {
        "ok": True,
        "mode": "live",
        "written": written,
        "objectType": object_type,
        "objectIds": ids,
        "mapping": mapping or DEFAULT_MAPPING,
        "passwordRef": "env:AOS_MSSQL_CONNECTOR_PASSWORD",
        "pluginId": "jdbc-sqlserver",
        "source": {"host": probed.get("host"), "mode": "live"},
    }
