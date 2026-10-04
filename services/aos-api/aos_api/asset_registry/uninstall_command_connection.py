"""Protected, dedicated database login for a runtime installation uninstall command."""

from contextlib import contextmanager
import os
import re

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from aos_api.db import get_dsn
from aos_api.extension_runtime.restricted_api_identity import read_identity


CREDENTIAL_FILE = "AOS_INSTALLATION_UNINSTALL_COMMAND_CREDENTIAL_FILE"
_SCHEMA = "aos.installation-uninstall-command-identity/v1"


def _identity():
    try:
        value = read_identity(
            os.getenv(CREDENTIAL_FILE, "").strip(),
            schema_version=_SCHEMA,
            logical_role="aos_app",
            label="Uninstall command",
        )
        command = conninfo_to_dict(value["dsn"])
        web = conninfo_to_dict(get_dsn())
        target = ("host", "port", "dbname")
        if (any(not command.get(key) or command[key] != web.get(key) for key in target)
                or any(command.get(key) for key in ("hostaddr", "service", "servicefile", "options"))
                or command.get("user") != value["role"]
                or command.get("user") == web.get("user")
                or value["dsn"] == get_dsn()):
            raise ValueError()
        return value
    except Exception:
        raise RuntimeError("uninstall command identity reference is invalid") from None


def _verify_connection(conn, expected_role, protected_schema):
    try:
        row = conn.execute(
            """SELECT session_user AS session_name,current_user AS current_name,
                current_database() AS database_name,
                r.rolcanlogin,r.rolinherit,r.rolsuper,r.rolbypassrls,
                r.rolcreaterole,r.rolcreatedb,r.rolreplication,
                pg_has_role(session_user,'aos_app','MEMBER') AS app_member,
                pg_has_role(session_user,'aos_app','USAGE') AS app_usage,
                pg_has_role(session_user,'aos_app','SET') AS app_set,
                pg_has_role(session_user,'aos_runtime','MEMBER') AS runtime_member,
                has_table_privilege(session_user,%s,'UPDATE')
                    AS binding_update,
                (SELECT count(*) FROM pg_catalog.pg_auth_members m
                    JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid
                    WHERE m.member=r.oid AND granted.rolname<>'aos_app') AS extra_roles,
                (SELECT bool_or(m.admin_option) FROM pg_catalog.pg_auth_members m
                    JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid
                    WHERE m.member=r.oid AND granted.rolname='aos_app') AS app_admin
                FROM pg_catalog.pg_roles r WHERE r.rolname=session_user""",
            (protected_schema + ".extension_runtime_binding",),
        ).fetchone()
        expected_db = conninfo_to_dict(get_dsn())["dbname"]
        if (row is None or row["session_name"] != expected_role
                or row["current_name"] != expected_role
                or row["database_name"] != expected_db
                or row["rolcanlogin"] is not True
                or any(row[key] is not False for key in (
                    "rolinherit", "rolsuper", "rolbypassrls", "rolcreaterole",
                    "rolcreatedb", "rolreplication", "app_usage", "app_set",
                    "runtime_member", "binding_update", "app_admin"
                ))
                or row["app_member"] is not True or row["extra_roles"] != 0):
            raise ValueError()
    except Exception:
        raise RuntimeError("uninstall command identity is not permitted") from None


@contextmanager
def connect_uninstall_command(*, _protected_schema="public"):
    """Verify the least-privilege session before yielding one command transaction."""
    if re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", _protected_schema) is None:
        raise RuntimeError("uninstall command protected schema is invalid")
    identity = _identity()
    try:
        conn = psycopg.connect(identity["dsn"], row_factory=dict_row, connect_timeout=10)
    except Exception:
        raise RuntimeError("uninstall command identity connection unavailable") from None
    with conn:
        conn.read_only = True
        try:
            _verify_connection(conn, identity["role"], _protected_schema)
            conn.commit()
            conn.read_only = False
        except Exception:
            conn.rollback()
            raise
        yield conn
