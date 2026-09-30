"""Exact, non-owner PostgreSQL connections for the separate approval issuer."""

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

from aos_api.tenant_scope import TenantScope, apply_transaction_scope


ISSUER_LOGIN = "aos_network_approval_issuer"
_DATABASE_NAME = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")
_FORBIDDEN_PG_ENV = ("PGPASSWORD", "PGPASSFILE", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")


class IssuerDatabaseBlocked(RuntimeError):
    pass


def _require_identity(conn, config: "IssuerDatabaseConfig", scope: TenantScope,
                      *, read_only: bool) -> None:
    identity = conn.execute("""SELECT current_database() AS db,
      session_user AS login,current_user AS role,
      current_setting('aos.org_id',true) AS org_id,
      current_setting('aos.project_id',true) AS project_id,
      r.rolcanlogin,r.rolsuper,r.rolbypassrls,r.rolinherit,
      pg_has_role(session_user,'aos_app','MEMBER') AS owner_member
      FROM pg_roles r WHERE r.rolname=session_user""").fetchone()
    if (identity is None or identity["db"] != config.database
            or identity["login"] != ISSUER_LOGIN
            or identity["role"] != "aos_runtime"
            or (identity["org_id"], identity["project_id"]) != scope.key
            or not identity["rolcanlogin"] or identity["rolsuper"]
            or identity["rolbypassrls"] or identity["rolinherit"]
            or identity["owner_member"] or conn.read_only is not read_only):
        raise IssuerDatabaseBlocked("ISSUER_DATABASE_IDENTITY_REQUIRED")


class _ScopedIssuerConnection:
    """Restore transaction-local role/scope for the Store's post-commit readback."""

    __slots__ = ("_raw", "_config", "_scope")

    def __init__(self, raw, config: "IssuerDatabaseConfig", scope: TenantScope) -> None:
        self._raw = raw
        self._config = config
        self._scope = scope

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def _reset_transaction(self) -> None:
        apply_transaction_scope(self._raw, self._scope)
        _require_identity(self._raw, self._config, self._scope, read_only=False)

    def commit(self) -> None:
        self._raw.commit()
        self._reset_transaction()

    def rollback(self) -> None:
        self._raw.rollback()
        self._reset_transaction()


@dataclass(frozen=True)
class IssuerDatabaseConfig:
    host: str
    port: int
    database: str
    passfile: Path

    def __post_init__(self) -> None:
        if (self.host not in {"127.0.0.1", "::1"}
                or type(self.port) is not int or not 1 <= self.port <= 65535
                or type(self.database) is not str or _DATABASE_NAME.fullmatch(self.database) is None):
            raise IssuerDatabaseBlocked("ISSUER_EXACT_DATABASE_REQUIRED")
        path = Path(self.passfile)
        try:
            parent = path.parent.lstat()
            secret = path.lstat()
            if (not stat.S_ISDIR(parent.st_mode) or not stat.S_ISREG(secret.st_mode)
                    or parent.st_uid != os.geteuid() or secret.st_uid != os.geteuid()
                    or stat.S_IMODE(parent.st_mode) != 0o700
                    or stat.S_IMODE(secret.st_mode) != 0o600):
                raise IssuerDatabaseBlocked("ISSUER_PRIVATE_CREDENTIAL_REQUIRED")
        except (OSError, TypeError, ValueError) as exc:
            raise IssuerDatabaseBlocked("ISSUER_PRIVATE_CREDENTIAL_REQUIRED") from exc
        object.__setattr__(self, "passfile", path)


@contextmanager
def _connect_issuer(config: IssuerDatabaseConfig, scope: TenantScope,
                    *, read_only: bool) -> Iterator:
    if (type(config) is not IssuerDatabaseConfig or type(scope) is not TenantScope
            or any(os.environ.get(name) for name in _FORBIDDEN_PG_ENV)):
        raise IssuerDatabaseBlocked("ISSUER_EXACT_CONNECTION_REQUIRED")
    # Recheck file ownership on every connect, not only when config was made.
    config.__post_init__()
    try:
        conn = connect(host=config.host, port=config.port, dbname=config.database,
                       user=ISSUER_LOGIN, passfile=str(config.passfile),
                       connect_timeout=5, row_factory=dict_row)
    except Exception:
        raise IssuerDatabaseBlocked("ISSUER_DATABASE_CONNECTION_FAILED") from None
    with conn:
        try:
            conn.isolation_level = (IsolationLevel.REPEATABLE_READ if read_only
                                    else IsolationLevel.SERIALIZABLE)
            conn.read_only = read_only
            apply_transaction_scope(conn, scope)
            _require_identity(conn, config, scope, read_only=read_only)
        except IssuerDatabaseBlocked:
            raise
        except Exception:
            raise IssuerDatabaseBlocked("ISSUER_DATABASE_IDENTITY_REQUIRED") from None
        yield conn if read_only else _ScopedIssuerConnection(conn, config, scope)


def connect_issuer_read_only(config: IssuerDatabaseConfig, scope: TenantScope):
    return _connect_issuer(config, scope, read_only=True)


def connect_issuer_decision(config: IssuerDatabaseConfig, scope: TenantScope):
    return _connect_issuer(config, scope, read_only=False)
