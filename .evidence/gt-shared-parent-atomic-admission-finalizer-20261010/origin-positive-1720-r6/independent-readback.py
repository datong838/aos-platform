"""Exact retained experiment readback. No replay, grants, DDL or business writes."""
from pathlib import Path
import hashlib,json,os,re,subprocess
import psycopg
from psycopg.rows import dict_row
from aos_api import aip_shared_parent_atomic_admission as api
from aos_api.aip_model_runtime_store import canonical_hash
B=Path(__file__).resolve().parent;R=B.parents[2]
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
result=json.loads((B/'result-r6.json').read_text());assert result['pytest_exit']==0 and len(result['databases'])==1
proof=json.loads((B/'native-origin-proof.json').read_text());doc=proof['origin'];body=doc['immutable']
assert doc['contentHash']=='sha256:'+canonical_hash(body)
assert body['originalRiskHash']=='sha256:'+canonical_hash(body['originalRisk'])
assert proof['legacy_preparation_unchanged'] and doc['legacyBefore']==doc['legacyAfter']==[0,0]
container=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',lab['name']]))[0]
assert container['Id']==lab['container_id'] and container['Image']==lab['image'] and container['State']['Running']
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
metadata=[]
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 assert c.execute('SELECT pg_xact_status(%s::xid8) AS state',(proof['rollback_xid'],)).fetchone()['state']=='aborted'
 for signature,statements,tag in ((api.FUNCTION,api.shared_parent_original_fact_statements(),'facts'),(api.ORIGIN,api.shared_parent_admission_origin_statements(),'origin')):
  row=c.execute('SELECT prosrc,proconfig,prosecdef,pg_get_userbyid(proowner) AS owner,proacl::text AS acl FROM pg_proc WHERE oid=to_regprocedure(%s)',(signature,)).fetchone()
  expected=re.search(r'\$'+tag+r'\$(.*?)\$'+tag+r'\$',statements[0],re.S)[1]
  assert row['prosrc']==expected and row['owner']==api.OWNER and row['proconfig']==['search_path=pg_catalog'] and row['prosecdef']
  assert not c.execute("SELECT has_function_privilege('aos_runtime',%s,'EXECUTE') AS allowed",(signature,)).fetchone()['allowed']
  metadata.append({'signature':signature,'body_sha256':hashlib.sha256(expected.encode()).hexdigest(),'owner':row['owner'],'acl':row['acl'],'native_body_exact':True,'runtime_execute':False})
 counts={t:c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+t).fetchone()['n'] for t in ('prepared_plan_risk','prepared_shared_risk_description')}
 assert all(v==0 for v in counts.values())
 facts=body['originalRisk']['originalFacts']
 for purpose,table in [('target','aip_model_eval_budget_reservation'),('judge','aip_model_judge_budget_reservation')]:
  assert c.execute('SELECT count(*) AS n FROM public.'+table+' WHERE reservation_id=%s',(facts[purpose]['reservationId'],)).fetchone()['n']==0
 c.rollback()
receipt={'status':'NATIVE_VERSIONED_ORIGIN_POSITIVE_AND_ROLLBACK_READBACK_PASS','task':'gt-shared-parent-atomic-admission-finalizer-20261010','authority':'AOS-001720','cluster':lab['cluster'],'database':result['databases'][0],'readonly':True,'native_functions':metadata,'legacy_counts':counts,'caller_xid_state':'aborted','two_original_parent_holds_after_rollback':0,'positive_cases':len(body['manifest']['cases']),'negative_cases':proof['negative_cases'],'original_files_unchanged':result['old_files_unchanged'],'execution_allowed':False,'formal_root_provenance':False,'full_admission_commit':False,'database_writes':False}
(B/'independent-readback.json').open('x').write(json.dumps(receipt,indent=2)+'\n')
print('Independent readback: native origin positive, exact no-grant functions, aborted caller and both parent holds rolled back')
