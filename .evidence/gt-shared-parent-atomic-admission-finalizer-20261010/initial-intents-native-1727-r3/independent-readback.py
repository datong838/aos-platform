"""Exact retained experiment readback. No replay, grants, DDL or business writes."""
from pathlib import Path
import hashlib,json,os,re,subprocess
import psycopg
from psycopg.rows import dict_row
from aos_api import aip_shared_parent_atomic_admission as api
from aos_api.aip_model_runtime_store import canonical_hash
B=Path(__file__).resolve().parent;R=B.parents[2]
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
result=json.loads((B/'result-r3.json').read_text());assert len(result['databases'])==1
proof=json.loads((B/'component-native-proof.json').read_text());doc=proof['origin'];body=doc['immutable']
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
 certificate_proof=proof['certificate_proof'];assert len(certificate_proof['certificates'])==4
 pending=certificate_proof['result'];assert pending['persisted'] and pending['executionAllowed'] is False
 assert proof['actual_commit_rejected'] and pending['contentHash']=='sha256:'+canonical_hash(pending['immutable'])
 assert pending['immutable']['certificateSetHash']=='sha256:'+hashlib.sha256(json.dumps(certificate_proof['certificates'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 assert certificate_proof['negative_cases']==['actual_input_bytes_tampered']
 from aos_api.aip_shared_parent_certificate_prepare import ISSUER_OWNER,VERIFY
 import base64
 from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
 root=certificate_proof['root'];key=Ed25519PublicKey.from_public_bytes(base64.b64decode(root['publicKeyBase64']))
 encode=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
 for envelope in certificate_proof['certificates']:
  key.verify(base64.b64decode(envelope['signatureBase64']),b'AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3\n'+encode(envelope['certificate']))
 signature=api.CERTIFICATE_SET;row=c.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,proconfig,prosecdef FROM pg_proc WHERE oid=to_regprocedure(%s)',(signature,)).fetchone()
 expected=re.search(r'\$set\$(.*?)\$set\$',api.shared_parent_admission_certificate_set_statements()[1],re.S)[1]
 assert row['prosrc']==expected and row['owner']==ISSUER_OWNER and row['prosecdef'] and row['proconfig']==['search_path=pg_catalog']
 for role in ('aos_runtime','aos_provider_capacity_issuer',api.OWNER):
  assert not c.execute('SELECT has_function_privilege(%s,%s,\'EXECUTE\') AS allowed',(role,signature)).fetchone()['allowed']
 assert not c.execute('SELECT has_function_privilege(%s,%s,\'EXECUTE\') AS allowed',(api.OWNER,VERIFY)).fetchone()['allowed']
 metadata.append({'signature':signature,'native_body_exact':True,'owner':ISSUER_OWNER,'runtime_execute':False,'physical_verifier_grant':False,'signed_legs':4,'negative_cases':certificate_proof['negative_cases']})
 guards=json.loads((B.parent/'native-finalizer-gap-1698.json').read_text())['guards']
 guard_readback=[]
 for guard in guards:
  table_name='aos_physical_capacity_occupation_private.'+guard['table']
  if c.execute('SELECT to_regclass(%s) AS t',(table_name,)).fetchone()['t'] is None:
   guard_readback.append({'table':table_name,'installed_in_this_fixture':False});continue
  row=c.execute('SELECT p.prosrc,pg_get_userbyid(p.proowner) AS owner,t.tgdeferrable,t.tginitdeferred FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid=%s::regclass AND t.tgname=%s',('aos_physical_capacity_occupation_private.'+guard['table'],guard['trigger'])).fetchone()
  assert hashlib.sha256(row['prosrc'].encode()).hexdigest()==guard['body_sha256'] and row['owner']==guard['owner'] and row['tgdeferrable'] and row['tginitdeferred']
  guard_readback.append({'table':table_name,'installed_in_this_fixture':True,'body_hash_exact':True})
 signature=api.READ_PENDING
 row=c.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,proconfig,prosecdef FROM pg_proc WHERE oid=to_regprocedure(%s)',(signature,)).fetchone()
 expected=re.search(r'\$lookup\$(.*?)\$lookup\$',api.shared_parent_pending_origin_lookup_statements()[0],re.S)[1]
 assert row['prosrc']==expected and row['owner']==ISSUER_OWNER and row['proconfig']==['search_path=pg_catalog'] and row['prosecdef']
 assert certificate_proof['replay_accepted_only_in_prior_r1_partial']
 initial=certificate_proof['initial_obligation'];assert initial['contentHash']=='sha256:'+canonical_hash(initial['immutable']) and initial['executionAllowed'] is False
 assert c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(api.OWNER,signature)).fetchone()['allowed']
 for role in ('aos_runtime','aos_provider_capacity_issuer'):
  assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(role,signature)).fetchone()['allowed']
 assert not c.execute("SELECT has_schema_privilege(%s,%s,'USAGE') AS allowed",(api.OWNER,api.ADMISSION_SCHEMA)).fetchone()['allowed']
 metadata.append({'signature':signature,'native_body_exact':True,'body_sha256':hashlib.sha256(expected.encode()).hexdigest(),'physical_owner_execute':True,'runtime_execute':False,'schema_table_grant':False})
 statements=api.shared_parent_physical_obligation_statements()
 for statement in statements:
  match=re.search(r'CREATE FUNCTION ([^(]+)\((.*?)\$(immutable|end|obligation)\$(.*?)\$\3\$',statement,re.S)
  if not match:continue
  name=match[1];expected=match[4]
  row=c.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,proconfig FROM pg_proc WHERE pronamespace=(SELECT oid FROM pg_namespace WHERE nspname=%s) AND proname=%s',(name.split('.')[0],name.split('.')[1])).fetchone()
  assert row['prosrc']==expected and row['owner']==api.OWNER and row['proconfig']==['search_path=pg_catalog']
  metadata.append({'name':name,'native_body_exact':True,'owner':row['owner'],'body_sha256':hashlib.sha256(expected.encode()).hexdigest()})
 obligation_table=api.PHYSICAL_SCHEMA+'.initial_target_obligation'
 assert c.execute('SELECT count(*) AS n FROM '+obligation_table).fetchone()['n']==0
 row=c.execute('SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) AS owner FROM pg_class WHERE oid=%s::regclass',(obligation_table,)).fetchone()
 assert row['owner']==api.OWNER and row['relrowsecurity'] and row['relforcerowsecurity']
 for role in ('aos_runtime','aos_provider_capacity_issuer'):
  for priv in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):
   assert not c.execute('SELECT has_table_privilege(%s,%s,%s) AS allowed',(role,obligation_table,priv)).fetchone()['allowed']
  assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(role,api.INITIAL_OBLIGATION)).fetchone()['allowed']
 assert c.execute('SELECT to_regprocedure(%s) AS f',(api.PHYSICAL_END,)).fetchone()['f'] is None
 storage=api.shared_parent_admission_storage_statements()
 for statement in storage:
  match=re.search(r'CREATE FUNCTION ([^(]+)\((.*?)\$(binding|immutable|end|persist)\$(.*?)\$\3\$',statement,re.S)
  if not match:continue
  name=match[1];tag=match[3];expected=match[4]
  row=c.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,proconfig,prosecdef FROM pg_proc WHERE pronamespace=(SELECT oid FROM pg_namespace WHERE nspname=%s) AND proname=%s',(name.split('.')[0],name.split('.')[1])).fetchone()
  assert row['prosrc']==expected and row['owner']==ISSUER_OWNER and row['proconfig']==['search_path=pg_catalog']
  assert row['prosecdef']==(tag in ('end','persist'))
  metadata.append({'name':name,'native_body_exact':True,'body_sha256':hashlib.sha256(expected.encode()).hexdigest(),'owner':row['owner']})
 table=api.ADMISSION_SCHEMA+'.pending_origin'
 row=c.execute('SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) AS owner FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()
 assert row['owner']==ISSUER_OWNER and row['relrowsecurity'] and row['relforcerowsecurity']
 assert c.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']==0
 assert c.execute('SELECT to_regprocedure(%s) AS f',(api.END_CHANNEL,)).fetchone()['f'] is None
 for role in ('aos_runtime','aos_provider_capacity_issuer',api.OWNER):
  for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):
   assert not c.execute('SELECT has_table_privilege(%s,%s,%s) AS allowed',(role,table,privilege)).fetchone()['allowed']
  assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(role,api.PERSIST)).fetchone()['allowed']
 trigger=c.execute('SELECT tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',(table,'require_complete_admission_end')).fetchone()
 assert trigger['tgdeferrable'] and trigger['tginitdeferred']
 counts={t:c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+t).fetchone()['n'] for t in ('prepared_plan_risk','prepared_shared_risk_description')}
 assert all(v==0 for v in counts.values())
 facts=body['originalRisk']['originalFacts']
 for purpose,table in [('target','aip_model_eval_budget_reservation'),('judge','aip_model_judge_budget_reservation')]:
  assert c.execute('SELECT count(*) AS n FROM public.'+table+' WHERE reservation_id=%s',(facts[purpose]['reservationId'],)).fetchone()['n']==0
 intents=certificate_proof['initial_intents']
 assert intents['targetIntentHash']=='sha256:'+canonical_hash(intents['targetIntent'])
 assert intents['judgeDependencyHash']=='sha256:'+canonical_hash(intents['judgeDependency'])
 assert intents['judgeDependency']['targetIntentHash']==intents['targetIntentHash']
 assert intents['judgeDependency']['inputDependency']['targetIntentId']==intents['targetIntent']['intentId']
 signature=api.INITIAL_INTENT
 row=c.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,proconfig,prosecdef FROM pg_proc WHERE oid=to_regprocedure(%s)',(signature,)).fetchone()
 statement=next(s for s in api.shared_parent_initial_intent_statements() if '$intents$' in s)
 expected=re.search(r'\$intents\$(.*?)\$intents\$',statement,re.S)[1]
 assert row['prosrc']==expected and row['owner']==api.OWNER and row['proconfig']==['search_path=pg_catalog'] and row['prosecdef']
 metadata.append({'signature':signature,'native_body_exact':True,'body_sha256':hashlib.sha256(expected.encode()).hexdigest(),'runtime_execute':False})
 for name in ('target_intent','judge_dependency'):
  table=api.PHYSICAL_SCHEMA+'.'+name
  assert c.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']==0
  row=c.execute('SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) AS owner FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()
  assert row['owner']==api.OWNER and row['relrowsecurity'] and row['relforcerowsecurity']
  for role in ('aos_runtime','aos_provider_capacity_issuer'):
   assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(role,signature)).fetchone()['allowed']
   for priv in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):
    assert not c.execute('SELECT has_table_privilege(%s,%s,%s) AS allowed',(role,table,priv)).fetchone()['allowed']
  tr=c.execute('SELECT tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s',(table,'require_complete_intent_end')).fetchone()
  assert tr['tgdeferrable'] and tr['tginitdeferred']
 c.rollback()
receipt={'status':'INITIAL_INTENTS_COMPONENT_NATIVE_ROLLBACK_READBACK','task':'gt-shared-parent-atomic-admission-finalizer-20261010','authority':'AOS-001727','cluster':lab['cluster'],'database':result['databases'][0],'readonly':True,'latest_entry_context_guard_installed':True,'whole_fixture_pass':result['pytest_exit']==0,'native_functions':metadata,'original_guard_readback':guard_readback,'legacy_counts':counts,'caller_xid_state':'aborted','two_original_parent_holds_after_rollback':0,'positive_cases':len(body['manifest']['cases']),'negative_cases':proof['negative_cases'],'original_files_unchanged':result['old_files_unchanged'],'execution_allowed':False,'formal_root_provenance':False,'full_admission_commit':False,'database_writes':False}
(B/'independent-readback.json').open('x').write(json.dumps(receipt,indent=2)+'\n')
print('Independent readback: native origin positive, exact no-grant functions, aborted caller and both parent holds rolled back')
