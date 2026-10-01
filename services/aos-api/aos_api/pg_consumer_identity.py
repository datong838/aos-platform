"""Shared catalog-only SQL consumer admission; identities supplied by fixed adapters."""
from aos_api.tenant_scope import TenantScope


class ConsumerDatabaseBlocked(RuntimeError):
    pass


def require_sql_consumer_identity(conn, scope: TenantScope, expected_database: str, *,
                                  caller: str, owner: str, function: str) -> None:
    if (type(scope) is not TenantScope or type(expected_database) is not str
            or not expected_database or expected_database != expected_database.strip()):
        raise ConsumerDatabaseBlocked('CONSUMER_EXACT_DATABASE_SCOPE_REQUIRED')
    try:
        row = conn.execute("""SELECT current_database() AS db,session_user AS login,current_user AS role,
            current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project""").fetchone()
        if (row is None or row['db'] != expected_database or row['login'] != caller
                or row['role'] != caller or (row['org'], row['project']) != scope.key):
            raise ConsumerDatabaseBlocked('CONSUMER_DATABASE_IDENTITY_REQUIRED')
        roles = conn.execute("""SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,
            rolcreaterole,rolreplication,rolbypassrls FROM pg_catalog.pg_roles WHERE rolname=ANY(%s)""",
            ([caller, owner],)).fetchall()
        if {r['rolname'] for r in roles} != {caller, owner}:
            raise ConsumerDatabaseBlocked('CONSUMER_ROLE_DRIFT')
        for role in roles:
            if (role['rolcanlogin'] is not (role['rolname'] == caller)
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
            AS unsafe""", (caller, owner, caller, owner, caller, owner, caller, owner, caller)).fetchone()
        if unsafe is None or unsafe['unsafe'] is not False:
            raise ConsumerDatabaseBlocked('CONSUMER_PRIVILEGE_DRIFT')
        function = conn.execute("""SELECT p.prosecdef,p.proconfig,p.proowner::regrole::text AS owner,
            has_function_privilege(session_user,p.oid,'EXECUTE') AS executable,
            EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
                WHERE a.privilege_type='EXECUTE' AND a.grantee NOT IN (%s::regrole,%s::regrole)) AS extra
            FROM pg_catalog.pg_proc p WHERE p.oid=to_regprocedure(%s)""", (caller, owner, function)).fetchone()
        if (function is None or function['prosecdef'] is not True or function['owner'] != owner
                or function['proconfig'] != ['search_path=pg_catalog']
                or function['executable'] is not True or function['extra'] is not False):
            raise ConsumerDatabaseBlocked('CONSUMER_FUNCTION_DRIFT')
    except ConsumerDatabaseBlocked:
        raise
    except Exception:
        raise ConsumerDatabaseBlocked('CONSUMER_DATABASE_PREFLIGHT_FAILED') from None
