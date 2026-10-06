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


def _original_evidence_boundary_sql():
    """The original Evidence catalog audit, without giving Owner table access."""
    from aos_api.aip_provider_capacity_evidence_fence import FUNCTIONS
    definitions=','.join("('"+name+"','"+digest+"')" for name,digest in FUNCTIONS.items())
    return r"""
CREATE FUNCTION aos_capacity_publication_private.require_original_evidence_boundary()
RETURNS void LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE
 owner_oid oid; table_oid oid; role_row record; table_row record; r record; expected record;
 reader boolean; signature text; caller text; allowed text[]; ids oid[]:=ARRAY[]::oid[];
 policy_expr text:='((org_id = NULLIF(current_setting(''aos.org_id''::text, true), ''''::text)) AND (project_id = NULLIF(current_setting(''aos.project_id''::text, true), ''''::text)))';
BEGIN
 BEGIN
  PERFORM aos_capacity_publication_private.require_original_epoch_pair_boundary();
 EXCEPTION WHEN SQLSTATE '22023' THEN
  RAISE EXCEPTION 'CAPACITY_EVIDENCE_PUBLICATION_CALLER_DRIFTED' USING ERRCODE='22023';
 END;
 SELECT * INTO role_row FROM pg_roles WHERE rolname='aos_capacity_evidence_epoch_owner';
 IF NOT FOUND OR role_row.rolcanlogin OR role_row.rolinherit OR role_row.rolsuper
  OR role_row.rolcreatedb OR role_row.rolcreaterole OR role_row.rolreplication OR role_row.rolbypassrls
  OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=role_row.oid OR member=role_row.oid) THEN
  RAISE EXCEPTION 'CAPACITY_EVIDENCE_OWNER_DRIFTED' USING ERRCODE='22023'; END IF;
 owner_oid:=role_row.oid;
 SELECT * INTO table_row FROM pg_class WHERE oid=to_regclass('public.aip_capacity_evidence_epoch');
 IF NOT FOUND OR table_row.relowner<>owner_oid OR table_row.relkind<>'r'
  OR NOT table_row.relrowsecurity OR NOT table_row.relforcerowsecurity THEN
  RAISE EXCEPTION 'CAPACITY_EVIDENCE_TABLE_DRIFTED' USING ERRCODE='22023'; END IF;
 table_oid:=table_row.oid;
 IF EXISTS(SELECT 1 FROM aclexplode(coalesce(table_row.relacl,acldefault('r',owner_oid))) a WHERE a.grantee<>owner_oid)
  OR EXISTS(SELECT 1 FROM pg_attribute c,LATERAL aclexplode(c.attacl) a
    WHERE c.attrelid=table_oid AND a.grantee<>owner_oid) THEN
  RAISE EXCEPTION 'CAPACITY_EVIDENCE_TABLE_DRIFTED' USING ERRCODE='22023'; END IF;
 SELECT * INTO r FROM pg_policy WHERE polrelid=table_oid;
 IF (SELECT count(*) FROM pg_policy WHERE polrelid=table_oid)<>1 OR NOT FOUND
  OR r.polname<>'capacity_evidence_epoch_scope' OR r.polcmd<>'*' OR NOT r.polpermissive
  OR r.polroles IS DISTINCT FROM ARRAY[owner_oid]
  OR pg_get_expr(r.polqual,r.polrelid) IS DISTINCT FROM policy_expr
  OR pg_get_expr(r.polwithcheck,r.polrelid) IS DISTINCT FROM policy_expr THEN
  RAISE EXCEPTION 'CAPACITY_EVIDENCE_RLS_POLICY_DRIFTED' USING ERRCODE='22023'; END IF;
 FOR expected IN SELECT * FROM (VALUES
"""+definitions+r""") v(name,digest) LOOP
  reader:=expected.name IN ('lock','issuer_lock');
  signature:='public.aos_capacity_evidence_epoch_'||expected.name||
   CASE WHEN reader THEN '(text,text,text)' ELSE '()' END;
  SELECT * INTO r FROM pg_proc WHERE oid=to_regprocedure(signature);
  IF NOT FOUND OR r.proowner<>owner_oid OR NOT r.prosecdef
   OR r.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog']
   OR r.prorettype<>(CASE WHEN reader THEN 20 ELSE 2279 END)
   OR r.proargtypes::text<>(CASE WHEN reader THEN '25 25 25' ELSE '' END)
   OR encode(sha256(convert_to(r.prosrc,'UTF8')),'hex')<>expected.digest THEN
   RAISE EXCEPTION 'CAPACITY_EVIDENCE_FUNCTION_DRIFTED' USING ERRCODE='22023'; END IF;
  ids:=array_append(ids,r.oid);
  caller:=CASE WHEN expected.name='lock' THEN 'aos_runtime' ELSE 'aos_provider_capacity_issuer' END;
  allowed:=ARRAY['aos_capacity_evidence_epoch_owner'];
  IF reader THEN allowed:=array_append(allowed,caller); END IF;
  IF expected.name='issuer_lock' THEN allowed:=array_append(allowed,'aos_capacity_publication_owner'); END IF;
  IF EXISTS(SELECT 1 FROM aclexplode(coalesce(r.proacl,acldefault('f',r.proowner))) a
    LEFT JOIN pg_roles roles ON roles.oid=a.grantee
    WHERE roles.rolname IS NULL OR NOT roles.rolname=ANY(allowed) OR a.privilege_type<>'EXECUTE'
     OR (roles.rolname<>'aos_capacity_evidence_epoch_owner' AND a.is_grantable))
   OR (reader AND NOT EXISTS(SELECT 1 FROM aclexplode(coalesce(r.proacl,acldefault('f',r.proowner))) a
    JOIN pg_roles roles ON roles.oid=a.grantee WHERE roles.rolname=caller)) THEN
   RAISE EXCEPTION 'CAPACITY_EVIDENCE_FUNCTION_ACL_DRIFTED' USING ERRCODE='22023'; END IF;
 END LOOP;
 IF (SELECT count(*) FROM pg_trigger WHERE tgrelid='public.aip_evidence_bundle_revoke_event'::regclass
   AND tgname=ANY(ARRAY['capacity_evidence_epoch_touch_a0v149','capacity_evidence_epoch_bump_a0v149']))<>2
  OR EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='public.aip_evidence_bundle_revoke_event'::regclass
   AND tgname=ANY(ARRAY['capacity_evidence_epoch_touch_a0v149','capacity_evidence_epoch_bump_a0v149'])
   AND (tgfoid<>(CASE WHEN tgname='capacity_evidence_epoch_touch_a0v149'
       THEN to_regprocedure('public.aos_capacity_evidence_epoch_touch()')::oid
       ELSE to_regprocedure('public.aos_capacity_evidence_epoch_bump()')::oid END)
    OR tgtype<>(CASE WHEN tgname='capacity_evidence_epoch_touch_a0v149' THEN 7 ELSE 5 END)
    OR tgenabled<>'O' OR tgattr::text<>'' OR tgqual IS NOT NULL OR tgargs<>''::bytea)) THEN
  RAISE EXCEPTION 'CAPACITY_EVIDENCE_TRIGGER_DRIFTED' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM pg_class c WHERE c.relowner=owner_oid AND c.oid<>table_oid AND c.oid<>table_row.reltoastrelid
   AND NOT EXISTS(SELECT 1 FROM pg_index i WHERE i.indexrelid=c.oid AND i.indrelid IN(table_oid,table_row.reltoastrelid)))
  OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner=owner_oid AND NOT oid=ANY(ids))
  OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspowner=owner_oid)
  OR EXISTS(SELECT 1 FROM pg_database WHERE datdba=owner_oid)
  OR EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE a.grantee=owner_oid AND c.oid<>table_oid)
  OR EXISTS(SELECT 1 FROM pg_attribute c,LATERAL aclexplode(c.attacl) a WHERE a.grantee=owner_oid AND c.attrelid<>table_oid)
  OR EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE a.grantee=owner_oid AND NOT p.oid=ANY(ids))
  OR EXISTS(SELECT 1 FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE a.grantee=owner_oid
    AND (n.nspname<>'public' OR a.privilege_type<>'USAGE' OR a.is_grantable)) THEN
  RAISE EXCEPTION 'CAPACITY_EVIDENCE_OWNER_EXTRA_PRIVILEGE' USING ERRCODE='22023'; END IF;
END $body$;
ALTER FUNCTION aos_capacity_publication_private.require_original_evidence_boundary() OWNER TO aos_capacity_publication_owner;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.require_original_evidence_boundary() FROM PUBLIC;
"""


def _original_facts_sql():
    """Installation SQL using fixed original readers and sequential lock calls.

    No runtime SQL or caller expression is compiled here. Complete157 must still
    authenticate, verify signed provenance, sign and commit in the native caller.
    """
    import re
    from aos_api import aip_provider_capacity_publication_store as original
    from aos_api.aip_provider_capacity_action import ProviderCapacityActionGuard
    from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard
    from aos_api.asset_registry.canonical_json import canonical_json

    fixed = dict(org_id="'org-org'", project_id="'dev-project'", maker='p_maker',
        proposal_id="source_ref->>'assetId'", proposal_revision="(source_ref->>'revision')::numeric",
        proposal_hash="source_ref->>'contentHash'", approval_event_id="event_ref->>'assetId'",
        approval_event_hash="event_ref->>'contentHash'",
        request_id="source_value->'allocationRequestRef'->>'assetId'",
        request_hash="source_value->'allocationRequestRef'->>'contentHash'")
    for kind, field in (('account', 'physicalAccountRef'), ('basis', 'basisRef')):
        fixed.update({kind+'_id':f"source_value->'{field}'->>'assetId'",
            kind+'_revision':f"(source_value->'{field}'->>'revision')::numeric",
            kind+'_hash':f"source_value->'{field}'->>'contentHash'"})
    ref_params = dict(provider_id="p_ref->>'assetId'", bundle_id="p_ref->>'assetId'",
        revision="(p_ref->>'revision')::numeric", content_hash="p_ref->>'contentHash'")

    def compile_query(statement, **overrides):
        parameters = {**fixed, **overrides}
        result = re.sub(r'%\((\w+)\)s', lambda m: '('+parameters[m.group(1)]+')', statement)
        if '%(' in result:
            raise ValueError('Uncompiled original Source SQL parameter')
        return result

    def metadata(guard):
        def literal(value):
            return "'"+canonical_json(value).decode().replace("'", "''")+"'::jsonb"
        return f"""
 SELECT to_jsonb(m) INTO STRICT metadata_value FROM (
  SELECT id,name,description,published,properties,required_markings
  FROM public.meta_object_type WHERE id='{guard.object_id}' FOR SHARE) m;
 IF metadata_value IS DISTINCT FROM {literal(guard.object_snapshot)} THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_METADATA_DRIFTED' USING ERRCODE='22023'; END IF;
 SELECT jsonb_build_object('id',m.id,'name',m.name,'objectType',m.object_type,
  'parameters',m.parameters,'requiredMarkings',m.required_markings,
  'submissionCriteria',m.submission_criteria) INTO STRICT metadata_value FROM (
  SELECT id,name,object_type,parameters,required_markings,submission_criteria
  FROM public.meta_action_type WHERE id='{guard.action_id}' FOR SHARE) m;
 IF metadata_value IS DISTINCT FROM {literal(guard.action_snapshot)} THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_METADATA_DRIFTED' USING ERRCODE='22023'; END IF;
"""

    source_query = compile_query(original.CAPACITY_NATIVE_APPROVED_SOURCE_ROW_SQL)
    request_query = compile_query(original.CAPACITY_NATIVE_REQUEST_ROW_SQL)
    allocation_query = compile_query(original.CAPACITY_APPROVED_ALLOCATION_ROW_SQL,
        approval_event_id="source_value->'allocationApprovalRef'->>'assetId'",
        approval_event_hash="source_value->'allocationApprovalRef'->>'contentHash'")
    candidate_queries = {}
    for kind, field in (('account','physicalAccountRef'), ('basis','basisRef')):
        candidate_queries[kind] = compile_query(original.CAPACITY_NATIVE_CANDIDATE_ROW_SQL,
            candidate_id=f"source_value->'{field}'->>'assetId'", candidate_kind=f"'{kind}'",
            revision=f"(source_value->'{field}'->>'revision')::numeric",
            content_hash=f"source_value->'{field}'->>'contentHash'")

    sql = _original_evidence_boundary_sql()+r"""
CREATE FUNCTION aos_capacity_publication_private.require_original_owner(p_actor text)
RETURNS void LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE roles text[];
BEGIN
 SELECT array_agg(m.role) INTO roles FROM (
  SELECT role FROM public.meta_membership
  WHERE org_id='org-org' AND project_id='dev-project' AND subject=p_actor FOR SHARE) m;
 IF cardinality(roles) IS DISTINCT FROM 1 OR lower(roles[1]) IS DISTINCT FROM 'owner' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_OWNER_REQUIRED' USING ERRCODE='22023'; END IF;
END $body$;

CREATE FUNCTION aos_capacity_publication_private.read_original_fact_provider(p_ref jsonb)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE result jsonb;
BEGIN
 SELECT q.normalized_provider INTO STRICT result FROM (
""" + compile_query(original.CAPACITY_NATIVE_PROVIDER_ROW_SQL, **ref_params) + r"""
 ) q;
 RETURN result;
END $body$;

CREATE FUNCTION aos_capacity_publication_private.require_original_fact_evidence(p_ref jsonb,p_build boolean)
RETURNS void LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE item record;
BEGIN
 -- Initial request read deliberately has no Build provenance predicate.
 SELECT e.* INTO STRICT item FROM public.aip_evidence_bundle_revision e
 WHERE e.org_id='org-org' AND e.project_id='dev-project'
  AND e.bundle_id=p_ref->>'assetId' AND e.revision=(p_ref->>'revision')::numeric
  AND e.content_hash=p_ref->>'contentHash' AND e.lifecycle='frozen'
  AND NOT EXISTS(SELECT 1 FROM public.aip_evidence_bundle_revoke_event r
   WHERE (r.org_id,r.project_id,r.bundle_id,r.revision,r.content_hash)=
         (e.org_id,e.project_id,e.bundle_id,e.revision,e.content_hash))
  AND e.coverage IN ('complete','partial','blocked','unknown')
  AND e.freshness IN ('fresh','stale','blocked','unknown')
  AND isfinite(e.created_at) AND isfinite(e.cutoff_at)
  AND extract(year FROM e.created_at AT TIME ZONE 'UTC') BETWEEN 1 AND 9999
  AND extract(year FROM e.cutoff_at AT TIME ZONE 'UTC') BETWEEN 1 AND 9999
  AND aos_capacity_publication_private.original_evidence_fields(e.brief_ref,e.subject_refs,e.item_refs,
      e.missing,e.conflicts,e.uncertainties,e.marking,e.license_summary);
 IF p_build THEN
  SELECT q.* INTO STRICT item FROM (
""" + compile_query(original.CAPACITY_NATIVE_EVIDENCE_ROW_SQL, **ref_params) + r"""
  ) q;
 END IF;
END $body$;

CREATE FUNCTION aos_capacity_publication_private.read_original_fact_request(source_value jsonb,p_maker text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE application jsonb;
BEGIN
 SELECT q.normalized_application INTO STRICT application FROM (
""" + request_query + r"""
 ) q;
 PERFORM aos_capacity_publication_private.read_original_fact_provider(application->'providerRef');
 PERFORM aos_capacity_publication_private.require_original_fact_evidence(application->'basisEvidenceRef',false);
 RETURN application;
END $body$;

CREATE FUNCTION aos_capacity_publication_private.read_original_source_facts(p_maker text,p_source_ref jsonb,p_event_ref jsonb)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE
 source_ref jsonb; event_ref jsonb; source_row jsonb; allocation_row jsonb;
 source_value jsonb; facts_application jsonb; account_value jsonb; basis_value jsonb;
 metadata_value jsonb; allocation_event record; source_event record; matched integer;
 target text; ref jsonb; evidence_refs jsonb[]; epochs jsonb:='{}'::jsonb;
 withdrawal_epochs jsonb:='{}'::jsonb; window_value record;
BEGIN
 IF current_user IS DISTINCT FROM 'aos_capacity_publication_owner'
  OR session_user IS DISTINCT FROM 'aos_provider_capacity_issuer'
  OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
  OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
  OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
  OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
  OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
  OR current_setting('TimeZone') IS DISTINCT FROM 'UTC' THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_FACT_CONTEXT_REQUIRED' USING ERRCODE='42501'; END IF;
 IF p_maker IS NULL OR p_source_ref IS NULL OR p_event_ref IS NULL THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_FACT_INPUT_REQUIRED' USING ERRCODE='22023'; END IF;
 PERFORM aos_capacity_publication_private.read_identifier(to_jsonb(p_maker));
 source_ref:=aos_capacity_publication_private.original_source_ref(p_source_ref,'ActionProposal');
 event_ref:=aos_capacity_publication_private.original_source_ref(p_event_ref,'ActionApprovalEvent');
 IF source_ref->'revision' IS DISTINCT FROM '2'::jsonb OR event_ref->'revision' IS DISTINCT FROM '1'::jsonb THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_FACT_INPUT_REQUIRED' USING ERRCODE='22023'; END IF;
 PERFORM aos_capacity_publication_private.require_original_withdrawal_boundary();
 SELECT to_jsonb(q) INTO STRICT source_row FROM (
""" + source_query + r"""
 ) q;
 source_value:=aos_capacity_publication_private.read_original_source_candidate(source_row->'payload'->'sourceCandidate');
 SELECT actor_id,expires_at INTO STRICT source_event FROM public.aip_action_approval_event
 WHERE org_id='org-org' AND project_id='dev-project' AND approval_event_id=event_ref->>'assetId';
""" + metadata(ProviderCapacitySourceActionGuard) + r"""
 PERFORM aos_capacity_publication_private.require_original_owner(p_maker);
 facts_application:=aos_capacity_publication_private.read_original_fact_request(source_value,p_maker);
 SELECT proposal_id,actor_id,expires_at INTO STRICT allocation_event FROM public.aip_action_approval_event
 WHERE org_id='org-org' AND project_id='dev-project'
  AND approval_event_id=source_value->'allocationApprovalRef'->>'assetId';
 SELECT to_jsonb(p) INTO STRICT allocation_row FROM public.aip_action_proposal p
 WHERE p.org_id='org-org' AND p.project_id='dev-project' AND p.proposal_id=allocation_event.proposal_id FOR SHARE;
 IF EXISTS(SELECT 1 FROM public.aip_action_withdrawal_event w
  WHERE w.org_id='org-org' AND w.project_id='dev-project' AND w.proposal_id=allocation_event.proposal_id) THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_APPROVAL_WITHDRAWN' USING ERRCODE='22023'; END IF;
""" + metadata(ProviderCapacityActionGuard) + r"""
 facts_application:=aos_capacity_publication_private.read_original_fact_request(source_value,p_maker);
 IF (allocation_row->>'expires_at')::timestamptz>
    (SELECT instant FROM aos_capacity_publication_private.original_source_time(facts_application->'proposalExpiresAt')) THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_ALLOCATION_EXPIRY_DRIFTED' USING ERRCODE='22023'; END IF;
 PERFORM aos_capacity_publication_private.require_original_owner(p_maker);
 PERFORM aos_capacity_publication_private.require_original_owner(allocation_event.actor_id);
 SELECT to_jsonb(q) INTO STRICT allocation_row FROM (
""" + allocation_query + r"""
 ) q;
 SELECT q.normalized_candidate INTO STRICT account_value FROM (
""" + candidate_queries['account'] + r"""
 ) q;
 SELECT q.normalized_candidate INTO STRICT basis_value FROM (
""" + candidate_queries['basis'] + r"""
 ) q;
 SELECT q.matched INTO STRICT matched FROM (
""" + compile_query(original.CAPACITY_NATIVE_SOURCE_COMBINATION_SQL) + r"""
 ) q;
 evidence_refs:=ARRAY[facts_application->'basisEvidenceRef',account_value->'evidenceRef',basis_value->'evidenceRef'];
 PERFORM aos_capacity_publication_private.require_original_evidence_boundary();
 -- All neutral locks first; then every original ref, without deduplication.
 FOR target IN SELECT DISTINCT e->>'assetId' COLLATE "C" FROM unnest(evidence_refs) e
  ORDER BY 1 LOOP
  epochs:=epochs||jsonb_build_object(target,public.aos_capacity_evidence_epoch_issuer_lock('org-org','dev-project',target));
 END LOOP;
 FOREACH ref IN ARRAY evidence_refs LOOP
  PERFORM aos_capacity_publication_private.require_original_fact_evidence(ref,true);
 END LOOP;
 FOR ref IN SELECT value FROM jsonb_array_elements(account_value->'providerRefs')
  ORDER BY value->>'assetId' COLLATE "C" LOOP
  PERFORM aos_capacity_publication_private.read_original_fact_provider(ref);
 END LOOP;
 PERFORM aos_capacity_publication_private.require_original_fact_evidence(account_value->'evidenceRef',true);
 PERFORM aos_capacity_publication_private.require_original_fact_evidence(basis_value->'evidenceRef',true);
 SELECT q.* INTO STRICT window_value FROM (
""" + compile_query(original.CAPACITY_NATIVE_SOURCE_WINDOW_SQL) + r"""
 ) q;
 PERFORM aos_capacity_publication_private.require_original_owner(source_event.actor_id);
 FOR target IN SELECT DISTINCT id COLLATE "C" FROM unnest(ARRAY[source_row->>'proposal_id',allocation_event.proposal_id]) id
  ORDER BY 1 LOOP
  withdrawal_epochs:=withdrawal_epochs||jsonb_build_object(target,public.aos_capacity_withdrawal_epoch_lock('org-org','dev-project',target));
 END LOOP;
 IF EXISTS(SELECT 1 FROM public.aip_action_withdrawal_event w WHERE w.org_id='org-org'
  AND w.project_id='dev-project' AND w.proposal_id=ANY(ARRAY[source_row->>'proposal_id',allocation_event.proposal_id])) THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_APPROVAL_WITHDRAWN' USING ERRCODE='22023'; END IF;
 IF clock_timestamp()>=least((source_row->>'expires_at')::timestamptz,
    (allocation_row->>'expires_at')::timestamptz,source_event.expires_at,allocation_event.expires_at,
    (SELECT instant FROM aos_capacity_publication_private.original_source_time(source_value->'validUntil'))) THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_APPROVAL_EXPIRED' USING ERRCODE='22023'; END IF;
 RETURN jsonb_build_object('source',source_value,'account',account_value,'basis',basis_value,
  'application',facts_application,'evidenceEpochs',epochs,'withdrawalEpochs',withdrawal_epochs,
  'sourceProposal',source_row->>'proposal_id','allocationProposal',allocation_event.proposal_id,
  'sourceApprovalExpiresAt',source_event.expires_at,'allocationApprovalExpiresAt',allocation_event.expires_at,
  'owner',current_user,'session',session_user,'xid',pg_current_xact_id()::text,'pid',pg_backend_pid());
END $body$;
"""
    for signature in ('require_original_owner(text)', 'read_original_fact_provider(jsonb)',
        'require_original_fact_evidence(jsonb,boolean)', 'read_original_fact_request(jsonb,text)',
        'read_original_source_facts(text,jsonb,jsonb)'):
        sql += f'\nALTER FUNCTION aos_capacity_publication_private.{signature} OWNER TO {OWNER};'
        sql += f'\nREVOKE ALL ON FUNCTION aos_capacity_publication_private.{signature} FROM PUBLIC;'
    return sql


# Reserved for complete157 installation; existing migrations remain unchanged.
CAPACITY_ORIGINAL_SOURCE_FACTS_SQL = _original_facts_sql()


# Untrusted original producer transport. Only the complete signing/COMMIT
# protocol can authenticate these hints and create a consumable Source.
CAPACITY_ORIGINAL_SOURCE_COMMAND_SQL = r"""
CREATE FUNCTION aos_capacity_publication_private.read_source_issuer_url(p jsonb)
RETURNS text LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE value text; authority text; host text; port text; suffix text; address text; i integer;
BEGIN
 IF p IS NULL OR jsonb_typeof(p) IS DISTINCT FROM 'string' THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 value:=p#>>'{}';
 IF length(value) NOT BETWEEN 1 AND 2000 OR left(value,8)<>'https://'
  OR strpos(value,'?')>0 OR strpos(value,'#')>0 THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 FOR i IN 1..length(value) LOOP
  PERFORM aos_capacity_publication_private.read_identifier(to_jsonb(substr(value,i,1)));
 END LOOP;
 authority:=split_part(substr(value,9),'/',1);
 IF authority='' OR strpos(authority,'@')>0
  OR normalize(translate(authority,':@?#',''),NFKC) ~ '[/?#@:]' THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 IF strpos(authority,'[')>0 OR strpos(authority,']')>0 THEN
  IF left(authority,1)<>'[' OR strpos(authority,']')=0 THEN
   RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
  host:=substr(authority,2,strpos(authority,']')-2);
  suffix:=substr(authority,strpos(authority,']')+1);
  IF suffix<>'' AND left(suffix,1)<>':' THEN
   RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
  port:=substr(suffix,2);
  IF left(host,1)='v' THEN
   IF host COLLATE "C" !~ '^v[a-fA-F0-9]+\..+$' THEN
    RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
  ELSE
   address:=split_part(host,'%',1);
   IF (strpos(host,'%')>0 AND (split_part(host,'%',2)='' OR length(host)-length(replace(host,'%',''))<>1))
    OR family(address::inet)<>6 OR strpos(address,'/')>0 THEN
    RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
  END IF;
 ELSE
  host:=split_part(authority,':',1);
  port:=CASE WHEN strpos(authority,':')>0 THEN substr(authority,strpos(authority,':')+1) ELSE '' END;
 END IF;
 IF host='' OR (port<>'' AND (port COLLATE "C" !~ '^[0-9]+$' OR port::numeric NOT BETWEEN 1 AND 65535)) THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 RETURN value;
EXCEPTION WHEN OTHERS THEN
 RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023';
END $body$;

CREATE FUNCTION aos_capacity_publication_private.read_source_command(p_raw bytea)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE packet jsonb; command jsonb; authentication jsonb; maker text; expected_hash text; ref jsonb; field text; kind text;
BEGIN
 IF p_raw IS NULL THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 packet:=aos_capacity_publication_private.read_signed_body(p_raw);
 IF jsonb_typeof(packet) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(packet))<>5
  OR packet-ARRAY['protocol','makerSubject','requestHash','command','authentication']<>'{}'::jsonb
  OR packet->'protocol' IS DISTINCT FROM '"aos-provider-capacity-source-command/v1"'::jsonb THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 maker:=aos_capacity_publication_private.read_identifier(packet->'makerSubject');
 IF maker='unknown' THEN RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 command:=packet->'command'; authentication:=packet->'authentication';
 IF jsonb_typeof(command) IS DISTINCT FROM 'object' OR (SELECT count(*) FROM jsonb_object_keys(command))<>6
  OR command-ARRAY['schemaVersion','tenant','approvedProposal','approvalEvent','supplierAttestationRef','sourcePolicyRef']<>'{}'::jsonb
  OR command->'schemaVersion' IS DISTINCT FROM '1'::jsonb
  OR command->'tenant' IS DISTINCT FROM '{"orgId":"org-org","projectId":"dev-project"}'::jsonb THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 FOR field,kind IN SELECT * FROM (VALUES
  ('approvedProposal','ActionProposal'),('approvalEvent','ActionApprovalEvent'),
  ('supplierAttestationRef','SupplierCapacityAttestationRevision'),
  ('sourcePolicyRef','ProviderCapacitySourcePolicyRevision')) v(field,kind) LOOP
  ref:=command->field;
  IF jsonb_typeof(ref) IS DISTINCT FROM 'object'
   OR ref-ARRAY['assetType','assetId','revision','contentHash']<>'{}'::jsonb THEN
   RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
  PERFORM aos_capacity_publication_private.original_source_ref(ref,kind);
  PERFORM aos_capacity_publication_private.read_identifier(ref->'assetId');
  IF (field='approvedProposal' AND ref->'revision' IS DISTINCT FROM '2'::jsonb)
   OR (field='approvalEvent' AND ref->'revision' IS DISTINCT FROM '1'::jsonb) THEN
   RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 END LOOP;
 expected_hash:=encode(sha256(convert_to(aos_capacity_publication_private.canonical_signed_json(
  jsonb_build_object('protocol','aos-provider-capacity-issuance-request/v1','maker',maker,'command',command)::json,1),'UTF8')),'hex');
 IF packet->'requestHash' IS DISTINCT FROM to_jsonb(expected_hash)
  OR jsonb_typeof(authentication) IS DISTINCT FROM 'object'
  OR (SELECT count(*) FROM jsonb_object_keys(authentication))<>4
  OR authentication-ARRAY['makerSubject','oidcIssuer','oidcAudience','authenticationExpiresAt']<>'{}'::jsonb
  OR authentication->'makerSubject' IS DISTINCT FROM packet->'makerSubject' THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 PERFORM aos_capacity_publication_private.read_source_issuer_url(authentication->'oidcIssuer');
 IF aos_capacity_publication_private.read_identifier(authentication->'oidcAudience')='unknown'
  OR aos_capacity_publication_private.read_signed_time(authentication->'authenticationExpiresAt')<=clock_timestamp() THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 RETURN packet;
EXCEPTION WHEN OTHERS THEN
 RAISE EXCEPTION 'CAPACITY_SOURCE_COMMAND_REQUIRED' USING ERRCODE='22023';
END $body$;

CREATE FUNCTION aos_capacity_publication_private.read_source_command_facts(p_raw bytea)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE packet jsonb; facts jsonb;
BEGIN
 packet:=aos_capacity_publication_private.read_source_command(p_raw);
 facts:=aos_capacity_publication_private.read_original_source_facts(packet->>'makerSubject',
  packet->'command'->'approvedProposal',packet->'command'->'approvalEvent');
 RETURN jsonb_build_object('packet',packet,'facts',facts);
END $body$;

ALTER FUNCTION aos_capacity_publication_private.read_source_issuer_url(jsonb) OWNER TO aos_capacity_publication_owner;
ALTER FUNCTION aos_capacity_publication_private.read_source_command(bytea) OWNER TO aos_capacity_publication_owner;
ALTER FUNCTION aos_capacity_publication_private.read_source_command_facts(bytea) OWNER TO aos_capacity_publication_owner;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_source_issuer_url(jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_source_command(bytea) FROM PUBLIC;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_source_command_facts(bytea) FROM PUBLIC;
"""


def _original_signed_facts_sql():
    """Compose original signed selectors after the complete original lock prefix."""
    import re
    from aos_api import aip_provider_capacity_publication_store as original

    fixed = dict(org_id="'org-org'", project_id="'dev-project'", maker="packet->>'makerSubject'")
    for prefix, ref in (
        ('proposal', "packet->'command'->'approvedProposal'"),
        ('approval_event', "packet->'command'->'approvalEvent'"),
        ('policy', "packet->'command'->'sourcePolicyRef'"),
        ('attestation', "packet->'command'->'supplierAttestationRef'"),
        ('permit', 'permit_ref'),
        ('account', "source_value->'physicalAccountRef'"),
        ('basis', "source_value->'basisRef'"),
    ):
        fixed[prefix+'_id'] = ref+"->>'assetId'"
        fixed[prefix+'_hash'] = ref+"->>'contentHash'"
        fixed[prefix+'_revision'] = ("("+ref+"->>'revision')::bigint"
            if prefix in ('proposal','approval_event','account','basis') else ref+"->>'revision'")

    def compile_query(statement, **overrides):
        parameters = {**fixed, **overrides}
        result = re.sub(r'%\((\w+)\)s', lambda m: '('+parameters[m.group(1)]+')', statement)
        if '%(' in result:
            raise ValueError('Uncompiled original signed Source parameter')
        return result

    registered = compile_query(original.CAPACITY_NATIVE_REGISTERED_DOCUMENT_ROW_SQL,
        kind="document_ref->>'assetType'", asset_id="document_ref->>'assetId'",
        revision="document_ref->>'revision'", content_hash="document_ref->>'contentHash'")
    supplier = compile_query(original.CAPACITY_NATIVE_SIGNED_SUPPLIER_COMBINATION_SQL)
    permit = compile_query(original.CAPACITY_NATIVE_SIGNING_PERMIT_COMBINATION_SQL)
    return r"""
CREATE FUNCTION aos_capacity_publication_private.read_source_command_signed_facts(p_raw bytea,p_permit_ref jsonb)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE
 input jsonb; packet jsonb; facts jsonb; source_value jsonb; permit_ref jsonb;
 fence jsonb; anchor jsonb; origin_value jsonb; document_ref jsonb; locked_document jsonb;
 checked_document jsonb; documents jsonb:='{}'::jsonb; supplier_row record; permit_row record;
 proposal_count integer; proposal_deadline timestamptz; final_checked_at timestamptz;
BEGIN
 IF p_permit_ref IS NULL THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_SIGNED_INPUT_REQUIRED' USING ERRCODE='22023'; END IF;
 permit_ref:=aos_capacity_publication_private.original_source_ref(p_permit_ref,'ProviderCapacitySigningPermitRevision');
 PERFORM aos_capacity_publication_private.read_identifier(permit_ref->'assetId');
 input:=aos_capacity_publication_private.read_source_command_facts(p_raw);
 packet:=input->'packet'; facts:=input->'facts'; source_value:=facts->'source';
 -- New-domain locks follow both original withdrawal epochs, never precede them.
 SELECT to_jsonb(f) INTO STRICT fence FROM aos_capacity_publication_private.registry_epoch f
 WHERE f.org_id='org-org' AND f.project_id='dev-project' FOR SHARE;
 SELECT to_jsonb(a) INTO STRICT anchor FROM aos_capacity_publication_private.deployment_anchor a
 WHERE a.org_id='org-org' AND a.project_id='dev-project' AND a.anchor_revision=fence->>'anchor_revision' FOR SHARE;
 SELECT to_jsonb(o) INTO STRICT origin_value FROM aos_capacity_publication_private.origin o
 WHERE o.org_id='org-org' AND o.project_id='dev-project' AND o.content_hash=fence->>'head_origin_hash'
  AND o.anchor_revision=anchor->>'anchor_revision' FOR SHARE;
 FOR document_ref IN SELECT value FROM jsonb_array_elements(jsonb_build_array(
   packet->'command'->'sourcePolicyRef',packet->'command'->'supplierAttestationRef',permit_ref))
   ORDER BY value->>'assetType' COLLATE "C",value->>'assetId' COLLATE "C",(value->>'revision')::numeric LOOP
  SELECT to_jsonb(d) INTO STRICT locked_document FROM aos_capacity_publication_private.document d
  WHERE d.org_id='org-org' AND d.project_id='dev-project' AND d.kind=document_ref->>'assetType'
   AND d.asset_id=document_ref->>'assetId' AND d.revision=document_ref->>'revision'
   AND d.content_hash=document_ref->>'contentHash' FOR SHARE;
  SELECT jsonb_build_object('payload',q.payload,'origin',q.origin_hash,'snapshot',q.snapshot_hash,
    'epoch',q.registry_current_epoch) INTO STRICT checked_document FROM (
""" + registered + r"""
  ) q;
  IF checked_document->'origin' IS DISTINCT FROM fence->'head_origin_hash'
   OR checked_document->'snapshot' IS DISTINCT FROM origin_value->'snapshot_hash'
   OR checked_document->'epoch' IS DISTINCT FROM fence->'epoch' THEN
   RAISE EXCEPTION 'CAPACITY_SOURCE_SIGNED_ORIGIN_DRIFTED' USING ERRCODE='22023'; END IF;
  documents:=documents||jsonb_build_object(document_ref->>'assetType',checked_document->'payload');
 END LOOP;
 SELECT q.* INTO STRICT supplier_row FROM (
""" + supplier + r"""
 ) q;
 IF supplier_row.source IS DISTINCT FROM source_value OR supplier_row.account IS DISTINCT FROM facts->'account'
  OR supplier_row.basis IS DISTINCT FROM facts->'basis' THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_SIGNED_ORIGINALS_DRIFTED' USING ERRCODE='22023'; END IF;
 SELECT q.* INTO STRICT permit_row FROM (
""" + permit + r"""
 ) q;
 IF permit_row.source IS DISTINCT FROM source_value
  OR permit_row.permit IS DISTINCT FROM documents->'ProviderCapacitySigningPermitRevision' THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_SIGNED_PERMIT_DRIFTED' USING ERRCODE='22023'; END IF;
 -- Re-read deadlines of already-held originals without taking any new original lock.
 SELECT count(*),min(p.expires_at) INTO proposal_count,proposal_deadline FROM public.aip_action_proposal p
 WHERE p.org_id='org-org' AND p.project_id='dev-project'
  AND p.proposal_id=ANY(ARRAY[facts->>'sourceProposal',facts->>'allocationProposal']);
 final_checked_at:=clock_timestamp();
 IF proposal_count<>2 OR proposal_deadline IS NULL OR final_checked_at>=least(proposal_deadline,
   (facts->>'sourceApprovalExpiresAt')::timestamptz,(facts->>'allocationApprovalExpiresAt')::timestamptz,
   (SELECT instant FROM aos_capacity_publication_private.original_source_time(source_value->'validUntil')))
  OR final_checked_at<(SELECT instant FROM aos_capacity_publication_private.original_source_time(source_value->'validFrom')) THEN
  RAISE EXCEPTION 'CAPACITY_ORIGINAL_APPROVAL_EXPIRED' USING ERRCODE='22023'; END IF;
 PERFORM aos_capacity_publication_private.read_source_command(p_raw);
 RETURN jsonb_build_object('packet',packet,'facts',facts,'signedDocuments',documents,'permitRef',permit_ref,
  'sourceSignerPublicKey',encode(permit_row.source_signer_public_key,'base64'),
  'sourceSignerRootRevision',permit_row.source_signer_root_revision,
  'origin',jsonb_build_object('anchorRevision',fence->'anchor_revision','originHash',fence->'head_origin_hash',
    'snapshotHash',origin_value->'snapshot_hash','epoch',fence->'epoch'));
END $body$;
ALTER FUNCTION aos_capacity_publication_private.read_source_command_signed_facts(bytea,jsonb) OWNER TO aos_capacity_publication_owner;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.read_source_command_signed_facts(bytea,jsonb) FROM PUBLIC;
"""


CAPACITY_ORIGINAL_SOURCE_SIGNED_FACTS_SQL = _original_signed_facts_sql()
