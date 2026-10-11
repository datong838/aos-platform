"""Read-only rollback and original-generator reconciliation; no caller replay."""
import pathlib,json,hashlib,subprocess,inspect
import psycopg
from aos_api import aip_shared_parent_atomic_admission as a
B=pathlib.Path(__file__).resolve().parent;R=B.parents[2];l=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
old=json.loads((B/'beforeimage.json').read_text());actual={n:hashlib.sha256('\n'.join(getattr(a,n)()).encode()).hexdigest() for n in old};assert actual==old
files=['services/aos-api/aos_api/aip_shared_parent_atomic_admission.py','services/aos-api/tests/aip/test_shared_parent_atomic_admission_pg.py'];prefix={}
for name in files:
 original=subprocess.check_output(['git','show','HEAD:'+name]);now=(R/name).read_bytes();assert now.startswith(original);prefix[name]={'original_sha256':hashlib.sha256(original).hexdigest(),'current_sha256':hashlib.sha256(now).hexdigest(),'original_bytes_unchanged':True}
with psycopg.connect(host='127.0.0.1',port=l['port'],user='aos_app',dbname='aos_test_05f1a1dcd51f_ti4_test',passfile=l['passfile']) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==l['cluster'];assert c.execute('SELECT to_regprocedure(%s)',(a.COMPLETE_END_FACTS,)).fetchone()[0] is None;assert c.execute('SELECT to_regprocedure(%s)',(a.FUNCTION,)).fetchone()[0] is None
 roles=c.execute("SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname IN ('aos_physical_capacity_occupation_owner','aos_provider_capacity_issuer','aos_provider_capacity_occupation','aos_model_eval_issuer_owner','aos_capacity_publication_owner') ORDER BY rolname").fetchall();assert len(roles)==5 and all(not any(x[1:]) for x in roles)
 pending=c.execute("SELECT prosrc,probin,proacl::text FROM pg_proc WHERE prosrc='aos_admission_pending_relations'").fetchall();assert len(pending)==1 and pending[0][1]=='/tmp/aos_admission_end_25913075ff7145d485a5509d8d55d142.so'
so=subprocess.check_output(['docker','--context','desktop-linux','exec',l['name'],'sha256sum','/usr/local/lib/postgresql/aos_ed25519.so'],text=True).split()[0];assert so=='6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'
result={'status':'COMPLETE_END_FACTS_COMPONENT_READBACK_GREEN','original_generators_exact':len(old),'original_product_prefixes':prefix,'native_definition_rolled_back_absent':True,'original_pending_reader':pending,'five_roles_closed':True,'signature_binary_unchanged':so,'full_eight_node_legitimate_source_positive_executed_this_wave':False,'full_native_ending_or_task_delivery':False,'execution_allowed':False}
(B/'independent-readback.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'old_generators_exact':len(old),'native_absent':True}))
