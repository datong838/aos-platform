#!/usr/bin/env python3
"""Bootstrap only the dedicated empty current-code preview database."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from psycopg import connect
from psycopg.rows import dict_row
from sqlalchemy import URL


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
TARGET = "aos_current_preview_20260927"
CONTEXT = "colima-aos-extension"
CONTAINER = "aos-a0v-recovery-pg"
HEAD = "a0v_106"


class BootstrapBlocked(RuntimeError):
    pass


def _connection_parameters() -> dict[str, object]:
    raw = subprocess.check_output([
        "docker", "--context", CONTEXT, "inspect", "--format", "{{json .}}", CONTAINER,
    ], text=True, stderr=subprocess.DEVNULL, timeout=15)
    item = json.loads(raw)
    if item.get("Name") != "/" + CONTAINER or not (item.get("State") or {}).get("Running"):
        raise BootstrapBlocked("DATABASE_CONTAINER_DRIFT")
    bindings = ((item.get("NetworkSettings") or {}).get("Ports") or {}).get("5432/tcp")
    if not isinstance(bindings, list) or len(bindings) != 1 or bindings[0].get("HostIp") not in {"127.0.0.1", "localhost"}:
        raise BootstrapBlocked("DATABASE_BINDING_DRIFT")
    env = dict(entry.split("=", 1) for entry in (item.get("Config") or {}).get("Env", []) if "=" in entry)
    if not env.get("POSTGRES_USER") or not env.get("POSTGRES_PASSWORD"):
        raise BootstrapBlocked("DATABASE_CREDENTIAL_UNAVAILABLE")
    return {"host": "127.0.0.1", "port": int(bindings[0]["HostPort"]),
            "user": env["POSTGRES_USER"], "password": env["POSTGRES_PASSWORD"],
            "dbname": TARGET}


def inspect_target() -> dict[str, object]:
    parameters = _connection_parameters()
    with connect(**parameters, row_factory=dict_row) as conn:
        identity = conn.execute("SELECT current_database() AS db,current_user AS role").fetchone()
        if identity["db"] != TARGET:
            raise BootstrapBlocked("DATABASE_TARGET_DRIFT")
        tables = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
        version = None
        if any(row["tablename"] == "alembic_version" for row in tables):
            versions = conn.execute("SELECT version_num FROM alembic_version").fetchall()
            version = [row["version_num"] for row in versions]
        return {"database": TARGET, "role": identity["role"], "tableCount": len(tables),
                "versions": version}


def migrate(*, state: Path, resume_after_assetintegration: bool = False) -> dict[str, object]:
    state = state.resolve()
    if state == ROOT or state.is_relative_to(ROOT):
        raise BootstrapBlocked("STATE_MUST_BE_OUTSIDE_REPOSITORY")
    before = inspect_target()
    if resume_after_assetintegration:
        intent = state / "migration-intent.json"
        if (not intent.is_file() or (state / "migration-result.json").exists()
                or before["versions"] != ["228assetintegration"]):
            raise BootstrapBlocked("RESUME_BOUNDARY_NOT_EXACT")
        fields = json.loads(intent.read_text(encoding="utf-8"))
        if {key: fields.get(key) for key in ("database", "from", "to")} != {
            "database": TARGET, "from": "empty", "to": HEAD,
        }:
            raise BootstrapBlocked("RESUME_INTENT_DRIFT")
    else:
        if state.exists() or before["tableCount"] != 0 or before["versions"] is not None:
            raise BootstrapBlocked("TARGET_NOT_EMPTY_RECONCILE_READ_ONLY")
        state.mkdir(mode=0o700)
        if stat.S_IMODE(state.stat().st_mode) != 0o700:
            raise BootstrapBlocked("STATE_PERMISSIONS_INVALID")
        (state / "migration-intent.json").write_text(json.dumps({
            "database": TARGET, "from": "empty", "to": HEAD,
            "createdAt": datetime.now(UTC).isoformat(),
        }, sort_keys=True) + "\n", encoding="utf-8")

    from alembic import command
    from alembic.config import Config
    from aos_api import twa_pg
    from aos_api.data_os_store import ensure_data_os_schema
    from aos_api.db import init_schema, connect as app_connect
    from aos_api.tenant_catalog import ensure_tenant_catalog_schema

    parameters = _connection_parameters()
    url = URL.create("postgresql", username=str(parameters["user"]),
                     password=str(parameters["password"]), host=str(parameters["host"]),
                     port=int(parameters["port"]), database=TARGET)
    previous_url = os.environ.get("AOS_DATABASE_URL")
    previous_twa = os.environ.get("AOS_TWA_STORE")
    os.environ["AOS_DOTENV_DISABLED"] = "1"
    os.environ["AOS_DATABASE_URL"] = url.render_as_string(hide_password=False)
    os.environ["AOS_TWA_STORE"] = "pg"
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
    try:
        twa_pg.clear_mode_cache()
        if not resume_after_assetintegration:
            command.upgrade(cfg, "228assetintegration")
        # First attempt failed before init_schema; it is idempotent and required
        # for legacy tables adopted by TI-3 (for example object_lifecycle).
        init_schema()
        ensure_tenant_catalog_schema()
        twa_pg.ensure_schema()
        with app_connect() as conn:
            conn.execute("INSERT INTO twa_org(id,name) VALUES ('org-org','栖月汇隔离预览') ON CONFLICT(id) DO NOTHING")
            conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES ('org-org','dev-project','当前源码隔离预览') ON CONFLICT(org_id,project_id) DO NOTHING")
            conn.commit()
        from aos_api.canvas_config import ensure_schema as ensure_canvas_schema
        from aos_api.module_deployments import ensure_schema as ensure_deployment_schema
        from aos_api.module_events import ensure_events_schema
        from aos_api.module_interfaces import ensure_schema as ensure_interface_schema
        from aos_api.module_queries import ensure_schema as ensure_query_schema
        from aos_api.module_store import ensure_module_schema
        from aos_api.module_variables import ensure_schema as ensure_variable_schema
        from aos_api.routers.drafts import ensure_draft_schema
        from aos_api.widget_instances import ensure_schema as ensure_widget_schema
        for ensure in (ensure_module_schema, ensure_canvas_schema, ensure_deployment_schema,
                       ensure_events_schema, ensure_interface_schema, ensure_query_schema,
                       ensure_variable_schema, ensure_widget_schema, ensure_draft_schema):
            ensure()
        command.upgrade(cfg, "head")
        ensure_data_os_schema()
    finally:
        if previous_url is None:
            os.environ.pop("AOS_DATABASE_URL", None)
        else:
            os.environ["AOS_DATABASE_URL"] = previous_url
        if previous_twa is None:
            os.environ.pop("AOS_TWA_STORE", None)
        else:
            os.environ["AOS_TWA_STORE"] = previous_twa
        twa_pg.clear_mode_cache()
    after = inspect_target()
    if after["versions"] != [HEAD]:
        raise BootstrapBlocked("MIGRATION_HEAD_MISMATCH")
    result = {"outcome": "CURRENT_PREVIEW_SCHEMA_READY", "before": before, "after": after,
              "externalBusinessEffects": 0}
    (state / "migration-result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    import sys
    sys.path.insert(0, str(API_ROOT))
    os.environ["AOS_DOTENV_DISABLED"] = "1"
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument("--resume-after-assetintegration", action="store_true")
    parser.add_argument("--state-dir", type=Path)
    args = parser.parse_args()
    if (args.migrate or args.resume_after_assetintegration) and args.state_dir is None:
        raise BootstrapBlocked("STATE_DIR_REQUIRED")
    result = (migrate(state=args.state_dir,
                      resume_after_assetintegration=args.resume_after_assetintegration)
              if args.migrate or args.resume_after_assetintegration else inspect_target())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Driver exceptions may embed the DSN; never print their message.
        original = getattr(exc, "orig", exc)
        diagnostic = getattr(original, "diag", None)
        print(json.dumps({"outcome": "SAFE_BLOCKED", "errorType": type(exc).__name__,
                          "sqlstate": getattr(original, "sqlstate", None),
                          "databaseError": getattr(diagnostic, "message_primary", None)}))
        raise SystemExit(2) from None
