#!/usr/bin/env python3
"""Provision isolated local runtime-host identities; read-only preflight by default."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import secrets
import stat
import subprocess
import uuid
from pathlib import Path
from typing import Any, Sequence

from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT.parent / ".aos-recovery-20260912"
STATE = RECOVERY / "state/ecommerce-runtime-host"
OUTPUT = RECOVERY / "logs/ecommerce-runtime-host-bootstrap.json"
CONTEXT = "colima-aos-extension"
CONTAINER = "aos-a0v-recovery-pg"
DATABASE = "aos_meta_head"
HOST_ID = "a0v-local-ecommerce-host-20260912"
ORG_ID, PROJECT_ID = "org-org", "dev-project"
CANARY_ORG_ID = "dev-org"
ROLES = {
    "web": "aos_a0v_web_20260912",
    "runtime": "aos_a0v_runtime_20260912",
    "directory": "aos_a0v_directory_20260912",
}


class BootstrapBlocked(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _load_first() -> Any:
    path = ROOT / "scripts/a0v_canonical_ecommerce_first_install.py"
    spec = importlib.util.spec_from_file_location("runtime_host_first_install", path)
    if spec is None or spec.loader is None:
        raise BootstrapBlocked("FIRST_INSTALLER_UNAVAILABLE", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _command_hash(value: dict[str, Any]) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _credentials(path: Path, *, parameters: dict[str, str], create: bool) -> dict[str, Any]:
    if path.exists():
        if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise BootstrapBlocked("CREDENTIAL_FILE_INVALID", str(path))
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BootstrapBlocked("CREDENTIAL_FILE_INVALID", str(path)) from exc
        if not isinstance(value, dict) or set(value) != set(ROLES):
            raise BootstrapBlocked("CREDENTIAL_FILE_INVALID", str(path))
        return value
    if not create:
        return {}
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    value = {}
    for plane, role in ROLES.items():
        password = secrets.token_urlsafe(36)
        dsn = make_conninfo(
            host=parameters["host"], port=parameters["port"], dbname=DATABASE,
            user=role, password=password, application_name=f"aos-a0v-{plane}",
        )
        value[plane] = {"role": role, "password": password, "dsn": dsn}
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
    return value


def _inspect(conn: Any) -> dict[str, Any]:
    roles = {}
    for plane, role in ROLES.items():
        row = conn.execute(
            """SELECT rolcanlogin,rolsuper,rolbypassrls,
                      pg_has_role(%s,'aos_runtime','member') AS runtime_member,
                      pg_has_role(%s,'aos_extension_directory','member') AS directory_member
                 FROM pg_roles WHERE rolname=%s""", (role, role, role)
        ).fetchone()
        roles[plane] = None if row is None else dict(row)
    identity = conn.execute(
        "SELECT database_role::text,host_id,enabled,revision FROM extension_runtime_host_identity WHERE host_id=%s",
        (HOST_ID,),
    ).fetchone()
    assignment = conn.execute(
        "SELECT host_id,state,revision FROM extension_runtime_host_assignment WHERE org_id=%s AND project_id=%s",
        (ORG_ID, PROJECT_ID),
    ).fetchone()
    canary = conn.execute(
        "SELECT count(*) AS count FROM extension_runtime_host_assignment WHERE org_id=%s AND project_id=%s",
        (CANARY_ORG_ID, PROJECT_ID),
    ).fetchone()
    return {"roles": roles, "identity": None if identity is None else dict(identity),
            "assignment": None if assignment is None else dict(assignment),
            "canaryAssignments": int(canary["count"])}


def _assert_exact(snapshot: dict[str, Any], *, applied: bool) -> None:
    expected_membership = {"web": (False, False), "runtime": (True, False), "directory": (False, True)}
    for plane, expected in expected_membership.items():
        row = snapshot["roles"][plane]
        if row is None:
            if applied:
                raise BootstrapBlocked("LOGIN_ROLE_MISSING", plane)
            continue
        actual = (row["runtime_member"], row["directory_member"])
        if not row["rolcanlogin"] or row["rolsuper"] or row["rolbypassrls"] or actual != expected:
            raise BootstrapBlocked("LOGIN_ROLE_DRIFT", plane)
    if snapshot["canaryAssignments"] != 0:
        raise BootstrapBlocked("CANARY_ASSIGNMENT_PRESENT", CANARY_ORG_ID)
    if snapshot["identity"] is not None and snapshot["identity"] != {
        "database_role": ROLES["directory"], "host_id": HOST_ID,
        "enabled": True, "revision": 1,
    }:
        raise BootstrapBlocked("HOST_IDENTITY_DRIFT", HOST_ID)
    if snapshot["assignment"] is not None and snapshot["assignment"] != {
        "host_id": HOST_ID, "state": "assigned", "revision": 1,
    }:
        raise BootstrapBlocked("HOST_ASSIGNMENT_DRIFT", HOST_ID)
    if applied:
        if snapshot["identity"] != {"database_role": ROLES["directory"], "host_id": HOST_ID, "enabled": True, "revision": 1}:
            raise BootstrapBlocked("HOST_IDENTITY_DRIFT", HOST_ID)
        if snapshot["assignment"] != {"host_id": HOST_ID, "state": "assigned", "revision": 1}:
            raise BootstrapBlocked("HOST_ASSIGNMENT_DRIFT", HOST_ID)


def _provision(conn: Any, credentials: dict[str, Any]) -> None:
    for plane, role in ROLES.items():
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
        if exists is None:
            conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS NOINHERIT").format(
                    sql.Identifier(role), sql.Literal(credentials[plane]["password"])
                )
            )
    conn.execute(sql.SQL("GRANT aos_runtime TO {}").format(sql.Identifier(ROLES["runtime"])))
    conn.execute(sql.SQL("GRANT aos_extension_directory TO {}").format(sql.Identifier(ROLES["directory"])))
    identity_payload = {"databaseRole": ROLES["directory"], "hostId": HOST_ID, "enabled": True}
    conn.execute(
        "SELECT extension_runtime_bind_host_identity(%s,%s,true,0,%s,%s,%s)",
        (ROLES["directory"], HOST_ID, "a0v-runtime-host-bootstrap",
         "a0v-runtime-host-identity-v1", _command_hash(identity_payload)),
    )
    assignment_payload = {"orgId": ORG_ID, "projectId": PROJECT_ID, "hostId": HOST_ID, "state": "assigned"}
    conn.execute(
        "SELECT extension_runtime_set_host_assignment(%s,%s,%s,'assigned',0,%s,%s,%s)",
        (ORG_ID, PROJECT_ID, HOST_ID, "a0v-runtime-host-bootstrap",
         "a0v-runtime-host-assignment-v1", _command_hash(assignment_payload)),
    )


def _backup(state_dir: Path) -> dict[str, Any]:
    try:
        inspected = json.loads(subprocess.check_output(
            ["docker", "--context", CONTEXT, "inspect", "--format", "{{json .}}", CONTAINER],
            text=True, stderr=subprocess.PIPE, timeout=15,
        ))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise BootstrapBlocked("DATABASE_CONTAINER_UNAVAILABLE", CONTAINER) from exc
    environment = {}
    for item in (inspected.get("Config") or {}).get("Env") or ():
        if isinstance(item, str) and "=" in item:
            key, value = item.split("=", 1)
            environment[key] = value
    directory = state_dir.resolve() / "backups"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    target = directory / "aos_meta_head-pre-runtime-host-bootstrap.dump"
    if not target.exists():
        temporary = target.with_name(target.name + ".tmp-" + uuid.uuid4().hex)
        try:
            with temporary.open("xb") as handle:
                completed = subprocess.run(
                    ["docker", "--context", CONTEXT, "exec", CONTAINER, "pg_dump",
                     "-U", environment.get("POSTGRES_USER", "postgres"), "--dbname", DATABASE,
                     "--format=custom", "--no-owner", "--no-privileges"],
                    stdout=handle, stderr=subprocess.PIPE, timeout=120, check=False,
                )
            if completed.returncode != 0 or temporary.stat().st_size <= 0:
                raise BootstrapBlocked("DATABASE_BACKUP_FAILED", str(target))
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    if not target.is_file() or target.stat().st_size <= 0:
        raise BootstrapBlocked("DATABASE_BACKUP_INVALID", str(target))
    return {"path": str(target), "size": target.stat().st_size, "sha256": _sha(target.read_bytes())}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database-name")
    parser.add_argument("--state-dir", type=Path, default=STATE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.apply and args.database_name != DATABASE:
        raise BootstrapBlocked("EXPLICIT_ISOLATED_DATABASE_REQUIRED", DATABASE)
    first = _load_first()
    connect = first.container_database_connect_factory(
        context=CONTEXT, container=CONTAINER, database_name=DATABASE
    )
    credential_path = args.state_dir.resolve() / "runtime-host-identities.json"
    with connect() as conn:
        before = _inspect(conn)
        _assert_exact(before, applied=False)
        parameters = conn.info.get_parameters()
    credentials = _credentials(
        credential_path,
        parameters={"host": parameters["host"], "port": parameters["port"]},
        create=args.apply,
    )
    if not args.apply:
        return {"outcome": "PREFLIGHT_GREEN", "mode": "preflight", "database": DATABASE,
                "credentialStatePresent": bool(credentials), "before": before}
    backup = _backup(args.state_dir)
    with connect() as conn:
        _provision(conn, credentials)
        conn.commit()
    with connect() as conn:
        after = _inspect(conn)
    _assert_exact(after, applied=True)
    return {"outcome": "RUNTIME_HOST_BOOTSTRAP_GREEN", "mode": "apply", "database": DATABASE,
            "hostId": HOST_ID, "roles": ROLES, "credentialFile": str(credential_path),
            "credentialFileHash": _sha(credential_path.read_bytes()), "backup": backup,
            "before": before, "after": after,
            "effects": {"providerInvocationCount": 0, "externalPublicationCount": 0,
                        "installationMutationCount": 0}}


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run(args)
        code = 0
    except BootstrapBlocked as exc:
        result = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.code, "message": str(exc)}
        code = 2
    except Exception as exc:
        result = {"outcome": "SAFE_BLOCKED", "reasonCode": "UNEXPECTED_DOMAIN_ERROR",
                  "errorType": type(exc).__name__, "message": str(exc)}
        code = 2
    _write(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
