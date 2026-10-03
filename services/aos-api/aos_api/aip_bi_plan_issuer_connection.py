"""Scoped PostgreSQL connections for the separate BI Plan issuer login."""

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

from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.tenant_scope import TenantScope


ISSUER_LOGIN = "aos_bi_plan_issuer"
_DATABASE_NAME = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")
_FORBIDDEN_PG_ENV = ("PGPASSWORD", "PGPASSFILE", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")
_TIMEOUT_OPTIONS = ('-c statement_timeout=10000 -c lock_timeout=5000 '
                    '-c idle_in_transaction_session_timeout=10000')


class BIIssuerDatabaseBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class BIIssuerDatabaseConfig:
    host: str
    port: int
    database: str
    passfile: Path

    def __post_init__(self) -> None:
        if (self.host not in {"127.0.0.1", "::1"}
                or type(self.port) is not int or not 1 <= self.port <= 65535
                or type(self.database) is not str
                or _DATABASE_NAME.fullmatch(self.database) is None):
            raise BIIssuerDatabaseBlocked("BI_ISSUER_EXACT_DATABASE_REQUIRED")
        path = Path(self.passfile)
        try:
            parent, secret = path.parent.lstat(), path.lstat()
            if (not path.is_absolute() or not stat.S_ISDIR(parent.st_mode)
                    or not stat.S_ISREG(secret.st_mode)
                    or parent.st_uid != os.geteuid() or secret.st_uid != os.geteuid()
                    or stat.S_IMODE(parent.st_mode) != 0o700
                    or stat.S_IMODE(secret.st_mode) != 0o600):
                raise BIIssuerDatabaseBlocked("BI_ISSUER_PRIVATE_CREDENTIAL_REQUIRED")
        except (OSError, TypeError, ValueError) as exc:
            raise BIIssuerDatabaseBlocked("BI_ISSUER_PRIVATE_CREDENTIAL_REQUIRED") from exc
        object.__setattr__(self, "passfile", path)


def _bind_scope(conn, scope: TenantScope) -> None:
    apply_asset_transaction_scope(conn, org_id=scope.org_id, project_id=scope.project_id)


def _require_identity(conn, config: BIIssuerDatabaseConfig, scope: TenantScope,
                      *, read_only: bool) -> None:
    identity = conn.execute("""SELECT current_database() AS db,
      session_user AS login,current_user AS role,
      current_setting('aos.org_id',true) AS org_id,
      current_setting('aos.project_id',true) AS project_id,
      (SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement_timeout_ms,
      (SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock_timeout_ms,
      (SELECT setting::int FROM pg_settings WHERE name='idle_in_transaction_session_timeout') AS idle_timeout_ms,
      r.rolcanlogin,r.rolsuper,r.rolbypassrls,r.rolinherit,
      pg_has_role(session_user,'aos_app','MEMBER') AS owner_member,
      pg_has_role(session_user,'aos_runtime','MEMBER') AS runtime_member
      FROM pg_roles r WHERE r.rolname=session_user""").fetchone()
    if (identity is None or identity["db"] != config.database
            or identity["login"] != ISSUER_LOGIN or identity["role"] != ISSUER_LOGIN
            or (identity["org_id"], identity["project_id"]) != scope.key
            or not identity["rolcanlogin"] or identity["rolsuper"]
            or identity["rolbypassrls"] or identity["rolinherit"]
            or identity["owner_member"] or identity["runtime_member"]
            or conn.read_only is not read_only
            or (identity['statement_timeout_ms'], identity['lock_timeout_ms'], identity['idle_timeout_ms'])
                != (10000, 5000, 10000)):
        raise BIIssuerDatabaseBlocked("BI_ISSUER_DATABASE_IDENTITY_REQUIRED")


class _ScopedBIIssuerConnection:
    """Rebind the transaction-local scope after an original Store commit."""

    __slots__ = ("_raw", "_config", "_scope")

    def __init__(self, raw, config: BIIssuerDatabaseConfig, scope: TenantScope) -> None:
        self._raw, self._config, self._scope = raw, config, scope

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def _rebind(self) -> None:
        _bind_scope(self._raw, self._scope)
        _require_identity(self._raw, self._config, self._scope, read_only=False)

    def commit(self) -> None:
        self._raw.commit()
        self._rebind()

    def rollback(self) -> None:
        self._raw.rollback()
        self._rebind()


@contextmanager
def _connect_bi_issuer(config: BIIssuerDatabaseConfig, scope: TenantScope,
                       *, read_only: bool) -> Iterator:
    if (type(config) is not BIIssuerDatabaseConfig or type(scope) is not TenantScope
            or any(os.environ.get(name) for name in _FORBIDDEN_PG_ENV)):
        raise BIIssuerDatabaseBlocked("BI_ISSUER_EXACT_CONNECTION_REQUIRED")
    config.__post_init__()
    try:
        conn = connect(host=config.host, port=config.port, dbname=config.database,
                       user=ISSUER_LOGIN, passfile=str(config.passfile),
                       connect_timeout=5, options=_TIMEOUT_OPTIONS, row_factory=dict_row)
    except Exception:
        raise BIIssuerDatabaseBlocked("BI_ISSUER_DATABASE_CONNECTION_FAILED") from None
    with conn:
        try:
            conn.isolation_level = (IsolationLevel.REPEATABLE_READ if read_only
                                    else IsolationLevel.SERIALIZABLE)
            conn.read_only = read_only
            _bind_scope(conn, scope)
            _require_identity(conn, config, scope, read_only=read_only)
        except BIIssuerDatabaseBlocked:
            raise
        except Exception:
            raise BIIssuerDatabaseBlocked("BI_ISSUER_DATABASE_IDENTITY_REQUIRED") from None
        yield conn if read_only else _ScopedBIIssuerConnection(conn, config, scope)


def connect_bi_issuer_read_only(config: BIIssuerDatabaseConfig, scope: TenantScope):
    return _connect_bi_issuer(config, scope, read_only=True)


def connect_bi_issuer_write(config: BIIssuerDatabaseConfig, scope: TenantScope):
    return _connect_bi_issuer(config, scope, read_only=False)
