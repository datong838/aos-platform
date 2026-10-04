"""Independent evaluator transaction admission; never provisions a role or grant."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterator

from psycopg import connect, IsolationLevel
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from aos_api.aip_registry_issuer_connection import (
    RegistryIssuerDatabaseConfig, RegistryIssuerConnectionBlocked,
)
from aos_api.tenant_scope import TenantScope

EVALUATOR_LOGIN = 'aos_aip_binding_evaluator'
_FORBIDDEN_ENV = ('PGPASSWORD', 'PGPASSFILE', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS')
_OPTIONS = ('-c statement_timeout=10000 -c lock_timeout=5000 '
            '-c idle_in_transaction_session_timeout=10000 -c search_path=pg_catalog,public')


class BindingEvaluatorConnectionBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class BindingEvaluatorDatabaseConfig:
    host: str
    port: int
    database: str
    passfile: Path

    def __post_init__(self) -> None:
        # Reuse existing private-file validation without borrowing its login or privileges.
        try:
            validated = RegistryIssuerDatabaseConfig(self.host, self.port, self.database, self.passfile)
        except (RegistryIssuerConnectionBlocked, TypeError, ValueError, OSError):
            raise BindingEvaluatorConnectionBlocked('EVALUATOR_EXACT_PRIVATE_CONFIGURATION_REQUIRED') from None
        object.__setattr__(self, 'passfile', validated.passfile)


def _require_identity(conn, config: BindingEvaluatorDatabaseConfig, scope: TenantScope) -> None:
    row = conn.execute("""SELECT current_database() AS db,session_user AS login,current_user AS role,
        current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project,
        (SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement_ms,
        (SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock_ms,
        (SELECT setting::int FROM pg_settings WHERE name='idle_in_transaction_session_timeout') AS idle_ms,
        r.rolcanlogin,r.rolsuper,r.rolbypassrls,r.rolinherit,r.rolcreatedb,r.rolcreaterole,r.rolreplication,
        EXISTS(SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid) AS membership
        FROM pg_roles r WHERE r.rolname=session_user""").fetchone()
    if (row is None or (row['db'], row['login'], row['role']) != (
            config.database, EVALUATOR_LOGIN, EVALUATOR_LOGIN)
            or (row['org'], row['project']) != scope.key
            or not row['rolcanlogin']
            or any(row[name] for name in ('rolsuper', 'rolbypassrls', 'rolinherit',
                                         'rolcreatedb', 'rolcreaterole', 'rolreplication', 'membership'))
            or (row['statement_ms'], row['lock_ms'], row['idle_ms']) != (10000, 5000, 10000)
            or conn.autocommit or conn.read_only
            or conn.isolation_level != IsolationLevel.SERIALIZABLE
            or conn.info.transaction_status != TransactionStatus.INTRANS):
        raise BindingEvaluatorConnectionBlocked('EVALUATOR_DATABASE_IDENTITY_REQUIRED')


@dataclass(frozen=True)
class BindingEvaluatorConnectionFactory:
    config: BindingEvaluatorDatabaseConfig

    @contextmanager
    def __call__(self, scope: TenantScope) -> Iterator:
        if (type(scope) is not TenantScope or type(self.config) is not BindingEvaluatorDatabaseConfig
                or any(type(v) is not str or not v or v != v.strip() for v in scope.key)
                or any(os.environ.get(key) for key in _FORBIDDEN_ENV)):
            raise BindingEvaluatorConnectionBlocked('EVALUATOR_EXACT_CONNECTION_REQUIRED')
        self.config.__post_init__()
        try:
            conn = connect(host=self.config.host, port=self.config.port, dbname=self.config.database,
                user=EVALUATOR_LOGIN, passfile=str(self.config.passfile), connect_timeout=5,
                options=_OPTIONS, row_factory=dict_row)
        except Exception:
            raise BindingEvaluatorConnectionBlocked('EVALUATOR_CONNECTION_FAILED') from None
        with conn:
            try:
                conn.isolation_level = IsolationLevel.SERIALIZABLE
                conn.read_only = False
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
                _require_identity(conn, self.config, scope)
            except BindingEvaluatorConnectionBlocked:
                raise
            except Exception:
                raise BindingEvaluatorConnectionBlocked('EVALUATOR_DATABASE_IDENTITY_REQUIRED') from None
            yield conn
