import os,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import psycopg,pytest
from psycopg.conninfo import conninfo_to_dict
REPO=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;lab=json.loads((OUT/'lab.json').read_text());PASS=Path(lab['passfile']);assert PASS.stat().st_mode&0o077==0
state=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect',lab['name']],text=True))[0];assert state['Id']==lab['container_id'] and state['State']['Running']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()=='6f4e2e984f345c81240063096091971edcb92458'
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(key,None)
os.environ.update(AOS_DATABASE_URL='postgresql://aos_app@127.0.0.1:5437/aos_meta',AOS_EXTENSION_PG_TEST='1',AOS_EXTENSION_PG_HOST='127.0.0.1',AOS_EXTENSION_PG_PORT='5437',AOS_EXTENSION_PG_USER='aos_app',AOS_EXTENSION_PG_DATABASE='aos_meta',AOS_TEST_RETAIN_DATABASE='1',AOS_TEST_USE_SHARED_DATABASE='0',AOS_DOTENV_DISABLED='1',AOS_SOURCE_MODEL_EVIDENCE_LABEL='source-newjudge-source-whole-r1',AOS_SOURCE_NEW_JUDGE_NATIVE='1',AOS_NEW_JUDGE_INTENT_NATIVE='1',AOS_SOURCE_NEWJUDGE_PROOF='newjudge-source-proof-1607.json',AOS_JUDGE_NATIVE_EVIDENCE_LABEL='source-whole-r1',AOS_MUTATION_BATCH='B')
sys.path.insert(0,str(REPO/'services/aos-api'));sys.path.insert(0,str(REPO/'services/aos-api/tests/extension_runtime'));sys.path.insert(0,str(REPO/'.evidence/gt-atomic-model-admission-20261008'));sys.path.insert(0,str(OUT))
original=psycopg.connect

def owned_connect(*args,**kwargs):
 assert len(args)<=1
 params=conninfo_to_dict(args[0] if args else kwargs.get('conninfo',''))
 for key in ('user','host','port','dbname'):
  if key in kwargs:params[key]=kwargs[key]
 if params.get('user')=='aos_app':
  assert params.get('host')=='127.0.0.1' and str(params.get('port'))=='5437'
  assert params.get('dbname')=='aos_meta' or params.get('dbname','').startswith('aos_test_')
  kwargs['passfile']=str(PASS)
  assert not kwargs.get('options') and not params.get('options')
  kwargs['options']='-c max_parallel_workers_per_gather=0 -c max_parallel_maintenance_workers=0'
 return original(*args,**kwargs)
psycopg.connect=owned_connect
with original(host='127.0.0.1',port=5437,user='aos_app',dbname='aos_meta',passfile=str(PASS)) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 assert c.execute("SELECT count(*) FROM pg_database WHERE datname LIKE 'aos_test_%'").fetchone()[0]>=2
with original(host='127.0.0.1',port=5437,user='aos_app',dbname='template1',passfile=str(PASS)) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute("SELECT extversion FROM pg_extension WHERE extname='aos_ed25519'").fetchone()==('1.0',)
import importlib.util
spec=importlib.util.spec_from_file_location('native_lab_memoryctl',REPO/'scripts/memory/memoryctl.py');mc=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mc;spec.loader.exec_module(mc)
assert mc.load_authority()['project_revision']=='AOS-001644'
task=json.loads((mc.DEFAULT_PATHS.receipts_path/'tasks'/'gt-source-full-suite-root-r6-20261009.json').read_text())
leases=[x for x in mc.load_leases(mc.DEFAULT_PATHS)['leases'] if x['task_id']==task['task_id']]
assert len(leases)==1 and task['owner']==leases[0]['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
assert datetime.fromisoformat(task['lease_expires_at'])>datetime.now(timezone.utc)
with (OUT/'native-normalization-r3-attempt.json').open('x') as h:json.dump({'head':'6f4e2e984f345c81240063096091971edcb92458','authority':'AOS-001644','lab':lab['container_id'],'cluster':lab['cluster'],'helper_sha256':__import__('hashlib').sha256((OUT/'input-bindings-r2.json').read_bytes()).hexdigest(),'product_sha256':__import__('hashlib').sha256((REPO/'services/aos-api/aos_api/aip_physical_capacity_occupation.py').read_bytes()).hexdigest(),'source_consumer_sha256':__import__('hashlib').sha256((REPO/'services/aos-api/aos_api/aip_provider_capacity_occupation_source.py').read_bytes()).hexdigest(),'fresh_original_bootstrap':True,'no_shared_database':True},h)
class Recorder:
 def __init__(self):self.database=None;self.results=[]
 def pytest_collection_finish(self,session):
  self.collected=[x.nodeid for x in session.items];(OUT/'normalization-r3-collection.json').write_text(json.dumps(self.collected,indent=2))
 def pytest_runtest_setup(self,item):
  free=int(subprocess.check_output(['docker','--context','colima-aos-extension','exec',lab['name'],'df','-P','-B1','/var/lib/postgresql/data'],text=True).splitlines()[-1].split()[3]);assert free>2580000000, 'ISOLATED_LAB_DISK_RESERVE_REQUIRED'
 def pytest_runtest_call(self,item):
  from aos_api.db import get_dsn
  self.database=conninfo_to_dict(get_dsn())['dbname'];assert self.database.startswith('aos_test_') and self.database.endswith('_ti4_test');self.results.append({'nodeid':item.nodeid,'phase':'database_binding','database':self.database})
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.results.append({'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome})
(OUT/'normalization-r3-process.json').write_text(json.dumps({'pid':os.getpid(),'started_at':datetime.now(timezone.utc).isoformat(),'head':'6f4e2e984f345c81240063096091971edcb92458','authority':'AOS-001644','state':'RUNNING','replay_allowed':False},indent=2))
r=Recorder();code=pytest.main([str(REPO/'services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py')+'::'+n for n in ('test_native_source_binding_rejects_coherent_wrong_hash', 'test_original_source_binding_uses_typed_normalization_in_private_reader', 'test_original_source_time_profile_matches_original_datetime_oracle', 'test_original_source_candidate_profile_matches_original_shape_oracle', 'test_native_original_capacity_application_profile_matches_original_model', 'test_native_original_capacity_request_rechecks_exact_row_expiry', 'test_native_original_candidate_profile_matches_original_model', 'test_native_original_candidate_rows_and_combination_keep_original_claims', 'test_native_candidate_combination_preserves_real_original_private_approval', 'test_native_candidate_combination_rejects_rehashed_original_row_term_faults', 'test_native_original_provider_profile_preserves_actual_business_hash', 'test_native_original_provider_profile_matches_original_model_domain', 'test_native_original_provider_current_row_rejects_coherent_payload_faults', 'test_native_provider_query_holds_original_head_share_fence', 'test_native_provider_query_checks_real_full_original_account_set', 'test_native_original_build_request_reads_actual_original_provenance', 'test_native_original_build_request_canonical_domain_and_acl', 'test_native_original_build_json_matches_original_decoded_hash_input', 'test_native_original_evidence_row_reads_real_verified_build', 'test_native_original_build_equality_matches_original_decoder', 'test_native_evidence_query_preserves_original_row_domains_and_faults', 'test_native_evidence_query_checks_three_distinct_original_source_origins', 'test_native_evidence_contract_rejects_coherently_rehashed_bad_metadata', 'test_native_evidence_query_preserves_genuine_build_cutoff_and_numeric_hash', 'test_original_request_large_offset_storage_boundary_is_not_source_authority', 'test_native_signing_permit_binds_exact_policy_and_controlled_source_root')]+['-q','-s','--maxfail=1'],plugins=[r]);(OUT/'native-normalization-r3-result.json').write_text(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),'database':r.database,'pytest_exit':int(code),'results':r.results,'scope':'Entire original26functions50nodes selected:2offset/signingpermit functions11nodes plus24adjacentfunctions39nodes; not whole386node Source acceptance'},indent=2)+'\n');raise SystemExit(code)
