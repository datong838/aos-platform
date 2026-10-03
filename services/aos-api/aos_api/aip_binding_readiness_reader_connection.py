"""Default-off non-owner, read-only connection for Capability readiness facts.

This is an isolated identity contract, not current-database provisioning or
permission to activate a binding. The writer must inject it explicitly.
"""

from __future__ import annotations

import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from psycopg import IsolationLevel, connect
from psycopg.rows import dict_row

from aos_api.tenant_scope import TenantScope


READINESS_READER_LOGIN = "aos_aip_binding_readiness_reader"
READINESS_READER_TABLES = (
    "aip_capability_revision",  # global catalog; intentionally has no tenant RLS
    "aip_release_gate_decision", "aip_eval_contract_revision",
    "aip_evidence_bundle_revision", "aip_evidence_bundle_revoke_event",
    "aip_eval_dataset_revision",
    "aip_model_route_head", "aip_model_route_revision",
    "aip_runtime_policy_revision", "aip_registered_model_revision",
    "aip_model_price_snapshot_revision", "aip_provider_instance_revision",
    "aip_provider_health_observation", "aip_runtime_guard_policy_revision",
    "aip_model_governance_policy_head", "aip_model_governance_policy_revision",
    "aip_budget_head", "aip_budget_revision",
)
_DATABASE = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")
_FORBIDDEN_PG_ENV = ("PGPASSWORD", "PGPASSFILE", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")
_OPTIONS = ("-c statement_timeout=10000 -c lock_timeout=5000 "
            "-c idle_in_transaction_session_timeout=10000 -c search_path=public,pg_catalog")


class ReadinessReaderConnectionBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class ReadinessReaderDatabaseConfig:
    host: str
    port: int
    database: str
    passfile: Path

    def __post_init__(self) -> None:
        if (self.host not in {"127.0.0.1", "::1"}
                or type(self.port) is not int or not 1 <= self.port <= 65535
                or type(self.database) is not str or _DATABASE.fullmatch(self.database) is None):
            raise ReadinessReaderConnectionBlocked("READINESS_READER_EXACT_DATABASE_REQUIRED")
        path = Path(self.passfile)
        try:
            parent, secret = path.parent.lstat(), path.lstat()
            if (not path.is_absolute() or not stat.S_ISDIR(parent.st_mode)
                    or not stat.S_ISREG(secret.st_mode)
                    or parent.st_uid != os.geteuid() or secret.st_uid != os.geteuid()
                    or stat.S_IMODE(parent.st_mode) != 0o700
                    or stat.S_IMODE(secret.st_mode) != 0o600):
                raise ValueError("private passfile required")
        except (OSError, TypeError, ValueError):
            raise ReadinessReaderConnectionBlocked("READINESS_READER_PRIVATE_CREDENTIAL_REQUIRED") from None
        object.__setattr__(self, "passfile", path)


def _require_identity(conn, config: ReadinessReaderDatabaseConfig,
                      scope: TenantScope | None) -> None:
    row = conn.execute("""SELECT current_database() AS database,session_user AS login,
      current_user AS role,current_setting('aos.org_id',true) AS org_id,
      current_setting('aos.project_id',true) AS project_id,
      current_setting('search_path') AS search_path,
      current_setting('transaction_read_only') AS readonly,
      (SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement_ms,
      (SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock_ms,
      (SELECT setting::int FROM pg_settings WHERE name='idle_in_transaction_session_timeout') AS idle_ms,
      r.rolcanlogin,r.rolsuper,r.rolbypassrls,r.rolcreatedb,r.rolcreaterole,r.rolreplication,
      pg_has_role(session_user,'aos_app','MEMBER') AS owner_member,
      pg_has_role(session_user,'aos_runtime','MEMBER') AS runtime_member
      FROM pg_roles r WHERE r.rolname=session_user""").fetchone()
    expected_scope = scope.key if scope is not None else (None, None)
    if (row is None or row["database"] != config.database
            or row["login"] != READINESS_READER_LOGIN or row["role"] != row["login"]
            or (row["org_id"], row["project_id"]) != expected_scope
            or row["search_path"] != "public,pg_catalog" or row["readonly"] != "on"
            or (row["statement_ms"], row["lock_ms"], row["idle_ms"]) != (10000, 5000, 10000)
            or not row["rolcanlogin"] or row["rolsuper"] or row["rolbypassrls"]
            or row["rolcreatedb"] or row["rolcreaterole"] or row["rolreplication"]
            or row["owner_member"] or row["runtime_member"]):
        raise ReadinessReaderConnectionBlocked("READINESS_READER_DATABASE_IDENTITY_REQUIRED")
    tables = conn.execute("""SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,
      has_table_privilege(session_user,c.oid,'SELECT') AS can_read,
      (has_table_privilege(session_user,c.oid,'INSERT') OR
       has_table_privilege(session_user,c.oid,'UPDATE') OR
       has_table_privilege(session_user,c.oid,'DELETE')) AS can_write
      FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='public' AND c.relkind='r' AND c.relname=ANY(%s)""",
      (list(READINESS_READER_TABLES),)).fetchall()
    if (len(tables) != len(READINESS_READER_TABLES)
            or any(not table["can_read"] or table["can_write"]
                   or (table["relname"] != "aip_capability_revision" and
                       not (table["relrowsecurity"] and table["relforcerowsecurity"]))
                   for table in tables)):
        raise ReadinessReaderConnectionBlocked("READINESS_READER_DATABASE_IDENTITY_REQUIRED")
    forbidden = conn.execute("""SELECT EXISTS(SELECT 1 FROM pg_class c
      JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
      AND c.relkind='r' AND (has_table_privilege(session_user,c.oid,'INSERT') OR
      has_table_privilege(session_user,c.oid,'UPDATE') OR
      has_table_privilege(session_user,c.oid,'DELETE'))) AS any_write,
      EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='public' AND c.relkind='r' AND c.relname<>ALL(%s)
      AND has_table_privilege(session_user,c.oid,'SELECT')) AS extra_read,
      has_schema_privilege(session_user,'public','CREATE') AS schema_create,
      has_database_privilege(session_user,current_database(),'CREATE') AS database_create""",
      (list(READINESS_READER_TABLES),)).fetchone()
    if (forbidden["any_write"] or forbidden["extra_read"]
            or forbidden["schema_create"] or forbidden["database_create"]):
        raise ReadinessReaderConnectionBlocked("READINESS_READER_DATABASE_IDENTITY_REQUIRED")


@dataclass(frozen=True)
class ReadinessReaderConnectionFactory:
    config: ReadinessReaderDatabaseConfig

    @contextmanager
    def __call__(self, scope: TenantScope | None = None) -> Iterator:
        if (scope is not None and type(scope) is not TenantScope
                or type(self.config) is not ReadinessReaderDatabaseConfig
                or any(os.environ.get(key) for key in _FORBIDDEN_PG_ENV)):
            raise ReadinessReaderConnectionBlocked("READINESS_READER_EXACT_CONNECTION_REQUIRED")
        self.config.__post_init__()
        try:
            conn = connect(host=self.config.host, port=self.config.port,
                           dbname=self.config.database, user=READINESS_READER_LOGIN,
                           passfile=str(self.config.passfile), connect_timeout=5,
                           options=_OPTIONS, row_factory=dict_row)
        except Exception:
            raise ReadinessReaderConnectionBlocked("READINESS_READER_CONNECTION_FAILED") from None
        with conn:
            try:
                conn.isolation_level = IsolationLevel.REPEATABLE_READ
                conn.read_only = True
                if scope is not None:
                    conn.execute("SELECT set_config('aos.org_id',%s,true), set_config('aos.project_id',%s,true)",
                                 scope.key)
                _require_identity(conn, self.config, scope)
            except ReadinessReaderConnectionBlocked:
                raise
            except Exception:
                raise ReadinessReaderConnectionBlocked("READINESS_READER_DATABASE_IDENTITY_REQUIRED") from None
            yield conn
