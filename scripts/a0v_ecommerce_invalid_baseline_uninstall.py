#!/usr/bin/env python3
"""Uninstall the never-active ecommerce 1.4 baseline after confirmed cleanup."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "services/aos-api"
RECOVERY = ROOT.parent / ".aos-recovery-20260912"
OUTPUT = RECOVERY / "logs/ecommerce-invalid-baseline-uninstall.json"
ORG_ID = "org-org"
PROJECT_ID = "dev-project"
CANARY_ORG_ID = "dev-org"
DATABASE = "aos_meta_head"
INSTALLATION_ID = "c1eb714f-56de-4f28-ba06-c3440b3d18cb"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
KEY = "a0v-ecommerce-invalid-1.4-uninstall-v1"
UNINSTALL_REASON = "Signed runtime API declarations are absent"


class UninstallBlocked(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def _load_first() -> Any:
    path = ROOT / "scripts/a0v_canonical_ecommerce_first_install.py"
    spec = importlib.util.spec_from_file_location("invalid_baseline_first", path)
    if spec is None or spec.loader is None:
        raise UninstallBlocked("FIRST_INSTALLER_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build(connect, trust_roots_file: Path):
    if str(API) not in sys.path:
        sys.path.insert(0, str(API))
    from aos_api.asset_registry.composition_store import PostgresCompositionStore
    from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
    from aos_api.asset_registry.installation_service import InstallationService
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.extension_runtime.runtime_uninstall import RuntimeUninstallGuard

    if not trust_roots_file.is_file():
        raise UninstallBlocked("TRUST_ROOTS_INVALID")
    policy = ReleasePolicy(
        trust_roots=FileTrustRootProvider(trust_roots_file.resolve()).snapshot()
    )
    store = PostgresInstallationStore(connect_factory=connect)
    service = InstallationService(
        store=store,
        composition_store=PostgresCompositionStore(connect_factory=connect),
        revalidator=InstallationRevalidator(release_policy=policy),
        runtime_uninstall_guard=RuntimeUninstallGuard(),
    )
    return store, service


def _assert_clean(connect) -> dict[str, int]:
    with connect() as conn:
        unresolved = conn.execute(
            """SELECT count(*) AS count FROM extension_runtime_operation
                 WHERE org_id=%s AND project_id=%s AND installation_id=%s
                   AND status NOT IN ('succeeded','failed','cancelled')""",
            (ORG_ID, PROJECT_ID, INSTALLATION_ID),
        ).fetchone()
        unsafe = conn.execute(
            """SELECT count(*) AS count FROM extension_runtime_resource_lease
                 WHERE org_id=%s AND project_id=%s AND operation_id IN (
                       SELECT operation_id FROM extension_runtime_operation
                        WHERE installation_id=%s)
                   AND (cleanup_state!='released' OR observed_release IS NOT TRUE)""",
            (ORG_ID, PROJECT_ID, INSTALLATION_ID),
        ).fetchone()
        binding = conn.execute(
            "SELECT count(*) AS count FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s",
            (ORG_ID, PROJECT_ID, INSTALLATION_ID),
        ).fetchone()
        canary = conn.execute(
            "SELECT count(*) AS count FROM bundle_installation WHERE org_id=%s AND project_id=%s",
            (CANARY_ORG_ID, PROJECT_ID),
        ).fetchone()
    result = {
        "unresolvedOperationCount": int(unresolved["count"]),
        "unsafeResourceCount": int(unsafe["count"]),
        "bindingCount": int(binding["count"]),
        "canaryInstallationCount": int(canary["count"]),
    }
    if any(result.values()):
        raise UninstallBlocked("INVALID_BASELINE_NOT_CLEAN", json.dumps(result, sort_keys=True))
    return result


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.apply or args.database_name != DATABASE:
        raise UninstallBlocked("EXPLICIT_ISOLATED_DATABASE_REQUIRED")
    first = _load_first()
    connect = first.container_database_connect_factory(
        context="colima-aos-extension", container="aos-a0v-recovery-pg",
        database_name=DATABASE,
    )
    clean = _assert_clean(connect)
    store, service = _build(connect, args.trust_roots_file)
    before = store.get_installation(
        org_id=ORG_ID, project_id=PROJECT_ID, installation_id=INSTALLATION_ID
    )
    if before.state not in {"approved", "uninstalled"} or before.active_revision is not None:
        raise UninstallBlocked("INVALID_BASELINE_STATE_DRIFT", before.state)
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest

    command = dict(
        installation_id=INSTALLATION_ID,
        request=UninstallInstallationRequest(reason=UNINSTALL_REASON),
        org_id=ORG_ID, project_id=PROJECT_ID, actor=ACTOR,
        roles=frozenset({"admin"}), markings=frozenset(),
        idempotency_key=KEY, if_match='"3"',
    )
    first_receipt = service.uninstall(**command)
    replay_receipt = service.uninstall(**command)
    after = store.get_installation(
        org_id=ORG_ID, project_id=PROJECT_ID, installation_id=INSTALLATION_ID
    )
    if after.state != "uninstalled" or after.active_revision is not None:
        raise UninstallBlocked("UNINSTALL_READBACK_DRIFT", after.state)
    return {
        "outcome": "INVALID_ECOMMERCE_1_4_UNINSTALLED_GREEN",
        "database": DATABASE,
        "installationId": INSTALLATION_ID,
        "cleanPrecondition": clean,
        "before": {"state": before.state, "revision": before.current_revision, "etag": before.etag_version},
        "after": {"state": after.state, "revision": after.current_revision, "etag": after.etag_version},
        "receipt": first_receipt.response_json,
        "firstReplayed": first_receipt.replayed,
        "secondReplayed": replay_receipt.replayed,
        "effects": {"providerInvocationCount": 0, "businessOperationCount": 0},
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database-name")
    parser.add_argument("--trust-roots-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result, code = run(args), 0
    except UninstallBlocked as exc:
        result, code = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.code, "message": str(exc)}, 2
    except Exception as exc:
        result, code = {"outcome": "SAFE_BLOCKED", "reasonCode": "UNEXPECTED_DOMAIN_ERROR",
                        "errorType": type(exc).__name__, "message": str(exc)}, 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, default=str, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, default=str, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
