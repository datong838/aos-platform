"""Read-only checks for the independent SQL consumer; never approval authority."""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import os
import re
import stat

import psycopg
from psycopg.rows import dict_row

from aos_api.tenant_scope import TenantScope
from aos_api.pg_consumer_identity import ConsumerDatabaseBlocked, require_sql_consumer_identity

CALLER = 'aos_network_consumer_call'
OWNER = 'aos_network_consumer_owner'
FUNCTION = 'public.aip_consume_network_activation_a0v_120(text,text,text,text)'


def require_consumer_identity(conn, scope: TenantScope, expected_database: str) -> None:
    require_sql_consumer_identity(conn, scope, expected_database,
                                 caller=CALLER, owner=OWNER, function=FUNCTION)


# Kept separate from issuer connections: no SET ROLE or runtime fallback is legal.
@dataclass(frozen=True)
class ConsumerDatabaseConfig:
    host: str
    port: int
    database: str
    passfile: Path

    def __post_init__(self):
        if (type(self.host) is not str or self.host not in {'127.0.0.1', '::1'}
                or type(self.port) is not int or not 1 <= self.port <= 65535
                or type(self.database) is not str
                or re.fullmatch(r'[a-z][a-z0-9_]{0,62}', self.database) is None):
            raise ConsumerDatabaseBlocked('CONSUMER_EXACT_DATABASE_REQUIRED')
        try:
            path = Path(self.passfile)
            parent, secret = path.parent.lstat(), path.lstat()
            if (not path.is_absolute() or not stat.S_ISDIR(parent.st_mode)
                    or not stat.S_ISREG(secret.st_mode) or not 0 < secret.st_size <= 65536
                    or parent.st_uid != os.geteuid() or secret.st_uid != os.geteuid()
                    or stat.S_IMODE(parent.st_mode) != 0o700
                    or stat.S_IMODE(secret.st_mode) != 0o600):
                raise ConsumerDatabaseBlocked('CONSUMER_PRIVATE_CREDENTIAL_REQUIRED')
        except (OSError, TypeError, ValueError):
            raise ConsumerDatabaseBlocked('CONSUMER_PRIVATE_CREDENTIAL_REQUIRED') from None
        object.__setattr__(self, 'passfile', path)


@contextmanager
def connect_consumer(config: ConsumerDatabaseConfig, scope: TenantScope, *, read_only=False):
    if (type(config) is not ConsumerDatabaseConfig or type(scope) is not TenantScope
            or type(read_only) is not bool
            or any(os.environ.get(key) for key in
                   ('PGPASSWORD', 'PGPASSFILE', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS'))):
        raise ConsumerDatabaseBlocked('CONSUMER_EXACT_CONNECTION_REQUIRED')
    config.__post_init__()
    try:
        conn = psycopg.connect(host=config.host, port=config.port, dbname=config.database,
                              user=CALLER, passfile=str(config.passfile), connect_timeout=5,
                              row_factory=dict_row)
    except Exception:
        raise ConsumerDatabaseBlocked('CONSUMER_DATABASE_CONNECTION_FAILED') from None
    try:
        with conn:
            conn.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
            conn.read_only = read_only
            conn.execute("SET LOCAL statement_timeout='10s'")
            conn.execute("SET LOCAL lock_timeout='5s'")
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
            require_consumer_identity(conn, scope, config.database)
            yield conn
    except psycopg.Error:
        # Includes commit-time connection loss: no retry, outcome must be reconciled.
        raise ConsumerDatabaseBlocked('CONSUMER_DATABASE_TRANSACTION_FAILED_RECONCILE_REQUIRED') from None
