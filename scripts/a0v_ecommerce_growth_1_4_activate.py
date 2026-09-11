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
ROLES = frozenset({"asset-installer"})
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
            idempotency_key="a0v-ecommerce-growth-1.4-runtime-apply-v1",
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
