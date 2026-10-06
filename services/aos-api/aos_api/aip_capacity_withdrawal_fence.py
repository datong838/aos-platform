"""Strict independent withdrawal epoch; caller retains original authority checks."""
import hashlib
from aos_api.tenant_scope import TenantScope

OWNER='aos_capacity_withdrawal_epoch_owner'
TABLE="public.aip_capacity_withdrawal_epoch"
HASHES={'lock': 'bdea4da16d8d4af2897cde94d5c755bb36019a884cd5307d5bc3c2fbfe181bd7', 'init': '159967048b7e16fa777469e06605fb0c24652b00b4423d949a3ac170844fdf7d', 'bump': '666fb5350dab9121e46c2fb21a19a09f82c8165078968140b623757ae9557a38'}

class CapacityWithdrawalFenceBlocked(ValueError):
    pass


def require_withdrawal_fence(conn):
    from aos_api.aip_provider_capacity_publication_lock_boundary import audited_publication_epoch_caller
    try:
        publication_caller=audited_publication_epoch_caller(conn)
    except ValueError as error:
        raise CapacityWithdrawalFenceBlocked('WITHDRAWAL_PUBLICATION_CALLER_DRIFT') from error
    role=conn.execute('SELECT oid,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(OWNER,)).fetchone()
    if not role or any(v for k,v in role.items() if k!='oid') or conn.execute('SELECT 1 FROM pg_auth_members WHERE roleid=%s OR member=%s',(role['oid'],role['oid'])).fetchone():
        raise CapacityWithdrawalFenceBlocked('WITHDRAWAL_OWNER_DRIFT')
    table=conn.execute('SELECT oid,relowner,relrowsecurity,relforcerowsecurity,relkind FROM pg_class WHERE oid=to_regclass(%s)',(TABLE,)).fetchone()
    if not table or table['relowner']!=role['oid'] or not table['relrowsecurity'] or not table['relforcerowsecurity'] or table['relkind']!='r':
        raise CapacityWithdrawalFenceBlocked('WITHDRAWAL_TABLE_DRIFT')
    if conn.execute("SELECT 1 FROM pg_class c,LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a WHERE c.oid=%s AND a.grantee<>%s",(table['oid'],role['oid'])).fetchone() or conn.execute('SELECT 1 FROM pg_attribute c,LATERAL aclexplode(c.attacl) a WHERE c.attrelid=%s',(table['oid'],)).fetchone():
        raise CapacityWithdrawalFenceBlocked('WITHDRAWAL_TABLE_ACL_DRIFT')
    columns=conn.execute("SELECT a.attname,a.atttypid,a.attnotnull,a.attidentity,a.attgenerated,pg_get_expr(d.adbin,d.adrelid) AS default_expr FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum",(table['oid'],)).fetchall()
    expected_columns=[dict(attname=n,atttypid=t,attnotnull=True,attidentity='',attgenerated='',default_expr=d) for n,t,d in [('org_id',25,None),('project_id',25,None),('proposal_id',25,None),('epoch',20,'0')]]
    constraints=conn.execute('SELECT contype,convalidated,condeferrable,condeferred,pg_get_constraintdef(oid,true) AS definition FROM pg_constraint WHERE conrelid=%s',(table['oid'],)).fetchall()
    expected_definitions={"CHECK (org_id = 'org-org'::text)","CHECK (project_id = 'dev-project'::text)","CHECK (proposal_id <> ''::text AND proposal_id = btrim(proposal_id))","CHECK (epoch >= 0)","PRIMARY KEY (org_id, project_id, proposal_id)"}
    if columns!=expected_columns or len(constraints)!=5 or {x['definition'] for x in constraints}!=expected_definitions or any(not x['convalidated'] or x['condeferrable'] or x['condeferred'] for x in constraints):
        raise CapacityWithdrawalFenceBlocked('WITHDRAWAL_TABLE_STRUCTURE_DRIFT')
    policy=conn.execute('SELECT polname,polcmd,polpermissive,polroles,pg_get_expr(polqual,polrelid) AS q,pg_get_expr(polwithcheck,polrelid) AS c FROM pg_policy WHERE polrelid=%s',(table['oid'],)).fetchall()
    expr="((org_id = NULLIF(current_setting('aos.org_id'::text, true), ''::text)) AND (project_id = NULLIF(current_setting('aos.project_id'::text, true), ''::text)))"
    if policy!=[dict(polname='capacity_withdrawal_epoch_scope',polcmd='*',polpermissive=True,polroles=[role['oid']],q=expr,c=expr)]:
        raise CapacityWithdrawalFenceBlocked('WITHDRAWAL_POLICY_DRIFT')
    ids={}
    for name,digest in HASHES.items():
        sig='public.aos_capacity_withdrawal_epoch_'+name+('(text,text,text)' if name=='lock' else '()')
        row=conn.execute('SELECT oid,proowner,prosecdef,proconfig,prosrc,prorettype,proargtypes::text AS args FROM pg_proc WHERE oid=to_regprocedure(%s)',(sig,)).fetchone()
        if not row or row['proowner']!=role['oid'] or not row['prosecdef'] or row['proconfig']!=['search_path=pg_catalog'] or hashlib.sha256(row['prosrc'].encode()).hexdigest()!=digest or row['prorettype']!=(20 if name=='lock' else 2279) or row['args']!=('25 25 25' if name=='lock' else ''):
            raise CapacityWithdrawalFenceBlocked('WITHDRAWAL_FUNCTION_DRIFT')
        ids[name]=row['oid']
        allowed={OWNER}|({'aos_runtime','aos_provider_capacity_issuer'} if name=='lock' else set())
        if name=='lock' and publication_caller:
            allowed.add(publication_caller)
        acl=conn.execute("SELECT coalesce(r.rolname,'PUBLIC') AS role,a.privilege_type,a.is_grantable FROM pg_proc p,LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a LEFT JOIN pg_roles r ON r.oid=a.grantee WHERE p.oid=%s",(row['oid'],)).fetchall()
        if {x['role'] for x in acl}!=allowed or any(x['privilege_type']!='EXECUTE' or x['is_grantable'] for x in acl):
            raise CapacityWithdrawalFenceBlocked('WITHDRAWAL_FUNCTION_ACL_DRIFT')
    extra=conn.execute("""SELECT
      EXISTS(SELECT 1 FROM pg_class c WHERE c.relowner=%s AND c.oid<>%s
        AND c.oid<>(SELECT reltoastrelid FROM pg_class WHERE oid=%s)
        AND NOT EXISTS(SELECT 1 FROM pg_index i WHERE i.indexrelid=c.oid AND i.indrelid IN(%s,(SELECT reltoastrelid FROM pg_class WHERE oid=%s))))
      OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner=%s AND NOT(oid=ANY(%s::oid[])))
      OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspowner=%s)
      OR EXISTS(SELECT 1 FROM pg_database WHERE datdba=%s)
      OR EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE a.grantee=%s AND c.relowner<>%s)
      OR EXISTS(SELECT 1 FROM pg_attribute c,LATERAL aclexplode(c.attacl) a WHERE a.grantee=%s)
      OR EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE a.grantee=%s AND NOT(p.oid=ANY(%s::oid[])))
      OR EXISTS(SELECT 1 FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE a.grantee=%s AND (n.nspname<>'public' OR a.privilege_type<>'USAGE' OR a.is_grantable))
      OR EXISTS(SELECT 1 FROM pg_proc p WHERE p.prosecdef AND has_function_privilege(%s,p.oid,'EXECUTE') AND NOT(p.oid=ANY(%s::oid[]))) AS extra""",
      (role['oid'],table['oid'],table['oid'],table['oid'],table['oid'],role['oid'],list(ids.values()),role['oid'],role['oid'],role['oid'],role['oid'],role['oid'],role['oid'],list(ids.values()),role['oid'],role['oid'],list(ids.values()))).fetchone()['extra']
    if extra:
        raise CapacityWithdrawalFenceBlocked('WITHDRAWAL_OWNER_EXTRA_PERMISSION')
    for relation,name,fn in [('public.aip_action_proposal','zz_capacity_withdrawal_epoch_init_a0v151','init'),('public.aip_action_withdrawal_event','zz_capacity_withdrawal_epoch_bump_a0v151','bump')]:
        t=conn.execute("SELECT tgfoid,tgtype,tgenabled,tgattr::text AS attrs,tgqual,tgargs FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s",(relation,name)).fetchone()
        if not t or t['tgfoid']!=ids[fn] or t['tgtype']!=5 or t['tgenabled']!='O' or t['attrs']!='' or t['tgqual'] is not None or bytes(t['tgargs'])!=b'':
            raise CapacityWithdrawalFenceBlocked('WITHDRAWAL_TRIGGER_DRIFT')
    fk=conn.execute("SELECT tgname,tgtype,tgdeferrable,tginitdeferred,tgenabled FROM pg_trigger WHERE tgrelid='public.aip_action_withdrawal_event'::regclass AND tgisinternal AND (tgtype & 4)=4").fetchall()
    if not fk or any(x['tgtype']!=5 or x['tgdeferrable'] or x['tginitdeferred'] or x['tgenabled']!='O' or x['tgname']>='zz_capacity_withdrawal_epoch_bump_a0v151' for x in fk):
        raise CapacityWithdrawalFenceBlocked('WITHDRAWAL_FOREIGN_KEY_ORDER_DRIFT')


def lock_capacity_withdrawals(conn,scope,proposal_ids):
    if type(scope) is not TenantScope or scope.key!=('org-org','dev-project'):
        raise CapacityWithdrawalFenceBlocked('WITHDRAWAL_SCOPE_REQUIRED')
    require_withdrawal_fence(conn)
    for proposal_id in sorted(set(proposal_ids)):
        conn.execute('SELECT public.aos_capacity_withdrawal_epoch_lock(%s,%s,%s)',(*scope.key,proposal_id)).fetchone()
