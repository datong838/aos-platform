"""Default-off, separate database connection for AIP assignee issuance.

This module only admits a connection. Deployment provisioning, external auth,
and the current-database ACL cutover are separate gates.
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


ISSUER_LOGIN = "aos_aip_assignee_issuer"
_DATABASE = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")
_FORBIDDEN_PG_ENV = ("PGPASSWORD", "PGPASSFILE", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")
_OPTIONS = ("-c statement_timeout=10000 -c lock_timeout=5000 "
            "-c idle_in_transaction_session_timeout=10000 -c search_path=public,pg_catalog")


class AssigneeIssuerConnectionBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class AssigneeIssuerDatabaseConfig:
    host: str
    port: int
    database: str
    passfile: Path

    def __post_init__(self) -> None:
        if (self.host not in {"127.0.0.1", "::1"}
                or type(self.port) is not int or not 1 <= self.port <= 65535
                or type(self.database) is not str or _DATABASE.fullmatch(self.database) is None):
            raise AssigneeIssuerConnectionBlocked("ASSIGNEE_ISSUER_EXACT_DATABASE_REQUIRED")
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
            raise AssigneeIssuerConnectionBlocked("ASSIGNEE_ISSUER_PRIVATE_CREDENTIAL_REQUIRED") from None
        object.__setattr__(self, "passfile", path)


def _require_identity(conn, config: AssigneeIssuerDatabaseConfig, scope: TenantScope) -> None:
    row = conn.execute("""SELECT current_database() AS database,
      session_user AS login,current_user AS role,
      current_setting('aos.org_id',true) AS org_id,
      current_setting('aos.project_id',true) AS project_id,
      current_setting('search_path') AS search_path,
      (SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement_ms,
      (SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock_ms,
      (SELECT setting::int FROM pg_settings WHERE name='idle_in_transaction_session_timeout') AS idle_ms,
      r.rolcanlogin,r.rolsuper,r.rolbypassrls,
      pg_has_role(session_user,'aos_app','MEMBER') AS owner_member,
      pg_has_role(session_user,'aos_runtime','MEMBER') AS runtime_member,
      (SELECT relowner::regrole::text FROM pg_class
        WHERE oid='public.aip_assignee_resolution_receipt'::regclass) AS receipt_owner,
      (SELECT pg_has_role(session_user,relowner,'MEMBER') FROM pg_class
        WHERE oid='public.aip_assignee_resolution_receipt'::regclass) AS receipt_owner_member,
      (SELECT relrowsecurity AND relforcerowsecurity FROM pg_class
        WHERE oid='public.aip_assignee_resolution_receipt'::regclass) AS forced_rls,
      has_table_privilege(session_user,'public.aip_assignee_resolution_receipt','SELECT') AS issuer_select,
      has_table_privilege(session_user,'public.aip_assignee_resolution_receipt','INSERT') AS issuer_insert,
      has_table_privilege(session_user,'public.aip_assignee_resolution_receipt','UPDATE') AS issuer_update,
      has_table_privilege(session_user,'public.aip_assignee_resolution_receipt','DELETE') AS issuer_delete,
      has_table_privilege('aos_runtime','public.aip_assignee_resolution_receipt','INSERT') AS runtime_insert
      FROM pg_roles r WHERE r.rolname=session_user""").fetchone()
    if (row is None or row["database"] != config.database
            or row["login"] != ISSUER_LOGIN or row["role"] != ISSUER_LOGIN
            or (row["org_id"], row["project_id"]) != scope.key
            or row["search_path"] != "public,pg_catalog"
            or (row["statement_ms"], row["lock_ms"], row["idle_ms"]) != (10000, 5000, 10000)
            or not row["rolcanlogin"] or row["rolsuper"] or row["rolbypassrls"]
            or row["owner_member"] or row["runtime_member"]
            or row["receipt_owner"] == ISSUER_LOGIN or row["receipt_owner_member"]
            or not row["forced_rls"]
            or not row["issuer_select"] or not row["issuer_insert"]
            or row["issuer_update"] or row["issuer_delete"] or row["runtime_insert"]
            or conn.read_only):
        raise AssigneeIssuerConnectionBlocked("ASSIGNEE_ISSUER_DATABASE_IDENTITY_REQUIRED")


@dataclass(frozen=True)
class AssigneeIssuerConnectionFactory:
    config: AssigneeIssuerDatabaseConfig

    @contextmanager
    def __call__(self, scope: TenantScope) -> Iterator:
        if (type(scope) is not TenantScope or type(self.config) is not AssigneeIssuerDatabaseConfig
                or any(os.environ.get(key) for key in _FORBIDDEN_PG_ENV)):
            raise AssigneeIssuerConnectionBlocked("ASSIGNEE_ISSUER_EXACT_CONNECTION_REQUIRED")
        self.config.__post_init__()
        try:
            conn = connect(host=self.config.host, port=self.config.port,
                           dbname=self.config.database, user=ISSUER_LOGIN,
                           passfile=str(self.config.passfile), connect_timeout=5,
                           options=_OPTIONS, row_factory=dict_row)
        except Exception:
            raise AssigneeIssuerConnectionBlocked("ASSIGNEE_ISSUER_CONNECTION_FAILED") from None
        with conn:
            try:
                conn.isolation_level = IsolationLevel.SERIALIZABLE
                conn.read_only = False
                conn.execute("SELECT set_config('aos.org_id',%s,true), set_config('aos.project_id',%s,true)", scope.key)
                _require_identity(conn, self.config, scope)
            except AssigneeIssuerConnectionBlocked:
                raise
            except Exception:
                raise AssigneeIssuerConnectionBlocked("ASSIGNEE_ISSUER_DATABASE_IDENTITY_REQUIRED") from None
            yield conn
