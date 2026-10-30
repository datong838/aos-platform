"""Protected database login for Route worker customer lifecycle receipts."""

from __future__ import annotations

from contextlib import contextmanager
import os
import re

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from aos_api.db import get_dsn
from aos_api.extension_runtime.restricted_api_identity import read_identity


CREDENTIAL_FILE = "AOS_ROUTE_WORKER_LIFECYCLE_COMMAND_CREDENTIAL_FILE"
_SCHEMA = "aos.route-worker-lifecycle-command-identity/v1"
_TABLE = "bundle_installation_command"
_POLICY = "route_worker_lifecycle_command_scope"
_SCOPE_PREDICATE = (
    "((org_id = 'org-org'::text) AND (project_id = 'dev-project'::text))"
)


def _identity() -> dict[str, str]:
    try:
        value = read_identity(
            os.getenv(CREDENTIAL_FILE, "").strip(),
            schema_version=_SCHEMA,
            logical_role="aos_runtime",
            label="Route worker lifecycle command",
        )
        command = conninfo_to_dict(value["dsn"])
        web_dsn = get_dsn()
        web = conninfo_to_dict(web_dsn)
        target = ("host", "port", "dbname")
        if (
            any(not command.get(key) or command[key] != web.get(key) for key in target)
            or any(
                command.get(key)
                for key in ("hostaddr", "service", "servicefile", "options")
            )
            or command.get("user") != value["role"]
            or command.get("user") == web.get("user")
            or value["dsn"] == web_dsn
        ):
            raise ValueError()
        return value
    except Exception:
        raise RuntimeError(
            "Route worker lifecycle command identity reference is invalid"
        ) from None


def _verify_connection(conn, expected_role: str, protected_schema: str) -> None:
    try:
        row = conn.execute(
            """
            SELECT session_user AS session_name,
                   current_user AS current_name,
                   current_database() AS database_name,
                   r.rolcanlogin,
                   r.rolinherit,
                   r.rolsuper,
                   r.rolbypassrls,
                   r.rolcreaterole,
                   r.rolcreatedb,
                   r.rolreplication,
                   pg_has_role(session_user, 'aos_runtime', 'MEMBER')
                     AS runtime_member,
                   pg_has_role(session_user, 'aos_runtime', 'USAGE')
                     AS runtime_usage,
                   pg_has_role(session_user, 'aos_runtime', 'SET')
                     AS runtime_set,
                   pg_has_role(session_user, 'aos_app', 'MEMBER')
                     AS app_member,
                   pg_has_role(session_user, 'aos_app', 'USAGE')
                     AS app_usage,
                   pg_has_role(session_user, 'aos_app', 'SET')
                     AS app_set,
                   (SELECT count(*)
                      FROM pg_catalog.pg_auth_members m
                     WHERE m.member = r.oid) AS extra_roles,
                   has_schema_privilege(session_user, %s, 'USAGE')
                     AS schema_usage,
                   has_schema_privilege(session_user, %s, 'CREATE')
                     AS schema_create,
                   has_table_privilege(session_user, %s, 'SELECT')
                     AS command_select,
                   has_table_privilege(session_user, %s, 'INSERT')
                     AS command_insert,
                   has_table_privilege(session_user, %s, 'UPDATE')
                     AS command_update,
                   has_table_privilege(session_user, %s, 'DELETE')
                     AS command_delete,
                   has_table_privilege(session_user, %s, 'TRUNCATE')
                     AS command_truncate,
                   has_table_privilege(session_user, %s, 'REFERENCES')
                     AS command_references,
                   has_table_privilege(session_user, %s, 'TRIGGER')
                     AS command_trigger,
                   command.relrowsecurity AS rls_enabled,
                   command.relforcerowsecurity AS rls_forced,
                   EXISTS(
                     SELECT 1
                       FROM pg_catalog.pg_policy policy
                      WHERE policy.polrelid = command.oid
                        AND policy.polname = %s
                        AND policy.polpermissive
                        AND policy.polcmd = '*'
                        AND policy.polroles = ARRAY[r.oid]::oid[]
                        AND pg_get_expr(policy.polqual, policy.polrelid) = %s
                        AND pg_get_expr(policy.polwithcheck, policy.polrelid) = %s
                   ) AS exact_policy,
                   (SELECT count(*)
                      FROM pg_catalog.pg_class other
                      JOIN pg_catalog.pg_namespace other_ns
                        ON other_ns.oid = other.relnamespace
                     WHERE other_ns.nspname = %s
                       AND other.relkind IN ('r', 'p')
                       AND other.oid <> command.oid
                       AND (
                         has_table_privilege(session_user, other.oid, 'INSERT')
                         OR has_table_privilege(session_user, other.oid, 'UPDATE')
                         OR has_table_privilege(session_user, other.oid, 'DELETE')
                         OR has_table_privilege(session_user, other.oid, 'TRUNCATE')
                         OR has_table_privilege(session_user, other.oid, 'REFERENCES')
                         OR has_table_privilege(session_user, other.oid, 'TRIGGER')
                       )) AS other_table_writes,
                   (SELECT count(*)
                      FROM pg_catalog.pg_class sequence
                      JOIN pg_catalog.pg_namespace sequence_ns
                        ON sequence_ns.oid = sequence.relnamespace
                     WHERE sequence_ns.nspname = %s
                       AND sequence.relkind = 'S'
                       AND (
                         has_sequence_privilege(session_user, sequence.oid, 'USAGE')
                         OR has_sequence_privilege(session_user, sequence.oid, 'UPDATE')
                       )) AS sequence_access
              FROM pg_catalog.pg_roles r
              JOIN pg_catalog.pg_namespace target_ns ON target_ns.nspname = %s
              JOIN pg_catalog.pg_class command
                ON command.relnamespace = target_ns.oid
               AND command.relname = %s
             WHERE r.rolname = session_user
            """,
            (
                protected_schema,
                protected_schema,
                f"{protected_schema}.{_TABLE}",
                f"{protected_schema}.{_TABLE}",
                f"{protected_schema}.{_TABLE}",
                f"{protected_schema}.{_TABLE}",
                f"{protected_schema}.{_TABLE}",
                f"{protected_schema}.{_TABLE}",
                f"{protected_schema}.{_TABLE}",
                _POLICY,
                _SCOPE_PREDICATE,
                _SCOPE_PREDICATE,
                protected_schema,
                protected_schema,
                protected_schema,
                _TABLE,
            ),
        ).fetchone()
        expected_db = conninfo_to_dict(get_dsn())["dbname"]
        denied = (
            "rolinherit",
            "rolsuper",
            "rolbypassrls",
            "rolcreaterole",
            "rolcreatedb",
            "rolreplication",
            "runtime_member",
            "runtime_usage",
            "runtime_set",
            "app_member",
            "app_usage",
            "app_set",
            "schema_create",
            "command_update",
            "command_delete",
            "command_truncate",
            "command_references",
            "command_trigger",
        )
        if (
            row is None
            or row["session_name"] != expected_role
            or row["current_name"] != expected_role
            or row["database_name"] != expected_db
            or row["rolcanlogin"] is not True
            or any(row[key] is not False for key in denied)
            or row["extra_roles"] != 0
            or row["schema_usage"] is not True
            or row["command_select"] is not True
            or row["command_insert"] is not True
            or row["rls_enabled"] is not True
            or row["rls_forced"] is not True
            or row["exact_policy"] is not True
            or row["other_table_writes"] != 0
            or row["sequence_access"] != 0
        ):
            raise ValueError()
    except Exception:
        raise RuntimeError(
            "Route worker lifecycle command identity is not permitted"
        ) from None


def _connect_identity(identity: dict[str, str]):
    try:
        return psycopg.connect(
            identity["dsn"], row_factory=dict_row, connect_timeout=10
        )
    except Exception:
        raise RuntimeError(
            "Route worker lifecycle command identity connection unavailable"
        ) from None


def probe_route_worker_lifecycle_command(*, _protected_schema: str = "public") -> bool:
    """Verify command-channel readiness without enabling a write transaction."""

    if re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", _protected_schema) is None:
        raise RuntimeError(
            "Route worker lifecycle command protected schema is invalid"
        )
    identity = _identity()
    conn = _connect_identity(identity)
    try:
        conn.read_only = True
        _verify_connection(conn, identity["role"], _protected_schema)
        conn.rollback()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def connect_route_worker_lifecycle_command(*, _protected_schema: str = "public"):
    """Verify the narrow login before yielding one lifecycle command transaction."""

    if re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", _protected_schema) is None:
        raise RuntimeError(
            "Route worker lifecycle command protected schema is invalid"
        )
    identity = _identity()
    conn = _connect_identity(identity)
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
