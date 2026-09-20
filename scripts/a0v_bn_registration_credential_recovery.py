#!/usr/bin/env python3
"""Recover BN's independent least-privilege registration identity."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from typing import Any

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

import a0v_bm_runtime_credential_rotation as admin


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/aos-api"))
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/bn-registration-credentials"
CREDENTIAL_FILE = STATE / "registration-main-identity.json"
ROLE = "aos_ecommerce_registration_control"
EXPECTED_MEMBERS = {"aos_runtime", "aos_extension_maintainer"}


class RecoveryBlocked(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _freeze(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def _inspect(conn: Any) -> dict[str, Any]:
    role = conn.execute(
        """SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,
                  rolreplication,rolinherit FROM pg_roles WHERE rolname=%s""", (ROLE,)
    ).fetchone()
    members = conn.execute(
        """SELECT target.rolname,m.admin_option
             FROM pg_auth_members m JOIN pg_roles member ON member.oid=m.member
             JOIN pg_roles target ON target.oid=m.roleid
            WHERE member.rolname=%s ORDER BY target.rolname""", (ROLE,)
    ).fetchall()
    return {"role": None if role is None else dict(role),
            "members": [dict(row) for row in members]}


def _assert_exact(snapshot: dict[str, Any]) -> None:
    role = snapshot["role"]
    if role is None or role != {"rolcanlogin": True, "rolsuper": False,
            "rolbypassrls": False, "rolcreaterole": False, "rolcreatedb": False,
            "rolreplication": False, "rolinherit": False}:
        raise RecoveryBlocked("REGISTRATION_ROLE_DRIFT", ROLE)
    members = snapshot["members"]
    if {row["rolname"] for row in members} != EXPECTED_MEMBERS or len(members) != 2:
        raise RecoveryBlocked("REGISTRATION_MEMBERSHIP_DRIFT", ROLE)
    if any(row["admin_option"] for row in members):
        raise RecoveryBlocked("REGISTRATION_ADMIN_OPTION_PRESENT", ROLE)


def _load() -> dict[str, str]:
    if (CREDENTIAL_FILE.is_symlink() or not CREDENTIAL_FILE.is_file()
            or stat.S_IMODE(CREDENTIAL_FILE.stat().st_mode) != 0o600):
        raise RecoveryBlocked("REGISTRATION_CREDENTIAL_FILE_INVALID", str(CREDENTIAL_FILE))
    value = json.loads(CREDENTIAL_FILE.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or set(value) != {"schemaVersion", "dsn", "role"}
            or value["schemaVersion"] != "aos.ecommerce.registration-identity/v1"
            or value["role"] != ROLE or not isinstance(value["dsn"], str)):
        raise RecoveryBlocked("REGISTRATION_CREDENTIAL_FILE_INVALID", str(CREDENTIAL_FILE))
    return value


def _probe() -> dict[str, Any]:
    identity = _load()
    previous = os.environ.get("AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE")
    os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(CREDENTIAL_FILE)
    try:
        from aos_api.ecommerce_growth_registration_connection import registration_connection
        with registration_connection() as conn:
            row = dict(conn.execute("SELECT session_user,current_user,current_database()").fetchone())
    except Exception as exc:
        raise RecoveryBlocked("REGISTRATION_CREDENTIAL_PROBE_FAILED", ROLE) from exc
    finally:
        if previous is None:
            os.environ.pop("AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE", None)
        else:
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = previous
    if row != {"session_user": ROLE, "current_user": ROLE, "current_database": admin.DATABASE}:
        raise RecoveryBlocked("REGISTRATION_CREDENTIAL_ROLE_MISMATCH", ROLE)
    return {"connected": True, "role": identity["role"], "database": row["current_database"]}


def preflight() -> dict[str, Any]:
    with admin._connect()() as conn:
        snapshot = _inspect(conn)
    _assert_exact(snapshot)
    probe = _probe() if CREDENTIAL_FILE.exists() else None
    return {"outcome": "BN_REGISTRATION_CREDENTIAL_PREFLIGHT_GREEN", "snapshot": snapshot,
            "credentialStatePresent": CREDENTIAL_FILE.exists(), "credentialProbe": probe}


def apply() -> dict[str, Any]:
    with admin._connect()() as conn:
        before = _inspect(conn)
        parameters = conn.info.get_parameters()
    _assert_exact(before)
    reconciled = CREDENTIAL_FILE.exists()
    if reconciled:
        identity = _load()
        try:
            probe = _probe()
            return {"outcome": "BN_REGISTRATION_CREDENTIAL_RECOVERY_GREEN",
                    "reconciled": True, "credentialFile": str(CREDENTIAL_FILE),
                    "credentialFileHash": _sha(CREDENTIAL_FILE.read_bytes()),
                    "before": before, "after": before, "credentialProbe": probe,
                    "effects": _zero_effects()}
        except RecoveryBlocked as exc:
            if exc.code != "REGISTRATION_CREDENTIAL_PROBE_FAILED":
                raise
    else:
        password = secrets.token_urlsafe(48)
        identity = {"schemaVersion": "aos.ecommerce.registration-identity/v1", "role": ROLE,
                    "dsn": make_conninfo(host=parameters["host"], port=parameters["port"],
                                         dbname=admin.DATABASE, user=ROLE, password=password,
                                         application_name="aos-a0v-bn-registration")}
        _freeze(CREDENTIAL_FILE, identity)
        _freeze(STATE / "rotation-intent.json", {"role": ROLE,
                "credentialFileHash": _sha(CREDENTIAL_FILE.read_bytes())})
    password = conninfo_to_dict(identity["dsn"])["password"]
    with admin._connect()() as conn:
        conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
            sql.Identifier(ROLE), sql.Literal(password)))
        conn.commit()
    probe = _probe()
    with admin._connect()() as conn:
        after = _inspect(conn)
    _assert_exact(after)
    return {"outcome": "BN_REGISTRATION_CREDENTIAL_RECOVERY_GREEN", "reconciled": reconciled,
            "credentialFile": str(CREDENTIAL_FILE),
            "credentialFileHash": _sha(CREDENTIAL_FILE.read_bytes()), "before": before,
            "after": after, "credentialProbe": probe, "effects": _zero_effects()}


def _zero_effects() -> dict[str, int]:
    return {"installationMutationCount": 0, "routeMutationCount": 0,
            "attemptCount": 0, "businessWriteCount": 0, "canaryWriteCount": 0,
            "sourceReadCount": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "apply"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result, code = globals()[args.action](), 0
    except RecoveryBlocked as exc:
        result, code = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.code,
                        "message": str(exc)}, 2
    except Exception as exc:
        result, code = {"outcome": "SAFE_BLOCKED", "reasonCode": type(exc).__name__.upper(),
                        "message": str(exc)}, 2
    _freeze(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
