from pathlib import Path
import json,time,statistics,hashlib,re,uuid,subprocess,inspect
import psycopg
from psycopg import sql
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
lab=json.loads((ROOT/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
params=dict(host='127.0.0.1',port=lab['port'],user='aos_app',passfile=lab['passfile'])
source='aos_test_7c4f2f6b4aa8_ti4_test';database='aos_test_'+uuid.uuid4().hex[:12]+'_ti4_test'
assert 'force_rollback' in inspect.signature(psycopg.Connection.transaction).parameters
with (OUT/'clone-attempt.json').open('x') as f:json.dump(dict(database=database,source_database=source,cluster=lab['cluster'],head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),unknown_outcome_requires_readonly_reconciliation=True,source_replay=False),f,indent=2)
with psycopg.connect(**params,dbname='aos_meta',autocommit=True) as c:
 assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 assert c.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=%s',(source,)).fetchone()[0]==0
 assert c.execute('SELECT count(*) FROM pg_database WHERE datname=%s',(database,)).fetchone()[0]==0
 c.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(database),sql.Identifier(source)))
with (OUT/'clone-created.json').open('x') as f:json.dump(dict(database=database,created=True,retained=True),f,indent=2)
name='public.test_owned_catalog_acl_candidate()'
original='aos_capacity_publication_private.require_original_fact_boundary()'
cases=[('baseline',None,True)]
for grantee in ['aos_capacity_publication_owner','PUBLIC']:
 for privilege in ['INSERT','UPDATE','REFERENCES','SELECT']:
  cases.append((grantee+'_column_'+privilege,'GRANT '+privilege+'(v) ON public.test_owned_acl_cost_table TO '+grantee,False))
 for privilege in ['INSERT','UPDATE','REFERENCES','SELECT']:
  cases.append((grantee+'_table_'+privilege,'GRANT '+privilege+' ON public.test_owned_acl_cost_table TO '+grantee,False))
cases.extend([('allowed_owner_duplicate','GRANT UPDATE(subject) ON public.meta_membership TO aos_capacity_publication_owner',True),('allowed_public_duplicate','GRANT UPDATE(subject) ON public.meta_membership TO PUBLIC',True),('allowed_column_grant_option','GRANT UPDATE(subject) ON public.meta_membership TO aos_capacity_publication_owner WITH GRANT OPTION',False),('own_table','ALTER TABLE public.test_owned_acl_cost_table OWNER TO aos_capacity_publication_owner',False)])
reports=[];timings=[]
with psycopg.connect(**params,dbname=database) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
 assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 body=c.execute('SELECT prosrc FROM pg_proc WHERE oid=%s::regprocedure',(original,)).fetchone()[0]
 pattern=r"\(has_column_privilege\(owner_oid,c\.oid,a\.attnum,'INSERT,REFERENCES'\)\s+OR has_column_privilege\(owner_oid,c\.oid,a\.attnum,'UPDATE'\)\)"
 candidate,n=re.subn(pattern,"EXISTS(SELECT 1 FROM aclexplode(a.attacl) acl WHERE acl.grantee IN (owner_oid,0::oid) AND acl.privilege_type IN ('INSERT','REFERENCES','UPDATE'))",body);assert n==2
 (OUT/'candidate-body.json').write_text(json.dumps({'prosrc':candidate,'sha256':hashlib.sha256(candidate.encode()).hexdigest()},indent=2)+'\n')
 c.execute('CREATE FUNCTION '+name+' RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $cost$'+candidate+'$cost$')
 c.execute('REVOKE ALL ON FUNCTION '+name+' FROM PUBLIC')
 c.execute('CREATE TABLE public.test_owned_acl_cost_table(v integer)')
 def evaluate(function):
  try:
   with c.transaction():c.execute('SELECT '+function)
   return dict(passed=True,sqlstate=None)
  except psycopg.Error as error:return dict(passed=False,sqlstate=error.sqlstate)
 for label,mutation,expected in cases:
  with c.transaction(force_rollback=True):
   if mutation:c.execute(mutation)
   left=evaluate(original);right=evaluate(name)
   reports.append(dict(case=label,expected_pass=expected,original=left,candidate=right,equal=left==right))
 for variant,function in [('original',original),('candidate',name),('candidate',name),('original',original)]:
  for n in range(12):
   start=time.perf_counter();c.execute('SELECT '+function);timings.append(dict(variant=variant,seconds=time.perf_counter()-start))
 assert c.execute('SELECT prosrc FROM pg_proc WHERE oid=%s::regprocedure',(original,)).fetchone()[0]==body
 c.rollback()
with psycopg.connect(**params,dbname=database) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute("SELECT to_regprocedure(%s) IS NULL AND to_regclass('public.test_owned_acl_cost_table') IS NULL",(name,)).fetchone()[0]
 assert c.execute('SELECT prosrc FROM pg_proc WHERE oid=%s::regprocedure',(original,)).fetchone()[0]==body;c.rollback()
data=dict(authority='AOS-001761',database=database,original_sha256=hashlib.sha256(body.encode()).hexdigest(),candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest(),exact_predicate_replacements=2,cases=reports,all_equal=all(r['equal'] for r in reports),all_expected=all(r['original']['passed']==r['expected_pass'] for r in reports),samples=timings,median_seconds={v:statistics.median(r['seconds'] for r in timings if r['variant']==v) for v in ['original','candidate']},original_unchanged=True,temporary_objects_and_grants_rolled_back=True,global_role_modified=False,source_issued_or_replayed=False,product_modified=False,formal_database_touched=False,whole_source_timing_recovered=False,execution_allowed=False,goal_complete=False)
with (OUT/'full-candidate-result.json').open('x') as f:json.dump(data,f,indent=2);f.write('\n')
print(json.dumps({k:data[k] for k in ['database','all_equal','all_expected','median_seconds']}))
assert data['all_equal'] and data['all_expected']
