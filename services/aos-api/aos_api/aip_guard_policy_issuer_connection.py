"""Exact PostgreSQL connections for the isolated guard policy approval issuer."""
from contextlib import contextmanager
from dataclasses import dataclass
import os
import re
import stat
from pathlib import Path

from psycopg import IsolationLevel, connect
from psycopg.rows import dict_row

from aos_api.tenant_scope import TenantScope, apply_transaction_scope


GUARD_ISSUER_LOGIN = "aos_guard_approval_issuer"
_DATABASE = re.compile(r"[a-z][a-z0-9_]{0,62}\Z")
_FORBIDDEN = ("PGPASSWORD", "PGPASSFILE", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")
_OPTIONS = "-c statement_timeout=10000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=10000"


class GuardIssuerDatabaseBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class GuardIssuerDatabaseConfig:
    host: str
    port: int
    database: str
    passfile: Path

    def __post_init__(self):
        if (self.host not in {"127.0.0.1", "::1"} or type(self.port) is not int
                or not 1 <= self.port <= 65535 or type(self.database) is not str
                or _DATABASE.fullmatch(self.database) is None):
            raise GuardIssuerDatabaseBlocked("GUARD_ISSUER_EXACT_DATABASE_REQUIRED")
        path = Path(self.passfile)
        try:
            parent, secret = path.parent.lstat(), path.lstat()
            if (not stat.S_ISDIR(parent.st_mode) or not stat.S_ISREG(secret.st_mode)
                    or parent.st_uid != os.geteuid() or secret.st_uid != os.geteuid()
                    or stat.S_IMODE(parent.st_mode) != 0o700 or stat.S_IMODE(secret.st_mode) != 0o600):
                raise ValueError()
        except Exception:
            raise GuardIssuerDatabaseBlocked("GUARD_ISSUER_PRIVATE_CREDENTIAL_REQUIRED") from None
        object.__setattr__(self, "passfile", path)


def _require_identity(conn, config, scope, *, read_only):
    row = conn.execute("""SELECT current_database() AS db,session_user AS login,current_user AS role,
      current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id,
      current_setting('transaction_isolation') AS isolation,
      (SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement_timeout_ms,
      (SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock_timeout_ms,
      (SELECT setting::int FROM pg_settings WHERE name='idle_in_transaction_session_timeout') AS idle_timeout_ms,
      r.rolcanlogin,r.rolsuper,r.rolbypassrls,r.rolinherit,r.rolcreatedb,r.rolcreaterole,r.rolreplication,
      pg_has_role(session_user,'aos_app','MEMBER') AS owner_member,
      EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=session_user::regrole
        OR (member=session_user::regrole AND (roleid<>'aos_runtime'::regrole OR admin_option))) AS extra_roles
      FROM pg_roles r WHERE r.rolname=session_user""").fetchone()
    expected_isolation = "repeatable read" if read_only else "serializable"
    if (not row or row["db"] != config.database or row["login"] != GUARD_ISSUER_LOGIN
            or row["role"] != "aos_runtime" or (row["org_id"], row["project_id"]) != scope.key
            or not row["rolcanlogin"] or any(row[name] for name in (
                "rolsuper", "rolbypassrls", "rolinherit", "rolcreatedb", "rolcreaterole", "rolreplication",
                "owner_member", "extra_roles"))
            or conn.read_only is not read_only or row["isolation"] != expected_isolation
            or (row["statement_timeout_ms"], row["lock_timeout_ms"], row["idle_timeout_ms"])
                != (10000, 5000, 10000)):
        raise GuardIssuerDatabaseBlocked("GUARD_ISSUER_DATABASE_IDENTITY_REQUIRED")


class _ScopedGuardConnection:
    __slots__ = ("_raw", "_config", "_scope")

    def __init__(self, raw, config, scope):
        self._raw, self._config, self._scope = raw, config, scope

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def _reset(self):
        apply_transaction_scope(self._raw, self._scope)
        _require_identity(self._raw, self._config, self._scope, read_only=False)

    def commit(self):
        self._raw.commit()
        self._reset()

    def rollback(self):
        self._raw.rollback()
        self._reset()


@contextmanager
def connect_guard_issuer(config, scope, read_only):
    if (type(config) is not GuardIssuerDatabaseConfig or type(scope) is not TenantScope
            or type(read_only) is not bool or any(os.environ.get(name) for name in _FORBIDDEN)):
        raise GuardIssuerDatabaseBlocked("GUARD_ISSUER_EXACT_CONNECTION_REQUIRED")
    config.__post_init__()
    try:
        conn = connect(host=config.host, port=config.port, dbname=config.database,
            user=GUARD_ISSUER_LOGIN, passfile=str(config.passfile), connect_timeout=5,
            options=_OPTIONS, row_factory=dict_row)
    except Exception:
        raise GuardIssuerDatabaseBlocked("GUARD_ISSUER_DATABASE_CONNECTION_FAILED") from None
    with conn:
        try:
            conn.isolation_level = IsolationLevel.REPEATABLE_READ if read_only else IsolationLevel.SERIALIZABLE
            conn.read_only = read_only
            apply_transaction_scope(conn, scope)
            _require_identity(conn, config, scope, read_only=read_only)
        except GuardIssuerDatabaseBlocked:
            raise
        except Exception:
            raise GuardIssuerDatabaseBlocked("GUARD_ISSUER_DATABASE_IDENTITY_REQUIRED") from None
        yield conn if read_only else _ScopedGuardConnection(conn, config, scope)
