"""T4.6 MySQL source connector (PyMySQL = JDBC-equivalent protocol face for Dev)."""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from aos_api.env_load import load_dotenv
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.mysql")

load_dotenv()

DEFAULT_MAPPING = {
    "id": "objectId",
    "title": "title",
    "status": "status",
    "site": "site",
    "priority": "priority",
}


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def disabled() -> bool:
    return _env("AOS_MYSQL_DISABLED", "").lower() in {"1", "true", "yes"}


def _wsl_ip() -> str:
    ip = _env("AOS_WSL_IP")
    if ip:
        return ip
    try:
        out = subprocess.check_output(
            ["wsl", "-d", "Ubuntu", "-e", "hostname", "-I"],
            text=True,
            timeout=3,
        )
        return out.strip().split()[0]
    except Exception:  # noqa: BLE001
        return ""


def get_settings() -> dict[str, Any]:
    load_dotenv()
    host = _env("AOS_MYSQL_HOST")
    if not host:
        wsl = _wsl_ip()
        host = wsl if wsl else "127.0.0.1"
    return {
        "host": host,
        "port": int(_env("AOS_MYSQL_PORT", "3307") or "3307"),
        "user": _env("AOS_MYSQL_USER", "aos_src"),
        "password": _env("AOS_MYSQL_PASSWORD", _env("MYSQL_PASSWORD", "aos_dev_only_change_me")),
        "database": _env("AOS_MYSQL_DATABASE", "aos_src"),
        "table": _env("AOS_MYSQL_TABLE", "src_work_orders"),
    }


def _connect(settings: dict[str, Any] | None = None):
    import pymysql

    s = settings or get_settings()
    return pymysql.connect(
        host=s["host"],
        port=int(s["port"]),
        user=s["user"],
        password=s["password"],
        database=s["database"],
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
    )


def probe(*, limit: int = 5, object_type: str = "WorkOrder") -> dict[str, Any]:
    if disabled():
        return {
            "ok": True,
            "mode": "disabled",
            "mappedObjectType": object_type,
            "rowsSampled": 0,
            "passwordRef": "env:AOS_MYSQL_PASSWORD",
        }
    s = get_settings()
    try:
        with _connect(s) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                cur.fetchone()
                cur.execute(f"SELECT * FROM `{s['table']}` LIMIT %s", (limit,))
                rows = list(cur.fetchall())
        log.info("mysql_probe ok host=%s rows=%s", s["host"], len(rows))
        return {
            "ok": True,
            "mode": "live",
            "host": s["host"],
            "port": s["port"],
            "database": s["database"],
            "table": s["table"],
            "mappedObjectType": object_type,
            "rowsSampled": len(rows),
            "sample": rows,
            "passwordRef": "env:AOS_MYSQL_PASSWORD",
            "driver": "pymysql",
            "note": "JDBC-equivalent protocol face; swap Java worker without API change",
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("mysql_probe_fail err=%s", exc)
        return {
            "ok": False,
            "mode": "error",
            "host": s["host"],
            "port": s["port"],
            "detail": str(exc),
            "passwordRef": "env:AOS_MYSQL_PASSWORD",
            "mappedObjectType": object_type,
            "rowsSampled": 0,
        }


def map_row(row: dict[str, Any], mapping: dict[str, str] | None = None) -> tuple[str, dict[str, Any]]:
    m = mapping or DEFAULT_MAPPING
    props: dict[str, Any] = {}
    object_id = None
    for src, dst in m.items():
        if src not in row:
            continue
        if dst == "objectId":
            object_id = str(row[src])
        else:
            props[dst] = row[src]
    if not object_id:
        object_id = str(row.get("id") or row.get("ID") or f"row-{abs(hash(str(row))) % 10_000_000}")
    return object_id, props


def ingest(
    *,
    object_type: str = "WorkOrder",
    limit: int = 100,
    mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """T4.6 + T4.7: pull MySQL rows → upsert obj_instance."""
    from aos_api.db import connect

    if disabled():
        return {"ok": False, "mode": "disabled", "written": 0}

    probed = probe(limit=limit, object_type=object_type)
    if not probed.get("ok") or probed.get("mode") != "live":
        return {**probed, "written": 0}

    written = 0
    ids: list[str] = []
    with connect() as conn:
        for row in probed.get("sample") or []:
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
    log.info("mysql_ingest written=%s objectType=%s", written, object_type)
    return {
        "ok": True,
        "mode": "live",
        "written": written,
        "objectType": object_type,
        "objectIds": ids,
        "mapping": mapping or DEFAULT_MAPPING,
        "passwordRef": "env:AOS_MYSQL_PASSWORD",
        "source": {
            "host": probed.get("host"),
            "database": probed.get("database"),
            "table": probed.get("table"),
        },
    }
