#!/usr/bin/env python3
"""Retained local a0v_038 -> a0v_050 upgrade, verified on a restored clone first."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "natural_chain_upgrade_storage", Path(__file__).with_name("a0v_controlled_source_claim_deploy.py")
)
storage = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(storage)

SOURCE, TARGET = "a0v_038", "a0v_050"
CLONE = "aos_natural_chain_upgrade_20260915_test"
TASK = "A0V-NATURAL-CHAIN-MAIN-UPGRADE-20260915"
STATE = ROOT.parent / ".aos-recovery-20260915/state/natural-chain-main-upgrade"
FILES = tuple(f"a0v_{revision:03d}_{name}.py" for revision, name in (
    (39, "product_event_schedule_schema"),
    (40, "product_event_schedule_write"),
    (41, "product_event_authority_lock"),
    (42, "product_event_control_receipt"),
    (43, "product_event_origin"),
    (44, "event_control_dispatch_group"),
    (45, "snapshot_group_journal"),
    (46, "snapshot_group_relationships"),
    (47, "snapshot_group_link_command"),
    (48, "snapshot_group_retirement"),
    (49, "data_requirement_current_lock"),
    (50, "data_requirement_outbox_completion"),
))
CHAIN = [f"a0v_{revision:03d}" for revision in range(50, 38, -1)]
BUSINESS_TABLES = (
    "meta_source", "data_source_configuration_revision", "meta_pipeline", "meta_schedule",
    "meta_schedule_run", "meta_dataset", "bundle_installation", "bundle_installation_revision",
    "extension_runtime_configuration", "extension_runtime_binding", "extension_runtime_operation",
    "extension_runtime_resource_lease", "extension_operation_dispatch_binding",
    "pipeline_source_selection_revision", "pipeline_runtime_control_revision",
    "pipeline_controlled_source_claim", "pipeline_schedule_control_binding",
    "ecommerce_investigation_schedule_policy_head", "ecommerce_investigation_schedule_policy_revision",
    "ecommerce_investigation_case_head", "ecommerce_investigation_case_revision",
    "ecommerce_investigation_run", "ecommerce_investigation_run_state_head", "aip_task",
    "aip_task_run", "data_requirement_head", "data_requirement_revision",
    "data_requirement_outbox", "data_requirement_outbox_delivery", "data_fulfillment_receipt",
    "ecommerce_growth_runtime_command_receipt", "ecom_object", "ecom_link", "ecom_ingest_receipt",
)
NEW_TABLES = (
    "ecommerce_product_event_control_receipt", "ecommerce_product_event_origin",
    "pipeline_snapshot_group_claim", "pipeline_snapshot_group_member", "pipeline_snapshot_group_input",
    "pipeline_snapshot_group_relationship", "pipeline_snapshot_group_link_command",
    "pipeline_snapshot_group_retirement",
)
RUNTIME_FUNCTIONS = (
    "ecommerce_product_event_policy_put_a0v_040",
    "ecommerce_product_event_lock_a0v_041",
    "data_requirement_lock_current_a0v_049",
    "data_requirement_outbox_complete_a0v_050",
    "data_requirement_outbox_reconcile_completed_a0v_050",
)

storage.CLONE = CLONE
storage.FILES = FILES


def require_lease() -> None:
    path = ROOT.parent / "docs/palantier/AOS项目开发上下文/memory/leases.json"
    leases = json.loads(path.read_text(encoding="utf-8"))["leases"]
    found = [item for item in leases if item.get("task_id") == TASK]
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    if (
        len(found) != 1
        or found[0].get("owner") != "m1"
        or found[0].get("status") != "ACTIVE"
        or datetime.fromisoformat(found[0]["lease_expires_at"]) <= datetime.now(timezone.utc)
        or branch != "m1"
    ):
        raise ValueError("current natural-chain migration lease required")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return "sha256:" + value.hexdigest()


def migration_hashes() -> dict[str, str]:
    directory = ROOT / "services/aos-api/alembic/versions"
    return {name: digest(directory / name) for name in FILES}


def executor_hashes() -> dict[str, str]:
    return {Path(__file__).name: digest(Path(__file__)), Path(storage.__file__).name: digest(Path(storage.__file__))}


def protected_write(path: Path, value: dict) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _canonical_expression(table: str) -> str:
    if table == "data_requirement_outbox_delivery":
        return "to_jsonb(t)-ARRAY['completion_fulfillment_ref','completion_analysis_ref']"
    return "to_jsonb(t)"


def fingerprint(conn) -> dict[str, dict]:
    from psycopg import sql

    result = {}
    for table in BUSINESS_TABLES:
        expression = sql.SQL(_canonical_expression(table))
        query = sql.SQL(
            "SELECT count(*) AS count,md5(string_agg(md5(({})::text),'' ORDER BY md5(({})::text))) AS digest "
            "FROM {} t"
        ).format(expression, expression, sql.Identifier("public", table))
        result[table] = dict(conn.execute(query).fetchone())
    return result


def quiet_state(conn) -> dict:
    runtime = conn.execute(
        """SELECT count(*) AS total,
                  count(*) FILTER(WHERE enabled OR NOT operation_fence) AS actionable
             FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s""",
        ("org-org", "dev-project"),
    ).fetchone()
    schedules = conn.execute(
        """SELECT count(*) AS n FROM meta_schedule_run
            WHERE org_id=%s AND project_id=%s AND executor_stopped IS NOT TRUE""",
        ("org-org", "dev-project"),
    ).fetchone()["n"]
    outbox = conn.execute(
        """SELECT count(*) AS n FROM data_requirement_outbox_delivery
            WHERE org_id=%s AND project_id=%s AND state IN ('claimed','unknown')""",
        ("org-org", "dev-project"),
    ).fetchone()["n"]
    dispatch = conn.execute(
        "SELECT count(*) AS n FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s",
        ("org-org", "dev-project"),
    ).fetchone()["n"]
    canary = conn.execute(
        "SELECT count(*) AS n FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s",
        ("dev-org", "dev-project"),
    ).fetchone()["n"]
    result = dict(runtimeBindings=runtime["total"], actionableBindings=runtime["actionable"],
                  unstoppedSchedules=schedules, unresolvedOutbox=outbox,
                  dispatchRoutes=dispatch, canaryDispatchRoutes=canary)
    if result["actionableBindings"] or schedules or outbox or dispatch != 9 or canary:
        raise ValueError("main runtime is not at the exact quiet migration boundary")
    return result


def verify_schema(conn) -> dict:
    from psycopg import sql

    tables = {}
    for table in NEW_TABLES:
        row = conn.execute(
            """SELECT c.relrowsecurity,c.relforcerowsecurity,
                      has_table_privilege('aos_runtime',c.oid,'SELECT') AS can_select,
                      has_table_privilege('aos_runtime',c.oid,'INSERT') AS can_insert,
                      has_table_privilege('aos_runtime',c.oid,'UPDATE,DELETE,TRUNCATE') AS can_mutate
                 FROM pg_class c WHERE c.oid=to_regclass(%s)""",
            ("public." + table,),
        ).fetchone()
        count = conn.execute(sql.SQL("SELECT count(*) AS n FROM {}").format(
            sql.Identifier("public", table))).fetchone()["n"]
        triggers = conn.execute(
            "SELECT count(*) AS n FROM pg_trigger WHERE tgrelid=to_regclass(%s) AND NOT tgisinternal",
            ("public." + table,),
        ).fetchone()["n"]
        if (
            row is None or row["relrowsecurity"] is not True or row["relforcerowsecurity"] is not True
            or row["can_select"] is not True or row["can_insert"] is not True or row["can_mutate"] is True
            or count != 0 or triggers < 1
        ):
            raise ValueError("new immutable snapshot table contract differs")
        tables[table] = dict(rows=count, immutableTriggers=triggers, forceRls=True)

    functions = {}
    for name in RUNTIME_FUNCTIONS:
        rows = conn.execute(
            """SELECT p.prosecdef,
                      has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_allowed,
                      EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
                             WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_allowed
                 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                WHERE n.nspname='public' AND p.proname=%s""", (name,),
        ).fetchall()
        if len(rows) != 1 or dict(rows[0]) != dict(prosecdef=True, runtime_allowed=True, public_allowed=False):
            raise ValueError("restricted migration function contract differs")
        functions[name] = "runtime-only-security-definer"

    columns = conn.execute(
        """SELECT attname FROM pg_attribute
            WHERE attrelid='public.data_requirement_outbox_delivery'::regclass
              AND attname IN ('completion_fulfillment_ref','completion_analysis_ref')
              AND attnum>0 AND NOT attisdropped ORDER BY attname"""
    ).fetchall()
    constraint = conn.execute(
        """SELECT count(*) AS n FROM pg_constraint
            WHERE conrelid='public.data_requirement_outbox_delivery'::regclass
              AND conname='ck_data_requirement_outbox_completion_refs_a0v_050'"""
    ).fetchone()["n"]
    pair = conn.execute(
        """SELECT count(*) AS n FROM pg_constraint
            WHERE conrelid='public.ecommerce_investigation_schedule_policy_revision'::regclass
              AND conname='ck_ecommerce_schedule_event_pair_a0v_039'"""
    ).fetchone()["n"]
    dispatch_body = conn.execute(
        "SELECT pg_get_functiondef('public.extension_dispatch_lock_group_a0v_028(uuid)'::regprocedure) AS body"
    ).fetchone()["body"]
    runtime_updates = conn.execute(
        """SELECT has_any_column_privilege('aos_runtime',
                   'public.data_requirement_outbox_delivery','UPDATE') AS allowed"""
    ).fetchone()["allowed"]
    expected_columns = ["completion_analysis_ref", "completion_fulfillment_ref"]
    if ([row["attname"] for row in columns] != expected_columns or constraint != 1 or pair != 1
            or "ecommerce_growth_event_control" not in dispatch_body or runtime_updates is True):
        raise ValueError("existing authority migration contract differs")
    return dict(tables=tables, functions=functions, dualReceiptColumns=expected_columns,
                eventSchedulePairConstraint=True, completeDispatchGroup=True,
                runtimeDirectOutboxUpdate=False)


def upgrade(database: str) -> None:
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import URL

    parameters = storage.parameters(database)
    with storage.connect(database, autocommit=True) as lock:
        acquired = lock.execute(
            "SELECT pg_try_advisory_lock(hashtext('aos.natural-chain.main-upgrade'),hashtext(current_database())) AS ok"
        ).fetchone()["ok"]
        if not acquired:
            raise ValueError("natural-chain migration lock busy")
        try:
            if storage.version(lock) != [SOURCE]:
                raise ValueError("exact a0v_038 baseline required")
            config = Config(str(ROOT / "services/aos-api/alembic.ini"))
            config.set_main_option("script_location", str(ROOT / "services/aos-api/alembic"))
            directory = ScriptDirectory.from_config(config)
            revisions = [item.revision for item in directory.iterate_revisions(TARGET, SOURCE)]
            if directory.get_heads() != [TARGET] or revisions != CHAIN:
                raise ValueError("exact a0v_038 to a0v_050 chain required")
            url = URL.create(
                "postgresql+psycopg", username=parameters["user"], password=parameters["password"],
                host=parameters["host"], port=int(parameters["port"]), database=database,
                query={"options": "-c lock_timeout=5s -c statement_timeout=120s"},
            )
            config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
            previous = os.environ.pop("AOS_DATABASE_URL", None)
            try:
                command.upgrade(config, TARGET)
            finally:
                if previous is not None:
                    os.environ["AOS_DATABASE_URL"] = previous
            if storage.version(lock) != [TARGET]:
                raise ValueError("migration commit not observed")
        finally:
            lock.execute(
                "SELECT pg_advisory_unlock(hashtext('aos.natural-chain.main-upgrade'),hashtext(current_database()))"
            )


def _proof_current(proof: dict) -> None:
    backup = STATE / "aos_meta_head-before-a0v_050.dump"
    if (
        proof.get("outcome") != "NATURAL_CHAIN_CLONE_UPGRADE_VERIFIED"
        or proof.get("source") != SOURCE or proof.get("target") != TARGET
        or proof.get("main") != storage.MAIN or proof.get("clone") != CLONE
        or proof.get("migrations") != migration_hashes() or proof.get("executors") != executor_hashes()
        or backup.is_symlink() or not backup.is_file() or backup.stat().st_mode & 0o777 != 0o600
        or proof.get("backup", {}).get("path") != str(backup)
        or proof["backup"].get("bytes") != backup.stat().st_size
        or proof["backup"].get("sha256") != digest(backup)
        or not proof.get("before") or proof.get("before") != proof.get("after")
    ):
        raise ValueError("retained natural-chain preparation differs")


def prepare() -> dict:
    from psycopg import sql

    require_lease()
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    backup = STATE / "aos_meta_head-before-a0v_050.dump"
    proof_path = STATE / "prepare.json"
    if backup.exists() or proof_path.exists():
        raise ValueError("retained preparation requires inspection")
    with storage.connect(storage.MAIN) as conn:
        if storage.version(conn) != [SOURCE]:
            raise ValueError("main source revision differs")
        before = fingerprint(conn)
        quiet = quiet_state(conn)
        if any(conn.execute("SELECT to_regclass(%s) IS NOT NULL AS present", ("public." + table,)).fetchone()["present"]
               for table in NEW_TABLES):
            raise ValueError("target snapshot tables already exist")
        if conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (CLONE,)).fetchone() is not None:
            raise ValueError("retained clone already exists")
        user = conn.info.user
    with backup.open("xb") as handle:
        os.chmod(backup, 0o600)
        process = subprocess.run(
            ["docker", "--context", storage.CONTEXT, "exec", storage.CONTAINER,
             "pg_dump", "-U", user, "-d", storage.MAIN, "-Fc"],
            stdout=handle, stderr=subprocess.PIPE, timeout=180,
        )
        handle.flush()
        os.fsync(handle.fileno())
    if process.returncode or not backup.stat().st_size:
        raise RuntimeError("protected main backup failed")
    with storage.connect(storage.MAIN, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(CLONE)))
        conn.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(sql.Identifier(CLONE)))
    with backup.open("rb") as handle:
        process = subprocess.run(
            ["docker", "--context", storage.CONTEXT, "exec", "-i", storage.CONTAINER,
             "pg_restore", "-U", user, "-d", CLONE, "--exit-on-error"],
            stdin=handle, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
        )
    if process.returncode:
        raise RuntimeError("isolated restore failed; retained clone requires inspection")
    with storage.connect(CLONE) as conn:
        if storage.version(conn) != [SOURCE] or fingerprint(conn) != before or quiet_state(conn) != quiet:
            raise ValueError("restored clone baseline differs")
    upgrade(CLONE)
    with storage.connect(CLONE) as conn:
        after = fingerprint(conn)
        schema = verify_schema(conn)
        if after != before or quiet_state(conn) != quiet:
            raise ValueError("clone business authority changed")
    proof = dict(
        outcome="NATURAL_CHAIN_CLONE_UPGRADE_VERIFIED", source=SOURCE, target=TARGET,
        main=storage.MAIN, clone=CLONE, at=datetime.now(timezone.utc).isoformat(),
        backup=dict(path=str(backup), bytes=backup.stat().st_size, sha256=digest(backup)),
        migrations=migration_hashes(), executors=executor_hashes(), before=before, after=after,
        quiet=quiet, schema=schema, businessWrites=0, sourceRowsRead=0,
    )
    protected_write(proof_path, proof)
    return proof


def readback() -> dict:
    require_lease()
    proof = json.loads((STATE / "prepare.json").read_text(encoding="utf-8"))
    _proof_current(proof)
    intent = json.loads((STATE / "apply-intent.json").read_text(encoding="utf-8"))
    if (intent.get("target") != TARGET or intent.get("migrations") != proof["migrations"]
            or intent.get("executors") != proof["executors"]):
        raise ValueError("natural-chain apply intent differs")
    with storage.connect(storage.MAIN) as conn:
        if storage.version(conn) != [TARGET] or fingerprint(conn) != proof["before"]:
            raise ValueError("main natural-chain deployment not verified")
        schema = verify_schema(conn)
        quiet = quiet_state(conn)
        if quiet != proof["quiet"]:
            raise ValueError("main quiet boundary drifted")
    result = dict(outcome="NATURAL_CHAIN_MAIN_SCHEMA_DEPLOYED", revision=TARGET,
                  schema=schema, quiet=quiet, businessWrites=0,
                  at=datetime.now(timezone.utc).isoformat())
    target = STATE / "apply.json"
    if not target.exists():
        protected_write(target, result)
    return result


def apply() -> dict:
    require_lease()
    intent_path = STATE / "apply-intent.json"
    if intent_path.exists():
        raise ValueError("existing apply intent requires readback")
    proof = json.loads((STATE / "prepare.json").read_text(encoding="utf-8"))
    _proof_current(proof)
    with storage.connect(CLONE) as conn:
        if storage.version(conn) != [TARGET] or fingerprint(conn) != proof["before"]:
            raise ValueError("verified clone drifted")
        verify_schema(conn)
        if quiet_state(conn) != proof["quiet"]:
            raise ValueError("verified clone quiet boundary drifted")
    with storage.connect(storage.MAIN) as conn:
        if storage.version(conn) != [SOURCE] or fingerprint(conn) != proof["before"]:
            raise ValueError("main changed since retained backup")
        if quiet_state(conn) != proof["quiet"]:
            raise ValueError("main quiet boundary changed")
    protected_write(intent_path, dict(target=TARGET, migrations=proof["migrations"],
                                      executors=proof["executors"], at=datetime.now(timezone.utc).isoformat()))
    upgrade(storage.MAIN)
    return readback()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "apply", "readback"))
    args = parser.parse_args()
    try:
        result = globals()[args.mode]()
    except Exception as exc:
        print(json.dumps(dict(outcome="NATURAL_CHAIN_UPGRADE_NEEDS_INSPECTION",
                              phase=args.mode, errorType=type(exc).__name__), sort_keys=True))
        raise SystemExit(2) from None
    public = {key: value for key, value in result.items() if key not in {"before", "after", "schema"}}
    print(json.dumps(public, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
