#!/usr/bin/env python3
"""Read-only cross-check of the current signed installation and Host identities.

This command never selects or starts a Runtime Host.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
# Importing the runtime package can construct the API app. Keep this dedicated
# preflight independent of the repository's development .env and its secrets.
os.environ["AOS_DOTENV_DISABLED"] = "1"
sys.path.insert(0, str(ROOT / "services/aos-api"))

from aos_api.extension_runtime.production_runtime import _PROTECTED_RELATIONS
from aos_api.extension_runtime.runtime_configuration_candidates import read_candidates
from aos_api.extension_runtime.runtime_connections import _runtime_file_dsns
from aos_api.extension_runtime.runtime_identity import (
    probe_runtime_database_identity, require_isolated_runtime_identities,
)
from aos_api.tenant_scope import TenantScope


class HostPreflightBlocked(RuntimeError):
    pass


def _load_signed_preflight():
    spec = importlib.util.spec_from_file_location(
        "current_signed_preview", ROOT / "scripts/a0v_current_preview_http.py")
    if spec is None or spec.loader is None:
        raise HostPreflightBlocked("SIGNED_PREFLIGHT_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.preflight


signed_preflight = _load_signed_preflight()


def _load_restored_preflight():
    # Use the existing preserved-volume and exact signed release reader, not the
    # active-generation image reader: preparation precedes installation apply.
    sys.path.insert(0, str(ROOT / 'scripts'))
    import a0v_qyh_restored_http
    return a0v_qyh_restored_http


def preflight_restored(*, identity_file: Path, installation_id: str,
                      bundle_root: Path, trust_roots_file: Path,
                      credential_file: Path, preparation_only: bool = False):
    if preparation_only is not True:
        raise HostPreflightBlocked('RESTORED_PREPARATION_ONLY_REQUIRED')
    if (any(not isinstance(path, Path) or not path.is_absolute() for path in
            (identity_file, bundle_root, trust_roots_file, credential_file))
            or type(installation_id) is not str or not installation_id):
        raise HostPreflightBlocked('RESTORED_PREFLIGHT_INPUT_INVALID')
    try:
        restored = _load_restored_preflight()
        report = restored.select_current_installation(
            identity_file=identity_file, installation_id=installation_id,
            bundle_root=bundle_root, trust_roots_file=trust_roots_file)
        selected = report['currentInstallation']
        if (report['identity']['database'] != 'aos_meta_head'
                or selected['installationId'] != installation_id
                or selected['authorization'] != 'CURRENT_INSTALLATION_EVIDENCE_ONLY_NO_START'
                or selected['runtimeHostEnabled'] is not False
                or selected['apiStartAuthorized'] is not False):
            raise ValueError('current restored evidence differs')
        identity = restored._identity_parameters(identity_file)
        parameters = {key: identity[key] for key in ('host', 'port', 'dbname', 'user')}
        parameters['passfile'] = identity['pgpassFile']
        if parameters['dbname'] != report['identity']['database']:
            raise ValueError('current restored database differs')
        signed = {'database': parameters['dbname'], 'installationId': selected['installationId'],
                  'signedRoot': str(bundle_root.resolve(strict=True)),
                  'trustRoots': str(trust_roots_file.resolve(strict=True))}
    except Exception:
        raise HostPreflightBlocked('RESTORED_INSTALLATION_INVALID') from None
    return _preflight_identities(parameters=parameters, signed=signed,
                                credential_file=credential_file, preparation_only=True)


def require_current_dsn_targets(dsns: dict[str, str], target: str) -> None:
    if set(dsns) != {"directory", "runtime", "web"}:
        raise HostPreflightBlocked("CREDENTIAL_FILE_INVALID")
    try:
        databases = {plane: conninfo_to_dict(dsn).get("dbname") for plane, dsn in dsns.items()}
    except Exception:
        raise HostPreflightBlocked("CREDENTIAL_FILE_INVALID") from None
    if any(database != target for database in databases.values()):
        raise HostPreflightBlocked("CREDENTIAL_DATABASE_DRIFT")


def require_current_identities(*, directory, runtime, web, authority) -> None:
    try:
        require_isolated_runtime_identities(directory=directory, runtime=runtime, web=web)
        if directory.authority != authority:
            raise RuntimeError("current signed database authority differs")
    except Exception:
        raise HostPreflightBlocked("RUNTIME_IDENTITY_INVALID") from None


def require_current_host_and_candidates(
    conn, directory, *, preparation_only: bool = False,
) -> dict[str, object]:
    if type(preparation_only) is not bool:
        raise HostPreflightBlocked("ADMISSION_MODE_INVALID")
    row = conn.execute(
        """SELECT a.state,a.host_id,i.database_role::text AS database_role,
                  i.database_role_oid,i.enabled
             FROM extension_runtime_host_assignment a
             LEFT JOIN extension_runtime_host_identity i ON i.host_id=a.host_id
            WHERE a.org_id=%s AND a.project_id=%s""",
        ("org-org", "dev-project"),
    ).fetchone()
    if row is None or row["state"] != "assigned" or not row["host_id"]:
        raise HostPreflightBlocked("HOST_ASSIGNMENT_MISSING")
    if (row["enabled"] is not True or row["database_role"] != directory.session_user
            or row["database_role_oid"] != directory.role_oid):
        raise HostPreflightBlocked("HOST_IDENTITY_MISMATCH")
    if preparation_only:
        existing = conn.execute(
            """SELECT count(*) AS enabled_bindings FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND enabled""",
            ("org-org", "dev-project"),
        ).fetchone()
        if (existing is None or type(existing["enabled_bindings"]) is not int
                or existing["enabled_bindings"] != 0):
            raise HostPreflightBlocked("ACTIVE_BINDING_REQUIRES_FULL_HOST")
    candidates = read_candidates(conn, TenantScope(org_id="org-org", project_id="dev-project"))
    if not candidates.all_present and not preparation_only:
        raise HostPreflightBlocked("CONFIGURATION_CANDIDATES_MISSING")
    return {"hostId": row["host_id"], "candidateCounts": candidates.counts,
            "admissionMode": "PREPARATION_ONLY" if preparation_only else "FULL"}


def preflight(*, signed_receipt: Path, credential_file: Path | None,
              preparation_only: bool = False) -> dict[str, object]:
    if type(preparation_only) is not bool:
        raise HostPreflightBlocked("ADMISSION_MODE_INVALID")
    if credential_file is None:
        raise HostPreflightBlocked("CREDENTIAL_FILE_REQUIRED")
    if not credential_file.is_absolute():
        raise HostPreflightBlocked("CREDENTIAL_FILE_INVALID")
    try:
        parameters, signed = signed_preflight(signed_receipt=signed_receipt)
    except Exception:
        raise HostPreflightBlocked("SIGNED_INSTALLATION_INVALID") from None
    return _preflight_identities(parameters=parameters, signed=signed,
                                credential_file=credential_file, preparation_only=preparation_only)


def _preflight_identities(*, parameters, signed, credential_file, preparation_only):
    """One unchanged database identity/admission gate for either signed reader."""
    try:
        dsns, credential_generation = _runtime_file_dsns(
            credential_file, with_generation=True)
    except Exception:
        raise HostPreflightBlocked("CREDENTIAL_FILE_INVALID") from None
    require_current_dsn_targets(dsns, signed["database"])
    try:
        with psycopg.connect(**parameters, row_factory=dict_row) as current:
            current.read_only = True
            authority_row = current.execute(
                """SELECT coalesce(inet_server_addr()::text,'local') AS server_addr,
                          inet_server_port() AS server_port,current_database() AS database_name"""
            ).fetchone()
            authority = (authority_row["server_addr"], authority_row["server_port"] or 0,
                         authority_row["database_name"])
            if authority[2] != signed["database"]:
                raise HostPreflightBlocked("SIGNED_DATABASE_DRIFT")
            with psycopg.connect(dsns["directory"], row_factory=dict_row) as directory_conn:
                directory_conn.read_only = True
                directory = probe_runtime_database_identity(
                    directory_conn, protected_relations=_PROTECTED_RELATIONS)
                with psycopg.connect(dsns["runtime"], row_factory=dict_row) as runtime_conn:
                    runtime_conn.read_only = True
                    runtime = probe_runtime_database_identity(
                        runtime_conn, protected_relations=_PROTECTED_RELATIONS)
                    with psycopg.connect(dsns["web"], row_factory=dict_row) as web_conn:
                        web_conn.read_only = True
                        web = probe_runtime_database_identity(
                            web_conn, protected_relations=_PROTECTED_RELATIONS)
                require_current_identities(directory=directory, runtime=runtime,
                                           web=web, authority=authority)
                host = require_current_host_and_candidates(
                    current, directory, preparation_only=preparation_only)
    except HostPreflightBlocked:
        raise
    except Exception:
        raise HostPreflightBlocked("DATABASE_PREFLIGHT_FAILED") from None
    try:
        _, current_generation = _runtime_file_dsns(credential_file, with_generation=True)
        if current_generation != credential_generation:
            raise HostPreflightBlocked("CREDENTIAL_FILE_CHANGED")
    except HostPreflightBlocked:
        raise
    except Exception:
        raise HostPreflightBlocked("CREDENTIAL_FILE_CHANGED") from None
    return {"outcome": "CURRENT_SIGNED_HOST_READONLY_PREFLIGHT_GREEN",
            "database": signed["database"], "installationId": signed["installationId"],
            "databaseAuthority": list(authority),
            "signedRoot": signed["signedRoot"], "trustRoots": signed["trustRoots"],
            "credentialFileGeneration": credential_generation,
            "scope": ["org-org", "dev-project"], **host,
            "authorization": "PREFLIGHT_ONLY_NO_RUNTIME_START"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signed-receipt", type=Path)
    parser.add_argument("--credential-file", type=Path)
    parser.add_argument("--preparation-only", action="store_true")
    parser.add_argument('--restored-api-identity', type=Path)
    parser.add_argument('--restored-installation')
    parser.add_argument('--bundle-root', type=Path)
    parser.add_argument('--trust-roots-file', type=Path)
    args = parser.parse_args()
    restored_values = (args.restored_api_identity, args.restored_installation,
                       args.bundle_root, args.trust_roots_file)
    if any(value is not None for value in restored_values):
        if (args.signed_receipt is not None or any(value is None for value in restored_values)
                or args.credential_file is None or not args.preparation_only):
            parser.error('restored preparation requires all exact inputs and no historical signed receipt')
    elif args.signed_receipt is None:
        parser.error('signed receipt or explicit restored preparation inputs required')
    try:
        if args.restored_api_identity is not None:
            result = preflight_restored(identity_file=args.restored_api_identity,
                installation_id=args.restored_installation, bundle_root=args.bundle_root,
                trust_roots_file=args.trust_roots_file, credential_file=args.credential_file,
                preparation_only=args.preparation_only)
        else:
            result = preflight(signed_receipt=args.signed_receipt,
                               credential_file=args.credential_file,
                               preparation_only=args.preparation_only)
        print(json.dumps(result, sort_keys=True))
        return 0
    except HostPreflightBlocked as exc:
        print(json.dumps({"outcome": "SAFE_BLOCKED", "reasonCode": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
