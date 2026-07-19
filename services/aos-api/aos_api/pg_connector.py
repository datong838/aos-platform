"""205m / 213m — JDBC PostgreSQL connector probe + ingest (psycopg · optional env)."""
from __future__ import annotations

import json
import os
import uuid
from typing import Any
from urllib.parse import urlparse

from aos_api.env_load import load_dotenv
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.pg-connector")
load_dotenv()


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def mock_mode() -> bool:
    return _env("AOS_PG_CONNECTOR_MOCK", "").lower() in {"1", "true", "yes"}


def configured() -> bool:
    if mock_mode():
        return True
    return bool(_env("AOS_PG_CONNECTOR_DSN") or _env("AOS_PG_CONNECTOR_HOST"))


def get_settings() -> dict[str, Any]:
    load_dotenv()
    dsn = _env("AOS_PG_CONNECTOR_DSN")
    if dsn:
        return {"dsn": dsn, "table": _env("AOS_PG_CONNECTOR_TABLE", "")}
    return {
        "host": _env("AOS_PG_CONNECTOR_HOST", "127.0.0.1"),
        "port": int(_env("AOS_PG_CONNECTOR_PORT", "5432") or "5432"),
        "user": _env("AOS_PG_CONNECTOR_USER", "aos"),
        "password": _env("AOS_PG_CONNECTOR_PASSWORD", ""),
        "database": _env("AOS_PG_CONNECTOR_DATABASE", "aos"),
        "table": _env("AOS_PG_CONNECTOR_TABLE", ""),
        "dsn": "",
    }


def probe(*, limit: int = 5, object_type: str = "WorkOrder") -> dict[str, Any]:
    if not configured():
        return {
            "ok": False,
            "mode": "stub",
            "detail": "not_configured",
            "pluginId": "jdbc-postgres",
        }
    if mock_mode():
        return {
            "ok": True,
            "mode": "mock",
            "mappedObjectType": object_type,
            "rowsSampled": 0,
            "sample": [],
            "driver": "psycopg-mock",
            "pluginId": "jdbc-postgres",
            "passwordRef": "env:AOS_PG_CONNECTOR_PASSWORD",
        }
    s = get_settings()
    try:
        import psycopg

        if s.get("dsn"):
            conn = psycopg.connect(s["dsn"], connect_timeout=5)
        else:
            conn = psycopg.connect(
                host=s["host"],
                port=int(s["port"]),
                user=s["user"],
                password=s["password"],
                dbname=s["database"],
                connect_timeout=5,
            )
        rows: list[dict[str, Any]] = []
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                cur.fetchone()
                table = (s.get("table") or "").strip()
                if table and table.replace("_", "").isalnum():
                    cur.execute(f'SELECT * FROM "{table}" LIMIT %s', (max(1, int(limit)),))
                    cols = [d.name for d in cur.description] if cur.description else []
                    for r in cur.fetchall():
                        rows.append(dict(zip(cols, r, strict=False)))
        host_disp = s.get("host") or urlparse(s.get("dsn") or "").hostname or "dsn"
        log.info("pg_probe ok host=%s rows=%s", host_disp, len(rows))
        return {
            "ok": True,
            "mode": "live",
            "host": host_disp,
            "mappedObjectType": object_type,
            "rowsSampled": len(rows),
            "sample": rows,
            "driver": "psycopg",
            "pluginId": "jdbc-postgres",
            "passwordRef": "env:AOS_PG_CONNECTOR_PASSWORD",
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("pg_probe_fail err=%s", exc)
        return {
            "ok": False,
            "mode": "error",
            "detail": str(exc),
            "pluginId": "jdbc-postgres",
            "mappedObjectType": object_type,
            "rowsSampled": 0,
            "passwordRef": "env:AOS_PG_CONNECTOR_PASSWORD",
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
        "pluginId": "jdbc-postgres",
        "passwordRef": r.get("passwordRef"),
    }


DEFAULT_MAPPING = {
    "id": "id",
    "title": "title",
    "status": "status",
}


def map_row(row: dict[str, Any], mapping: dict[str, str] | None = None) -> tuple[str, dict[str, Any]]:
    m = mapping or DEFAULT_MAPPING
    oid = str(row.get(m.get("id", "id")) or row.get("id") or row.get("object_id") or "")
    if not oid:
        oid = f"pg-{abs(hash(json.dumps(row, sort_keys=True, default=str))) % 10_000_000}"
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
    """213m — pull PG rows (or mock) → upsert obj_instance."""
    from aos_api.db import connect

    if not configured():
        return {
            "ok": False,
            "mode": "stub",
            "detail": "not_configured",
            "written": 0,
            "pluginId": "jdbc-postgres",
        }

    if mock_mode():
        oid = f"mock-pg-{uuid.uuid4().hex[:8]}"
        props = {"title": "PG mock ingest", "status": "open", "source": "jdbc-postgres-mock"}
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
        log.info("pg_ingest mock written=1 objectType=%s", object_type)
        return {
            "ok": True,
            "mode": "mock",
            "written": 1,
            "objectType": object_type,
            "objectIds": [oid],
            "mapping": mapping or DEFAULT_MAPPING,
            "passwordRef": "env:AOS_PG_CONNECTOR_PASSWORD",
            "pluginId": "jdbc-postgres",
            "source": {"mode": "mock"},
        }

    probed = probe(limit=limit, object_type=object_type)
    if not probed.get("ok") or probed.get("mode") != "live":
        return {**probed, "written": 0, "pluginId": "jdbc-postgres"}

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
    log.info("pg_ingest written=%s objectType=%s", written, object_type)
    return {
        "ok": True,
        "mode": "live",
        "written": written,
        "objectType": object_type,
        "objectIds": ids,
        "mapping": mapping or DEFAULT_MAPPING,
        "passwordRef": "env:AOS_PG_CONNECTOR_PASSWORD",
        "pluginId": "jdbc-postgres",
        "source": {"host": probed.get("host"), "mode": "live"},
    }
