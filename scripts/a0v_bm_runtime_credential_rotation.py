#!/usr/bin/env python3
"""Rotate the three fixed A0-V runtime-host login credentials for BM."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import uuid
from typing import Any

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/bm-runtime-credentials"
CREDENTIAL_FILE = STATE / "runtime-host-identities.json"
CONTEXT = "colima-aos-extension"
CONTAINER = "aos-a0v-recovery-pg"
DATABASE = "aos_meta_head"
HOST_ID = "a0v-local-ecommerce-host-20260912"
ROLES = {
    "web": "aos_a0v_web_20260912",
    "runtime": "aos_a0v_runtime_20260912",
    "directory": "aos_a0v_directory_20260912",
}


class RotationBlocked(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _first() -> Any:
    path = ROOT / "scripts/a0v_canonical_ecommerce_first_install.py"
    spec = importlib.util.spec_from_file_location("bm_credential_first", path)
    if spec is None or spec.loader is None:
        raise RotationBlocked("FIRST_INSTALLER_UNAVAILABLE", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _freeze(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def _connect() -> Any:
    return _first().container_database_connect_factory(
        context=CONTEXT, container=CONTAINER, database_name=DATABASE
    )


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
        "SELECT host_id,state,revision FROM extension_runtime_host_assignment WHERE org_id='org-org' AND project_id='dev-project'"
    ).fetchone()
    canary = conn.execute(
        "SELECT count(*) AS n FROM extension_runtime_host_assignment WHERE org_id='dev-org' AND project_id='dev-project'"
    ).fetchone()["n"]
    return {"roles": roles, "identity": None if identity is None else dict(identity),
            "assignment": None if assignment is None else dict(assignment), "canaryAssignments": int(canary)}


def _assert_exact(value: dict[str, Any]) -> None:
    membership = {"web": (False, False), "runtime": (True, False), "directory": (False, True)}
    for plane, expected in membership.items():
        row = value["roles"].get(plane)
        if row is None or not row["rolcanlogin"] or row["rolsuper"] or row["rolbypassrls"]:
            raise RotationBlocked("LOGIN_ROLE_DRIFT", plane)
        if (row["runtime_member"], row["directory_member"]) != expected:
            raise RotationBlocked("LOGIN_ROLE_MEMBERSHIP_DRIFT", plane)
    if value["identity"] != {"database_role": ROLES["directory"], "host_id": HOST_ID,
                              "enabled": True, "revision": 1}:
        raise RotationBlocked("HOST_IDENTITY_DRIFT", HOST_ID)
    if value["assignment"] != {"host_id": HOST_ID, "state": "assigned", "revision": 1}:
        raise RotationBlocked("HOST_ASSIGNMENT_DRIFT", HOST_ID)
    if value["canaryAssignments"] != 0:
        raise RotationBlocked("CANARY_ASSIGNMENT_PRESENT", "dev-org/dev-project")


def _new_credentials(parameters: dict[str, str]) -> dict[str, dict[str, str]]:
    return {plane: {"role": role, "password": (password := secrets.token_urlsafe(36)),
                    "dsn": make_conninfo(host=parameters["host"], port=parameters["port"],
                                         dbname=DATABASE, user=role, password=password,
                                         application_name=f"aos-a0v-bm-{plane}")}
            for plane, role in ROLES.items()}


def _load_credentials() -> dict[str, dict[str, str]]:
    if CREDENTIAL_FILE.is_symlink() or not CREDENTIAL_FILE.is_file() or stat.S_IMODE(CREDENTIAL_FILE.stat().st_mode) != 0o600:
        raise RotationBlocked("CREDENTIAL_FILE_INVALID", str(CREDENTIAL_FILE))
    value = json.loads(CREDENTIAL_FILE.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != set(ROLES):
        raise RotationBlocked("CREDENTIAL_FILE_INVALID", str(CREDENTIAL_FILE))
    return value


def _backup() -> dict[str, Any]:
    target = STATE / "backups/aos_meta_head-pre-bm-credential-rotation.dump"
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not target.exists():
        inspected = json.loads(subprocess.check_output(
            ["docker", "--context", CONTEXT, "inspect", "--format", "{{json .}}", CONTAINER],
            text=True, timeout=15,
        ))
        environment = dict(item.split("=", 1) for item in (inspected.get("Config") or {}).get("Env") or () if "=" in item)
        user = environment.get("POSTGRES_USER")
        if not user:
            raise RotationBlocked("DATABASE_USER_UNAVAILABLE", CONTAINER)
        temporary = target.with_name(target.name + ".tmp-" + uuid.uuid4().hex)
        with temporary.open("xb") as stream:
            completed = subprocess.run(
                ["docker", "--context", CONTEXT, "exec", CONTAINER, "pg_dump", "-U", user,
                 "--dbname", DATABASE, "--format=custom", "--no-owner", "--no-privileges"],
                stdout=stream, stderr=subprocess.PIPE, timeout=120, check=False,
            )
        if completed.returncode != 0 or temporary.stat().st_size == 0:
            temporary.unlink(missing_ok=True)
            raise RotationBlocked("DATABASE_BACKUP_FAILED", str(target))
        temporary.replace(target)
    return {"path": str(target), "size": target.stat().st_size, "sha256": _sha(target.read_bytes())}


def _probe(credentials: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    probes = []
    for plane, role in ROLES.items():
        try:
            with psycopg.connect(credentials[plane]["dsn"], row_factory=dict_row, connect_timeout=5) as conn:
                row = conn.execute(
                    "SELECT current_user AS role, pg_has_role(current_user,'aos_runtime','member') AS runtime_member, pg_has_role(current_user,'aos_extension_directory','member') AS directory_member"
                ).fetchone()
        except psycopg.Error as exc:
            raise RotationBlocked("CREDENTIAL_PROBE_FAILED", plane) from exc
        if row["role"] != role:
            raise RotationBlocked("CREDENTIAL_ROLE_MISMATCH", plane)
        probes.append({"plane": plane, "role": role, "connected": True,
                       "runtimeMember": row["runtime_member"], "directoryMember": row["directory_member"]})
    return probes


def preflight() -> dict[str, Any]:
    with _connect()() as conn:
        snapshot = _inspect(conn)
        parameters = conn.info.get_parameters()
    _assert_exact(snapshot)
    probes = _probe(_load_credentials()) if CREDENTIAL_FILE.exists() else []
    return {"outcome": "BM_CREDENTIAL_PREFLIGHT_GREEN", "snapshot": snapshot,
            "credentialStatePresent": CREDENTIAL_FILE.exists(), "credentialProbes": probes,
            "databaseHost": parameters["host"], "databasePort": parameters["port"]}


def apply() -> dict[str, Any]:
    before = preflight()
    if CREDENTIAL_FILE.exists():
        if len(before["credentialProbes"]) != 3:
            raise RotationBlocked("CREDENTIAL_RECONCILIATION_FAILED", str(CREDENTIAL_FILE))
        return {**before, "outcome": "BM_RUNTIME_CREDENTIAL_ROTATION_GREEN", "reconciled": True}
    with _connect()() as conn:
        parameters = conn.info.get_parameters()
    credentials = _new_credentials({"host": parameters["host"], "port": parameters["port"]})
    CREDENTIAL_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _freeze(CREDENTIAL_FILE, credentials)
    _freeze(STATE / "rotation-intent.json", {"roles": ROLES,
        "credentialFileHash": _sha(CREDENTIAL_FILE.read_bytes()), "hostId": HOST_ID})
    backup = _backup()
    with _connect()() as conn:
        for plane, role in ROLES.items():
            conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(credentials[plane]["password"])))
        conn.commit()
    probes = _probe(credentials)
    with _connect()() as conn:
        after = _inspect(conn)
    _assert_exact(after)
    return {"outcome": "BM_RUNTIME_CREDENTIAL_ROTATION_GREEN", "reconciled": False,
            "roles": ROLES, "hostId": HOST_ID, "credentialFile": str(CREDENTIAL_FILE),
            "credentialFileHash": _sha(CREDENTIAL_FILE.read_bytes()), "backup": backup,
            "before": before["snapshot"], "after": after, "credentialProbes": probes,
            "effects": {"installationMutationCount": 0, "providerInvocationCount": 0,
                        "externalPublicationCount": 0, "sourceReadCount": 0}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "apply"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = globals()[args.action]()
        code = 0
    except RotationBlocked as exc:
        result = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.code, "message": str(exc)}
        code = 2
    except Exception as exc:
        result = {"outcome": "SAFE_BLOCKED", "reasonCode": type(exc).__name__.upper(), "message": str(exc)}
        code = 2
    _freeze(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
