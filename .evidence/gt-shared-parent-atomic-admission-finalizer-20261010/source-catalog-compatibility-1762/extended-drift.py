from pathlib import Path
import json,hashlib,subprocess
import psycopg
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
lab=json.loads((ROOT/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());database='aos_test_08aeabe72b44_ti4_test'
params=dict(host='127.0.0.1',port=lab['port'],dbname=database,user='aos_app',passfile=lab['passfile'])
source=json.loads((ROOT/'.evidence/gt-shared-parent-atomic-admission-finalizer-20261010/source-catalog-cost-1761/candidate-body.json').read_text())
original='aos_capacity_publication_private.require_original_fact_boundary()';candidate='public.test_owned_extended_acl_candidate()'
cases=[('baseline',None,True),
 ('rls_disabled','ALTER TABLE public.meta_membership DISABLE ROW LEVEL SECURITY',False),
 ('rls_not_forced','ALTER TABLE public.meta_membership NO FORCE ROW LEVEL SECURITY',False),
 ('missing_policy','DROP POLICY capacity_publication_fact_a0v155 ON public.meta_membership',False),
 ('policy_using_changed','ALTER POLICY capacity_publication_fact_a0v155 ON public.meta_membership USING (true)',False),
 ('policy_check_changed','ALTER POLICY capacity_publication_fact_a0v155 ON public.meta_membership WITH CHECK (true)',False),
 ('policy_role_changed','ALTER POLICY capacity_publication_fact_a0v155 ON public.meta_membership TO PUBLIC',False),
 ('extra_owner_policy','CREATE POLICY test_owned_extra_policy ON public.meta_membership TO aos_capacity_publication_owner USING (false)',False),
 ('missing_fact_select','REVOKE SELECT ON public.meta_membership FROM aos_capacity_publication_owner',False),
 ('missing_allowed_column','REVOKE UPDATE(subject) ON public.meta_membership FROM aos_capacity_publication_owner',False),
 ('schema_create_grant','GRANT CREATE ON SCHEMA public TO aos_capacity_publication_owner',False),
 ('owner_default_acl','ALTER DEFAULT PRIVILEGES FOR ROLE aos_capacity_publication_owner GRANT SELECT ON TABLES TO aos_runtime',False),
 ('foreign_default_acl_to_owner','ALTER DEFAULT PRIVILEGES FOR ROLE aos_app GRANT SELECT ON TABLES TO aos_capacity_publication_owner',False),
 ('guard_search_path','ALTER FUNCTION public.capacity_publication_owner_read_lock_only_a0v155() SET search_path=public',False),
 ('guard_security_definer','ALTER FUNCTION public.capacity_publication_owner_read_lock_only_a0v155() SECURITY DEFINER',False),
 ('guard_public_execute','GRANT EXECUTE ON FUNCTION public.capacity_publication_owner_read_lock_only_a0v155() TO PUBLIC',False),
 ('guard_owner_changed','ALTER FUNCTION public.capacity_publication_owner_read_lock_only_a0v155() OWNER TO aos_app',False)]
queries=["SELECT relname,relrowsecurity,relforcerowsecurity,relacl::text FROM pg_class WHERE oid='public.meta_membership'::regclass", "SELECT polname,polpermissive,polcmd,polroles::text,pg_get_expr(polqual,polrelid),pg_get_expr(polwithcheck,polrelid) FROM pg_policy WHERE polrelid='public.meta_membership'::regclass ORDER BY polname", "SELECT proowner::text,prosecdef,proconfig,proacl::text,prosrc FROM pg_proc WHERE oid='public.capacity_publication_owner_read_lock_only_a0v155()'::regprocedure", "SELECT defaclrole::text,defaclnamespace::text,defaclobjtype,defaclacl::text FROM pg_default_acl ORDER BY 1,2,3", "SELECT nspacl::text FROM pg_namespace WHERE nspname='public'"]
reports=[]
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 assert c.execute('SELECT to_regprocedure(%s) IS NULL',(candidate,)).fetchone()[0]
 before=[c.execute(q).fetchall() for q in queries]
 original_body=c.execute('SELECT prosrc FROM pg_proc WHERE oid=%s::regprocedure',(original,)).fetchone()[0]
 assert hashlib.sha256(source['prosrc'].encode()).hexdigest()==source['sha256']
 c.execute('CREATE FUNCTION '+candidate+' RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $candidate$'+source['prosrc']+'$candidate$');c.execute('REVOKE ALL ON FUNCTION '+candidate+' FROM PUBLIC')
 def evaluate(function):
  try:
   with c.transaction():c.execute('SELECT '+function)
   return dict(passed=True,sqlstate=None)
  except psycopg.Error as error:return dict(passed=False,sqlstate=error.sqlstate)
 for label,mutation,expected in cases:
  with c.transaction(force_rollback=True):
   if mutation:c.execute(mutation)
   left=evaluate(original);right=evaluate(candidate)
   reports.append(dict(case=label,expected_pass=expected,original=left,candidate=right,equal=left==right))
 assert [c.execute(q).fetchall() for q in queries]==before
 assert c.execute('SELECT prosrc FROM pg_proc WHERE oid=%s::regprocedure',(original,)).fetchone()[0]==original_body;c.rollback()
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY');assert [c.execute(q).fetchall() for q in queries]==before;assert c.execute('SELECT to_regprocedure(%s) IS NULL',(candidate,)).fetchone()[0];c.rollback()
data=dict(authority='AOS-001762',head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),database=database,original_sha256=hashlib.sha256(original_body.encode()).hexdigest(),candidate_sha256=source['sha256'],cases=reports,all_equal=all(r['equal'] for r in reports),all_expected=all(r['original']['passed']==r['expected_pass'] for r in reports),independent_catalog_restoration=True,original_body_unchanged=True,no_trigger_disabled=True,no_global_role_mutation=True,no_source_issue_or_replay=True,no_product_changes=True,formal_database_touched=False,whole_source_timing_recovered=False,execution_allowed=False,goal_complete=False)
with (OUT/'extended-result.json').open('x') as f:json.dump(data,f,indent=2);f.write('\n')
print(json.dumps({'cases':len(reports),'all_equal':data['all_equal'],'all_expected':data['all_expected'],'independent_restoration':True}))
assert data['all_equal'] and data['all_expected']
