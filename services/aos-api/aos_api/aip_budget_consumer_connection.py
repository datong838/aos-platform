"""Fixed budget consumer connection; no HTTP, provisioning, fallback or retry.

This adapter alone does not authorize an actor or implement receipt inquiry.
Those belong to the finite private service before any consumption request.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from aos_api.aip_network_consumer_connection import ConsumerDatabaseConfig
from aos_api.pg_consumer_identity import require_sql_consumer_identity
from aos_api.pg_authority_schema import authority_schema_snapshot
from aos_api.tenant_scope import TenantScope


CALLER = 'aos_budget_consumer_call'
OWNER = 'aos_budget_consumer_owner'
FUNCTION = 'public.aip_consume_budget_as_actor_a0v_127(text,text,text,text,text,text)'
OWNER_FUNCTIONS = (FUNCTION,
    'public.aip_reconcile_budget_as_actor_a0v_127(text,text,text,text,text,text)',
    'public.aip_budget_cost_actor_a0v_127(text,text,text,text,text)',
    'public.aip_consume_budget_cost_a0v_126(text,text,text,text)')
_TABLES = (
    'aip_budget_cost_proposal', 'aip_budget_cost_proposal_receipt',
    'aip_budget_cost_decision', 'aip_budget_cost_revocation', 'aip_budget_cost_issuer_receipt',
    'meta_membership', 'aip_budget_head', 'aip_budget_revision', 'aip_budget_receipt',
    'aip_provider_instance_head', 'aip_provider_instance_revision',
    'aip_capability_invocation', 'aip_budget_reservation', 'aip_budget_bucket',
    'aip_budget_cost_runtime_fence',
)
_FORBIDDEN_ENV = ('PGPASSWORD', 'PGPASSFILE', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS')


class BudgetConsumerBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class BudgetConsumerConfig:
    host: str
    port: int
    database: str
    passfile: Path

    def __post_init__(self):
        try:
            # Structure/private file validation only; never its network connector.
            checked = ConsumerDatabaseConfig(self.host, self.port, self.database, self.passfile)
            object.__setattr__(self, 'passfile', checked.passfile)
        except Exception:
            raise BudgetConsumerBlocked('BUDGET_CONSUMER_PRIVATE_CONFIG_REQUIRED') from None


def budget_consumer_schema_snapshot(conn):
    owners = {
        **{name: OWNER for name in OWNER_FUNCTIONS},
        'public.aip_budget_cost_hash_a0v_126(jsonb)': 'aos_app',
        'public.canonical_asset_registry_jsonb(jsonb)': 'aos_app',
    }
    # Include trigger implementations, not only trigger attachment/enabled flags.
    triggers = conn.execute("""SELECT DISTINCT p.oid::regprocedure::text AS signature
        FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
        WHERE n.nspname='public' AND c.relname=ANY(%s) AND NOT t.tgisinternal
        ORDER BY signature""", (list(_TABLES),)).fetchall()
    owners.update({row['signature']: 'aos_app' for row in triggers})
    return authority_schema_snapshot(conn, tables=_TABLES, function_owners=owners)


def require_budget_consumer(conn, config, scope, *, read_only):
    try:
        if (type(config) is not BudgetConsumerConfig or type(scope) is not TenantScope
                or scope.key != ('org-org', 'dev-project') or type(read_only) is not bool
                or conn.read_only is not read_only):
            raise BudgetConsumerBlocked('BUDGET_CONSUMER_EXACT_CONNECTION_REQUIRED')
        require_sql_consumer_identity(conn, scope, config.database,
                                     caller=CALLER, owner=OWNER, function=FUNCTION)
        mode = conn.execute("""SELECT current_setting('transaction_isolation') AS isolation,
            current_setting('transaction_read_only') AS read_only,
            current_setting('search_path') AS search_path,
            (SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement,
            (SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock,
            (SELECT setting::int FROM pg_settings WHERE name='idle_in_transaction_session_timeout') AS idle,
            has_schema_privilege(%s,'public','CREATE') OR has_schema_privilege(%s,'public','CREATE') AS unsafe""",
            (CALLER, OWNER)).fetchone()
        if mode != dict(isolation='read committed', read_only='on' if read_only else 'off',
                        search_path='pg_catalog,public', statement=10000, lock=5000, idle=10000, unsafe=False):
            raise BudgetConsumerBlocked('BUDGET_CONSUMER_TRANSACTION_REQUIRED')
        extra = conn.execute("""SELECT
            EXISTS(SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
                LATERAL aclexplode(c.relacl) a WHERE a.grantee=%s::regrole
                AND NOT (n.nspname='public' AND c.relname=ANY(%s)))
            OR EXISTS(SELECT 1 FROM pg_catalog.pg_attribute att JOIN pg_catalog.pg_class c ON c.oid=att.attrelid
                JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
                LATERAL aclexplode(att.attacl) a WHERE a.grantee=%s::regrole
                AND NOT (n.nspname='public' AND c.relname=ANY(%s)))
            OR EXISTS(SELECT 1 FROM pg_catalog.pg_proc WHERE proowner=%s::regrole
                AND oid<>ALL(ARRAY(SELECT to_regprocedure(x) FROM unnest(%s::text[]) x))) AS unsafe""",
            (OWNER, list(_TABLES), OWNER, list(_TABLES), OWNER, list(OWNER_FUNCTIONS))).fetchone()
        if extra is None or extra['unsafe'] is not False:
            raise BudgetConsumerBlocked('BUDGET_CONSUMER_PRIVILEGE_DRIFT')
        expected = json.loads(Path(__file__).with_name('aip_budget_consumer_schema.json').read_text())
        if budget_consumer_schema_snapshot(conn) != expected:
            raise BudgetConsumerBlocked('BUDGET_CONSUMER_SCHEMA_DRIFT')
    except BudgetConsumerBlocked:
        raise
    except Exception:
        raise BudgetConsumerBlocked('BUDGET_CONSUMER_PREFLIGHT_FAILED') from None


@contextmanager
def connect_budget_consumer(config, scope, *, read_only=False):
    if (type(config) is not BudgetConsumerConfig or type(scope) is not TenantScope
            or scope.key != ('org-org', 'dev-project') or type(read_only) is not bool
            or any(os.environ.get(name) for name in _FORBIDDEN_ENV)):
        raise BudgetConsumerBlocked('BUDGET_CONSUMER_EXACT_CONNECTION_REQUIRED')
    config.__post_init__()
    try:
        conn = psycopg.connect(host=config.host, port=config.port, dbname=config.database,
            user=CALLER, passfile=str(config.passfile), connect_timeout=5, row_factory=dict_row,
            options='-c statement_timeout=10000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=10000 -c search_path=pg_catalog,public')
    except Exception:
        raise BudgetConsumerBlocked('BUDGET_CONSUMER_CONNECTION_FAILED') from None
    try:
        with conn:
            conn.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
            conn.read_only = read_only
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
            require_budget_consumer(conn, config, scope, read_only=read_only)
            yield conn
    except psycopg.Error:
        raise BudgetConsumerBlocked('BUDGET_CONSUMER_TRANSACTION_FAILED_RECONCILE_REQUIRED') from None
