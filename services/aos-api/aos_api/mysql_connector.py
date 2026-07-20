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


def get_settings(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    load_dotenv()
    host = _env("AOS_MYSQL_HOST")
    if not host:
        wsl = _wsl_ip()
        host = wsl if wsl else "127.0.0.1"
    s: dict[str, Any] = {
        "host": host,
        "port": int(_env("AOS_MYSQL_PORT", "3307") or "3307"),
        "user": _env("AOS_MYSQL_USER", "aos_src"),
        "password": _env("AOS_MYSQL_PASSWORD", _env("MYSQL_PASSWORD", "aos_dev_only_change_me")),
        "database": _env("AOS_MYSQL_DATABASE", "aos_src"),
        "table": _env("AOS_MYSQL_TABLE", "src_work_orders"),
    }
    if overrides:
        for k in ("host", "port", "user", "password", "database", "table"):
            v = overrides.get(k)
            if v is None or v == "":
                continue
            s[k] = int(v) if k == "port" else v
    return s


def _connect(
    settings: dict[str, Any] | None = None,
    *,
    read_timeout: int = 10,
    write_timeout: int = 10,
):
    import pymysql

    s = settings or get_settings()
    return pymysql.connect(
        host=s["host"],
        port=int(s["port"]),
        user=s["user"],
        password=s["password"],
        database=s["database"],
        charset="utf8mb4",
        use_unicode=True,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        read_timeout=read_timeout,
        write_timeout=write_timeout,
    )


def probe(
    *,
    limit: int = 5,
    object_type: str = "WorkOrder",
    table: str | None = None,
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
) -> dict[str, Any]:
    """Pull rows from MySQL. ``limit<=0`` means full table (digital twin ingest)."""
    if disabled():
        return {
            "ok": True,
            "mode": "disabled",
            "mappedObjectType": object_type,
            "rowsSampled": 0,
            "tableRowCount": 0,
            "passwordRef": "env:AOS_MYSQL_PASSWORD",
        }
    overrides = {
        "table": table,
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }
    s = get_settings({k: v for k, v in overrides.items() if v is not None})
    full = int(limit or 0) <= 0
    # 全量孪生可能较慢；探活采样仍用短超时
    rt = 120 if full else 10
    try:
        with _connect(s, read_timeout=rt, write_timeout=rt) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                cur.fetchone()
                cur.execute(f"SELECT COUNT(*) AS c FROM `{s['table']}`")
                count_row = cur.fetchone() or {}
                table_row_count = int(count_row.get("c") or 0)
                if full:
                    cur.execute(f"SELECT * FROM `{s['table']}`")
                else:
                    cur.execute(f"SELECT * FROM `{s['table']}` LIMIT %s", (int(limit),))
                rows = list(cur.fetchall())
        log.info(
            "mysql_probe ok host=%s table=%s rows=%s full=%s tableRowCount=%s",
            s["host"],
            s["table"],
            len(rows),
            full,
            table_row_count,
        )
        return {
            "ok": True,
            "mode": "live",
            "host": s["host"],
            "port": s["port"],
            "database": s["database"],
            "table": s["table"],
            "mappedObjectType": object_type,
            "rowsSampled": len(rows),
            "tableRowCount": table_row_count,
            "fullTable": full,
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
            "table": s.get("table"),
            "database": s.get("database"),
        }


def map_row(
    row: dict[str, Any],
    mapping: dict[str, str] | None = None,
    *,
    include_all: bool = False,
    id_field: str | None = None,
) -> tuple[str, dict[str, Any]]:
    if include_all:
        pk = id_field or "id"
        object_id = str(row.get(pk) or row.get("id") or row.get("ID") or f"row-{abs(hash(str(row))) % 10_000_000}")
        props = {str(k): v for k, v in row.items()}
        return object_id, props
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


# Canonical Dev seed titles (must match deploy/dev/mysql/init.sql)
_SOURCE_TITLE_SEED = (
    ("mysql-wo-001", "MySQL供数-巡检单", "open", "DC-East", "P1"),
    ("mysql-wo-002", "MySQL供数-备件", "in_progress", "DC-West", "P0"),
)


def repair_mysql_source_titles() -> dict[str, Any]:
    """36 §7 · Fix double-encoded Dev source titles (idempotent)."""
    if disabled():
        return {"ok": True, "mode": "disabled", "updated": 0}
    s = get_settings()
    # 仅对 Dev 工单源表尝试；其它表（如 ns_order）跳过，避免污染孪生库
    if (s.get("table") or "") != "src_work_orders":
        return {"ok": True, "mode": "skipped", "updated": 0, "table": s.get("table")}
    try:
        with _connect(s) as conn:
            with conn.cursor() as cur:
                cur.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
                updated = 0
                for oid, title, status, site, priority in _SOURCE_TITLE_SEED:
                    cur.execute(
                        f"""
                        INSERT INTO `{s['table']}` (id, title, status, site, priority)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                          title=VALUES(title),
                          status=VALUES(status),
                          site=VALUES(site),
                          priority=VALUES(priority)
                        """,
                        (oid, title, status, site, priority),
                    )
                    updated += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
            conn.commit()
        log.info("mysql_source_titles_repaired updated=%s", updated)
        return {"ok": True, "mode": "live", "updated": updated, "table": s["table"]}
    except Exception as exc:  # noqa: BLE001
        log.warning("mysql_source_titles_repair_fail err=%s", exc)
        return {"ok": False, "mode": "error", "detail": str(exc), "updated": 0}


def ensure_object_type(object_type: str, *, display_name: str | None = None) -> bool:
    """Ensure meta_object_type row exists (FK for obj_instance). Returns True if created."""
    from aos_api.db import connect

    name = display_name or object_type
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM meta_object_type WHERE id=%s", (object_type,)
        ).fetchone()
        if exists:
            return False
        conn.execute(
            """
            INSERT INTO meta_object_type (id, name, description, published, properties)
            VALUES (%s,%s,%s,%s,%s::jsonb)
            """,
            (
                object_type,
                name,
                f"auto-created by jdbc ingest for {object_type}",
                False,
                "[]",
            ),
        )
        conn.commit()
    log.info("mysql_ingest_auto_ot created=%s", object_type)
    return True


def ingest(
    *,
    object_type: str = "WorkOrder",
    limit: int = 0,
    mapping: dict[str, str] | None = None,
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
) -> dict[str, Any]:
    """T4.6 + T4.7: pull MySQL rows → upsert obj_instance."""
    from aos_api.db import connect

    if disabled():
        return {"ok": False, "mode": "disabled", "written": 0}

    # 仅 Dev 工单源表做标题修复；孪生多表 ingest 跳过，避免误连/误写
    eff_table = table or get_settings().get("table")
    if eff_table == "src_work_orders":
        repair_mysql_source_titles()
    probed = probe(
        limit=limit,
        object_type=object_type,
        table=table,
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )
    if not probed.get("ok") or probed.get("mode") != "live":
        return {**probed, "written": 0}

    ot_created = False
    if auto_create_object_type:
        ot_created = ensure_object_type(object_type)

    written = 0
    ids: list[str] = []
    with connect() as conn:
        for row in probed.get("sample") or []:
            oid, props = map_row(row, mapping, include_all=include_all, id_field=id_field)
            if org_id:
                props["_aosOrgId"] = org_id
            if project_id:
                props["_aosProjectId"] = project_id
            conn.execute(
                """
                INSERT INTO obj_instance (object_type, object_id, props)
                VALUES (%s,%s,%s::jsonb)
                ON CONFLICT (object_type, object_id)
                DO UPDATE SET props = EXCLUDED.props
                """,
                (object_type, oid, json.dumps(props, ensure_ascii=False, default=str)),
            )
            written += 1
            ids.append(oid)
        conn.commit()
    log.info("mysql_ingest written=%s objectType=%s table=%s", written, object_type, probed.get("table"))
    return {
        "ok": True,
        "mode": "live",
        "written": written,
        "objectType": object_type,
        "objectIds": ids,
        "tableRowCount": probed.get("tableRowCount"),
        "fullTable": probed.get("fullTable"),
        "mapping": mapping or DEFAULT_MAPPING,
        "includeAll": include_all,
        "idField": id_field,
        "autoCreateObjectType": auto_create_object_type,
        "objectTypeCreated": ot_created,
        "orgId": org_id,
        "projectId": project_id,
        "passwordRef": "env:AOS_MYSQL_PASSWORD",
        "source": {
            "host": probed.get("host"),
            "database": probed.get("database"),
            "table": probed.get("table"),
        },
    }
