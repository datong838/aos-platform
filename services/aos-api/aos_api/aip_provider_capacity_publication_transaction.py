"""Original-fact access for the complete publication definer; no Source issued."""
import hashlib
import json
import re

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


# Future complete157 composition only. No migration/public issuer grant yet.
CAPACITY_SOURCE_PENDING_SQL = r"""
CREATE TABLE aos_capacity_publication_private.global_account(
 account_id uuid PRIMARY KEY,supplier_id text NOT NULL,fingerprint text NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{64}$'),
 org_id text NOT NULL,project_id text NOT NULL,UNIQUE(supplier_id,fingerprint));
CREATE TABLE aos_capacity_publication_private.global_provider(
 provider_id text PRIMARY KEY,account_id uuid NOT NULL REFERENCES aos_capacity_publication_private.global_account,
 org_id text NOT NULL,project_id text NOT NULL);
CREATE TABLE aos_capacity_publication_private.source_pending(
 org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
 maker text NOT NULL,attempt_key text NOT NULL CHECK(length(attempt_key) BETWEEN 1 AND 200),
 attempt_id uuid NOT NULL UNIQUE,source_asset_id text NOT NULL,account_id uuid NOT NULL,
 request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
 native_xid xid8 NOT NULL,native_pid integer NOT NULL,native_session text NOT NULL,
 command_raw bytea NOT NULL,permit_ref jsonb NOT NULL,signed_facts jsonb NOT NULL,
 source_raw bytea NOT NULL CHECK(octet_length(source_raw) BETWEEN 1 AND 2097152),
 source_hash text NOT NULL CHECK(source_hash=encode(sha256(source_raw),'hex')),
 finalized boolean NOT NULL DEFAULT false,
 PRIMARY KEY(org_id,project_id,maker,attempt_key),UNIQUE(org_id,project_id,source_asset_id),
 UNIQUE(org_id,project_id,maker,request_hash));
ALTER TABLE aos_capacity_publication_private.global_account OWNER TO aos_capacity_publication_owner;
ALTER TABLE aos_capacity_publication_private.global_provider OWNER TO aos_capacity_publication_owner;
ALTER TABLE aos_capacity_publication_private.source_pending OWNER TO aos_capacity_publication_owner;
REVOKE ALL ON aos_capacity_publication_private.global_account,aos_capacity_publication_private.global_provider,
 aos_capacity_publication_private.source_pending FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer,aos_provider_capacity_policy_publisher;
ALTER TABLE aos_capacity_publication_private.global_account ENABLE ROW LEVEL SECURITY;
ALTER TABLE aos_capacity_publication_private.global_account FORCE ROW LEVEL SECURITY;
ALTER TABLE aos_capacity_publication_private.global_provider ENABLE ROW LEVEL SECURITY;
ALTER TABLE aos_capacity_publication_private.global_provider FORCE ROW LEVEL SECURITY;
ALTER TABLE aos_capacity_publication_private.source_pending ENABLE ROW LEVEL SECURITY;
ALTER TABLE aos_capacity_publication_private.source_pending FORCE ROW LEVEL SECURITY;
-- Only the NOLOGIN private Owner can inspect global collisions. No caller
-- can read another scope; the derivation routine returns one generic denial.
CREATE POLICY source_global_owner ON aos_capacity_publication_private.global_account TO aos_capacity_publication_owner
 USING(true) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
CREATE POLICY source_global_owner ON aos_capacity_publication_private.global_provider TO aos_capacity_publication_owner
 USING(true) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
CREATE POLICY source_pending_owner ON aos_capacity_publication_private.source_pending TO aos_capacity_publication_owner
 USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
 WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));

CREATE FUNCTION aos_capacity_publication_private.require_pending_source_finalized()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog
 SET "aos.org_id"='org-org' SET "aos.project_id"='dev-project' AS $body$
BEGIN
 IF EXISTS(SELECT 1 FROM aos_capacity_publication_private.source_pending p
   WHERE (p.org_id,p.project_id,p.maker,p.attempt_key)=(NEW.org_id,NEW.project_id,NEW.maker,NEW.attempt_key)
    AND NOT p.finalized) THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_PENDING_NOT_FINALIZED' USING ERRCODE='23514'; END IF;
 RETURN NULL;
END $body$;
ALTER FUNCTION aos_capacity_publication_private.require_pending_source_finalized() OWNER TO aos_capacity_publication_owner;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.require_pending_source_finalized() FROM PUBLIC;
CREATE CONSTRAINT TRIGGER source_pending_finalized AFTER INSERT OR UPDATE ON aos_capacity_publication_private.source_pending
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION aos_capacity_publication_private.require_pending_source_finalized();

CREATE FUNCTION aos_capacity_publication_private.prepare_original_source(
 p_raw bytea,p_attempt_key text,p_source_asset_id text,p_permit_ref jsonb)
RETURNS TABLE(source_raw bytea,account_id uuid,attempt_id uuid)
LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE
 v_input jsonb;v_packet jsonb;v_facts jsonb;v_source jsonb;v_account jsonb;v_basis jsonb;v_permit jsonb;
 v_origin jsonb;v_attestation jsonb;v_ref jsonb;v_evidence jsonb;v_context jsonb;v_doc jsonb;
 v_key bigint;v_account_id uuid;v_attempt_id uuid;v_now timestamptz;v_now_text text;v_raw bytea;
 v_pending_account_id uuid;v_pending_account_count bigint;
 v_account_row aos_capacity_publication_private.global_account%ROWTYPE;
 v_provider_row aos_capacity_publication_private.global_provider%ROWTYPE;
 v_pending aos_capacity_publication_private.source_pending%ROWTYPE;
BEGIN
 IF p_attempt_key IS NULL OR length(p_attempt_key) NOT BETWEEN 1 AND 200 OR p_source_asset_id IS NULL THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_PREPARE_INPUT_REQUIRED' USING ERRCODE='22023'; END IF;
 PERFORM aos_capacity_publication_private.read_identifier(to_jsonb(p_source_asset_id));
 v_input:=aos_capacity_publication_private.read_source_command_signed_facts(p_raw,p_permit_ref);
 v_packet:=v_input->'packet';v_facts:=v_input->'facts';v_source:=v_facts->'source';
 v_account:=v_facts->'account';v_basis:=v_facts->'basis';
 v_permit:=v_input->'signedDocuments'->'ProviderCapacitySigningPermitRevision';
 v_attestation:=v_input->'signedDocuments'->'SupplierCapacityAttestationRevision';
 -- All identity locks follow the full original and signed-material prefix.
 -- JSON framing prevents key ambiguity; collisions only serialize callers.
 FOR v_key IN SELECT DISTINCT ('x'||substr(encode(sha256(convert_to(
   aos_capacity_publication_private.canonical_signed_json(k.value::json,1),'UTF8')),'hex'),1,16))::bit(64)::bigint
  FROM jsonb_array_elements(jsonb_build_array(
    jsonb_build_array('aos-capacity-global-account/v1',v_account->>'supplierId',v_account->>'supplierAccountFingerprint'),
    jsonb_build_array('aos-capacity-source-attempt/v1','org-org','dev-project',v_packet->>'makerSubject',p_attempt_key),
    jsonb_build_array('aos-capacity-source-request/v1','org-org','dev-project',v_packet->>'makerSubject',v_packet->>'requestHash'))
    ||(SELECT jsonb_agg(jsonb_build_array('aos-capacity-global-provider/v1',r.value->>'assetId'))
      FROM jsonb_array_elements(v_account->'providerRefs') r)) k ORDER BY 1 LOOP
  PERFORM pg_advisory_xact_lock(v_key);
 END LOOP;
 SELECT a.* INTO v_account_row FROM aos_capacity_publication_private.global_account a
  WHERE a.supplier_id=v_account->>'supplierId' AND a.fingerprint=v_account->>'supplierAccountFingerprint' FOR SHARE;
 IF FOUND THEN
  IF (v_account_row.org_id,v_account_row.project_id) IS DISTINCT FROM ('org-org'::text,'dev-project'::text) THEN
   RAISE EXCEPTION 'CAPACITY_SOURCE_GLOBAL_OWNERSHIP_CONFLICT' USING ERRCODE='42501'; END IF;
  v_account_id:=v_account_row.account_id;
 END IF;
 -- Uncommitted preparations in this exact native transaction already own
 -- one physical identity, although global mappings are published only later.
 SELECT count(DISTINCT p.account_id),min(p.account_id::text)::uuid
  INTO v_pending_account_count,v_pending_account_id
  FROM aos_capacity_publication_private.source_pending p
  WHERE p.org_id='org-org' AND p.project_id='dev-project'
   AND p.native_xid=pg_current_xact_id() AND p.native_pid=pg_backend_pid() AND p.native_session=session_user
   AND p.signed_facts->'facts'->'account'->>'supplierId'=v_account->>'supplierId'
   AND p.signed_facts->'facts'->'account'->>'supplierAccountFingerprint'=v_account->>'supplierAccountFingerprint';
 IF v_pending_account_count>1 OR (v_account_id IS NOT NULL AND v_pending_account_id IS NOT NULL
   AND v_account_id<>v_pending_account_id) THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_GLOBAL_OWNERSHIP_CONFLICT' USING ERRCODE='42501'; END IF;
 v_account_id:=coalesce(v_account_id,v_pending_account_id,gen_random_uuid());
 FOR v_ref IN SELECT value FROM jsonb_array_elements(v_account->'providerRefs') ORDER BY value->>'assetId' COLLATE "C" LOOP
  SELECT m.* INTO v_provider_row FROM aos_capacity_publication_private.global_provider m
   WHERE m.provider_id=v_ref->>'assetId' FOR SHARE;
  IF FOUND AND ((v_provider_row.org_id,v_provider_row.project_id) IS DISTINCT FROM ('org-org'::text,'dev-project'::text)
   OR v_provider_row.account_id IS DISTINCT FROM v_account_id) THEN
   RAISE EXCEPTION 'CAPACITY_SOURCE_GLOBAL_OWNERSHIP_CONFLICT' USING ERRCODE='42501'; END IF;
 END LOOP;
 SELECT p.* INTO v_pending FROM aos_capacity_publication_private.source_pending p
  WHERE p.org_id='org-org' AND p.project_id='dev-project' AND p.maker=v_packet->>'makerSubject'
   AND (p.attempt_key=p_attempt_key OR p.request_hash=v_packet->>'requestHash') FOR UPDATE;
 -- Identity/row waits may cross a deadline. Recheck already-held originals
 -- after every possible wait, including a same-transaction pending replay.
 v_input:=aos_capacity_publication_private.read_source_command_signed_facts(p_raw,p_permit_ref);
 IF v_pending.attempt_id IS NOT NULL THEN
  IF v_pending.attempt_key<>p_attempt_key OR v_pending.request_hash<>v_packet->>'requestHash' OR v_pending.source_asset_id<>p_source_asset_id
   OR v_pending.command_raw<>p_raw OR v_pending.permit_ref<>p_permit_ref
   OR v_pending.native_xid<>pg_current_xact_id() OR v_pending.native_pid<>pg_backend_pid()
   OR v_pending.native_session<>session_user OR v_pending.finalized THEN
   RAISE EXCEPTION 'CAPACITY_SOURCE_PENDING_BINDING_CONFLICT' USING ERRCODE='42501'; END IF;
  RETURN QUERY SELECT v_pending.source_raw,v_pending.account_id,v_pending.attempt_id;RETURN;
 END IF;
 SELECT aos_capacity_publication_private.read_origin_bootstrap(o.raw_body) INTO STRICT v_origin
  FROM aos_capacity_publication_private.origin o WHERE o.org_id='org-org' AND o.project_id='dev-project'
   AND o.content_hash=v_input->'origin'->>'originHash';
 SELECT jsonb_agg(e.ref ORDER BY e.ref->>'assetType' COLLATE "C",e.ref->>'assetId' COLLATE "C") INTO v_evidence
  FROM (SELECT DISTINCT value AS ref FROM jsonb_array_elements(jsonb_build_array(
   v_facts->'application'->'basisEvidenceRef',v_account->'evidenceRef',v_basis->'evidenceRef'))) e;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(v_evidence) e GROUP BY e.value->>'assetType',e.value->>'assetId' HAVING count(*)>1) THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_EVIDENCE_REF_CONFLICT' USING ERRCODE='42501'; END IF;
 v_now:=clock_timestamp();
 IF v_now>=(SELECT instant FROM aos_capacity_publication_private.original_source_time(v_source->'validUntil'))
  OR v_now<(SELECT instant FROM aos_capacity_publication_private.original_source_time(v_source->'validFrom'))
  OR v_now>=aos_capacity_publication_private.read_signed_time(v_packet->'authentication'->'authenticationExpiresAt') THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_PREPARE_EXPIRED' USING ERRCODE='42501'; END IF;
 IF aos_capacity_publication_private.read_signed_time(v_attestation->'observedAt')>v_now THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_OBSERVATION_NOT_CURRENT' USING ERRCODE='42501'; END IF;
 v_now_text:=to_char(v_now AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS')||
  CASE WHEN to_char(v_now AT TIME ZONE 'UTC','US')='000000' THEN '' ELSE '.'||to_char(v_now AT TIME ZONE 'UTC','US') END||'Z';
 v_attempt_id:=gen_random_uuid();
 v_context:=(v_packet->'authentication')||jsonb_build_object('issuerRole',session_user,
   'transactionId',pg_current_xact_id()::text,'backendPid',pg_backend_pid(),'attemptId',v_attempt_id::text);
 v_doc:=jsonb_build_object('schemaVersion',2,'tenant',v_source->'tenant','assetId',p_source_asset_id,'revision',1,
  'publisher',v_permit->'signerPublisher','keyId',v_permit->'signerKeyId','purpose','provider_capacity_published_source',
  'validFrom',v_source->'validFrom','validUntil',v_source->'validUntil','deploymentTarget',v_permit->'deploymentTarget',
  'physicalAccountId',v_account_id::text,'supplierId',v_account->'supplierId','supplierAccountFingerprint',v_account->'supplierAccountFingerprint',
  'providerRefs',v_account->'providerRefs','evidenceRefs',v_evidence,
  'sourceProposalRef',v_packet->'command'->'approvedProposal','sourceApprovalRef',v_packet->'command'->'approvalEvent',
  'allocationRequestRef',v_source->'allocationRequestRef','allocationApprovalRef',v_source->'allocationApprovalRef',
  'accountCandidateRef',v_source->'physicalAccountRef','basisCandidateRef',v_source->'basisRef',
  'sourcePolicyRef',v_packet->'command'->'sourcePolicyRef','supplierAttestationRef',v_packet->'command'->'supplierAttestationRef',
  'signingPermitRef',p_permit_ref,'originRef',jsonb_build_object('assetType','ProviderCapacityOriginBootstrapRevision',
   'assetId',v_origin->'assetId','revision',v_origin->'revision','contentHash',v_input->'origin'->'originHash'),
  'originEpoch',v_input->'origin'->'epoch','sourceWithdrawalEpoch',v_facts->'withdrawalEpochs'->(v_facts->>'sourceProposal'),
  'allocationWithdrawalEpoch',v_facts->'withdrawalEpochs'->(v_facts->>'allocationProposal'),
  'requestHash',v_packet->'requestHash','maxConcurrency',v_basis->'maxConcurrency','tokenLimit',v_basis->'tokenLimit',
  'observedAt',v_attestation->'observedAt','issuedAt',v_now_text,'executionAllowed',false,'issuanceContext',v_context);
 PERFORM aos_capacity_publication_private.read_identifier(v_doc->'supplierId');
 FOR v_ref IN SELECT value FROM jsonb_array_elements(
  v_doc->'providerRefs'||v_doc->'evidenceRefs'||jsonb_build_array(
   v_doc->'sourceProposalRef',v_doc->'sourceApprovalRef',v_doc->'allocationRequestRef',v_doc->'allocationApprovalRef',
   v_doc->'accountCandidateRef',v_doc->'basisCandidateRef',v_doc->'sourcePolicyRef',v_doc->'supplierAttestationRef',
   v_doc->'signingPermitRef',v_doc->'originRef')) LOOP
  PERFORM aos_capacity_publication_private.read_identifier(v_ref->'assetId');
 END LOOP;
 v_raw:=convert_to(aos_capacity_publication_private.canonical_signed_json(v_doc::json,1),'UTF8');
 INSERT INTO aos_capacity_publication_private.source_pending(org_id,project_id,maker,attempt_key,attempt_id,source_asset_id,
  account_id,request_hash,native_xid,native_pid,native_session,command_raw,permit_ref,signed_facts,source_raw,source_hash)
 VALUES('org-org','dev-project',v_packet->>'makerSubject',p_attempt_key,v_attempt_id,p_source_asset_id,v_account_id,
  v_packet->>'requestHash',pg_current_xact_id(),pg_backend_pid(),session_user,p_raw,p_permit_ref,v_input,v_raw,encode(sha256(v_raw),'hex'));
 RETURN QUERY SELECT v_raw,v_account_id,v_attempt_id;
END $body$;
ALTER FUNCTION aos_capacity_publication_private.prepare_original_source(bytea,text,text,jsonb) OWNER TO aos_capacity_publication_owner;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.prepare_original_source(bytea,text,text,jsonb) FROM PUBLIC;
"""


CAPACITY_SOURCE_COMMIT_SQL = r"""
CREATE TABLE aos_capacity_publication_private.source_publication(
 org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
 asset_id text NOT NULL,revision integer NOT NULL CHECK(revision=1),
 content_hash text NOT NULL CHECK(content_hash=encode(sha256(source_raw),'hex')),
 source_raw bytea NOT NULL,signature bytea NOT NULL CHECK(octet_length(signature)=64),
 account_id uuid NOT NULL REFERENCES aos_capacity_publication_private.global_account,
 attempt_id uuid NOT NULL UNIQUE REFERENCES aos_capacity_publication_private.source_pending(attempt_id),
 PRIMARY KEY(org_id,project_id,asset_id));
CREATE TABLE aos_capacity_publication_private.source_provenance(
 org_id text NOT NULL,project_id text NOT NULL,asset_id text NOT NULL,
 original_signed_facts jsonb NOT NULL,source_signer_root_revision text NOT NULL,
 native_xid xid8 NOT NULL,native_pid integer NOT NULL,native_session text NOT NULL,
 PRIMARY KEY(org_id,project_id,asset_id),
 FOREIGN KEY(org_id,project_id,asset_id) REFERENCES aos_capacity_publication_private.source_publication);
ALTER TABLE aos_capacity_publication_private.source_publication OWNER TO aos_capacity_publication_owner;
ALTER TABLE aos_capacity_publication_private.source_provenance OWNER TO aos_capacity_publication_owner;
REVOKE ALL ON aos_capacity_publication_private.source_publication,aos_capacity_publication_private.source_provenance
 FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer,aos_provider_capacity_policy_publisher;
ALTER TABLE aos_capacity_publication_private.source_publication ENABLE ROW LEVEL SECURITY;
ALTER TABLE aos_capacity_publication_private.source_publication FORCE ROW LEVEL SECURITY;
ALTER TABLE aos_capacity_publication_private.source_provenance ENABLE ROW LEVEL SECURITY;
ALTER TABLE aos_capacity_publication_private.source_provenance FORCE ROW LEVEL SECURITY;
CREATE POLICY source_publication_owner ON aos_capacity_publication_private.source_publication TO aos_capacity_publication_owner
 USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
 WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
CREATE POLICY source_provenance_owner ON aos_capacity_publication_private.source_provenance TO aos_capacity_publication_owner
 USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
 WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
CREATE FUNCTION aos_capacity_publication_private.refuse_source_publication_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $body$
BEGIN RAISE EXCEPTION 'CAPACITY_SOURCE_PUBLICATION_IMMUTABLE' USING ERRCODE='42501'; END $body$;
ALTER FUNCTION aos_capacity_publication_private.refuse_source_publication_mutation() OWNER TO aos_capacity_publication_owner;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.refuse_source_publication_mutation() FROM PUBLIC;
CREATE TRIGGER source_identity_immutable BEFORE UPDATE OR DELETE ON aos_capacity_publication_private.global_account
 FOR EACH ROW EXECUTE FUNCTION aos_capacity_publication_private.refuse_source_publication_mutation();
CREATE TRIGGER source_identity_immutable BEFORE UPDATE OR DELETE ON aos_capacity_publication_private.global_provider
 FOR EACH ROW EXECUTE FUNCTION aos_capacity_publication_private.refuse_source_publication_mutation();
CREATE TRIGGER source_publication_immutable BEFORE UPDATE OR DELETE ON aos_capacity_publication_private.source_publication
 FOR EACH ROW EXECUTE FUNCTION aos_capacity_publication_private.refuse_source_publication_mutation();
CREATE TRIGGER source_provenance_immutable BEFORE UPDATE OR DELETE ON aos_capacity_publication_private.source_provenance
 FOR EACH ROW EXECUTE FUNCTION aos_capacity_publication_private.refuse_source_publication_mutation();

CREATE FUNCTION aos_capacity_publication_private.commit_original_source(p_key text,p_raw bytea,p_signature bytea)
RETURNS TABLE(asset_id text,revision integer,content_hash text,source_raw bytea,signature bytea)
LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $body$
DECLARE
 v_pending aos_capacity_publication_private.source_pending%ROWTYPE;
 v_existing aos_capacity_publication_private.source_publication%ROWTYPE;
 v_account aos_capacity_publication_private.global_account%ROWTYPE;
 v_provider aos_capacity_publication_private.global_provider%ROWTYPE;
 v_input jsonb;v_candidate jsonb;v_ref jsonb;
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
 IF p_key IS NULL OR p_raw IS NULL OR p_signature IS NULL OR octet_length(p_signature)<>64 THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMIT_BINDING_CONFLICT' USING ERRCODE='42501'; END IF;
 -- Do not acquire pending before the original lock prefix in a fresh caller.
 -- An unfinished row is usable only by its already-lock-holding native caller.
 SELECT p.* INTO v_pending FROM aos_capacity_publication_private.source_pending p
  WHERE p.org_id='org-org' AND p.project_id='dev-project' AND p.attempt_key=p_key AND p.source_raw=p_raw;
 IF NOT FOUND OR v_pending.source_hash<>encode(sha256(p_raw),'hex') THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMIT_BINDING_CONFLICT' USING ERRCODE='42501'; END IF;
 IF v_pending.finalized THEN
  SELECT s.* INTO v_existing FROM aos_capacity_publication_private.source_publication s
   WHERE s.org_id='org-org' AND s.project_id='dev-project' AND s.attempt_id=v_pending.attempt_id;
  IF NOT FOUND OR v_existing.source_raw<>p_raw OR v_existing.signature<>p_signature THEN
   RAISE EXCEPTION 'CAPACITY_SOURCE_COMMIT_BINDING_CONFLICT' USING ERRCODE='42501'; END IF;
  RETURN QUERY SELECT v_existing.asset_id,v_existing.revision,v_existing.content_hash,v_existing.source_raw,v_existing.signature;
  RETURN;
 END IF;
 IF v_pending.native_xid<>pg_current_xact_id() OR v_pending.native_pid<>pg_backend_pid()
  OR v_pending.native_session<>session_user THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMIT_BINDING_CONFLICT' USING ERRCODE='42501'; END IF;
 v_input:=aos_capacity_publication_private.read_source_command_signed_facts(v_pending.command_raw,v_pending.permit_ref);
 IF v_input IS DISTINCT FROM v_pending.signed_facts THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMIT_ORIGINALS_DRIFTED' USING ERRCODE='42501'; END IF;
 SELECT p.* INTO STRICT v_pending FROM aos_capacity_publication_private.source_pending p
  WHERE p.attempt_id=v_pending.attempt_id FOR UPDATE;
 -- The original registered-material query audits the exact native C verifier
 -- and derives the current trusted Source key from the separate signing root.
 IF aos_ed25519.verify(p_signature,p_raw,decode(v_input->>'sourceSignerPublicKey','base64')) IS DISTINCT FROM true THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMIT_SIGNATURE_INVALID' USING ERRCODE='42501'; END IF;
 v_candidate:=v_input->'facts'->'account';
 INSERT INTO aos_capacity_publication_private.global_account(account_id,supplier_id,fingerprint,org_id,project_id)
 VALUES(v_pending.account_id,v_candidate->>'supplierId',v_candidate->>'supplierAccountFingerprint','org-org','dev-project')
 ON CONFLICT DO NOTHING;
 SELECT a.* INTO STRICT v_account FROM aos_capacity_publication_private.global_account a
  WHERE a.supplier_id=v_candidate->>'supplierId' AND a.fingerprint=v_candidate->>'supplierAccountFingerprint' FOR SHARE;
 IF v_account.account_id<>v_pending.account_id OR (v_account.org_id,v_account.project_id) IS DISTINCT FROM ('org-org'::text,'dev-project'::text) THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_GLOBAL_OWNERSHIP_CONFLICT' USING ERRCODE='42501'; END IF;
 FOR v_ref IN SELECT value FROM jsonb_array_elements(v_candidate->'providerRefs') ORDER BY value->>'assetId' COLLATE "C" LOOP
  INSERT INTO aos_capacity_publication_private.global_provider(provider_id,account_id,org_id,project_id)
   VALUES(v_ref->>'assetId',v_pending.account_id,'org-org','dev-project') ON CONFLICT DO NOTHING;
  SELECT m.* INTO STRICT v_provider FROM aos_capacity_publication_private.global_provider m
   WHERE m.provider_id=v_ref->>'assetId' FOR SHARE;
  IF v_provider.account_id<>v_pending.account_id OR (v_provider.org_id,v_provider.project_id) IS DISTINCT FROM ('org-org'::text,'dev-project'::text) THEN
   RAISE EXCEPTION 'CAPACITY_SOURCE_GLOBAL_OWNERSHIP_CONFLICT' USING ERRCODE='42501'; END IF;
 END LOOP;
 -- Mapping checks can wait. Recheck all current deadlines before publishing.
 v_input:=aos_capacity_publication_private.read_source_command_signed_facts(v_pending.command_raw,v_pending.permit_ref);
 IF v_input IS DISTINCT FROM v_pending.signed_facts THEN
  RAISE EXCEPTION 'CAPACITY_SOURCE_COMMIT_ORIGINALS_DRIFTED' USING ERRCODE='42501'; END IF;
 INSERT INTO aos_capacity_publication_private.source_publication(org_id,project_id,asset_id,revision,content_hash,source_raw,signature,account_id,attempt_id)
 VALUES('org-org','dev-project',v_pending.source_asset_id,1,v_pending.source_hash,p_raw,p_signature,v_pending.account_id,v_pending.attempt_id)
 RETURNING * INTO v_existing;
 INSERT INTO aos_capacity_publication_private.source_provenance(org_id,project_id,asset_id,original_signed_facts,source_signer_root_revision,native_xid,native_pid,native_session)
 VALUES('org-org','dev-project',v_pending.source_asset_id,v_input,v_input->>'sourceSignerRootRevision',pg_current_xact_id(),pg_backend_pid(),session_user);
 UPDATE aos_capacity_publication_private.source_pending p SET finalized=true WHERE p.attempt_id=v_pending.attempt_id;
 RETURN QUERY SELECT v_existing.asset_id,v_existing.revision,v_existing.content_hash,v_existing.source_raw,v_existing.signature;
END $body$;
ALTER FUNCTION aos_capacity_publication_private.commit_original_source(text,bytea,bytea) OWNER TO aos_capacity_publication_owner;
REVOKE ALL ON FUNCTION aos_capacity_publication_private.commit_original_source(text,bytea,bytea) FROM PUBLIC;
"""


def _source_transaction_statements():
    from aos_api import aip_provider_capacity_publication_store as store
    profiles = (
        'CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL', 'CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL',
        'CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL', 'CAPACITY_ORIGINAL_PROVIDER_PROFILE_SQL',
        'CAPACITY_ORIGINAL_BUILD_PROFILE_SQL', 'CAPACITY_ORIGINAL_BUILD_JSON_SQL',
        'CAPACITY_ORIGINAL_EVIDENCE_PROFILE_SQL', 'CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL',
    )
    return (*(getattr(store, name) for name in profiles), CAPACITY_ORIGINAL_SOURCE_FACTS_SQL,
            CAPACITY_ORIGINAL_SOURCE_COMMAND_SQL, CAPACITY_ORIGINAL_SOURCE_SIGNED_FACTS_SQL,
            CAPACITY_SOURCE_PENDING_SQL, CAPACITY_SOURCE_COMMIT_SQL)


def install_source_transaction_boundary(execute):
    """Install the private composition in the caller's migration transaction.

    Requires the original a155/a156 boundaries. No public entry or issuer grant;
    errors must propagate so the caller rolls back the entire installation.
    """
    for statement in _source_transaction_statements():
        execute(statement)


def source_transaction_function_manifest():
    """Compile exact function contracts from trusted SQL, never target catalogs.

    This deliberately accepts only the restricted grammar used by these fixed
    definitions; a new unsupported definition must fail rather than be skipped.
    Table, constraint, policy and trigger contracts require a separate audit.
    """
    return _trusted_function_manifest(_source_transaction_statements())


def _trusted_function_manifest(statements):
    """Parse every function in fixed installer SQL, failing on unsupported DDL."""
    pattern = re.compile(
        r'CREATE FUNCTION\s+(aos_capacity_publication_private\.\w+|public\.(?:prepare_capacity_source|commit_capacity_source))\s*\((.*?)\)\s*'
        r'(.*?)\bAS\s+(\$\w*\$)(.*?)\4', re.S | re.I)
    manifest = []
    for statement in statements:
        matches = list(pattern.finditer(statement))
        if len(matches) != len(re.findall(r'\bCREATE FUNCTION\b', statement, re.I)):
            raise ValueError('CAPACITY_SOURCE_FUNCTION_CONTRACT_UNSUPPORTED')
        for match in matches:
            name, arguments, header, _, body = match.groups()
            inputs = [item.strip().split(None, 1) for item in arguments.split(',') if item.strip()]
            returned = re.search(r'RETURNS\s+(.*?)\s+LANGUAGE\s+plpgsql\b', header, re.S | re.I)
            if not returned or any(len(item) != 2 for item in inputs):
                raise ValueError('CAPACITY_SOURCE_FUNCTION_CONTRACT_UNSUPPORTED')
            result = returned.group(1).strip()
            table = re.fullmatch(r'TABLE\s*\((.*?)\)', result, re.S | re.I)
            outputs = [item.strip().split(None, 1) for item in table.group(1).split(',')] if table else []
            settings = re.findall(r'\bSET\s+("[^"]+"|[\w.]+)\s*=\s*(\x27[^\x27]*\x27|[\w.]+)', header, re.I)
            manifest.append(dict(
                signature=name+'('+','.join(item[1] for item in inputs)+')',
                names=[item[0] for item in inputs+outputs],
                input_types=[item[1] for item in inputs],
                all_types=[item[1] for item in inputs+outputs] if outputs else None,
                modes=['i']*len(inputs)+['t']*len(outputs) if outputs else None,
                return_type='record' if table else result, returns_set=bool(table),
                body_sha256=hashlib.sha256(body.encode()).hexdigest(),
                strict=bool(re.search(r'\bSTRICT\b', header, re.I)),
                volatility='i' if re.search(r'\bIMMUTABLE\b', header, re.I) else
                           's' if re.search(r'\bSTABLE\b', header, re.I) else 'v',
                security_definer=bool(re.search(r'\bSECURITY DEFINER\b', header, re.I)),
                config=[key.strip('"')+'='+value.strip("'") for key, value in settings] or None,
            ))
    if len({item['signature'] for item in manifest}) != len(manifest):
        raise ValueError('CAPACITY_SOURCE_FUNCTION_CONTRACT_DUPLICATED')
    return tuple(manifest)



def original_registry_function_manifest():
    """Compile the original 152-154 functions; never execute installer SQL."""
    return _trusted_function_manifest(_original_registry_statements())


def _original_registry_statements():
    """Capture fixed original installers, without executing their statements."""
    from aos_api.aip_provider_capacity_publication_registry import (
        install_registry_schema, install_origin_registration,
    )
    from aos_api.aip_provider_capacity_document_registry import install_document_registry
    from aos_api.aip_provider_capacity_withdrawal_registry import install_withdrawal_registry
    statements = []
    for install in (install_registry_schema, install_origin_registration,
                    install_document_registry, install_withdrawal_registry):
        install(statements.append)
    return tuple(statements)

def require_source_transaction_functions(conn):
    """Audit exact new functions plus original boundaries; not full S01."""
    from aos_api.aip_provider_capacity_publication_lock_boundary import require_publication_lock_boundary
    require_publication_lock_boundary(conn)
    manifest = source_transaction_function_manifest()
    names = sorted({item['signature'].split('(')[0].split('.')[1] for item in manifest})
    count = conn.execute("SELECT count(*) AS n FROM pg_proc WHERE "
        "pronamespace='aos_capacity_publication_private'::regnamespace AND proname=ANY(%s::text[])",
        (names,)).fetchone()['n']
    if count != len(manifest):
        raise CapacityPublicationBoundaryBlocked('CAPACITY_SOURCE_FUNCTION_INSTALLATION_DRIFTED')
    for expected in manifest:
        row = conn.execute("""SELECT p.oid,r.rolname AS owner,l.lanname AS language,
            p.prosrc,p.prosecdef,p.proconfig,p.proisstrict,p.provolatile,p.proparallel,
            p.proargnames,p.proargtypes::oid[] AS inputs,p.proallargtypes,p.proargmodes,
            p.prorettype,p.proretset,p.pronargdefaults,p.prokind,p.provariadic,
            EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
                   WHERE a.grantee<>p.proowner OR a.privilege_type<>'EXECUTE' OR a.is_grantable) AS bad_acl
            FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner
            JOIN pg_language l ON l.oid=p.prolang WHERE p.oid=to_regprocedure(%s)""",
            (expected['signature'],)).fetchone()
        def types(names):
            return [conn.execute('SELECT to_regtype(%s)::oid AS oid', (name,)).fetchone()['oid'] for name in names]
        if (not row or row['owner']!=OWNER or row['language']!='plpgsql'
            or hashlib.sha256(row['prosrc'].encode()).hexdigest()!=expected['body_sha256']
            or row['prosecdef']!=expected['security_definer'] or row['proconfig']!=expected['config']
            or row['proisstrict']!=expected['strict'] or row['provolatile']!=expected['volatility']
            or row['proparallel']!='u' or row['proargnames']!=(expected['names'] or None)
            or row['inputs']!=types(expected['input_types'])
            or row['proallargtypes']!=(types(expected['all_types']) if expected['all_types'] else None)
            or row['proargmodes']!=expected['modes']
            or row['prorettype']!=types([expected['return_type']])[0]
            or row['proretset']!=expected['returns_set'] or row['pronargdefaults']!=0
            or row['prokind']!='f' or row['provariadic']!=0 or row['bad_acl']):
            raise CapacityPublicationBoundaryBlocked('CAPACITY_SOURCE_FUNCTION_INSTALLATION_DRIFTED')


# Fixed PostgreSQL16 catalog contract reviewed against trusted pending/commit
# DDL. Provenance: full157-table-contract-reviewed.json at AOS-001447. Target
# catalogs never define expectations. Generated RI names/OIDs are excluded;
# constraint identity, related relations, functions, arguments and flags remain.
_SOURCE_TABLE_NAMES = ('global_account','global_provider','source_pending','source_publication','source_provenance')
_SOURCE_TABLE_QUERIES = {
 'columns': """SELECT a.attnum,a.attname,tn.nspname AS type_schema,t.typname AS type_name,
    a.atttypmod,a.attnotnull,a.attidentity,a.attgenerated,a.attisdropped,
    CASE WHEN a.attcollation=0 THEN NULL ELSE cn.nspname||'.'||cl.collname END AS collation,
    pg_get_expr(d.adbin,d.adrelid) AS default_expr FROM pg_attribute a
    JOIN pg_type t ON t.oid=a.atttypid JOIN pg_namespace tn ON tn.oid=t.typnamespace
    LEFT JOIN pg_collation cl ON cl.oid=a.attcollation LEFT JOIN pg_namespace cn ON cn.oid=cl.collnamespace
    LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
    WHERE a.attrelid=%s AND a.attnum>0 ORDER BY a.attnum""",
 'acl': """SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee)::text END AS grantee,
    pg_get_userbyid(a.grantor)::text AS grantor,a.privilege_type,a.is_grantable
    FROM pg_class p,LATERAL aclexplode(coalesce(p.relacl,acldefault('r',p.relowner))) a
    WHERE p.oid=%s ORDER BY grantee,grantor,privilege_type,is_grantable""",
 'column_acl': """SELECT a.attname,CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee)::text END AS grantee,
    pg_get_userbyid(x.grantor)::text AS grantor,x.privilege_type,x.is_grantable
    FROM pg_attribute a,LATERAL aclexplode(a.attacl) x WHERE a.attrelid=%s
    ORDER BY attname,grantee,grantor,privilege_type,is_grantable""",
 'policies': """SELECT polname,polcmd,polpermissive,
    ARRAY(SELECT CASE WHEN r=0 THEN 'PUBLIC' ELSE pg_get_userbyid(r)::text END FROM unnest(polroles) r ORDER BY 1) AS roles,
    pg_get_expr(polqual,polrelid) AS using_expr,pg_get_expr(polwithcheck,polrelid) AS check_expr
    FROM pg_policy WHERE polrelid=%s ORDER BY polname""",
 'constraints': """SELECT conname,contype,condeferrable,condeferred,convalidated,conislocal,coninhcount,connoinherit,
    pg_get_constraintdef(oid,false) AS definition FROM pg_constraint WHERE conrelid=%s ORDER BY conname""",
 'indexes': """SELECT x.relname AS name,n.nspname AS schema,am.amname AS method,
    i.indisunique,i.indisprimary,i.indisvalid,i.indisready,i.indislive,i.indisexclusion,i.indimmediate,
    i.indnullsnotdistinct,i.indisreplident,i.indnkeyatts,i.indnatts,i.indkey::smallint[] AS keys,
    i.indoption::smallint[] AS options,
    ARRAY(SELECT ns.nspname||'.'||op.opcname FROM unnest(i.indclass::oid[]) WITH ORDINALITY z(id,pos)
          JOIN pg_opclass op ON op.oid=z.id JOIN pg_namespace ns ON ns.oid=op.opcnamespace ORDER BY z.pos) AS opclasses,
    ARRAY(SELECT CASE WHEN z.id=0 THEN NULL ELSE ns.nspname||'.'||cl.collname END
          FROM unnest(i.indcollation::oid[]) WITH ORDINALITY z(id,pos)
          LEFT JOIN pg_collation cl ON cl.oid=z.id LEFT JOIN pg_namespace ns ON ns.oid=cl.collnamespace ORDER BY z.pos) AS collations,
    pg_get_expr(i.indexprs,i.indrelid) AS expressions,pg_get_expr(i.indpred,i.indrelid) AS predicate,
    x.reloptions,pg_get_indexdef(i.indexrelid) AS definition
    FROM pg_index i JOIN pg_class x ON x.oid=i.indexrelid JOIN pg_namespace n ON n.oid=x.relnamespace
    JOIN pg_am am ON am.oid=x.relam WHERE i.indrelid=%s ORDER BY name""",
 'triggers': """SELECT CASE WHEN t.tgisinternal THEN NULL ELSE t.tgname END AS name,
    t.tgenabled,t.tgtype,t.tgdeferrable,t.tginitdeferred,t.tgisinternal,
    ns.nspname||'.'||quote_ident(p.proname)||'('||pg_get_function_identity_arguments(p.oid)||')' AS function,
    co.conname AS constraint_name,co.contype AS constraint_type,
    co.conrelid::regclass::text AS constraint_table,co.confrelid::regclass::text AS referenced_table,
    CASE WHEN t.tgconstrrelid=0 THEN NULL ELSE t.tgconstrrelid::regclass::text END AS related_table,
    t.tgnargs,encode(t.tgargs,'hex') AS arguments,t.tgattr::smallint[] AS columns,
    pg_get_expr(t.tgqual,t.tgrelid) AS condition
    FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace ns ON ns.oid=p.pronamespace
    LEFT JOIN pg_constraint co ON co.oid=t.tgconstraint WHERE t.tgrelid=%s
    ORDER BY name NULLS LAST,constraint_name,function,tgtype""",
}
_SOURCE_TABLE_PROPERTIES = """SELECT c.relname,c.relkind,c.relpersistence,c.relrowsecurity,c.relforcerowsecurity,
    c.relreplident,c.relispartition,c.relhassubclass,c.relhasrules,c.reloptions,
    r.rolname AS owner,n.nspname AS schema,
    EXISTS(SELECT 1 FROM pg_inherits WHERE inhrelid=c.oid OR inhparent=c.oid) AS inheritance
    FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE c.oid=%s"""

def _source_transaction_table_catalog(conn):
    result={}
    for name in _SOURCE_TABLE_NAMES:
        oid=conn.execute('SELECT to_regclass(%s)::oid AS oid',('aos_capacity_publication_private.'+name,)).fetchone()['oid']
        if oid is None:
            result[name]=None
            continue
        table=conn.execute(_SOURCE_TABLE_PROPERTIES,(oid,)).fetchone()
        for key,query in _SOURCE_TABLE_QUERIES.items():table[key]=conn.execute(query,(oid,)).fetchall()
        result[name]=table
    return result

_SOURCE_TABLE_HASHES = {'global_account': '0146c1484cbb7b63f75e1c4ad0a19dde78d619772aa737119098dd2788bd9338',
 'global_provider': '9f2a9c6306332498800fd3ab3e0da1ec4cb7e420fa2f0af64725af8e9c0b5241',
 'source_pending': 'b540872f86c0b53e9cc1c811dee486a475fb92a88029b2b001f0641ecc480d61',
 'source_provenance': '4247c46aea460636257f6f9af4cd4a88e684b8cd163e98df4e623da86169c15b',
 'source_publication': '11d0e5aa0cec62d6109cb2b6eb2e4a6b6582d9290611fd085c494db691abcd46'}
_SOURCE_TABLE_SQL_HASHES = ('8bc47c5697dce3f7b99862c205e3753d8c2ff7dc82177a33c6a8793790174524', 'a2f4e5bcecceecfc9aed28fad84b8c9f46c5e7d224409581235a0e96d299bab1')


def require_source_transaction_tables(conn):
    """Require exact five-table contracts and the original function boundaries.

    This is an installation audit component. Public entry enforcement, original
    registry/issuer audit and final COMMIT TTL remain separate full157 gates.
    """
    require_source_transaction_functions(conn)
    if tuple(hashlib.sha256(s.encode()).hexdigest() for s in
             (CAPACITY_SOURCE_PENDING_SQL,CAPACITY_SOURCE_COMMIT_SQL)) != _SOURCE_TABLE_SQL_HASHES:
        raise CapacityPublicationBoundaryBlocked('CAPACITY_SOURCE_TABLE_CONTRACT_REVIEW_REQUIRED')
    for name, actual in _source_transaction_table_catalog(conn).items():
        digest = hashlib.sha256(json.dumps(actual,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if digest != _SOURCE_TABLE_HASHES[name]:
            raise CapacityPublicationBoundaryBlocked('CAPACITY_SOURCE_TABLE_INSTALLATION_DRIFTED')


# Original 152-154 tables reconstructed exclusively from trusted installers
# in a rollback-only schema. See full157-original-registry-table-contract-reviewed.json.
_ORIGINAL_REGISTRY_TABLE_HASHES = {'deployment_anchor': 'af48e08595f03facff2e69dd03f4c5abe899071f8c41629b80a2662cd9edf403', 'root_snapshot': '1f7ec404b3de6aec611b9e31aea28f09dc0e26241722c42340e4eeb0f9543823', 'origin': '1fd040bf9a4344d43bab566ff6d28ae248476848785e3f1beecdd33b36420331', 'root_entry': '3ab5bd4c4624ad9061f65a4aedd54e7f9b6546607d2dc58375fe041bf0142953', 'registry_epoch': '9f78aa91dcfac96ae7a9b425035013328dcc80c48234f1fc0a2402a302be7854', 'document': 'acdba63c46b9b1ff2f4b89ba03d1204ce34b25e493f4e4312c59896e58ae9224', 'origin_withdrawal': 'e1fc33c92208755c4c9a2a60770608de4099418ae587e6bd83d8fe7bb5941fad'}
_ORIGINAL_REGISTRY_STATEMENTS_HASH = '20b8551d18a88f04cbc9b7554cc0c02727134b35327c1750e2f09fd2e34e1144'

def source_private_installation_audit_sql():
    """Compile a private native current-call audit from trusted code contracts.

    This covers private functions, Source tables and original live guards. Public entries must
    additionally enforce original authority/issuer boundaries and integrity of
    this audit itself; this function supplies no public privilege or JWT proof.
    All queries are fixed SQL. No target catalog or caller input is compiled.
    """
    from aos_api.aip_provider_capacity_publication_registry import PUBLISHER

    def literal(value):
        return "'" + value.replace("'", "''") + "'"

    def array(values, kind='text'):
        if values is None:
            return 'NULL::' + kind + '[]'
        return 'ARRAY[' + ','.join(literal(v) for v in values) + ']::' + kind + '[]'

    def types(values):
        if values is None:
            return 'NULL::oid[]'
        return 'ARRAY[' + ','.join(literal(v) + '::regtype::oid' for v in values) + ']::oid[]'

    if tuple(hashlib.sha256(s.encode()).hexdigest() for s in
             (CAPACITY_SOURCE_PENDING_SQL, CAPACITY_SOURCE_COMMIT_SQL)) != _SOURCE_TABLE_SQL_HASHES:
        raise CapacityPublicationBoundaryBlocked('CAPACITY_SOURCE_TABLE_CONTRACT_REVIEW_REQUIRED')
    original_ddl_hash = hashlib.sha256(json.dumps(
        [hashlib.sha256(s.encode()).hexdigest() for s in _original_registry_statements()],
        separators=(',', ':')).encode()).hexdigest()
    if original_ddl_hash != _ORIGINAL_REGISTRY_STATEMENTS_HASH:
        raise CapacityPublicationBoundaryBlocked('CAPACITY_SOURCE_TABLE_CONTRACT_REVIEW_REQUIRED')
    # Original registry functions include the canonicalizer used below; audit
    # their definitions and exact registration privileges before invoking them.
    manifest = [*original_registry_function_manifest(), *source_transaction_function_manifest()]
    if len({item['signature'] for item in manifest}) != len(manifest):
        raise ValueError('CAPACITY_SOURCE_FUNCTION_CONTRACT_DUPLICATED')
    publisher_entries = {
        'aos_capacity_publication_private.register_origin(bytea,bytea,bytea)',
        'aos_capacity_publication_private.register_document(text,bytea,bytea)',
        'aos_capacity_publication_private.withdraw_origin(bytea,bytea)',
    }
    names = sorted({item['signature'].split('(')[0].split('.')[1] for item in manifest})
    fail = "RAISE EXCEPTION 'CAPACITY_SOURCE_CURRENT_INSTALLATION_DRIFTED' USING ERRCODE='42501';"
    body = [f"""DECLARE v_oid oid; v_table jsonb; v_part jsonb;
BEGIN
 IF current_user<>{literal(OWNER)} OR NOT EXISTS(SELECT 1 FROM pg_roles r
    WHERE r.rolname={literal(OWNER)} AND NOT(r.rolcanlogin OR r.rolinherit OR r.rolsuper
      OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
    AND NOT EXISTS(SELECT 1 FROM pg_auth_members a WHERE a.roleid=r.oid OR a.member=r.oid)) THEN
    {fail} END IF;
 IF (SELECT count(*) FROM pg_proc WHERE pronamespace=
     'aos_capacity_publication_private'::regnamespace AND proname=ANY({array(names)}))<>{len(manifest)} THEN
    {fail} END IF;"""]
    for item in manifest:
        allowed = [OWNER, PUBLISHER] if item['signature'] in publisher_entries else [OWNER]
        acl = "aclexplode(coalesce(p.proacl,acldefault('f',p.proowner)))"
        checks = [
            "NOT EXISTS(SELECT 1 FROM " + acl + " a WHERE a.grantee NOT IN ("
                + ','.join(literal(role) + '::regrole::oid' for role in allowed)
                + ") OR a.grantor<>p.proowner OR a.privilege_type<>'EXECUTE' OR a.is_grantable)",
            *["EXISTS(SELECT 1 FROM " + acl + " a WHERE a.grantee="
                + literal(role) + "::regrole::oid AND a.privilege_type='EXECUTE')" for role in allowed],
            'r.rolname=' + literal(OWNER), "l.lanname='plpgsql'",
            "encode(sha256(convert_to(p.prosrc,'UTF8')),'hex')=" + literal(item['body_sha256']),
            'p.prosecdef=' + str(item['security_definer']).lower(),
            'p.proconfig IS NOT DISTINCT FROM ' + array(item['config']),
            'p.proisstrict=' + str(item['strict']).lower(),
            'p.provolatile=' + literal(item['volatility']), "p.proparallel='u'",
            'p.proargnames IS NOT DISTINCT FROM ' + array(item['names'] or None),
            'ARRAY(SELECT unnest(p.proargtypes::oid[]))=' + types(item['input_types']),
            'p.proallargtypes IS NOT DISTINCT FROM ' + types(item['all_types']),
            'p.proargmodes::text[] IS NOT DISTINCT FROM ' + array(item['modes']),
            'p.prorettype=' + literal(item['return_type']) + '::regtype::oid',
            'p.proretset=' + str(item['returns_set']).lower(),
            "p.pronargdefaults=0 AND p.prokind='f' AND p.provariadic=0",
        ]
        body.append('IF NOT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner '
            'JOIN pg_language l ON l.oid=p.prolang WHERE p.oid=to_regprocedure('
            + literal(item['signature']) + ') AND ' + ' AND '.join(checks) + ') THEN ' + fail + ' END IF;')
    # Original extension SQL/control plus the 152 publication Owner grants
    # define this contract. Current catalog observations never define it.
    # Match catalog names directly so revoked schema USAGE is our drift verdict,
    # rather than an unclassified regprocedure lookup permission error.
    body.append(f"""IF NOT EXISTS(
      SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      JOIN pg_language l ON l.oid=p.prolang JOIN pg_roles r ON r.oid=p.proowner
      WHERE n.nspname='aos_ed25519' AND p.proname='verify'
       AND p.proargtypes='17 17 17'::oidvector AND p.prorettype='boolean'::regtype
       AND p.proargnames=ARRAY['signature','message','public_key']::text[]
       AND p.proallargtypes IS NULL AND p.proargmodes IS NULL
       AND p.probin='$libdir/aos_ed25519' AND p.prosrc='aos_ed25519_verify'
       AND l.lanname='c' AND NOT p.prosecdef AND p.provolatile='i' AND p.proisstrict
       AND p.proparallel='s' AND p.proconfig IS NULL AND p.pronargdefaults=0
       AND p.prokind='f' AND p.provariadic=0 AND NOT p.proretset
       AND NOT p.proleakproof AND p.prosupport=0
       AND r.rolname='aos_ed25519_owner' AND n.nspowner=r.oid
       AND NOT(r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb
         OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
       AND NOT EXISTS(SELECT 1 FROM pg_auth_members a WHERE a.roleid=r.oid OR a.member=r.oid)
       AND (SELECT count(*) FROM pg_proc x WHERE x.pronamespace=n.oid AND x.proname='verify')=1
       AND EXISTS(SELECT 1 FROM pg_depend d JOIN pg_extension e ON e.oid=d.refobjid
         WHERE d.classid='pg_proc'::regclass AND d.objid=p.oid
         AND d.refclassid='pg_extension'::regclass AND d.deptype='e'
         AND e.extname='aos_ed25519' AND e.extversion='1.0'
         AND e.extnamespace=n.oid AND NOT e.extrelocatable)
       AND NOT EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
         WHERE a.grantee NOT IN (r.oid,{literal(OWNER)}::regrole::oid)
         OR a.grantor<>r.oid OR a.privilege_type<>'EXECUTE' OR a.is_grantable)
       AND EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
         WHERE a.grantee=r.oid AND a.privilege_type='EXECUTE')
       AND EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
         WHERE a.grantee={literal(OWNER)}::regrole::oid AND a.privilege_type='EXECUTE')
       AND NOT EXISTS(SELECT 1 FROM aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a
         WHERE a.grantor<>r.oid OR a.is_grantable OR NOT(
           (a.grantee=r.oid AND a.privilege_type IN ('USAGE','CREATE'))
           OR (a.grantee={literal(OWNER)}::regrole::oid AND a.privilege_type='USAGE')))
       AND EXISTS(SELECT 1 FROM aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a
         WHERE a.grantee=r.oid AND a.privilege_type='USAGE')
       AND EXISTS(SELECT 1 FROM aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a
         WHERE a.grantee=r.oid AND a.privilege_type='CREATE')
       AND EXISTS(SELECT 1 FROM aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a
         WHERE a.grantee={literal(OWNER)}::regrole::oid AND a.privilege_type='USAGE')
    ) THEN {fail} END IF;""")
    for name, expected_hash in {**_SOURCE_TABLE_HASHES, **_ORIGINAL_REGISTRY_TABLE_HASHES}.items():
        body.append('v_oid:=to_regclass(' + literal('aos_capacity_publication_private.' + name) + '); '
                    'IF v_oid IS NULL THEN ' + fail + ' END IF;')
        if _SOURCE_TABLE_PROPERTIES.count('%s') != 1:
            raise ValueError('CAPACITY_SOURCE_TABLE_QUERY_UNSUPPORTED')
        body.append('SELECT to_jsonb(q) INTO v_table FROM ('
                    + _SOURCE_TABLE_PROPERTIES.replace('%s', 'v_oid') + ') q;')
        for key, query in _SOURCE_TABLE_QUERIES.items():
            if query.count('%s') != 1:
                raise ValueError('CAPACITY_SOURCE_TABLE_QUERY_UNSUPPORTED')
            body.append("SELECT coalesce(jsonb_agg(to_jsonb(q)),'[]'::jsonb) INTO v_part FROM ("
                        + query.replace('%s', 'v_oid') + ') q; '
                        + 'v_table:=v_table||jsonb_build_object(' + literal(key) + ',v_part);')
        body.append("IF encode(sha256(convert_to(aos_capacity_publication_private.canonical_signed_json("
                    "v_table::json,1),'UTF8')),'hex')<>" + literal(expected_hash)
                    + ' THEN ' + fail + ' END IF;')
    # The trusted helper bodies alone do not prove current original ACL/RLS/
    # epoch catalogs. Invoke their existing live audits on every native call.
    body.extend([
        'PERFORM aos_capacity_publication_private.require_original_fact_boundary();',
        'PERFORM aos_capacity_publication_private.require_original_withdrawal_boundary();',
        'PERFORM aos_capacity_publication_private.require_original_evidence_boundary();',
    ])
    body.append('END;')
    return ('CREATE FUNCTION aos_capacity_publication_private.require_current_source_installation() '
        'RETURNS void LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $audit$\n'
        + '\n'.join(body) + '\n$audit$;\n'
        + 'ALTER FUNCTION aos_capacity_publication_private.require_current_source_installation() OWNER TO ' + OWNER + ';\n'
        + 'REVOKE ALL ON FUNCTION aos_capacity_publication_private.require_current_source_installation() FROM PUBLIC;\n')


_PUBLIC_SOURCE_ENTRIES=(('prepare_capacity_source',
    'p_raw bytea,p_attempt_key text,p_source_asset_id text,p_permit_ref jsonb',
    'source_raw bytea,account_id uuid,attempt_id uuid','prepare_original_source',
    'p_raw,p_attempt_key,p_source_asset_id,p_permit_ref','bytea,text,text,jsonb'),
    ('commit_capacity_source','p_key text,p_raw bytea,p_signature bytea',
    'asset_id text,revision integer,content_hash text,source_raw bytea,signature bytea',
    'commit_original_source','p_key,p_raw,p_signature','text,bytea,bytea'))


def _public_source_call_guard_sql():
    """Compile original issuer constraints; no private privileges for issuer."""
    from aos_api.aip_provider_capacity_formal_boundary import GUARD_HASH
    issuer = "'aos_provider_capacity_issuer'::regrole::oid"
    def literal(value):return "'"+value.replace("'","''")+"'"
    table_oids='ARRAY['+','.join(literal('public.'+n)+'::regclass::oid' for n in TABLES)+']::oid[]'
    entries=('public.aos_capacity_evidence_epoch_issuer_lock(text,text,text)',
             'public.aos_capacity_withdrawal_epoch_lock(text,text,text)',
             'public.prepare_capacity_source(bytea,text,text,jsonb)',
             'public.commit_capacity_source(text,bytea,bytea)')
    function_oids='ARRAY['+','.join(literal(n)+'::regprocedure::oid' for n in entries)+']::oid[]'
    lock_predicate=' OR '.join('(c.oid='+literal('public.'+n)+'::regclass AND x.attname='+literal(col)+')' for n,col in LOCKS.items())
    denied="RAISE EXCEPTION 'CAPACITY_SOURCE_ISSUER_BOUNDARY_DRIFTED' USING ERRCODE='42501';"
    checks=[f"""session_user<>'aos_provider_capacity_issuer' OR current_user<>{literal(OWNER)}
     OR current_setting('transaction_isolation')<>'serializable'
     OR current_setting('transaction_read_only')<>'off'
     OR current_setting('session_replication_role')<>'origin' OR current_setting('TimeZone')<>'UTC'
     OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
     OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
     OR NOT EXISTS(SELECT 1 FROM pg_roles r WHERE r.oid={issuer} AND r.rolcanlogin
       AND NOT(r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls))
     OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid={issuer} OR member={issuer})
     OR EXISTS(SELECT 1 FROM pg_class WHERE relowner={issuer})
     OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner={issuer})
     OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspowner={issuer})
     OR EXISTS(SELECT 1 FROM pg_database WHERE datdba={issuer})""",
     f"""(SELECT count(*) FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE a.grantee={issuer})<>{len(TABLES)}
     OR EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE a.grantee={issuer}
       AND (NOT(c.oid=ANY({table_oids})) OR a.privilege_type<>'SELECT' OR a.is_grantable))
     OR (SELECT count(*) FROM pg_class c JOIN pg_attribute x ON x.attrelid=c.oid,
       LATERAL aclexplode(x.attacl) a WHERE a.grantee={issuer})<>{len(LOCKS)}
     OR EXISTS(SELECT 1 FROM pg_class c JOIN pg_attribute x ON x.attrelid=c.oid,
       LATERAL aclexplode(x.attacl) a WHERE a.grantee={issuer}
       AND (NOT({lock_predicate}) OR a.privilege_type<>'UPDATE' OR a.is_grantable))""",
     f"""EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
       WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND c.relkind IN('r','v','m','p','f')
       AND (has_table_privilege({issuer},c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES')
       OR (NOT(c.oid=ANY({table_oids})) AND (has_table_privilege({issuer},c.oid,'SELECT')
       OR has_any_column_privilege({issuer},c.oid,'SELECT,INSERT,UPDATE,REFERENCES')))))
     OR EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
       JOIN pg_attribute x ON x.attrelid=c.oid WHERE n.nspname !~ '^pg_'
       AND n.nspname<>'information_schema' AND c.relkind IN('r','v','m','p','f') AND x.attnum>0 AND NOT x.attisdropped
       AND (has_column_privilege({issuer},c.oid,x.attnum,'INSERT,REFERENCES')
       OR (has_column_privilege({issuer},c.oid,x.attnum,'UPDATE') AND NOT({lock_predicate}))))""",
     f"""EXISTS(SELECT 1 FROM pg_proc p WHERE p.prosecdef AND has_function_privilege({issuer},p.oid,'EXECUTE')
       AND NOT(p.oid=ANY({function_oids})))
     OR EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE a.grantee={issuer}
       AND (NOT(p.oid=ANY({function_oids})) OR a.privilege_type<>'EXECUTE' OR a.is_grantable))
     OR (SELECT count(*) FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE a.grantee={issuer})<>1
     OR EXISTS(SELECT 1 FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE a.grantee={issuer}
       AND (n.nspname<>'public' OR a.privilege_type<>'USAGE' OR a.is_grantable))
     OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname NOT IN('public','information_schema')
       AND has_schema_privilege({issuer},oid,'USAGE'))
     OR EXISTS(SELECT 1 FROM pg_namespace WHERE has_schema_privilege({issuer},oid,'CREATE'))
     OR EXISTS(SELECT 1 FROM pg_database WHERE datname=current_database() AND has_database_privilege({issuer},oid,'CREATE'))""",
    ]
    for name,args,returns,_callee,_values,types in _PUBLIC_SOURCE_ENTRIES:
        fields=[item.strip().split() for item in (args+','+returns).split(',')]
        names='ARRAY['+','.join(literal(item[0]) for item in fields)+']::text[]'
        all_types='ARRAY['+','.join(literal(item[1])+'::regtype::oid' for item in fields)+']::oid[]'
        modes='ARRAY['+','.join(literal('i' if i<len(types.split(',')) else 't') for i in range(len(fields)))+']::"char"[]'
        signature=literal('public.'+name+'('+types+')')+'::regprocedure::oid'
        checks.append(f"""NOT EXISTS(SELECT 1 FROM pg_proc p WHERE p.oid={signature}
          AND p.proowner={literal(OWNER)}::regrole AND p.prolang=(SELECT oid FROM pg_language WHERE lanname='plpgsql')
          AND p.prosecdef AND NOT p.proisstrict AND p.provolatile='v' AND p.proparallel='u'
          AND p.proconfig=ARRAY['search_path=pg_catalog']::text[] AND p.proretset AND p.prorettype='record'::regtype
          AND p.pronargs={len(types.split(','))} AND p.proallargtypes={all_types}
          AND p.proargnames={names} AND p.proargmodes={modes}
          AND p.pronargdefaults=0 AND p.provariadic=0 AND p.prokind='f' AND NOT p.proleakproof AND p.prosupport=0
          AND (SELECT count(*) FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))))=2
          AND EXISTS(SELECT 1 FROM aclexplode(p.proacl) a WHERE a.grantee={issuer})
          AND EXISTS(SELECT 1 FROM aclexplode(p.proacl) a WHERE a.grantee=p.proowner)
          AND NOT EXISTS(SELECT 1 FROM aclexplode(p.proacl) a
            WHERE a.grantee NOT IN(p.proowner,{issuer}) OR a.grantor<>p.proowner
            OR a.privilege_type<>'EXECUTE' OR a.is_grantable))""")
    for table in (*SCOPED,'aip_action_proposal','aip_action_draft','aip_action_approval_event'):
        name='capacity_issuer_scope_a0v150' if table in SCOPED else ('capacity_issuer_proposal_a0v150' if table=='aip_action_proposal' else 'capacity_issuer_related_a0v150')
        oid=literal('public.'+table)+'::regclass'
        checks.append(f"NOT EXISTS(SELECT 1 FROM pg_class WHERE oid={oid} AND relrowsecurity AND relforcerowsecurity) OR (SELECT count(*) FROM pg_policy WHERE polrelid={oid} AND {issuer}=ANY(polroles))<>2")
        expression=literal(_normalized(_policy_expression(table)).replace('FROM aip_action_proposal p','FROM public.aip_action_proposal p'))
        for policy,permissive in ((name,'true'),(name.replace('_a0v150','_restrict_a0v150'),'false')):
            checks.append(f"""NOT EXISTS(SELECT 1 FROM pg_policy WHERE polrelid={oid} AND polname={literal(policy)}
             AND polcmd='*' AND polpermissive={permissive} AND polroles=ARRAY[{issuer}]::oid[]
             AND btrim(regexp_replace(pg_get_expr(polqual,polrelid),'\\s+',' ','g'))={expression}
             AND btrim(regexp_replace(pg_get_expr(polwithcheck,polrelid),'\\s+',' ','g'))={expression})""")
    checks.append(f"""NOT EXISTS(SELECT 1 FROM pg_proc p WHERE p.oid='public.capacity_issuer_read_lock_only_a0v150()'::regprocedure
      AND NOT p.prosecdef AND p.proconfig=ARRAY['search_path=pg_catalog']::text[]
      AND p.proowner=(SELECT datdba FROM pg_database WHERE datname=current_database())
      AND encode(sha256(convert_to(p.prosrc,'UTF8')),'hex')={literal(GUARD_HASH)}
      AND NOT EXISTS(SELECT 1 FROM aclexplode(p.proacl) a WHERE a.grantee<>p.proowner))
      OR (SELECT count(*) FROM pg_trigger WHERE tgname='capacity_issuer_read_lock_only_a0v150')<>{len(LOCKS)}
      OR EXISTS(SELECT 1 FROM pg_trigger t WHERE t.tgname='capacity_issuer_read_lock_only_a0v150'
        AND (NOT(t.tgrelid=ANY(ARRAY[{','.join(literal('public.'+n)+'::regclass::oid' for n in LOCKS)}]::oid[]))
        OR t.tgfoid<>'public.capacity_issuer_read_lock_only_a0v150()'::regprocedure OR t.tgenabled<>'O'
        OR t.tgtype<>31 OR t.tgqual IS NOT NULL OR octet_length(t.tgargs)<>0 OR t.tgnargs<>0
        OR cardinality(t.tgattr::smallint[])<>0))""")
    audit=source_private_installation_audit_sql()
    body=re.search(r'AS \$audit\$(.*?)\$audit\$;',audit,re.S)[1]
    checks.append(f"""NOT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='aos_capacity_publication_private' AND p.proname='require_current_source_installation'
      AND p.pronargs=0 AND p.prorettype='void'::regtype AND p.proowner={literal(OWNER)}::regrole
      AND p.prolang=(SELECT oid FROM pg_language WHERE lanname='plpgsql')
      AND NOT p.prosecdef AND NOT p.proisstrict AND p.provolatile='v' AND p.proparallel='u'
      AND p.proconfig=ARRAY['search_path=pg_catalog']::text[] AND NOT p.proretset
      AND p.pronargdefaults=0 AND p.provariadic=0 AND p.prokind='f'
      AND encode(sha256(convert_to(p.prosrc,'UTF8')),'hex')={literal(hashlib.sha256(body.encode()).hexdigest())}
      AND NOT EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
        WHERE a.grantee<>p.proowner OR a.privilege_type<>'EXECUTE' OR a.is_grantable))""")
    return '\n'.join('IF '+check+' THEN '+denied+' END IF;' for check in checks)


def source_public_entry_statements():
    """Exact approved interfaces, not automatically installed or authorized."""
    guard=_public_source_call_guard_sql()
    result=[source_private_installation_audit_sql()]
    for name,args,returns,callee,values,types in _PUBLIC_SOURCE_ENTRIES:
        result.extend([f"""CREATE FUNCTION public.{name}({args}) RETURNS TABLE({returns})
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $entry$
          BEGIN {guard}
          PERFORM aos_capacity_publication_private.require_current_source_installation();
          RETURN QUERY SELECT * FROM aos_capacity_publication_private.{callee}({values}); END $entry$;""",
          f'ALTER FUNCTION public.{name}({types}) OWNER TO {OWNER}',
          f'REVOKE ALL ON FUNCTION public.{name}({types}) FROM PUBLIC',
          f'GRANT EXECUTE ON FUNCTION public.{name}({types}) TO aos_provider_capacity_issuer'])
    return tuple(result)


def source_public_entry_manifest():
    return _trusted_function_manifest(source_public_entry_statements()[1:])


def require_source_public_entry_definitions(conn):
    """Allow only both exact definitions; absent installation keeps legacy gates."""
    manifest=source_public_entry_manifest()
    rows=conn.execute("SELECT p.*,p.prosupport::oid AS support_oid,r.rolname,l.lanname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner JOIN pg_language l ON l.oid=p.prolang WHERE n.nspname='public' AND p.proname=ANY(%s)",([m['signature'].split('(')[0].split('.')[1] for m in manifest],)).fetchall()
    if not rows:return ()
    if len(rows)!=2:raise CapacityPublicationBoundaryBlocked('CAPACITY_SOURCE_PUBLIC_INSTALLATION_DRIFTED')
    oids=[]
    for m in manifest:
        row=next((r for r in rows if r['proname']==m['signature'].split('(')[0].split('.')[1]),None)
        expected_types=conn.execute('SELECT ARRAY(SELECT value::regtype::oid FROM unnest(%s::text[]) value) AS value',(m['all_types'],)).fetchone()['value']
        if (not row or row['rolname']!=OWNER or row['lanname']!='plpgsql' or not row['prosecdef']
            or row['proisstrict'] or row['provolatile']!='v' or row['proparallel']!='u'
            or row['proconfig']!=m['config'] or row['proargnames']!=m['names']
            or row['proallargtypes']!=expected_types or list(row['proargmodes'] or [])!=m['modes']
            or not row['proretset'] or row['prorettype']!=2249 or row['pronargdefaults']!=0
            or row['prokind']!='f' or row['provariadic']!=0 or row['proleakproof'] or row['support_oid']!=0
            or row['pronargs']!=len(m['input_types'])
            or hashlib.sha256(row['prosrc'].encode()).hexdigest()!=m['body_sha256']):
            raise CapacityPublicationBoundaryBlocked('CAPACITY_SOURCE_PUBLIC_INSTALLATION_DRIFTED')
        acl=conn.execute("SELECT a.grantee::regrole::text AS grantee,a.grantor::regrole::text AS grantor,a.privilege_type,a.is_grantable FROM pg_proc p,LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s",(row['oid'],)).fetchall()
        if ({a['grantee'] for a in acl}!={OWNER,'aos_provider_capacity_issuer'} or len(acl)!=2
            or any(a['grantor']!=OWNER or a['privilege_type']!='EXECUTE' or a['is_grantable'] for a in acl)):
            raise CapacityPublicationBoundaryBlocked('CAPACITY_SOURCE_PUBLIC_INSTALLATION_DRIFTED')
        oids.append(row['oid'])
    return tuple(oids)
