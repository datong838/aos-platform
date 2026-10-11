from pathlib import Path
import os,sys,json,hashlib,subprocess,importlib.util
B=Path(__file__).resolve().parent;R=B.parents[2]
J=R/'.evidence/gt-judge-call-authority-20261008';M=R/'.evidence/gt-atomic-model-admission-20261008'
label='gt-expression-types-transient-catalog-20261011-r2';target=B/'fresh-judge-evidence'
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
c=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']],text=True))[0]
assert c['Id']==lab['container_id'] and c['Image']==lab['image'] and c['State']['Running']
assert lab['cluster']=='7694680278363095064' and lab['port']==5441
free=int(subprocess.check_output(['docker','--context',lab['context'],'exec',lab['name'],'df','-P','-B1','/var/lib/postgresql/data'],text=True).splitlines()[-1].split()[3]);assert free>2500000000
old=[M/'legal-model-prefix-application-r4.json',M/'legal-eval-application-result-r4.json',R/'services/aos-api/aos_api/aip_model_eval_execution_reader.py',R/'services/aos-api/aos_api/aip_model_eval_execution_authority.py']
before={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in old}
target.mkdir()
for n in ('legal_model_prefix_for_application_r4.py','legal_eval_application_fixture_r4.py','build_whole_native_plan_1602.py'):
 (target/n).open('xb').write((M/n).read_bytes())
for n in ('legal_model_prefix_for_application_r4.py','legal_eval_application_fixture_r4.py','build_whole_native_plan_1602.py'):
 (B/n).open('xb').write((M/n).read_bytes())
(B/'original_source_plan_fixture_r1.py').open('xb').write((M/'original_source_plan_fixture_r1.py').read_bytes())
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5441/aos_meta',AOS_DOTENV_DISABLED='1',AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5441',AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0',AOS_JUDGE_FIXTURE_EVIDENCE_ROOT=str(target),AOS_JUDGE_NATIVE_EVIDENCE_LABEL=label,AOS_PARENT_LIFECYCLE_EVIDENCE=str(B))
sys.path[:0]=[str(R/'services/aos-api'),str(R/'services/aos-api/tests/extension_runtime'),str(R/'services/aos-api/tests')]
import psycopg
from psycopg.conninfo import conninfo_to_dict
connect=psycopg.connect
observed_oids=set()
plan_tags=set()
unreviewed_tags=set()
typed_records=set()
def capture_oid(diag):
 message=diag.message_primary or ''
 prefix='TEST_FIXED_COLLECTOR_EXPRESSION_TYPES '
 if message.startswith(prefix):
  values=message[len(prefix):].split()
  assert 3<=len(values)<=103 and all(v.isdigit() for v in values)
  typed_records.add(tuple(int(v) for v in values))
 for prefix, target in [('TEST_FIXED_COLLECTOR_PLAN_TAG ',plan_tags),('TEST_FIXED_COLLECTOR_PLAN_EXTRA_UNREVIEWED ',unreviewed_tags)]:
  if message.startswith(prefix):
   value=message[len(prefix):]
   assert value.isdigit()
   target.add(int(value))
 prefix='TEST_FIXED_COLLECTOR_FUNCTION_OID '
 if message.startswith(prefix):
  value=message[len(prefix):]
  assert value.isdigit()
  observed_oids.add(int(value))
def owned_connect(*args,**kwargs):
 assert len(args)<=1
 params=conninfo_to_dict(args[0] if args else kwargs.get('conninfo',''))
 for k in ('host','port','user','dbname'):
  if k in kwargs:params[k]=kwargs[k]
 if params.get('user')=='aos_app':
  assert params.get('host')=='127.0.0.1' and str(params.get('port'))=='5441'
  assert params.get('dbname')=='aos_meta' or params.get('dbname','').startswith('aos_test_')
  kwargs['passfile']=lab['passfile']
 c=connect(*args,**kwargs)
 c.add_notice_handler(capture_oid)
 return c
psycopg.connect=owned_connect
import pytest
s=importlib.util.spec_from_file_location('expected',J/'registered_judge_expected_fixture_1659.py');fixture=importlib.util.module_from_spec(s);s.loader.exec_module(fixture);patch=pytest.MonkeyPatch();fixture.install(patch)
import isolated_evidence_scope_adapter
isolated_evidence_scope_adapter.install(patch,B,R)

os.environ.update(AOS_SOURCE_MODEL_EVIDENCE_LABEL=label,AOS_SOURCE_NEW_JUDGE_NATIVE='1',AOS_NEW_JUDGE_INTENT_NATIVE='1')
sys.path.insert(0,str(B))
import source_newjudge_native_trial_1606 as trial
from catalog_fixture_restore import original_family_restoration_statements
from aos_api import aip_provider_capacity_catalog_audit_profile as catalog_profile
fixed_restore = original_family_restoration_statements()
assert len(fixed_restore) == len(catalog_profile.epoch.legacy_epoch_profile_restoration_statements()) + 1
patch.setattr(catalog_profile.epoch, 'legacy_epoch_profile_restoration_statements', lambda: fixed_restore)
(B/'fixture-restoration-binding.json').open('x').write(json.dumps({'fixed_original_fact_restoration':True,'fixed_statements_sha256':[hashlib.sha256(s.encode()).hexdigest() for s in fixed_restore],'product_generator_unmodified':True,'fresh_attempt':True},indent=2)+'\n')
from aos_api.aip_model_eval_execution_owner import ModelEvalExecutionOwner
original_judge=ModelEvalExecutionOwner.prepare_judge_application
def record_judge(self,*args,**kwargs):
 trial.POLICY=kwargs
 return original_judge(self,*args,**kwargs)
patch.setattr(ModelEvalExecutionOwner,'prepare_judge_application',record_judge)
import tests.aip.test_physical_capacity_occupation_pg as test_module
PlainPath=Path
class EvidencePath(type(Path())):
 def __truediv__(self,other):
  result=super().__truediv__(other)
  if str(result)==str(M):return B
  return result
patch.setattr(test_module,'Path',EvidencePath)
class Recorder:
 def __init__(self):self.databases=[];self.results=[]
 def pytest_collection_modifyitems(self,items):
  for item in items:
   if str(item.path).endswith('test_physical_capacity_occupation_pg.py'):
    patch.setattr(item.module,'Path',EvidencePath)
    from auth_boundary_fixture import install as install_auth_boundaries
    bindings=install_auth_boundaries(patch,B,occupation_module=item.module)
    assert item.obj.__code__.co_filename==str(B/'test_source_model_preparation_original_native_caller-fresh-auth.py')
    (B/'auth-boundary-bindings.json').open('x').write(json.dumps({'module':item.module.__name__,'collected_function_bound':True,'bindings':bindings},indent=2)+'\n')
 def pytest_runtest_call(self,item):
  from aos_api.db import get_dsn
  db=conninfo_to_dict(get_dsn())['dbname'];self.databases.append(db)
  assert db.startswith('aos_test_') and db.endswith('_ti4_test')
  from psycopg import sql
  with connect(host='127.0.0.1',port=5441,user='aos_app',dbname=db,passfile=lab['passfile'],autocommit=True) as admin:
   prior=admin.execute('SELECT setconfig FROM pg_db_role_setting WHERE setdatabase=(SELECT oid FROM pg_database WHERE datname=%s) AND setrole=0',(db,)).fetchone()
   assert not prior or not any(x.startswith('track_functions=') for x in prior[0])
   (B/'profile-config-intent.json').open('x').write(json.dumps({'database':db,'prior_track_functions_override':None,'setting':'pl','global_change':False},indent=2)+'\n')
   admin.execute(sql.SQL("ALTER DATABASE {} SET track_functions='pl'").format(sql.Identifier(db)))
   (B/'profile-config-result.json').open('x').write(json.dumps({'database':db,'configured':True},indent=2)+'\n')
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.results.append({'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome})
rec=Recorder()
files=['services/aos-api/aos_api/aip_shared_parent_atomic_admission.py','services/aos-api/tests/aip/test_shared_parent_atomic_admission_pg.py','services/aos-api/aos_api/aip_physical_capacity_occupation.py','services/aos-api/tests/aip/test_physical_capacity_occupation_pg.py','services/aos-api/aos_api/aip_model_eval_execution_contracts.py','services/aos-api/aos_api/aip_model_eval_execution_owner.py','services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py','services/aos-api/aos_api/aip_physical_capacity_occupation_contracts.py']
files += ['services/aos-api/aos_api/aip_provider_capacity_catalog_audit_profile.py','services/aos-api/tests/aip/test_provider_capacity_catalog_audit_profile_pg.py']
bindings={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in files}
(B/'attempt-r2.json').open('x').write(json.dumps({'cluster':lab['cluster'],'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'file_hashes':bindings,'old_hashes':before,'free_bytes':free,'execution_allowed':False},indent=2))
# Observe only public test-owned call durations; no args, raw packets or secrets.
import time,re
catalog_witnesses={}
original_execute=psycopg.Connection.execute
catalog_sql='''SELECT p.oid,p.oid::regprocedure::text,l.lanname,p.proowner::regrole::text,p.prosecdef,p.proconfig,p.provolatile,p.prorettype,p.proargtypes::text,p.prosrc FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang WHERE n.nspname='public' ORDER BY p.oid'''

def measured_execute(self,query,*args,**kwargs):
 name=re.match(r'SELECT (public\.test_owned_[A-Za-z0-9_]+)\(',query) if isinstance(query,str) else None
 if not name:return original_execute(self,query,*args,**kwargs)
 for row in original_execute(self,catalog_sql).fetchall():
  witness={'oid':row[0],'signature':row[1],'language':row[2],'owner':row[3],'prosecdef':row[4],'proconfig':row[5],'provolatile':row[6],'return_type_oid':row[7],'declared_arg_type_oids':row[8],'source_sha256':hashlib.sha256(row[9].encode()).hexdigest(),'before_function':name.group(1),'caller_pid':self.info.backend_pid}
  catalog_witnesses[row[0]]=witness
 started=time.monotonic();outcome='returned';error=None
 try:return original_execute(self,query,*args,**kwargs)
 except Exception as exc:
  outcome='rejected';error=str(exc).splitlines()[0];raise
 finally:
  record={'function':name.group(1),'elapsed_seconds':round(time.monotonic()-started,6),'outcome':outcome,'error':error,'observed_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
  if outcome=='returned':
   record['nested_functions']=original_execute(self,'SELECT schemaname,funcname,calls,total_time,self_time FROM pg_stat_xact_user_functions ORDER BY self_time DESC,schemaname,funcname').fetchall()
  with (B/'native-call-timings.jsonl').open('a') as out:out.write(json.dumps(record)+'\n')
psycopg.Connection.execute=measured_execute
# Record only exception classes and allowlisted-shaped fixed error codes.
from aos_api import aip_provider_capacity_occupation_source as diagnostic_occupation
from aos_api import aip_provider_capacity_source_issuer as diagnostic_supplier
import functools
for module, attribute in [(diagnostic_occupation,'consume_capacity_source_for_occupation'),
                          (diagnostic_supplier,'check_native_capacity_supplier_inputs')]:
 original_function=getattr(module,attribute)
 def diagnostic_wrapper(original_function,attribute):
  @functools.wraps(original_function)
  def wrapped(*args,**kwargs):
   try:return original_function(*args,**kwargs)
   except Exception as exc:
    chain=[];seen=set();current=exc
    while current is not None and id(current) not in seen:
     seen.add(id(current));message=str(current)
     chain.append({'type':type(current).__name__,'code':message if re.fullmatch(r'[A-Z][A-Z0-9_]{3,120}',message) else None})
     current=current.__cause__ or current.__context__
    with (B/'diagnostic-exceptions.jsonl').open('a') as out:
     out.write(json.dumps({'function':attribute,'chain':chain,'observed_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()})+'\n')
    raise
  return wrapped
 replacement=diagnostic_wrapper(original_function,attribute)
 for loaded in list(sys.modules.values()):
  if loaded is not None and getattr(loaded,'__name__','').startswith(('aos_api.','tests.')):
   for key,value in list(vars(loaded).items()):
    if value is original_function:patch.setattr(loaded,key,replacement)
try:
 code=pytest.main([str(R/'services/aos-api/tests/aip/test_physical_capacity_occupation_pg.py')+'::test_source_model_preparation_original_native_caller','-q','-s','-p','no:cacheprovider'],plugins=[rec])
finally:
 if (B/'profile-config-result.json').exists():
  from psycopg import sql
  config=json.loads((B/'profile-config-result.json').read_text());db=config['database']
  assert rec.databases==[db]
  with connect(host='127.0.0.1',port=5441,user='aos_app',dbname=db,passfile=lab['passfile'],autocommit=True) as admin:
   admin.execute(sql.SQL('ALTER DATABASE {} RESET track_functions').format(sql.Identifier(db)))
   prior=admin.execute('SELECT setconfig FROM pg_db_role_setting WHERE setdatabase=(SELECT oid FROM pg_database WHERE datname=%s) AND setrole=0',(db,)).fetchone()
   assert not prior or not any(x.startswith('track_functions=') for x in prior[0])
  (B/'profile-config-reset.json').open('x').write(json.dumps({'database':db,'restored_no_override':True,'global_change':False},indent=2)+'\n')
after={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in old};assert before==after
(B/'result-r2.json').open('x').write(json.dumps({'pytest_exit':int(code),'databases':rec.databases,'reports':rec.results,'old_files_unchanged':before==after,'file_hashes':bindings,'execution_allowed':False,'full_task_delivered':False},indent=2))
(B/'observed-oids.json').open('x').write(json.dumps(sorted(observed_oids)))
(B/'plan-tags.json').open('x').write(json.dumps(dict(observed=sorted(plan_tags),unreviewed=sorted(unreviewed_tags))))
(B/'typed-records.json').open('x').write(json.dumps(sorted(typed_records)))
(B/'pre-rollback-catalog-witnesses.json').open('x').write(json.dumps([catalog_witnesses[i] for i in sorted(observed_oids) if i in catalog_witnesses],indent=2)+'\n')
raise SystemExit(code)
