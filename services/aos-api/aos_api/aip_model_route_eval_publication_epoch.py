"""Candidate least-privilege bridge to the original shared publication epoch.

No Source/approval/identity authority, provisioning at runtime or automatic retry.
Installation is a separate reviewed migration, never a request-time fallback.
"""
from hashlib import sha256
import re

from aos_api.tenant_scope import TenantScope

OWNER='aos_model_route_eval_publication_reader'
SIGNATURE='public.aos_model_route_eval_publication_epoch_lock(text,text,text)'
POLICY='model_route_eval_publication_reader_a0v167'
POLICY_EXPR="((org_id = 'org-org'::text) AND (project_id = 'dev-project'::text))"
ROLE_FLAGS=('rolcanlogin','rolinherit','rolsuper','rolcreatedb','rolcreaterole','rolreplication','rolbypassrls')
ORIGINAL_TRIGGERS=(
    ('bump',5,'deeecd5fedaeb1af5f3017eae2a49bd01140b002b0ef1495f84fb89c93db16d8'),
    ('touch',7,'af74c2fccca02671cb89f5f489f516c6f98aeaac5241dbd26499dcdeeb3c0527'),
)
FUNCTION_BODY="""
DECLARE result bigint; BEGIN
  IF current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
    OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
    OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
    OR p_org IS DISTINCT FROM 'org-org' OR p_project IS DISTINCT FROM 'dev-project'
    OR p_org IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
    OR p_project IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'')
    OR p_id IS NULL OR p_id='' OR p_id<>btrim(p_id) OR length(p_id)>200 THEN
    RAISE EXCEPTION 'MODEL_ROUTE_PUBLICATION_EPOCH_CALLER_REQUIRED' USING ERRCODE='42501';
  END IF;
  SELECT epoch INTO result FROM public.aip_publication_epoch
    WHERE org_id=p_org AND project_id=p_project AND publication_id=p_id FOR SHARE;
  IF NOT FOUND OR result IS NULL OR result<1 THEN
    RAISE EXCEPTION 'MODEL_ROUTE_PUBLICATION_EPOCH_CURRENT_REQUIRED' USING ERRCODE='42501';
  END IF;
  RETURN result;
END;
"""
FUNCTION_SHA256=sha256(FUNCTION_BODY.encode()).hexdigest()


class EvalPublicationEpochRejected(ValueError):
    """Safe public category; underlying native SQLSTATE is never retried."""


def install_eval_publication_epoch_reader(execute):
    """Candidate migration only. Reject drift; never replay original installation."""
    trigger_conditions=' OR '.join(
        f"(t.tgname='publication_epoch_{name}_a0v144' AND t.tgtype={kind} "
        f"AND p.proname='aos_publication_epoch_{name}' "
        f"AND encode(sha256(convert_to(p.prosrc,'UTF8')),'hex')='{digest}')"
        for name,kind,digest in ORIGINAL_TRIGGERS)
    execute(f"""DO $$ DECLARE r record; BEGIN
      IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_roles o ON o.oid=c.relowner
        WHERE c.oid=pg_catalog.to_regclass('public.aip_publication_epoch')
          AND o.rolname='aos_publication_epoch_owner' AND c.relrowsecurity AND c.relforcerowsecurity
          AND NOT(o.rolcanlogin OR o.rolinherit OR o.rolsuper OR o.rolcreatedb OR o.rolcreaterole
            OR o.rolreplication OR o.rolbypassrls)
          AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member=o.oid OR m.roleid=o.oid))
        OR (SELECT count(*) FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
          JOIN pg_catalog.pg_roles o ON o.oid=p.proowner JOIN pg_catalog.pg_language l ON l.oid=p.prolang
          WHERE t.tgrelid=pg_catalog.to_regclass('public.aip_publication_event') AND NOT t.tgisinternal
          AND t.tgenabled='O' AND t.tgnargs=0 AND t.tgqual IS NULL
          AND o.rolname='aos_publication_epoch_owner' AND l.lanname='plpgsql' AND p.prosecdef
          AND p.proconfig=ARRAY['search_path=pg_catalog, public, pg_temp']
          AND p.proargtypes=''::oidvector AND p.prorettype=2279 AND ({trigger_conditions}))<>2 THEN
        RAISE EXCEPTION 'MODEL_ROUTE_ORIGINAL_PUBLICATION_EPOCH_DRIFT' USING ERRCODE='42501';
      END IF;
      SELECT * INTO r FROM pg_catalog.pg_roles WHERE rolname='{OWNER}';
      IF NOT FOUND THEN
        CREATE ROLE {OWNER} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
      ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
        OR r.rolreplication OR r.rolbypassrls
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members WHERE roleid=r.oid OR member=r.oid)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_class WHERE relowner=r.oid)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_proc WHERE proowner=r.oid)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_namespace WHERE nspowner=r.oid)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_database WHERE datdba=r.oid)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_class c,LATERAL pg_catalog.aclexplode(c.relacl) a WHERE a.grantee=r.oid)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_attribute c,LATERAL pg_catalog.aclexplode(c.attacl) a WHERE a.grantee=r.oid)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_proc p,LATERAL pg_catalog.aclexplode(p.proacl) a WHERE a.grantee=r.oid)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_namespace n,LATERAL pg_catalog.aclexplode(n.nspacl) a WHERE a.grantee=r.oid)
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_database d,LATERAL pg_catalog.aclexplode(d.datacl) a WHERE a.grantee=r.oid) THEN
        RAISE EXCEPTION 'MODEL_ROUTE_PUBLICATION_READER_OWNER_DRIFT' USING ERRCODE='42501';
      END IF;
    END $$""")
    execute(f'GRANT USAGE ON SCHEMA public TO {OWNER}')
    execute(f'GRANT SELECT,UPDATE(epoch) ON public.aip_publication_epoch TO {OWNER}')
    execute(f"CREATE POLICY {POLICY} ON public.aip_publication_epoch TO {OWNER} "
        "USING(org_id='org-org' AND project_id='dev-project') "
        "WITH CHECK(org_id='org-org' AND project_id='dev-project')")
    execute('CREATE FUNCTION public.aos_model_route_eval_publication_epoch_lock(p_org text,p_project text,p_id text) '
        'RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$'+FUNCTION_BODY+'$$')
    execute(f'ALTER FUNCTION {SIGNATURE} OWNER TO {OWNER}')
    execute(f'REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC')
    execute(f'GRANT EXECUTE ON FUNCTION {SIGNATURE} TO aos_runtime')
    # Custom creator default ACLs must abort the migration, never leak a bridge.
    execute(f"""DO $$ BEGIN
      IF pg_catalog.has_schema_privilege('{OWNER}','public','CREATE')
        OR (SELECT count(*) FROM pg_catalog.pg_proc p,
        LATERAL pg_catalog.aclexplode(p.proacl) a
        WHERE p.oid=pg_catalog.to_regprocedure('{SIGNATURE}'))<>2
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_proc p,
          LATERAL pg_catalog.aclexplode(p.proacl) a
          LEFT JOIN pg_catalog.pg_roles r ON r.oid=a.grantee
          WHERE p.oid=pg_catalog.to_regprocedure('{SIGNATURE}')
            AND (r.rolname IS NULL OR r.rolname NOT IN ('{OWNER}','aos_runtime')
              OR a.privilege_type<>'EXECUTE' OR a.is_grantable)) THEN
        RAISE EXCEPTION 'MODEL_ROUTE_PUBLICATION_READER_DEFAULT_ACL_DRIFT' USING ERRCODE='42501';
      END IF;
    END $$""")


def _caller(conn,scope):
    from aos_api.aip_model_route_eval_owner import _require_native_connection
    _require_native_connection(conn)
    row=conn.execute("""SELECT TRUE AS epoch_reader_context,pg_catalog.current_database() AS database,
        (SELECT oid FROM pg_catalog.pg_database WHERE datname=pg_catalog.current_database()) AS database_oid,
        session_user AS login,current_user AS role,
        pg_catalog.current_setting('aos.org_id',true) AS org_id,
        pg_catalog.current_setting('aos.project_id',true) AS project_id,
        pg_catalog.current_setting('transaction_isolation') AS isolation,
        pg_catalog.current_setting('transaction_read_only') AS readonly,
        pg_catalog.pg_backend_pid() AS pid,pg_catalog.pg_current_xact_id()::text AS xid""").fetchone()
    if (type(row) is not dict or row.get('database')!=conn.info.dbname
        or type(row.get('database_oid')) is not int or row['database_oid']<1
        or type(row.get('pid')) is not int or row['pid']<1
        or type(row.get('xid')) is not str or re.fullmatch(r'[1-9][0-9]*',row['xid']) is None
        or type(row.get('login')) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,62}',row['login']) is None
        or (row.get('role'),row.get('org_id'),row.get('project_id'),row.get('isolation'),row.get('readonly'))
           !=('aos_runtime',*scope.key,'serializable','off')):
        raise EvalPublicationEpochRejected('MODEL_ROUTE_PUBLICATION_NATIVE_CALLER_REQUIRED')
    return row


def _audit(conn):
    row=conn.execute("""SELECT TRUE AS epoch_reader_profile,r.oid AS owner_oid,p.oid AS function_oid,
        r.rolname AS owner,r.rolcanlogin,r.rolinherit,r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolreplication,r.rolbypassrls,
        l.lanname AS language,p.prosecdef AS security_definer,p.proconfig AS config,
        p.prorettype AS return_type,p.proargtypes::text AS args,
        p.provolatile AS volatility,p.proparallel AS parallel,p.proisstrict AS strict,
        pg_catalog.has_schema_privilege(r.oid,'public','CREATE') AS schema_create,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(p.prosrc,'UTF8')),'hex') AS body_hash,
        (SELECT count(*) FROM pg_catalog.pg_auth_members WHERE member=r.oid OR roleid=r.oid) AS edges,
        (SELECT count(*) FROM pg_catalog.pg_proc WHERE proowner=r.oid) AS owned_functions,
        (SELECT count(*) FROM pg_catalog.pg_class WHERE relowner=r.oid) AS owned_relations,
        (SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspowner=r.oid) AS owned_schemas,
        (SELECT count(*) FROM pg_catalog.pg_database WHERE datdba=r.oid) AS owned_databases,
        ARRAY(SELECT coalesce(g.rolname,'PUBLIC')||':'||a.privilege_type||':'||a.is_grantable::text
          FROM pg_catalog.aclexplode(coalesce(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
          LEFT JOIN pg_catalog.pg_roles g ON g.oid=a.grantee ORDER BY 1) AS function_acl,
        ARRAY(SELECT n.nspname||'.'||c.relname||':'||a.privilege_type||':'||a.is_grantable::text
          FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
          LATERAL pg_catalog.aclexplode(c.relacl) a WHERE a.grantee=r.oid ORDER BY 1) AS relation_acl,
        ARRAY(SELECT n.nspname||'.'||c.relname||':'||col.attname||':'||a.privilege_type||':'||a.is_grantable::text
          FROM pg_catalog.pg_attribute col JOIN pg_catalog.pg_class c ON c.oid=col.attrelid
          JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
          LATERAL pg_catalog.aclexplode(col.attacl) a WHERE a.grantee=r.oid ORDER BY 1) AS column_acl,
        ARRAY(SELECT n.nspname||':'||a.privilege_type||':'||a.is_grantable::text
          FROM pg_catalog.pg_namespace n,LATERAL pg_catalog.aclexplode(n.nspacl) a
          WHERE a.grantee=r.oid ORDER BY 1) AS schema_acl,
        ARRAY(SELECT d.datname||':'||a.privilege_type||':'||a.is_grantable::text
          FROM pg_catalog.pg_database d,LATERAL pg_catalog.aclexplode(d.datacl) a
          WHERE a.grantee=r.oid ORDER BY 1) AS database_acl,
        ARRAY(SELECT p2.oid::text||':'||a.privilege_type||':'||a.is_grantable::text
          FROM pg_catalog.pg_proc p2,LATERAL pg_catalog.aclexplode(p2.proacl) a
          WHERE a.grantee=r.oid AND p2.oid<>p.oid ORDER BY 1) AS other_function_acl
        FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
        JOIN pg_catalog.pg_language l ON l.oid=p.prolang
        WHERE p.oid=pg_catalog.to_regprocedure(%s)""",(SIGNATURE,)).fetchone()
    expected=dict(owner=OWNER,language='plpgsql',security_definer=True,config=['search_path=pg_catalog'],
        return_type=20,args='25 25 25',body_hash=FUNCTION_SHA256,volatility='v',parallel='u',strict=False,schema_create=False,edges=0,owned_functions=1,
        owned_relations=0,owned_schemas=0,owned_databases=0,
        function_acl=sorted([OWNER+':EXECUTE:false','aos_runtime:EXECUTE:false']),
        relation_acl=['public.aip_publication_epoch:SELECT:false'],
        column_acl=['public.aip_publication_epoch:epoch:UPDATE:false'],schema_acl=['public:USAGE:false'],
        database_acl=[],other_function_acl=[])
    if (type(row) is not dict or any(row.get(k)!=v for k,v in expected.items())
        or any(row.get(k) is not False for k in ROLE_FLAGS)
        or row.get('security_definer') is not True or row.get('strict') is not False or row.get('schema_create') is not False
        or any(type(row.get(k)) is not int or row[k]<1 for k in ('owner_oid','function_oid'))):
        raise EvalPublicationEpochRejected('MODEL_ROUTE_PUBLICATION_READER_PROFILE_DRIFT')
    table=conn.execute("""SELECT TRUE AS epoch_original_table,o.rolname AS owner,
        c.relrowsecurity AS rls,c.relforcerowsecurity AS force_rls,
        (SELECT count(*) FROM pg_catalog.pg_auth_members WHERE member=o.oid OR roleid=o.oid) AS owner_edges,
        o.rolcanlogin,o.rolinherit,o.rolsuper,o.rolcreatedb,o.rolcreaterole,o.rolreplication,o.rolbypassrls,
        pg_catalog.has_table_privilege('aos_runtime',c.oid,'SELECT') AS runtime_select,
        pg_catalog.has_any_column_privilege('aos_runtime',c.oid,'UPDATE') AS runtime_any_update,
        pg_catalog.has_table_privilege(%s,c.oid,'UPDATE') AS reader_table_update,
        pg_catalog.has_table_privilege(%s,c.oid,'INSERT') AS reader_insert,
        pg_catalog.has_table_privilege(%s,c.oid,'DELETE') AS reader_delete,
        pg_catalog.has_table_privilege(%s,c.oid,'TRUNCATE') AS reader_truncate
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_roles o ON o.oid=c.relowner
        WHERE c.oid=pg_catalog.to_regclass('public.aip_publication_epoch')""",(OWNER,)*4).fetchone()
    if (type(table) is not dict or table.get('owner')!='aos_publication_epoch_owner'
        or table.get('rls') is not True or table.get('force_rls') is not True
        or type(table.get('owner_edges')) is not int or table['owner_edges']!=0
        or any(table.get(k) is not False for k in (*ROLE_FLAGS,'runtime_select','runtime_any_update',
            'reader_table_update','reader_insert','reader_delete','reader_truncate'))):
        raise EvalPublicationEpochRejected('MODEL_ROUTE_ORIGINAL_PUBLICATION_TABLE_DRIFT')
    policies=conn.execute("""SELECT TRUE AS epoch_reader_policy,p.polname AS name,p.polroles AS roles,
        p.polcmd AS command,p.polpermissive AS permissive,
        pg_catalog.pg_get_expr(p.polqual,p.polrelid) AS using,
        pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid) AS check
        FROM pg_catalog.pg_policy p WHERE p.polrelid=pg_catalog.to_regclass('public.aip_publication_epoch')
          AND (0=ANY(p.polroles) OR %s=ANY(p.polroles)) ORDER BY p.polname""",(row['owner_oid'],)).fetchall()
    policy=dict(name=POLICY,roles=[row['owner_oid']],command='*',permissive=True,using=POLICY_EXPR,check=POLICY_EXPR)
    if (len(policies)!=1 or type(policies[0]) is not dict
        or any(policies[0].get(k)!=v for k,v in policy.items()) or policies[0].get('permissive') is not True):
        raise EvalPublicationEpochRejected('MODEL_ROUTE_PUBLICATION_READER_POLICY_DRIFT')
    triggers=conn.execute("""SELECT TRUE AS epoch_original_trigger,t.tgname AS name,t.tgenabled AS enabled,
        t.tgtype AS type,t.tgnargs AS args_count,t.tgqual AS qualification,
        p.proname AS function,o.rolname AS owner,l.lanname AS language,p.prosecdef AS security_definer,
        p.proconfig AS config,p.proargtypes::text AS args,p.prorettype AS return_type,
        pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(p.prosrc,'UTF8')),'hex') AS body_hash
        FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid
        JOIN pg_catalog.pg_roles o ON o.oid=p.proowner JOIN pg_catalog.pg_language l ON l.oid=p.prolang
        WHERE t.tgrelid=pg_catalog.to_regclass('public.aip_publication_event') AND NOT t.tgisinternal
          AND t.tgname=ANY(%s::text[]) ORDER BY t.tgname""",
        ([f'publication_epoch_{name}_a0v144' for name,_,_ in ORIGINAL_TRIGGERS],)).fetchall()
    if len(triggers)!=2:raise EvalPublicationEpochRejected('MODEL_ROUTE_PUBLICATION_TRIGGER_DRIFT')
    for trigger,(name,kind,digest) in zip(triggers,ORIGINAL_TRIGGERS):
        wanted=dict(name=f'publication_epoch_{name}_a0v144',enabled='O',type=kind,args_count=0,
            qualification=None,function=f'aos_publication_epoch_{name}',owner='aos_publication_epoch_owner',
            language='plpgsql',security_definer=True,config=['search_path=pg_catalog, public, pg_temp'],
            args='',return_type=2279,body_hash=digest)
        if type(trigger) is not dict or any(trigger.get(k)!=v for k,v in wanted.items()) or trigger.get('security_definer') is not True:
            raise EvalPublicationEpochRejected('MODEL_ROUTE_PUBLICATION_TRIGGER_DRIFT')
    return row,table,policies,triggers


def lock_eval_publication_epoch(conn,scope,publication_id):
    """Necessary original-epoch protection only. Keep original published-row lock first.

    An old SERIAL snapshot after a committed bump raises native 40001; do not
    catch/retry it here. This helper proves no Source, Maker, approval or budget.
    """
    if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
        or type(publication_id) is not str or not 1<=len(publication_id)<=200
        or publication_id!=publication_id.strip()):
        raise EvalPublicationEpochRejected('MODEL_ROUTE_PUBLICATION_EXACT_INPUT_REQUIRED')
    before=_caller(conn,scope);profile=_audit(conn)
    row=conn.execute('SELECT public.aos_model_route_eval_publication_epoch_lock(%s,%s,%s) AS epoch',
        (*scope.key,publication_id)).fetchone()
    if type(row) is not dict or type(row.get('epoch')) is not int or row['epoch']<1:
        raise EvalPublicationEpochRejected('MODEL_ROUTE_PUBLICATION_CURRENT_EPOCH_REQUIRED')
    if _audit(conn)!=profile or _caller(conn,scope)!=before:
        raise EvalPublicationEpochRejected('MODEL_ROUTE_PUBLICATION_CALLER_OR_PROFILE_CHANGED')
    return row['epoch']
