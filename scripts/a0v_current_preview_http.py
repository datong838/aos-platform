#!/usr/bin/env python3
"""Serve the current approved ecommerce preview with all execution workers off."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from psycopg import connect
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
TARGET = "aos_current_preview_20260927"
INSTALLATION = "ccdcb0f0-1040-4bc6-aa0c-d045f5689813"
EXPECTED_SCHEMA_HEAD = "a0v_116"
FLAGS = {
    "AOS_DOTENV_DISABLED": "1", "AOS_DB_MIGRATION_MODE": "disabled",
    "AOS_QYH_CRON_ENABLED": "false", "AOS_AIP_LOGIC_AUTOMATION_ENABLED": "false",
    "AOS_SNAPSHOT_GROUP_WORKER_ENABLED": "false",
    "AOS_AIP_TEXT_HEALTH_MAINTENANCE_ENABLED": "false",
    "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0", "AOS_JDBC_SSH_PREBUILD_ENABLED": "false",
    "AOS_ECOM_CONTENT_TASKRUN_WORKER_ENABLED": "false",
    "AOS_ECOM_CONTENT_AGENTRUN_WORKER_ENABLED": "false",
    "AOS_ECOM_CONTENT_CAPACITY_WORKER_ENABLED": "false",
    "AOS_ECOM_CONTENT_BUDGET_COMMAND_WORKER_ENABLED": "false",
    "AOS_ECOM_FEEDBACK_WORKER_ENABLED": "false",
    "AOS_ECOM_IMPROVEMENT_WORKER_ENABLED": "false",
    "AOS_ECOM_EFFECT_REVIEW_WORKER_ENABLED": "false",
    "AOS_ECOM_MEMORY_CANDIDATE_WORKER_ENABLED": "false",
    "AOS_ECOM_CONTENT_RETURN_WORKER_ENABLED": "false",
    "AOS_ECOM_CONTENT_WORKER_ENABLED": "false",
    "AOS_ECOM_CONTENT_STEP_WORKER_ENABLED": "false",
    "AOS_ECOM_CONTENT_REVIEW_STEP_WORKER_ENABLED": "false",
}


class PreviewBlocked(RuntimeError):
    pass


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PreviewBlocked("MODULE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verify_signed_bundles(*, builder, signed_root: Path, trust_path: Path,
                           content_hashes: object) -> None:
    previous_dotenv = os.environ.get("AOS_DOTENV_DISABLED")
    os.environ["AOS_DOTENV_DISABLED"] = "1"
    sys.path.insert(0, str(API_ROOT))
    try:
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.release_policy import ReleasePolicy
        from aos_api.asset_registry.signature import FileTrustRootProvider

        trust = FileTrustRootProvider(trust_path).snapshot()
        loader = ManifestLoader({"a0v-current": signed_root}, trust_roots=trust)
        policy = ReleasePolicy(trust_roots=trust)
        observed = {}
        for relative, bundle_id, _, _ in builder.ALL_CASES:
            loaded = loader.load(f"bundle://a0v-current/{relative}")
            policy.evaluate(builder._release_record(loaded), checked_at=datetime.now(UTC))
            observed[bundle_id] = loaded.content_hash
        if len(observed) != 4 or observed != content_hashes:
            raise ValueError("signed content does not match receipt")
    except Exception:
        raise PreviewBlocked("SIGNED_BUNDLE_CRYPTO_INVALID") from None
    finally:
        sys.path.remove(str(API_ROOT))
        if previous_dotenv is None:
            os.environ.pop("AOS_DOTENV_DISABLED", None)
        else:
            os.environ["AOS_DOTENV_DISABLED"] = previous_dotenv


def preflight(*, signed_receipt: Path) -> tuple[dict[str, object], dict[str, object]]:
    signed_receipt = signed_receipt.resolve(strict=True)
    signed_state = signed_receipt.parent / "signing-state"
    signed_root = signed_state / "signed-bundles"
    trust_path = signed_state / "trust-roots.json"
    receipt = json.loads(signed_receipt.read_text(encoding="utf-8"))
    if (receipt.get("outcome") != "SIGNED_TREE_GREEN" or receipt.get("signedTree") != str(signed_root)
            or not signed_root.is_dir() or not trust_path.is_file()):
        raise PreviewBlocked("SIGNING_RECEIPT_DRIFT")
    builder = _load(ROOT / "scripts/build_ecommerce_current_candidates.py", "preview_profile").load_builder()
    if receipt.get("signedTreeHash") != builder._tree_hash(signed_root):
        raise PreviewBlocked("SIGNED_TREE_HASH_DRIFT")
    _verify_signed_bundles(builder=builder, signed_root=signed_root, trust_path=trust_path,
                           content_hashes=receipt.get("contentHashes"))
    bootstrap = _load(ROOT / "scripts/a0v_current_preview_bootstrap.py", "preview_bootstrap")
    parameters = bootstrap._connection_parameters()
    with connect(**parameters, row_factory=dict_row) as conn:
        conn.read_only = True
        if conn.info.dbname != TARGET:
            raise PreviewBlocked("DATABASE_TARGET_DRIFT")
        version = conn.execute("SELECT version_num FROM alembic_version").fetchall()
        installed = conn.execute("""SELECT i.installation_id,r.state
            FROM bundle_installation i JOIN bundle_installation_revision r
              ON r.installation_pk=i.installation_pk AND r.revision=i.current_revision""").fetchall()
        bindings = conn.execute("SELECT count(*) AS n FROM extension_runtime_binding").fetchone()["n"]
        versions = conn.execute("""SELECT b.bundle_id,v.version,v.status,v.content_hash
            FROM asset_bundle_version v JOIN asset_bundle b ON b.bundle_pk=v.bundle_pk""").fetchall()
    expected = {bundle_id: ver for _, bundle_id, ver, _ in builder.ALL_CASES}
    if ([row["version_num"] for row in version] != [EXPECTED_SCHEMA_HEAD]
            or [(str(row["installation_id"]), row["state"]) for row in installed]
            != [(INSTALLATION, "approved")]
            or bindings != 0 or len(versions) != 4
            or {row["bundle_id"]: row["version"] for row in versions} != expected
            or {row["bundle_id"]: row["content_hash"] for row in versions} != receipt.get("contentHashes")
            or any(row["status"] != "published" for row in versions)):
        raise PreviewBlocked("PREVIEW_DATABASE_DRIFT")
    return parameters, {"database": TARGET, "version": EXPECTED_SCHEMA_HEAD,
                        "installationId": INSTALLATION, "installationState": "approved",
                        "runtimeBindings": 0, "publishedVersions": 4,
                        "signedRoot": str(signed_root), "trustRoots": str(trust_path)}


def _port_free(port: int) -> bool:
    result = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                            capture_output=True, timeout=5, check=False)
    return result.returncode == 1 and not result.stderr


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signed-receipt", type=Path, required=True)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    parameters, report = preflight(signed_receipt=args.signed_receipt)
    if not args.serve:
        print(json.dumps({"outcome": "CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN", **report}, sort_keys=True))
        return 0
    if not _port_free(8080) or not _port_free(18181):
        raise PreviewBlocked("HTTP_OR_SECOND_RUNTIME_PORT_OCCUPIED")
    os.environ.update(FLAGS)
    os.environ["AOS_DATABASE_URL"] = make_conninfo(**parameters)
    os.environ["AOS_BUNDLE_ROOT"] = report["signedRoot"]
    os.environ["AOS_BUNDLE_TRUST_ROOTS_FILE"] = report["trustRoots"]
    print(json.dumps({"outcome": "CURRENT_PREVIEW_HTTP_STARTING",
                      "database": TARGET, "port": 8080, "runtimeHost": 0,
                      "workersEnabled": 0, "migrationMode": "disabled"}, sort_keys=True), flush=True)
    sys.path.insert(0, str(API_ROOT))
    from aos_api.main import app
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080, workers=1,
                reload=False, access_log=False, log_level="warning")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        original = getattr(exc, "orig", exc)
        diagnostic = getattr(original, "diag", None)
        print(json.dumps({"outcome": "SAFE_BLOCKED", "errorType": type(exc).__name__,
                          "reasonCode": str(exc) if isinstance(exc, PreviewBlocked) else None,
                          "sqlstate": getattr(original, "sqlstate", None),
                          "databaseError": getattr(diagnostic, "message_primary", None)}))
        raise SystemExit(2) from None
