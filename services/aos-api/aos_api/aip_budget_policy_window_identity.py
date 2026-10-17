"""Private window identities; no connection provisioning or public actor claims.

Maker/checker retain the existing protected renewal identity. Window consumption
uses the original cost consumer, never the separate policy-renewal consumer.
Deployment provenance, transport authentication and native seals are additional
store/service obligations; a valid identity is not an execution permit.
"""
import psycopg
from psycopg.rows import dict_row

from aos_api.aip_budget_policy_renewal_identity import (
    CheckerBinding, MachineMakerIdentity, RenewalIdentityBlocked,
    _database_identity as _renewal_database_identity,
    authenticate_checker as _renewal_authenticate_checker,
)

CALLERS = {'maker': 'aos_budget_renewal_maker_call',
           'issuer': 'aos_budget_renewal_issuer_call',
           'consumer': 'aos_budget_consumer_call'}


class WindowIdentityBlocked(ValueError):
    pass


def database_identity(conn, purpose, *, read_only):
    if type(purpose) is not str or purpose not in CALLERS or type(read_only) is not bool:
        raise WindowIdentityBlocked('POLICY_WINDOW_EXACT_PURPOSE_REQUIRED')
    if type(conn) is not psycopg.Connection or conn.closed:
        raise WindowIdentityBlocked('POLICY_WINDOW_REAL_DATABASE_SESSION_REQUIRED')
    try:
        if purpose in {'maker', 'issuer'}:
            login = _renewal_database_identity(conn, purpose)
        else:
            with conn.cursor(row_factory=dict_row) as cursor:
                row = cursor.execute("""SELECT session_user AS login,current_user AS role,
                    current_setting('aos.org_id',true) AS org_id,
                    current_setting('aos.project_id',true) AS project_id,
                    current_schemas(true) AS schemas,
                    r.rolcanlogin,r.rolsuper,r.rolbypassrls,r.rolinherit,
                    r.rolcreatedb,r.rolcreaterole,r.rolreplication,
                    has_schema_privilege(r.oid,'public','CREATE') AS schema_create,
                    EXISTS(SELECT 1 FROM pg_auth_members
                        WHERE roleid=r.oid OR member=r.oid) AS membership
                    FROM pg_roles r WHERE r.rolname=session_user""").fetchone()
            if (not row or row['login'] != CALLERS['consumer'] or row['role'] != row['login']
                    or (row['org_id'], row['project_id']) != ('org-org', 'dev-project')
                    or row['rolcanlogin'] is not True
                    or any(row[key] is not False for key in (
                        'rolsuper', 'rolbypassrls', 'rolinherit', 'rolcreatedb',
                        'rolcreaterole', 'rolreplication', 'membership', 'schema_create'))
                    or not row['schemas'] or not set(row['schemas']) <= {'pg_catalog', 'public'}):
                raise WindowIdentityBlocked('POLICY_WINDOW_DATABASE_IDENTITY_PROFILE_REQUIRED')
            login = row['login']
        with conn.cursor(row_factory=dict_row) as cursor:
            state = cursor.execute("""SELECT current_setting('transaction_isolation') AS isolation,
                current_setting('transaction_read_only') AS read_only,
                has_schema_privilege(session_user,'public','CREATE') AS schema_create""").fetchone()
        if (not state or state['isolation'] != 'read committed'
                or state['read_only'] != ('on' if read_only else 'off')
                or state['schema_create'] is not False):
            raise WindowIdentityBlocked('POLICY_WINDOW_EXACT_TRANSACTION_PROFILE_REQUIRED')
        return login
    except WindowIdentityBlocked:
        raise
    except RenewalIdentityBlocked:
        raise WindowIdentityBlocked('POLICY_WINDOW_DATABASE_IDENTITY_PROFILE_REQUIRED') from None
    except Exception:
        raise WindowIdentityBlocked('POLICY_WINDOW_DATABASE_IDENTITY_UNAVAILABLE') from None


def authenticate_machine_maker(conn, *, read_only):
    login = database_identity(conn, 'maker', read_only=read_only)
    return MachineMakerIdentity(subject='postgres-service:' + login, session_user=login)


def authenticate_checker(token, *, binding, conn, read_only):
    database_identity(conn, 'issuer', read_only=read_only)
    try:
        return _renewal_authenticate_checker(token, binding=binding, conn=conn)
    except RenewalIdentityBlocked:
        raise WindowIdentityBlocked('POLICY_WINDOW_ORIGINAL_HUMAN_IDENTITY_REQUIRED') from None
