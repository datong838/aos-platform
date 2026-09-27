#!/usr/bin/env python3
"""Approve a no-baseline current ecommerce installation in the isolated preview DB."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
TARGET = "aos_current_preview_20260927"
EXPECTED_SCHEMA_HEAD = "a0v_107"
VERSIONS = {
    "domain.ecommerce.core": "1.4.0",
    "platform.ecommerce.niushop": "1.23.0",
    "solution.ecommerce.growth": "1.11.0",
    "solution.ecommerce.operations-base": "1.2.0",
}


class InstallBlocked(RuntimeError):
    pass


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise InstallBlocked("MODULE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def preflight(*, signed_receipt: Path):
    receipt_path = signed_receipt.resolve(strict=True)
    signed_state = receipt_path.parent / "signing-state"
    trust_path = signed_state / "trust-roots.json"
    signed_root = signed_state / "signed-bundles"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (receipt.get("outcome") != "SIGNED_TREE_GREEN"
            or receipt.get("signedTree") != str(signed_root)
            or not trust_path.is_file() or not signed_root.is_dir()):
        raise InstallBlocked("SIGNING_RECEIPT_DRIFT")
    builder = _load(ROOT / "scripts/build_ecommerce_current_candidates.py", "current_install_profile").load_builder()
    if receipt.get("signedTreeHash") != builder._tree_hash(signed_root):
        raise InstallBlocked("SIGNED_TREE_HASH_DRIFT")
    pub = _load(ROOT / "scripts/a0v_current_preview_registry_publish.py", "current_registry_connector")
    factory = pub._connect_factory()
    with factory() as conn:
        revisions = conn.execute("SELECT version_num FROM alembic_version").fetchall()
        rows = conn.execute("""SELECT b.bundle_id,v.version,v.status,v.content_hash
            FROM asset_bundle_version v JOIN asset_bundle b ON b.bundle_pk=v.bundle_pk
            ORDER BY b.bundle_id""").fetchall()
        installations = conn.execute("SELECT count(*) AS n FROM bundle_installation").fetchone()["n"]
        canary = conn.execute("SELECT count(*) AS n FROM twa_org WHERE id='dev-org'").fetchone()["n"]
    if [row["version_num"] for row in revisions] != [EXPECTED_SCHEMA_HEAD] or installations or canary:
        raise InstallBlocked("DATABASE_BASELINE_DRIFT")
    versions = {row["bundle_id"]: row["version"] for row in rows}
    contents = {row["bundle_id"]: row["content_hash"] for row in rows}
    if (versions != VERSIONS or contents != receipt.get("contentHashes")
            or any(row["status"] != "published" for row in rows)):
        raise InstallBlocked("REGISTRY_RELEASE_DRIFT")
    from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.asset_registry.signature import FileTrustRootProvider

    trust = FileTrustRootProvider(trust_path).snapshot()
    snapshot = RegistrySnapshotReader(connect_factory=factory,
        release_policy=ReleasePolicy(trust_roots=trust)).read()
    return factory, trust_path, snapshot.snapshot_hash


def apply(*, signed_receipt: Path, state: Path) -> dict[str, object]:
    state = state.resolve()
    if state == ROOT or state.is_relative_to(ROOT) or state.exists():
        raise InstallBlocked("STATE_MUST_BE_NEW_OUTSIDE_REPOSITORY")
    factory, trust_path, snapshot_hash = preflight(signed_receipt=signed_receipt)
    state.mkdir(mode=0o700)
    (state / "installation-intent.json").write_text(json.dumps({
        "database": TARGET, "snapshotHash": snapshot_hash, "versions": VERSIONS,
        "createdAt": datetime.now(UTC).isoformat(),
    }, sort_keys=True) + "\n", encoding="utf-8")
    old = _load(ROOT / "scripts/a0v_canonical_ecommerce_first_install.py", "current_install_helpers")
    installed = old.create_approved_first_installation(
        connect_factory=factory, state_dir=state,
        core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        operations_version=VERSIONS["solution.ecommerce.operations-base"],
        trust_path=trust_path, overlay_revision="a0v-current-preview-20260927",
        display_name="栖月汇当前源码电商八工作台隔离首装",
        maker_actor="a0v-current-preview-install-maker",
        checker_actor="a0v-current-preview-install-checker",
        idempotency_prefix="a0v-current-preview-install-v1",
    )
    if (installed["snapshotHash"] != snapshot_hash or installed["moduleCount"] != 8
            or installed["edgeCount"] != 3 or installed["installationState"] != "approved"):
        raise InstallBlocked("INSTALLATION_RESULT_DRIFT")
    with factory() as conn:
        count = conn.execute("SELECT count(*) AS n FROM bundle_installation").fetchone()["n"]
    if count != 1:
        raise InstallBlocked("INSTALLATION_COUNT_DRIFT")
    result = {"outcome": "CURRENT_INSTALLATION_APPROVED_RUNTIME_BLOCKED",
              "database": TARGET, "installation": installed,
              "installationCount": count, "runtimeHostStarted": False,
              "providerInvocationCount": 0, "externalPublicationCount": 0}
    (state / "installation-result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    os.environ["AOS_DOTENV_DISABLED"] = "1"
    sys.path.insert(0, str(API_ROOT))
    parser = argparse.ArgumentParser()
    parser.add_argument("--signed-receipt", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--state-dir", type=Path)
    args = parser.parse_args()
    if args.apply:
        if args.state_dir is None:
            raise InstallBlocked("STATE_DIR_REQUIRED")
        result = apply(signed_receipt=args.signed_receipt, state=args.state_dir)
    else:
        _, _, snapshot_hash = preflight(signed_receipt=args.signed_receipt)
        result = {"outcome": "CURRENT_INSTALLATION_PREFLIGHT_GREEN",
                  "database": TARGET, "snapshotHash": snapshot_hash, "effects": 0}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        original = getattr(exc, "orig", exc)
        diagnostic = getattr(original, "diag", None)
        print(json.dumps({"outcome": "SAFE_BLOCKED", "errorType": type(exc).__name__,
                          "reasonCode": str(exc) if isinstance(exc, InstallBlocked) else None,
                          "sqlstate": getattr(original, "sqlstate", None),
                          "databaseError": getattr(diagnostic, "message_primary", None)}))
        raise SystemExit(2) from None
