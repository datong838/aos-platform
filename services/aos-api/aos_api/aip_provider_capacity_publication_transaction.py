"""Original-fact access for the complete publication definer; no Source issued."""
import hashlib

from aos_api.aip_provider_capacity_formal_boundary import TABLES, SCOPED, LOCKS, _policy_expression, _normalized
from aos_api.aip_provider_capacity_publication_registry import OWNER

GUARD_NAME = 'capacity_publication_owner_read_lock_only_a0v155'
GUARD_BODY = """
BEGIN
 IF current_user='aos_capacity_publication_owner' THEN
  RAISE EXCEPTION 'CAPACITY_PUBLICATION_ORIGINAL_FACTS_READ_ONLY' USING ERRCODE='42501';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END;
"""
POLICY_TABLES = (*SCOPED, 'aip_action_proposal', 'aip_action_draft', 'aip_action_approval_event')


class CapacityPublicationBoundaryBlocked(ValueError):
    pass


def install_original_fact_boundary(execute):
    """Add the exact original fact reads/locks, never any Source entrypoint."""
    execute(f"""DO $$ DECLARE r record; BEGIN
     SELECT * INTO r FROM pg_roles WHERE rolname='{OWNER}';
     IF NOT FOUND OR r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb
       OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls
       OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=r.oid OR member=r.oid) THEN
       RAISE EXCEPTION 'CAPACITY_PUBLICATION_OWNER_REQUIRED' USING ERRCODE='42501';
     END IF;
    END $$""")
    execute(f'GRANT USAGE ON SCHEMA public TO {OWNER}')
    for table in TABLES:
        execute(f'GRANT SELECT ON public.{table} TO {OWNER}')
    for table in POLICY_TABLES:
        expression = _policy_expression(table)
        execute(f'CREATE POLICY capacity_publication_fact_a0v155 ON public.{table} TO {OWNER} USING({expression}) WITH CHECK({expression})')
        execute(f'CREATE POLICY capacity_publication_fact_restrict_a0v155 ON public.{table} AS RESTRICTIVE TO {OWNER} USING({expression}) WITH CHECK({expression})')
    for table, column in LOCKS.items():
        execute(f'GRANT UPDATE({column}) ON public.{table} TO {OWNER}')
    execute(f'CREATE FUNCTION public.{GUARD_NAME}() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $body${GUARD_BODY}$body$')
    execute(f'ALTER FUNCTION public.{GUARD_NAME}() OWNER TO {OWNER}')
    execute(f'REVOKE ALL ON FUNCTION public.{GUARD_NAME}() FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer,aos_provider_capacity_policy_publisher')
    for table in LOCKS:
        execute(f'CREATE TRIGGER {GUARD_NAME} BEFORE INSERT OR UPDATE OR DELETE ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.{GUARD_NAME}()')


def require_original_fact_boundary(conn):
    """Native catalog audit only; cannot authenticate, approve or issue Source."""
    def deny():
        raise CapacityPublicationBoundaryBlocked('CAPACITY_PUBLICATION_ORIGINAL_FACT_BOUNDARY_DRIFTED')
    role = conn.execute('SELECT oid,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s', (OWNER,)).fetchone()
    if (not role or any(value for key, value in role.items() if key!='oid')
        or conn.execute('SELECT 1 FROM pg_auth_members WHERE roleid=%s OR member=%s', (role['oid'], role['oid'])).fetchone()):
        deny()
    if (conn.execute('SELECT 1 FROM pg_default_acl d WHERE d.defaclrole=%s OR EXISTS '
        '(SELECT 1 FROM aclexplode(d.defaclacl) a WHERE a.grantee=%s)',(role['oid'],role['oid'])).fetchone()
        or conn.execute("SELECT 1 FROM pg_namespace WHERE nspname='public' AND has_schema_privilege(%s,oid,'CREATE')",(OWNER,)).fetchone()
        or conn.execute('SELECT 1 FROM pg_database WHERE datname=current_database() AND has_database_privilege(%s,oid,\'CREATE\')',(OWNER,)).fetchone()):
        deny()
    identities = conn.execute("SELECT name,to_regclass('public.'||name)::oid AS oid FROM unnest(%s::text[]) name", (list(TABLES),)).fetchall()
    by_name = {row['name']:row['oid'] for row in identities}
    if None in by_name.values() or len(set(by_name.values()))!=len(TABLES):
        deny()
    grants = conn.execute("SELECT c.oid,a.privilege_type,a.is_grantable FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE c.relnamespace='public'::regnamespace AND a.grantee=%s", (role['oid'],)).fetchall()
    if ({(r['oid'],r['privilege_type']) for r in grants}!={(oid,'SELECT') for oid in by_name.values()}
        or any(r['is_grantable'] for r in grants)):
        deny()
    columns = conn.execute('SELECT c.oid,x.attname,a.privilege_type,a.is_grantable FROM pg_class c JOIN pg_attribute x ON x.attrelid=c.oid,LATERAL aclexplode(x.attacl) a WHERE a.grantee=%s', (role['oid'],)).fetchall()
    if ({(r['oid'],r['attname'],r['privilege_type']) for r in columns}!={(by_name[t],c,'UPDATE') for t,c in LOCKS.items()}
        or any(r['is_grantable'] for r in columns)):
        deny()
    # PUBLIC grants are effective even for NOINHERIT roles. They cannot
    # expand the original public fact set or permit a table-level write.
    if conn.execute("SELECT 1 FROM pg_class c WHERE c.relnamespace='public'::regnamespace "
        "AND c.relkind IN('r','v','m','p','f') AND (has_table_privilege(%s,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES') "
        "OR (NOT(c.oid=ANY(%s::oid[])) AND (has_table_privilege(%s,c.oid,'SELECT') "
        "OR has_any_column_privilege(%s,c.oid,'SELECT,INSERT,UPDATE,REFERENCES')))) LIMIT 1",
        (OWNER,list(by_name.values()),OWNER,OWNER)).fetchone():
        deny()
    effective_columns = conn.execute("SELECT c.oid,a.attname FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid "
        "WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped "
        "AND (has_column_privilege(%s,c.oid,a.attnum,'INSERT,REFERENCES') "
        "OR has_column_privilege(%s,c.oid,a.attnum,'UPDATE'))",(OWNER,OWNER)).fetchall()
    if {(r['oid'],r['attname']) for r in effective_columns}!={(by_name[t],c) for t,c in LOCKS.items()}:
        deny()
    for table in POLICY_TABLES:
        flags = conn.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s', (by_name[table],)).fetchone()
        policies = conn.execute('SELECT polname,polcmd,polpermissive,polroles,pg_get_expr(polqual,polrelid) AS us,pg_get_expr(polwithcheck,polrelid) AS wc FROM pg_policy WHERE polrelid=%s AND %s=ANY(polroles)', (by_name[table], role['oid'])).fetchall()
        expected = {'capacity_publication_fact_a0v155':True, 'capacity_publication_fact_restrict_a0v155':False}
        if (not flags or not all(flags.values()) or len(policies)!=2 or {r['polname'] for r in policies}!=set(expected)
            or any(r['polcmd']!='*' or r['polpermissive'] is not expected[r['polname']] or r['polroles']!=[role['oid']]
                or any(_normalized(r[k] or '')!=_normalized(_policy_expression(table)) for k in ('us','wc')) for r in policies)):
            deny()
    signature='public.'+GUARD_NAME+'()'
    guard = conn.execute('SELECT oid,proowner,prosrc,prosecdef,proconfig,prorettype,proargtypes::text AS args FROM pg_proc WHERE oid=to_regprocedure(%s)', (signature,)).fetchone()
    if (not guard or guard['proowner']!=role['oid'] or guard['prosecdef'] or guard['proconfig']!=['search_path=pg_catalog']
        or guard['prorettype']!=2279 or guard['args']!=''
        or hashlib.sha256(guard['prosrc'].encode()).digest()!=hashlib.sha256(GUARD_BODY.encode()).digest()
        or conn.execute('SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE p.oid=%s AND a.grantee<>p.proowner', (guard['oid'],)).fetchone()):
        deny()
    triggers = conn.execute('SELECT tgrelid,tgfoid,tgenabled,tgtype,tgqual,tgargs,tgnargs,cardinality(tgattr::smallint[]) AS column_count FROM pg_trigger WHERE tgname=%s', (GUARD_NAME,)).fetchall()
    if ({r['tgrelid'] for r in triggers}!={by_name[t] for t in LOCKS} or len(triggers)!=len(LOCKS)
        or any(r['tgfoid']!=guard['oid'] or r['tgenabled']!='O' or r['tgtype']!=31 or r['tgqual'] is not None
            or bytes(r['tgargs'])!=b'' or r['tgnargs']!=0 or r['column_count']!=0 for r in triggers)):
        deny()
