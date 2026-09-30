#!/usr/bin/env python3
"""Serve the current approved ecommerce preview with all execution workers off."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path

from psycopg import connect
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
TARGET = "aos_current_preview_20260927"
INSTALLATION = "ccdcb0f0-1040-4bc6-aa0c-d045f5689813"
EXPECTED_SCHEMA_HEAD = "a0v_118"
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
    return parameters, {"database": TARGET, "databaseHost": parameters["host"],
                        "databasePort": parameters["port"], "version": EXPECTED_SCHEMA_HEAD,
                        "installationId": INSTALLATION, "installationState": "approved",
                        "runtimeBindings": 0, "publishedVersions": 4,
                        "signedRoot": str(signed_root), "trustRoots": str(trust_path)}


def _port_free(port: int) -> bool:
    result = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                            capture_output=True, timeout=5, check=False)
    return result.returncode == 1 and not result.stderr


def _private_file(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise PreviewBlocked("API_IDENTITY_FILE_INVALID")
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
        raise PreviewBlocked("API_IDENTITY_MODE_INVALID")
    return path.resolve(strict=True)


def _limited_identity(path: Path, report: dict[str, object]) -> dict[str, object]:
    try:
        data = json.loads(_private_file(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        raise PreviewBlocked("API_IDENTITY_FILE_INVALID") from None
    if not isinstance(data, dict) or set(data) != {"host", "port", "dbname", "user", "pgpassFile"}:
        raise PreviewBlocked("API_IDENTITY_FILE_INVALID")
    if (data["host"] != "127.0.0.1" or data["host"] != report.get("databaseHost")
            or type(data["port"]) is not int or data["port"] != report.get("databasePort")
            or data["dbname"] != TARGET):
        raise PreviewBlocked("API_IDENTITY_TARGET_DRIFT")
    if (not isinstance(data["user"], str)
            or not re.fullmatch(r"[a-z][a-z0-9_]{2,62}", data["user"])
            or data["user"] in {"aos_app", "aos_runtime"}):
        raise PreviewBlocked("API_IDENTITY_ROLE_INVALID")
    if not isinstance(data["pgpassFile"], str):
        raise PreviewBlocked("API_IDENTITY_FILE_INVALID")
    data["pgpassFile"] = str(_private_file(Path(data["pgpassFile"])))
    return data


def _verify_limited_login(identity: dict[str, object]) -> None:
    with connect(host=identity["host"], port=identity["port"],
                 dbname=identity["dbname"], user=identity["user"],
                 passfile=identity["pgpassFile"], row_factory=dict_row) as conn:
        conn.read_only = True
        row = conn.execute("""SELECT session_user AS login, current_user AS role,
            r.rolsuper, r.rolbypassrls, r.rolinherit,
            pg_has_role(session_user, 'aos_runtime', 'MEMBER') AS runtime_member,
            pg_has_role(session_user, 'aos_app', 'MEMBER') AS owner_member,
            has_table_privilege(session_user, 'public.aip_action_proposal', 'SELECT') AS direct_select
            FROM pg_roles r WHERE r.rolname=session_user""").fetchone()
        if (row is None or row["login"] != identity["user"] or row["role"] != identity["user"]
                or row["rolsuper"] or row["rolbypassrls"] or row["rolinherit"]
                or not row["runtime_member"] or row["owner_member"] or row["direct_select"]):
            raise PreviewBlocked("API_IDENTITY_PRIVILEGE_DRIFT")
        conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute("SELECT version_num FROM alembic_version").fetchone()


def _require_external_oidc() -> None:
    urls = os.environ.get("AOS_OIDC_JWKS_URLS") or os.environ.get("AOS_OIDC_JWKS_URL") or ""
    issuers = os.environ.get("AOS_OIDC_ISSUERS") or os.environ.get("AOS_OIDC_ISSUER") or ""
    audience = os.environ.get("AOS_OIDC_AUDIENCE") or ""
    if not urls.strip() or not issuers.strip() or not audience.strip():
        raise PreviewBlocked("EXTERNAL_OIDC_CONFIG_REQUIRED")
    for value in [*urls.split(","), *issuers.split(",")]:
        parsed = urllib.parse.urlsplit(value.strip())
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
                or parsed.username or parsed.password):
            raise PreviewBlocked("EXTERNAL_OIDC_CONFIG_INVALID")


def serve_limited(*, signed_receipt: Path, identity_file: Path) -> None:
    _require_external_oidc()
    if not _port_free(8080) or not _port_free(18181):
        raise PreviewBlocked("HTTP_OR_SECOND_RUNTIME_PORT_OCCUPIED")
    child_env = {k: v for k, v in os.environ.items()
                 if k not in {"AOS_DATABASE_URL", "PGPASSWORD", "PGPASSFILE"}}
    child = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                            "--signed-receipt", str(signed_receipt)],
                           env=child_env, capture_output=True, text=True,
                           timeout=90, check=False)
    try:
        report = json.loads(child.stdout.strip().splitlines()[-1])
    except (ValueError, TypeError):
        raise PreviewBlocked("SIGNED_PREFLIGHT_CHILD_FAILED") from None
    if child.returncode != 0 or report.get("outcome") != "CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN":
        raise PreviewBlocked("SIGNED_PREFLIGHT_CHILD_FAILED")
    identity = _limited_identity(identity_file, report)
    _verify_limited_login(identity)
    service_env = {k: v for k, v in child_env.items() if k not in {"AOS_DATABASE_URL", "PGPASSWORD"}}
    service_env.update(FLAGS)
    service_env.update({"AOS_AUTH_ALLOW_DEV": "0", "AOS_AUTH_EXTERNAL_ONLY": "1",
                        "AOS_REST_CONNECTOR_MOCK": "0"})
    service_env["PGPASSFILE"] = str(identity["pgpassFile"])
    service_env["AOS_DATABASE_URL"] = make_conninfo(host=identity["host"],
        port=identity["port"], dbname=identity["dbname"], user=identity["user"])
    service_env["AOS_BUNDLE_ROOT"] = str(report["signedRoot"])
    service_env["AOS_BUNDLE_TRUST_ROOTS_FILE"] = str(report["trustRoots"])
    print(json.dumps({"outcome": "CURRENT_PREVIEW_HTTP_LIMITED_STARTING",
                      "database": TARGET, "port": 8080, "runtimeHost": 0,
                      "workersEnabled": 0, "migrationMode": "disabled"}, sort_keys=True), flush=True)
    os.execve(sys.executable, [sys.executable, "-m", "uvicorn", "aos_api.main:app",
                            "--host", "127.0.0.1", "--port", "8080", "--workers", "1",
                            "--no-access-log", "--log-level", "warning"],
              {**service_env, "PYTHONPATH": str(API_ROOT) + os.pathsep + service_env.get("PYTHONPATH", "")})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signed-receipt", type=Path, required=True)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--serve-limited", action="store_true")
    parser.add_argument("--api-identity-file", type=Path)
    args = parser.parse_args()
    if args.serve_limited:
        if args.serve or args.api_identity_file is None:
            raise PreviewBlocked("API_IDENTITY_FILE_REQUIRED")
        serve_limited(signed_receipt=args.signed_receipt, identity_file=args.api_identity_file)
        return 0
    if args.api_identity_file is not None:
        raise PreviewBlocked("API_IDENTITY_FILE_UNEXPECTED")
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
