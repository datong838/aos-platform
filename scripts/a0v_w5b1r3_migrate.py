#!/usr/bin/env python3
"""One-shot, journaled local migration of the narrow retired-dispatch lock."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

from a0v_formal_text_model_renewal import database_connect
import a0v_w5b1r3_enable_retirement as retirement_context

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5b1r3-migration")
FUNCTION = "extension_dispatch_retired_read_lock_a0v_092(uuid,uuid)"


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    fd = os.open(STATE / (name + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, ensure_ascii=False, indent=2, default=str)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def preflight():
    retirement_context.retirement.preflight()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute("""SELECT (SELECT version_num FROM alembic_version) AS version,
          to_regprocedure(%s) IS NOT NULL AS function_exists,
          current_user AS database_user""", ("public." + FUNCTION,)).fetchone()
    if row["version"] != "a0v_091" or row["function_exists"] or row["database_user"] != "aos_app":
        raise ValueError("W5B1R3_MIGRATION_PREFLIGHT_DRIFT")
    return {"outcome": "W5B1R3_MIGRATION_PREFLIGHT_GREEN", "from": row["version"],
            "to": "a0v_092", "database": "aos_meta_head", "businessRuns": 0}


def apply():
    if STATE.exists():
        raise ValueError("W5B1R3_MIGRATION_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", before)
    filename = ROOT / "services/aos-api/alembic/versions/a0v_092_retired_dispatch_read_lock.py"
    spec = importlib.util.spec_from_file_location("a0v_092", filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    with database_connect("aos_meta_head")() as conn:
        current = conn.execute("SELECT version_num FROM alembic_version FOR UPDATE").fetchone()
        if current is None or current["version_num"] != "a0v_091":
            raise ValueError("W5B1R3_MIGRATION_HEAD_CHANGED")
        if conn.execute("SELECT to_regprocedure(%s) AS ref", ("public." + FUNCTION,)).fetchone()["ref"]:
            raise ValueError("W5B1R3_MIGRATION_FUNCTION_ALREADY_EXISTS")
        module.op = SimpleNamespace(execute=conn.execute)
        module.upgrade()
        updated = conn.execute("UPDATE alembic_version SET version_num='a0v_092' "
                               "WHERE version_num='a0v_091'")
        if updated.rowcount != 1:
            raise ValueError("W5B1R3_MIGRATION_VERSION_WRITE_FAILED")
    result = audit()
    _write("result", result)
    return result


def audit():
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute("""SELECT (SELECT version_num FROM alembic_version) AS version,
          to_regprocedure(%s) IS NOT NULL AS function_exists,
          has_function_privilege('aos_runtime',%s,'EXECUTE') AS runtime_execute,
          has_function_privilege('aos_extension_maintainer',%s,'EXECUTE') AS maintainer_execute,
          has_table_privilege('aos_runtime','public.extension_dispatch_cutover_operation','UPDATE')
            AS runtime_base_update""", ("public." + FUNCTION,) * 3).fetchone()
    if (row["version"] != "a0v_092" or not row["function_exists"]
            or not row["runtime_execute"] or row["maintainer_execute"]
            or row["runtime_base_update"]):
        raise ValueError("W5B1R3_MIGRATION_AUDIT_NOT_GREEN")
    return {"outcome": "W5B1R3_MIGRATION_GREEN", "version": "a0v_092",
            "runtimeExecute": True, "maintainerExecute": False, "runtimeBaseUpdate": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "apply", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False))
