#!/usr/bin/env python3
"""Activate the one approved canonical ecommerce growth 1.4 installation."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services/aos-api"
RECOVERY = ROOT.parent / ".aos-recovery-20260912"
OUTPUT = RECOVERY / "logs/ecommerce-growth-1.4-activation.json"
ORG_ID = "org-org"
PROJECT_ID = "dev-project"
CANARY_ORG_ID = "dev-org"
DATABASE = "aos_meta_head"
INSTALLATION_ID = "c1eb714f-56de-4f28-ba06-c3440b3d18cb"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
ROLES = frozenset({"admin"})
MARKINGS = frozenset()


class ActivationBlocked(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def _load_first() -> Any:
    path = ROOT / "scripts/a0v_canonical_ecommerce_first_install.py"
    spec = importlib.util.spec_from_file_location("growth_1_4_first", path)
    if spec is None or spec.loader is None:
        raise ActivationBlocked("FIRST_INSTALLER_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _services(connect, trust_roots_file: Path):
    if str(API) not in sys.path:
        sys.path.insert(0, str(API))
    from aos_api.asset_registry.composition_store import PostgresCompositionStore
    from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
    from aos_api.asset_registry.installation_service import InstallationService
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.extension_runtime.lifecycle_service import RuntimeLifecycleService
    from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator

    if not trust_roots_file.is_file():
        raise ActivationBlocked("TRUST_ROOTS_INVALID")
    policy = ReleasePolicy(
        trust_roots=FileTrustRootProvider(trust_roots_file.resolve()).snapshot()
    )
    store = PostgresInstallationStore(connect_factory=connect)
    planning = RuntimeReleaseRevalidator(release_policy=policy)
    reader = InstallationService(
        store=store,
        composition_store=PostgresCompositionStore(connect_factory=connect),
        revalidator=InstallationRevalidator(release_policy=policy),
        planning_revalidator=planning,
    )
    return store, RuntimeLifecycleService(
        installation_store=store, installation_reader=reader, revalidator=planning
    )


def _ensure_control_membership(connect) -> dict[str, int]:
    """CAS-like, audited grant matching the existing Membership dual-write model."""
    with connect() as conn:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"a0v-runtime-membership:{ORG_ID}:{PROJECT_ID}:{ACTOR}",),
        )
        rows = conn.execute(
            "SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s FOR UPDATE",
            (ORG_ID, PROJECT_ID, ACTOR),
        ).fetchall()
        if len(rows) > 1 or (rows and rows[0]["role"] != "admin"):
            raise ActivationBlocked("CONTROL_MEMBERSHIP_DRIFT")
        canary = conn.execute(
            "SELECT count(*) AS count FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",
            (CANARY_ORG_ID, PROJECT_ID, ACTOR),
        ).fetchone()
        if int(canary["count"]) != 0:
            raise ActivationBlocked("CANARY_CONTROL_MEMBERSHIP_PRESENT")
        created = 0
        if not rows:
            conn.execute(
                "INSERT INTO meta_membership(org_id,project_id,subject,role,updated_at) VALUES(%s,%s,%s,'admin',now())",
                (ORG_ID, PROJECT_ID, ACTOR),
            )
            conn.execute(
                """INSERT INTO twa_ws_member(org_id,project_id,subject,role)
                   VALUES(%s,%s,%s,'admin')
                   ON CONFLICT(org_id,project_id,subject) DO UPDATE SET role=EXCLUDED.role""",
                (ORG_ID, PROJECT_ID, ACTOR),
            )
            conn.execute(
                """INSERT INTO twa_audit(id,ts,org_id,project_id,actor_id,action,detail)
                   VALUES(%s,now()::text,%s,%s,'user:dev','membership.upsert',%s::jsonb)
                   ON CONFLICT(id) DO NOTHING""",
                (
                    "a0v-ecommerce-runtime-owner-admin-v1", ORG_ID, PROJECT_ID,
                    json.dumps({"subject": ACTOR, "role": "admin"}, sort_keys=True),
                ),
            )
            created = 1
        conn.commit()
    return {"created": created, "positiveCount": 1, "canaryCount": 0}


def _settle_expired_apply(connect) -> dict[str, Any]:
    if str(API) not in sys.path:
        sys.path.insert(0, str(API))
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore

    with connect() as conn:
        with conn.transaction():
            apply_asset_transaction_scope(conn, org_id=ORG_ID, project_id=PROJECT_ID)
            rows = conn.execute(
                """SELECT operation_id,status,phase,revision,deadline < clock_timestamp() AS expired
                     FROM extension_runtime_operation
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s
                      AND kind='runtime-apply' AND status NOT IN ('succeeded','failed','cancelled')
                    ORDER BY operation_id FOR UPDATE""",
                (ORG_ID, PROJECT_ID, INSTALLATION_ID),
            ).fetchall()
            if not rows:
                return {"settledCount": 0}
            if len(rows) != 1:
                raise ActivationBlocked("AMBIGUOUS_ACTIVE_APPLY")
            row = rows[0]
            if (row["status"], row["phase"], row["expired"]) != ("accepted", "accepted", True):
                raise ActivationBlocked("ACTIVE_APPLY_NOT_RECOVERABLE")
            result = RuntimeOperationStore().fail_uncommitted_preparation(
                conn,
                org_id=ORG_ID,
                project_id=PROJECT_ID,
                operation_id=row["operation_id"],
                expected_revision=row["revision"],
                failure_code="PREPARATION_EXPIRED",
            )
        conn.commit()
    return {
        "settledCount": 1,
        "operationId": str(result.operation_id),
        "status": result.status,
        "revision": result.revision,
        "failureCode": "PREPARATION_EXPIRED",
    }


def _snapshot(connect, store) -> dict[str, Any]:
    record = store.get_installation(
        org_id=ORG_ID, project_id=PROJECT_ID, installation_id=INSTALLATION_ID
    )
    with connect() as conn:
        canary = conn.execute(
            "SELECT count(*) AS count FROM bundle_installation WHERE org_id=%s AND project_id=%s",
            (CANARY_ORG_ID, PROJECT_ID),
        ).fetchone()
        binding = conn.execute(
            """SELECT generation,installation_revision,desired_state,observed_state,enabled,
                      operation_fence
                 FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
            (ORG_ID, PROJECT_ID, INSTALLATION_ID),
        ).fetchone()
        operations = conn.execute(
            """SELECT kind,status,phase,revision,idempotency_key
                 FROM extension_runtime_operation
                WHERE org_id=%s AND project_id=%s AND installation_id=%s
                ORDER BY kind""",
            (ORG_ID, PROJECT_ID, INSTALLATION_ID),
        ).fetchall()
    return {
        "installationId": str(record.installation_id),
        "state": record.state,
        "revision": record.current_revision,
        "etag": record.etag_version,
        "activeRevision": record.active_revision,
        "canaryInstallationCount": int(canary["count"]),
        "binding": None if binding is None else dict(binding),
        "operations": [dict(row) for row in operations],
    }


def _wait_for(store, state: str, *, timeout_seconds: int) -> Any:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        record = store.get_installation(
            org_id=ORG_ID, project_id=PROJECT_ID, installation_id=INSTALLATION_ID
        )
        if record.state == state:
            return record
        time.sleep(1)
    raise ActivationBlocked(f"INSTALLATION_{state.upper()}_TIMEOUT")


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.apply or args.database_name != DATABASE:
        raise ActivationBlocked("EXPLICIT_ISOLATED_DATABASE_REQUIRED")
    first = _load_first()
    connect = first.container_database_connect_factory(
        context="colima-aos-extension",
        container="aos-a0v-recovery-pg",
        database_name=DATABASE,
    )
    membership = _ensure_control_membership(connect)
    recovery = _settle_expired_apply(connect)
    store, lifecycle = _services(connect, args.trust_roots_file)
    before = _snapshot(connect, store)
    if before["canaryInstallationCount"] != 0:
        raise ActivationBlocked("CANARY_INSTALLATION_PRESENT")
    if before["installationId"] != INSTALLATION_ID:
        raise ActivationBlocked("INSTALLATION_ID_DRIFT")
    receipts = []
    current = store.get_installation(
        org_id=ORG_ID, project_id=PROJECT_ID, installation_id=INSTALLATION_ID
    )
    if current.state == "approved":
        receipt = lifecycle.request_preparation(
            installation_id=INSTALLATION_ID, kind="runtime-apply",
            org_id=ORG_ID, project_id=PROJECT_ID, actor=ACTOR,
            roles=ROLES, markings=MARKINGS,
            idempotency_key="a0v-ecommerce-growth-1.4-runtime-apply-v2",
            if_match=f'"{current.etag_version}"',
        )
        receipts.append({"kind": "runtime-apply", **receipt.response_json})
        current = _wait_for(store, "applied", timeout_seconds=args.timeout_seconds)
    if current.state == "applied":
        receipt = lifecycle.request_preparation(
            installation_id=INSTALLATION_ID, kind="runtime-verify",
            org_id=ORG_ID, project_id=PROJECT_ID, actor=ACTOR,
            roles=ROLES, markings=MARKINGS,
            idempotency_key="a0v-ecommerce-growth-1.4-runtime-verify-v1",
            if_match=f'"{current.etag_version}"',
        )
        receipts.append({"kind": "runtime-verify", **receipt.response_json})
        current = _wait_for(store, "active", timeout_seconds=args.timeout_seconds)
    if current.state != "active":
        raise ActivationBlocked("INSTALLATION_STATE_DRIFT", current.state)
    after = _snapshot(connect, store)
    if (
        after["activeRevision"] != after["revision"]
        or after["binding"] is None
        or after["binding"]["observed_state"] != "ready"
        or after["binding"]["enabled"] is not False
        or after["binding"]["operation_fence"] is not True
    ):
        raise ActivationBlocked("ACTIVE_BINDING_DRIFT")
    return {
        "outcome": "ECOMMERCE_GROWTH_1_4_ACTIVE_GREEN",
        "database": DATABASE,
        "controlMembership": membership,
        "expiredApplyRecovery": recovery,
        "before": before,
        "receipts": receipts,
        "after": after,
        "effects": {"providerInvocationCount": 0, "businessOperationCount": 0},
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database-name")
    parser.add_argument("--trust-roots-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args(argv)


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run(args)
        code = 0
    except ActivationBlocked as exc:
        result = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.code, "message": str(exc)}
        code = 2
    except Exception as exc:
        result = {"outcome": "SAFE_BLOCKED", "reasonCode": "UNEXPECTED_DOMAIN_ERROR",
                  "errorType": type(exc).__name__, "message": str(exc)}
        code = 2
    _write(args.output.resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
