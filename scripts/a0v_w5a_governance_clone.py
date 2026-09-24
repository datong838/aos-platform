"""One-shot, governance-only current-state clone for the frozen W5a plan."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

from psycopg import connect, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from a0v_formal_text_model_renewal import database_connect


MAIN = "aos_meta_head"
CLONE = "aos_w5a_governance_20260924"
ORG = "org-org"
PROJECT = "dev-project"
CONTEXT = "colima-aos-extension"
CONTAINER = "aos-a0v-recovery-pg"
PLAN = (Path(__file__).resolve().parents[2] /
        ".aos-recovery-20260920/state/q-advisor-baseline/br-text-governance-renewal/"
        "20260924-w5a/formal-renewal/plan.json")
PLAN_HASH = "41813b34c4ce092d3bddd81115169ac52ca1b644819e57e5b29e801fb27a1265"
TABLES = (
    "twa_org", "twa_workspace",
    "aip_budget_head", "aip_budget_revision",
    "aip_model_governance_policy_head", "aip_model_governance_policy_revision",
    "aip_runtime_guard_policy_head", "aip_runtime_guard_policy_revision",
    "aip_network_policy_head", "aip_network_policy_revision",
    "aip_provider_instance_head", "aip_provider_instance_revision",
    "aip_model_price_snapshot_head", "aip_model_price_snapshot_revision",
    "aip_runtime_policy_head", "aip_runtime_policy_revision",
    "aip_registered_model_head", "aip_registered_model_revision",
    "aip_model_route_head", "aip_model_route_revision",
)
HEADS = (
    "aip_budget_head", "aip_model_governance_policy_head",
    "aip_runtime_guard_policy_head", "aip_network_policy_head",
    "aip_provider_instance_head", "aip_model_price_snapshot_head",
    "aip_runtime_policy_head", "aip_registered_model_head", "aip_model_route_head",
)


def require_table(table: str) -> None:
    if table not in TABLES or table.startswith(("ecommerce_", "pipeline_")):
        raise ValueError("W5A1_TABLE_OUTSIDE_GOVERNANCE_ALLOWLIST")


def scope_clause(table: str) -> tuple[str, tuple[str, ...]]:
    require_table(table)
    if table == "twa_org":
        return "id=%s", (ORG,)
    return "org_id=%s AND project_id=%s", (ORG, PROJECT)


def _parameters(main_conn):
    parameters = main_conn.info.get_parameters()
    parameters["password"] = main_conn.info.password
    if main_conn.info.dbname != MAIN:
        raise ValueError("W5A1_MAIN_DATABASE_DRIFT")
    return parameters


def _clone_connection(parameters):
    args = {**parameters, "dbname": CLONE}
    connection = connect(**args, row_factory=dict_row)
    if connection.info.dbname != CLONE:
        connection.close()
        raise ValueError("W5A1_CLONE_DATABASE_DRIFT")
    return connection


def _columns(conn, table):
    require_table(table)
    rows = conn.execute(
        "SELECT column_name,data_type FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
        (table,),
    ).fetchall()
    columns = [(row["column_name"], row["data_type"]) for row in rows]
    expected_org_column = "id" if table == "twa_org" else "org_id"
    if not columns or expected_org_column not in {column for column, _ in columns}:
        raise ValueError("W5A1_TABLE_SCHEMA_DRIFT")
    if table != "twa_org" and "project_id" not in {column for column, _ in columns}:
        raise ValueError("W5A1_TABLE_SCOPE_DRIFT")
    return columns


def _rows(conn, table):
    predicate, values = scope_clause(table)
    rows = conn.execute(
        sql.SQL("SELECT * FROM {} WHERE " + predicate).format(sql.Identifier(table)), values
    ).fetchall()
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, default=str,
                                                    ensure_ascii=False))


def _insert(conn, table, rows, columns):
    if not rows:
        raise ValueError("W5A1_GOVERNANCE_DEPENDENCY_EMPTY")
    names = [column for column, _ in columns]
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(",").join(map(sql.Identifier, names)),
        sql.SQL(",").join(sql.Placeholder() for _ in names),
    )
    for row in rows:
        org_value = row["id"] if table == "twa_org" else row["org_id"]
        if org_value != ORG or (table != "twa_org" and row["project_id"] != PROJECT):
            raise ValueError("W5A1_TENANT_SCOPE_DRIFT")
        values = [Jsonb(row[name]) if kind in {"json", "jsonb"} else row[name]
                  for name, kind in columns]
        conn.execute(query, values)


def _head_digest(conn, table):
    rows = _rows(conn, table)
    payload = json.dumps(rows, sort_keys=True, default=str, ensure_ascii=False)
    return {"count": len(rows), "sha256": hashlib.sha256(payload.encode()).hexdigest()}


def _legacy_head_digest(conn, table):
    """Read back the unordered digest emitted by the initial prepare version."""
    predicate, values = scope_clause(table)
    rows = conn.execute(sql.SQL("SELECT * FROM {} WHERE " + predicate).format(
        sql.Identifier(table)), values).fetchall()
    payload = json.dumps(rows, sort_keys=True, default=str, ensure_ascii=False)
    return {"count": len(rows), "sha256": hashlib.sha256(payload.encode()).hexdigest()}


def _require_plan_and_heads(conn):
    from a0v_formal_text_model import PRICE_ID, MODEL_ID, ROUTE_ID, canonical_hash
    plan = json.loads(PLAN.read_text())
    if plan.get("planHash") != PLAN_HASH or canonical_hash({
            key: value for key, value in plan.items() if key != "planHash"}) != PLAN_HASH:
        raise ValueError("W5A1_FROZEN_PLAN_DRIFT")
    if datetime.fromisoformat(plan["price"]["effectiveUntil"]) <= datetime.now(UTC):
        raise ValueError("W5A1_FROZEN_PLAN_EXPIRED")
    checks = (
        ("aip_model_governance_policy_head", "policy_id", plan["budget"]["policyId"], "budgetExpectedVersion"),
        ("aip_model_price_snapshot_head", "model_price_snapshot_id", PRICE_ID, "priceExpectedVersion"),
        ("aip_runtime_policy_head", "runtime_policy_id", plan["policy"]["policyId"], "policyExpectedVersion"),
        ("aip_registered_model_head", "registered_model_id", MODEL_ID, "modelExpectedVersion"),
        ("aip_model_route_head", "model_route_id", ROUTE_ID, "routeExpectedVersion"),
    )
    for table, key, asset_id, expected in checks:
        found = conn.execute(sql.SQL(
            "SELECT version FROM {} WHERE org_id=%s AND project_id=%s AND {}=%s"
        ).format(sql.Identifier(table), sql.Identifier(key)), (ORG, PROJECT, asset_id)).fetchone()
        if found is None or found["version"] != plan[expected]:
            raise ValueError("W5A1_FROZEN_HEAD_CAS_DRIFT")
    return plan


def _schema_dump(path: Path, user: str):
    if path.exists():
        raise ValueError("W5A1_SCHEMA_DUMP_ALREADY_EXISTS")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            run = subprocess.run(
                ["docker", "--context", CONTEXT, "exec", CONTAINER,
                 "pg_dump", "-U", user, "-d", MAIN, "--schema-only", "--format=custom",
                 "--no-owner"], stdout=out, stderr=subprocess.PIPE, timeout=120, check=False,
            )
        if run.returncode:
            raise RuntimeError("W5A1_SCHEMA_DUMP_FAILED")
        listing = subprocess.run(
            ["docker", "--context", CONTEXT, "exec", "-i", CONTAINER,
             "pg_restore", "--list"], input=path.read_bytes(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False,
        )
        if listing.returncode or b"TABLE DATA" in listing.stdout or b"BLOBS" in listing.stdout:
            raise ValueError("W5A1_SCHEMA_DUMP_CONTAINS_DATA")
    except Exception:
        # Preserve the unknown artifact for inspection; never silently retry.
        raise


def prepare(state_dir: Path):
    state_dir = state_dir.resolve()
    if state_dir.exists():
        raise ValueError("W5A1_STATE_ALREADY_EXISTS_RECONCILE_FIRST")
    with database_connect(MAIN)() as main:
        parameters = _parameters(main)
        main.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        _require_plan_and_heads(main)
        identity = main.execute("SELECT current_user AS username, "
                                "(SELECT version_num FROM alembic_version) AS migration").fetchone()
        user = identity["username"]
        baseline = {table: _head_digest(main, table) for table in HEADS}
        rows = {table: _rows(main, table) for table in TABLES}
        columns = {table: _columns(main, table) for table in TABLES}
        if any(not value for value in rows.values()):
            raise ValueError("W5A1_GOVERNANCE_DEPENDENCY_EMPTY")
        state_dir.mkdir(parents=True, mode=0o700)
        os.chmod(state_dir, 0o700)
        _schema_dump(state_dir / "schema-only.dump", user)
        with connect(**parameters, autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (CLONE,)).fetchone():
                raise ValueError("W5A1_CLONE_ALREADY_EXISTS_RECONCILE_FIRST")
            admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(CLONE)))
            admin.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(sql.Identifier(CLONE)))
        with (state_dir / "schema-only.dump").open("rb") as source:
            restored = subprocess.run(
                ["docker", "--context", CONTEXT, "exec", "-i", CONTAINER,
                 "pg_restore", "-U", user, "-d", CLONE, "--no-owner", "--exit-on-error"],
                stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=180, check=False,
            )
        if restored.returncode:
            raise RuntimeError("W5A1_SCHEMA_RESTORE_FAILED_RECONCILE_FIRST")
        with _clone_connection(parameters) as clone:
            clone.execute("INSERT INTO alembic_version(version_num) VALUES(%s)",
                          (identity["migration"],))
            migration = clone.execute("SELECT version_num FROM alembic_version").fetchone()
            if migration["version_num"] != identity["migration"]:
                raise ValueError("W5A1_MIGRATION_DRIFT")
            for table in TABLES:
                _insert(clone, table, rows[table], columns[table])
            copied = {table: _head_digest(clone, table) for table in HEADS}
            if copied != baseline:
                raise ValueError("W5A1_HEAD_DIGEST_DRIFT")
            source_tables = clone.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND (tablename LIKE 'ecommerce_%' OR tablename LIKE 'pipeline_%')"
            ).fetchall()
            for source_table in source_tables:
                count = clone.execute(sql.SQL("SELECT count(*) AS n FROM {}").format(
                    sql.Identifier(source_table["tablename"]))).fetchone()["n"]
                if count:
                    raise ValueError("W5A1_CLONE_SOURCE_TABLE_NOT_EMPTY")
            clone.commit()
        proof = {"outcome": "W5A1_GOVERNANCE_CLONE_PREPARED", "main": MAIN,
                 "clone": CLONE, "migration": identity["migration"], "heads": baseline,
                 "copiedRows": {table: len(rows[table]) for table in TABLES},
                 "sourceDataRowsCopied": 0, "emptySourceTableCount": len(source_tables)}
        destination = state_dir / "prepare.json"
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(proof, output, indent=2)
            output.write("\n")
        return proof


def preserve_main(state_dir: Path):
    """Capture only the exact pre-apply governance rows in binary COPY format."""
    state_dir = state_dir.resolve()
    prepared = state_dir / "prepare.json"
    applied = state_dir / "clone-apply-result.json"
    backup = state_dir / "main-governance-preservation"
    if not prepared.is_file() or not applied.is_file() or backup.exists():
        raise ValueError("W5A1_PRESERVATION_BOUNDARY_INVALID")
    prep = json.loads(prepared.read_text())
    result = json.loads(applied.read_text())
    if (prep.get("outcome") != "W5A1_GOVERNANCE_CLONE_PREPARED"
            or prep.get("sourceDataRowsCopied") != 0
            or result.get("planHash") != PLAN_HASH
            or result.get("providerCalls") != 0 or result.get("businessRuns") != 0):
        raise ValueError("W5A1_CLONE_RESULT_UNVERIFIED")
    with database_connect(MAIN)() as main:
        _parameters(main)
        main.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        _require_plan_and_heads(main)
        heads = {table: _head_digest(main, table) for table in HEADS}
        if heads != prep["heads"] and {
                table: _legacy_head_digest(main, table) for table in HEADS} != prep["heads"]:
            raise ValueError("W5A1_PREAPPLY_HEADS_DRIFT")
        backup.mkdir(mode=0o700)
        os.chmod(backup, 0o700)
        manifest = {"outcome": "W5A1_MAIN_GOVERNANCE_PRESERVED", "main": MAIN,
                    "planHash": PLAN_HASH, "heads": heads, "tables": {}}
        for table in TABLES:
            predicate, values = scope_clause(table)
            path = backup / (table + ".copy")
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            digest = hashlib.sha256()
            size = 0
            query = sql.SQL("COPY (SELECT * FROM {} WHERE " + predicate + ") TO STDOUT WITH (FORMAT binary)").format(
                sql.Identifier(table))
            with os.fdopen(fd, "wb") as output, main.cursor() as cursor:
                with cursor.copy(query, values) as copy:
                    while block := copy.read():
                        output.write(block)
                        digest.update(block)
                        size += len(block)
                output.flush()
                os.fsync(output.fileno())
            manifest["tables"][table] = {"rows": len(_rows(main, table)),
                                         "sha256": digest.hexdigest(), "bytes": size}
        manifest_path = backup / "manifest.json"
        fd = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(manifest, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        return {"outcome": manifest["outcome"], "tables": len(TABLES),
                "sourceDataRows": 0, "planHash": PLAN_HASH}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--preserve-main", action="store_true")
    args = parser.parse_args()
    if args.preserve_main:
        print(json.dumps(preserve_main(args.state_dir)))
    else:
        result = prepare(args.state_dir)
        print(json.dumps({"outcome": result["outcome"], "clone": result["clone"],
                          "sourceDataRowsCopied": 0}))
