"""Default-off independent database identity for a future formal Eval writer."""
from __future__ import annotations

import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row


_CREDENTIAL_FILE = "AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE"
_SCHEMA = "aos.aip.eval-writer-identity/v1"
_ROLE = "aos_aip_eval_writer"


def _unique_pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError("duplicate Eval writer identity field")
        value[key] = item
    return value


def _identity_file() -> dict[str, str]:
    try:
        reference = os.getenv(_CREDENTIAL_FILE, "").strip()
        path = Path(reference)
        if not reference or not path.is_absolute():
            raise ValueError("absolute identity reference required")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            metadata = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_uid != os.getuid()
                or not 0 < metadata.st_size <= 65536
            ):
                raise ValueError("protected Eval writer file required")
            raw = handle.read(65537)
        if len(raw.encode("utf-8")) > 65536:
            raise ValueError("Eval writer identity too large")
        value = json.loads(raw, object_pairs_hook=_unique_pairs)
        if (
            type(value) is not dict
            or set(value) != {"schemaVersion", "dsn", "role"}
            or value["schemaVersion"] != _SCHEMA
            or value["role"] != _ROLE
            or type(value["dsn"]) is not str
            or not value["dsn"]
            or value["dsn"] != value["dsn"].strip()
            or "\x00" in value["dsn"]
        ):
            raise ValueError("Eval writer identity shape differs")
        return value
    except Exception:
        raise RuntimeError("Eval writer identity reference is invalid") from None


def _verify_identity(conn: psycopg.Connection, expected_database: str) -> None:
    row = conn.execute("""SELECT session_user AS session_name,
        current_user AS current_name,current_database() AS database_name,
        rolcanlogin,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,
        rolreplication,rolinherit
        FROM pg_catalog.pg_roles WHERE rolname=session_user""").fetchone()
    if (
        row is None
        or row["database_name"] != expected_database
        or row["session_name"] != row["current_name"]
        or row["session_name"] in (_ROLE, "aos_runtime", "aos_app")
        or row["rolcanlogin"] is not True
        or row["rolinherit"] is not False
        or any(row[key] is not False for key in (
            "rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication"
        ))
    ):
        raise ValueError("independent unprivileged Eval writer login required")
    reachable = conn.execute("""SELECT rolname,rolcanlogin,rolsuper,
        rolbypassrls,rolcreaterole,rolcreatedb,rolreplication,rolinherit
        FROM pg_catalog.pg_roles WHERE rolname<>session_user
          AND pg_catalog.pg_has_role(session_user,oid,'MEMBER')""").fetchall()
    if (
        len(reachable) != 1
        or reachable[0]["rolname"] != _ROLE
        or any(reachable[0][key] is not False for key in (
            "rolcanlogin", "rolsuper", "rolbypassrls", "rolcreaterole",
            "rolcreatedb", "rolreplication", "rolinherit"
        ))
    ):
        raise ValueError("Eval writer role reachability differs")
    admin = conn.execute("""SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m
        JOIN pg_catalog.pg_roles r ON r.oid=m.member
        WHERE r.rolname=session_user AND m.admin_option) AS unsafe""").fetchone()
    if admin is None or admin["unsafe"] is not False:
        raise ValueError("Eval writer role administration is forbidden")


@contextmanager
def eval_writer_connection(*, expected_database: str):
    """Verify one independent login; grants and signed authority are separate gates."""
    if not isinstance(expected_database, str) or not expected_database:
        raise RuntimeError("Eval writer expected database is required")
    identity = _identity_file()
    try:
        conn = psycopg.connect(identity["dsn"], row_factory=dict_row, connect_timeout=10)
    except Exception:
        raise RuntimeError("Eval writer identity connection unavailable") from None
    with conn:
        try:
            if conn.info.transaction_status != TransactionStatus.IDLE:
                raise ValueError("idle Eval writer connection required")
            with conn.transaction():
                conn.execute("SET LOCAL statement_timeout='3s'")
                _verify_identity(conn, expected_database)
            if conn.info.transaction_status != TransactionStatus.IDLE:
                raise ValueError("Eval writer identity check must finish")
        except Exception:
            raise RuntimeError("Eval writer identity is not permitted") from None
        yield conn


def configured_eval_writer_connection():
    """Never fall back to the runtime or superuser identity."""
    return eval_writer_connection if os.getenv(_CREDENTIAL_FILE, "").strip() else None
