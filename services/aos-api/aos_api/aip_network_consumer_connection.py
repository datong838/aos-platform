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

CALLER = 'aos_network_consumer_call'
OWNER = 'aos_network_consumer_owner'
FUNCTION = 'public.aip_consume_network_activation_a0v_120(text,text,text,text)'


class ConsumerDatabaseBlocked(RuntimeError):
    pass


def require_consumer_identity(conn, scope: TenantScope, expected_database: str) -> None:
    if (type(scope) is not TenantScope or type(expected_database) is not str
            or not expected_database or expected_database != expected_database.strip()):
        raise ConsumerDatabaseBlocked('CONSUMER_EXACT_DATABASE_SCOPE_REQUIRED')
    try:
        row = conn.execute("""SELECT current_database() AS db,session_user AS login,current_user AS role,
            current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project""").fetchone()
        if (row is None or row['db'] != expected_database or row['login'] != CALLER
                or row['role'] != CALLER or (row['org'], row['project']) != scope.key):
            raise ConsumerDatabaseBlocked('CONSUMER_DATABASE_IDENTITY_REQUIRED')
        roles = conn.execute("""SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,
            rolcreaterole,rolreplication,rolbypassrls FROM pg_catalog.pg_roles WHERE rolname=ANY(%s)""",
            ([CALLER, OWNER],)).fetchall()
        if {r['rolname'] for r in roles} != {CALLER, OWNER}:
            raise ConsumerDatabaseBlocked('CONSUMER_ROLE_DRIFT')
        for role in roles:
            if (role['rolcanlogin'] is not (role['rolname'] == CALLER)
                    or any(role[key] is not False for key in
                           ('rolinherit','rolsuper','rolcreatedb','rolcreaterole','rolreplication','rolbypassrls'))):
                raise ConsumerDatabaseBlocked('CONSUMER_ROLE_DRIFT')
        unsafe = conn.execute("""SELECT
            EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members WHERE
                roleid IN (%s::regrole,%s::regrole) OR member IN (%s::regrole,%s::regrole))
            OR EXISTS(SELECT 1 FROM pg_catalog.pg_class WHERE relowner IN (%s::regrole,%s::regrole))
            OR EXISTS(SELECT 1 FROM pg_catalog.pg_namespace WHERE nspowner IN (%s::regrole,%s::regrole))
            OR EXISTS(SELECT 1 FROM pg_catalog.pg_proc WHERE proowner=%s::regrole)
            OR EXISTS(SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
                AND (has_table_privilege(session_user,c.oid,'DELETE,TRUNCATE,TRIGGER')
                    OR has_any_column_privilege(session_user,c.oid,'SELECT,INSERT,UPDATE,REFERENCES')))
            AS unsafe""", (CALLER, OWNER, CALLER, OWNER, CALLER, OWNER, CALLER, OWNER, CALLER)).fetchone()
        if unsafe is None or unsafe['unsafe'] is not False:
            raise ConsumerDatabaseBlocked('CONSUMER_PRIVILEGE_DRIFT')
        function = conn.execute("""SELECT p.prosecdef,p.proconfig,p.proowner::regrole::text AS owner,
            has_function_privilege(session_user,p.oid,'EXECUTE') AS executable,
            EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
                WHERE a.privilege_type='EXECUTE' AND a.grantee NOT IN (%s::regrole,%s::regrole)) AS extra
            FROM pg_catalog.pg_proc p WHERE p.oid=to_regprocedure(%s)""", (CALLER, OWNER, FUNCTION)).fetchone()
        if (function is None or function['prosecdef'] is not True or function['owner'] != OWNER
                or function['proconfig'] != ['search_path=pg_catalog']
                or function['executable'] is not True or function['extra'] is not False):
            raise ConsumerDatabaseBlocked('CONSUMER_FUNCTION_DRIFT')
    except ConsumerDatabaseBlocked:
        raise
    except Exception:
        raise ConsumerDatabaseBlocked('CONSUMER_DATABASE_PREFLIGHT_FAILED') from None


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
