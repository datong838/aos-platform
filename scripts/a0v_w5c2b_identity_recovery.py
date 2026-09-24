#!/usr/bin/env python3
"""Journaled password rotation for the existing non-privileged installation role."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c2a_ds_uninstall as prior

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c2b-installation-identity")
ROLE = "aos_a0v_installation_20260912"
IDENTITY = STATE / "installation-identity.json"


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    fd = os.open(STATE / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, ensure_ascii=False, default=str)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def _read(name):
    path = STATE / name
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("W5C2B_PRIVATE_IDENTITY_REQUIRED")
    return json.loads(path.read_text())


def preflight():
    prior.preflight()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute("""SELECT rolcanlogin,rolsuper,rolbypassrls,rolinherit,
          pg_has_role(%s,'aos_app','member') AS app_member FROM pg_roles WHERE rolname=%s""",
          (ROLE, ROLE)).fetchone()
        connections = conn.execute("""SELECT count(*) AS n FROM pg_stat_activity
          WHERE usename=%s AND pid<>pg_backend_pid()""", (ROLE,)).fetchone()["n"]
        command = conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id='org-org' AND project_id='dev-project'
          AND idempotency_key='a0v-w5c2a-ds-uninstall-20260924-v1'""").fetchone()["n"]
    if (row is None or dict(row) != {"rolcanlogin": True, "rolsuper": False,
            "rolbypassrls": False, "rolinherit": False, "app_member": True}
            or connections != 0 or command != 0):
        raise ValueError("W5C2B_INSTALLATION_ROLE_DRIFT")
    return {"outcome": "W5C2B_IDENTITY_PREFLIGHT_GREEN", "role": ROLE,
            "activeConnections": 0, "oldUninstallCommands": 0}


def rotate():
    if STATE.exists():
        raise ValueError("W5C2B_IDENTITY_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    password = secrets.token_urlsafe(48)
    _write("intent.json", {**before, "password": password, "resend": False})
    try:
        with database_connect("aos_meta_head")() as conn:
            current = conn.execute("""SELECT count(*) AS n FROM pg_stat_activity
              WHERE usename=%s AND pid<>pg_backend_pid()""", (ROLE,)).fetchone()["n"]
            if current:
                raise ValueError("W5C2B_ROLE_BECAME_ACTIVE")
            conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(ROLE), sql.Literal(password)))
    except Exception:
        raise ValueError("W5C2B_ROLE_ROTATION_BOUNDARY_RECONCILE_ONLY") from None
    result = verify()
    _write("installation-identity.json", {"role": ROLE, "password": password})
    _write("result.json", result)
    return result


def verify():
    intent = _read("intent.json")
    password = intent["password"]
    if intent["role"] != ROLE or not isinstance(password, str) or len(password) < 48:
        raise ValueError("W5C2B_INTENT_INVALID")
    try:
        with psycopg.connect(host="127.0.0.1", port=18435, dbname="aos_meta_head",
                             user=ROLE, password=password, row_factory=dict_row) as conn:
            identity = conn.execute("SELECT session_user,current_user").fetchone()
            if dict(identity) != {"session_user": ROLE, "current_user": ROLE}:
                raise ValueError("W5C2B_SESSION_USER_DRIFT")
            conn.execute("SET ROLE aos_app")
            role = conn.execute("SELECT session_user,current_user").fetchone()
            if dict(role) != {"session_user": ROLE, "current_user": "aos_app"}:
                raise ValueError("W5C2B_APP_ROLE_DRIFT")
    except Exception:
        raise ValueError("W5C2B_IDENTITY_VERIFY_FAILED_RECONCILE_ONLY") from None
    return {"outcome": "W5C2B_INSTALLATION_IDENTITY_GREEN", "sessionUser": ROLE,
            "adoptedRole": "aos_app", "passwordPrinted": False}


@contextmanager
def installation_connection():
    identity = _read("installation-identity.json")
    if identity.get("role") != ROLE or identity.get("password") != _read("intent.json")["password"]:
        raise ValueError("W5C2B_IDENTITY_FILE_DRIFT")
    with psycopg.connect(host="127.0.0.1", port=18435, dbname="aos_meta_head",
                         user=ROLE, password=identity["password"], row_factory=dict_row) as conn:
        conn.execute("SET ROLE aos_app")
        conn.commit()
        yield conn


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "rotate", "verify"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False))
