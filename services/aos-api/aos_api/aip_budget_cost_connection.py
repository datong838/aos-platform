"""Private fixed-identity connections for a separately provisioned budget issuer.

No environment DSN, shared API connection, role provisioning or retry. This is
connection admission only; schema and OS-process admission remain separate.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path

from psycopg import IsolationLevel, connect
from psycopg.rows import dict_row

from aos_api.aip_budget_cost_issuer import BudgetCostIssuerBlocked, _db
from aos_api.aip_network_issuer_connection import IssuerDatabaseConfig
from aos_api.tenant_scope import TenantScope, apply_transaction_scope


_LOGIN = 'aos_budget_cost_issuer'
_FORBIDDEN_ENV = ('PGPASSWORD', 'PGPASSFILE', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS')
_OPTIONS = ('-c statement_timeout=10000 -c lock_timeout=5000 '
            '-c idle_in_transaction_session_timeout=10000 -c search_path=public,pg_catalog')


@dataclass(frozen=True)
class BudgetCostDatabaseConfig:
    host: str
    port: int
    database: str
    passfile: Path

    def __post_init__(self):
        try:
            path = Path(self.passfile)
            if not path.is_absolute():
                raise ValueError('absolute private path required')
            # Reuse field/path validation only. The network identity and its
            # connector are never used to establish budget signing authority.
            checked = IssuerDatabaseConfig(self.host, self.port, self.database, path)
            object.__setattr__(self, 'passfile', checked.passfile)
        except Exception:
            raise BudgetCostIssuerBlocked('BUDGET_COST_CONNECTION_CONFIG_REQUIRED') from None


def require_budget_connection(conn, config, scope, *, read_only):
    """Read back exact server identity, transaction mode and bounded SQL limits."""
    _db(conn, scope, read_only)
    row = conn.execute("""SELECT current_database() AS database,
      (SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement,
      (SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock,
      (SELECT setting::int FROM pg_settings WHERE name='idle_in_transaction_session_timeout') AS idle,
      current_setting('search_path') AS search_path""").fetchone()
    if (row is None or row['database'] != config.database
            or (row['statement'], row['lock'], row['idle']) != (10000, 5000, 10000)
            or row['search_path'] != 'public,pg_catalog'):
        raise BudgetCostIssuerBlocked('BUDGET_COST_DATABASE_IDENTITY_REQUIRED')


class _ScopedBudgetConnection:
    """Rebind and revalidate SET LOCAL scope after either transaction boundary."""
    def __init__(self, raw, config, scope, read_only):
        self._raw, self._config = raw, config
        self._scope, self._read_only = scope, read_only

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def _reset(self):
        apply_transaction_scope(self._raw, self._scope)
        require_budget_connection(self._raw, self._config, self._scope, read_only=self._read_only)

    def commit(self):
        self._raw.commit()
        self._reset()

    def rollback(self):
        self._raw.rollback()
        self._reset()


@dataclass(frozen=True)
class BudgetCostConnectionFactory:
    config: BudgetCostDatabaseConfig
    scope: TenantScope

    def __post_init__(self):
        if type(self.config) is not BudgetCostDatabaseConfig or type(self.scope) is not TenantScope:
            raise BudgetCostIssuerBlocked('BUDGET_COST_CONNECTION_CONFIG_REQUIRED')
        self.config.__post_init__()
        self.scope.__post_init__()

    @contextmanager
    def __call__(self, scope, read_only):
        if (type(scope) is not TenantScope or scope != self.scope
                or type(read_only) is not bool
                or any(os.environ.get(name) for name in _FORBIDDEN_ENV)):
            raise BudgetCostIssuerBlocked('BUDGET_COST_CONNECTION_CONFIG_REQUIRED')
        self.__post_init__()
        try:
            conn = connect(host=self.config.host, port=self.config.port,
                dbname=self.config.database, user=_LOGIN, passfile=str(self.config.passfile),
                connect_timeout=5, options=_OPTIONS, row_factory=dict_row)
        except Exception:
            raise BudgetCostIssuerBlocked('BUDGET_COST_DATABASE_CONNECTION_FAILED') from None
        with conn:
            try:
                conn.isolation_level = (IsolationLevel.REPEATABLE_READ if read_only
                                        else IsolationLevel.SERIALIZABLE)
                conn.read_only = read_only
                scoped = _ScopedBudgetConnection(conn, self.config, scope, read_only)
                scoped._reset()
            except BudgetCostIssuerBlocked:
                raise
            except Exception:
                raise BudgetCostIssuerBlocked('BUDGET_COST_DATABASE_IDENTITY_REQUIRED') from None
            yield scoped
