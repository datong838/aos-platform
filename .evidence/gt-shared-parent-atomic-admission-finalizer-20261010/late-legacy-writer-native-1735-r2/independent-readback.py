"""Read only the exact retained native attempt; never replay its commands."""
from pathlib import Path
import hashlib,json,re,base64
import psycopg
from psycopg.rows import dict_row
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from aos_api import aip_shared_parent_atomic_admission as api
from aos_api.aip_model_runtime_store import canonical_hash
from aos_api.aip_shared_parent_certificate_prepare import ISSUER_OWNER
B=Path(__file__).resolve().parent;R=B.parents[2]
result=json.loads((B/'result-r1.json').read_text());assert len(result['databases'])==1
proof=json.loads((B/'component-native-proof.json').read_text());cp=proof['certificate_proof'];pending=cp['result'];material=cp['retained_authority']
assert proof['actual_commit_rejected'] and material['contentHash']=='sha256:'+canonical_hash(material['immutable'])
assert material['immutable']['pendingOriginHash']==pending['contentHash']
assert cp['retained_readback'] is None # Not repeated; no standalone positive claim.
assert cp['window_snapshot_not_current'] is True
target=pending['immutable']['origin']['immutable']['originalRisk']['originalFacts']['target']
assert cp['actual_union_after_late_writer']['requests']>target['maxConcurrency']
assert cp['actual_union_after_late_writer']['tokens']>target['tokenLimit']['maxTokens']
assert cp['late_legacy_debit']['physicalRequests']==2
assert cp['negative_cases']==[]
assert len(cp['certificates'])==4
key=Ed25519PublicKey.from_public_bytes(base64.b64decode(cp['root']['publicKeyBase64']))
encode=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
for envelope in cp['certificates']:
 key.verify(base64.b64decode(envelope['signatureBase64']),b'AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3\n'+encode(envelope['certificate']))
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());metadata=[]
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 assert c.execute('SELECT pg_xact_status(%s::xid8) AS state',(proof['rollback_xid'],)).fetchone()['state']=='aborted'
 for statement in api.shared_parent_end_authority_statements():
  match=re.search(r'CREATE FUNCTION ([^(]+)\(.*?\$(retained_binding|retain|retained)\$(.*?)\$\2\$',statement,re.S)
  if not match:continue
  name,tag,body=match.groups()
  row=c.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,proconfig,prosecdef FROM pg_proc WHERE pronamespace=(SELECT oid FROM pg_namespace WHERE nspname=%s) AND proname=%s',tuple(name.split('.'))).fetchone()
  assert row['prosrc']==body and row['owner']==ISSUER_OWNER and row['proconfig']==['search_path=pg_catalog'] and row['prosecdef']==(tag!='retained_binding')
  metadata.append({'name':name,'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'native_body_exact':True,'owner':row['owner']})
 for sig in (api.STAGE_AUTHORITY,api.READ_RETAINED):
  for role in ('aos_runtime','aos_provider_capacity_issuer'):
   assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(role,sig)).fetchone()['allowed']
 assert c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(api.OWNER,api.READ_RETAINED)).fetchone()['allowed']
 assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(api.OWNER,api.STAGE_AUTHORITY)).fetchone()['allowed']
 for table in ('pending_origin','end_authority'):
  table=api.ADMISSION_SCHEMA+'.'+table
  assert c.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']==0
  row=c.execute('SELECT pg_get_userbyid(relowner) AS owner,relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()
  assert row['owner']==ISSUER_OWNER and row['relrowsecurity'] and row['relforcerowsecurity']
  for role in ('aos_runtime','aos_provider_capacity_issuer',api.OWNER):
   for priv in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):
    assert not c.execute('SELECT has_table_privilege(%s,%s,%s) AS allowed',(role,table,priv)).fetchone()['allowed']
 assert not c.execute("SELECT has_schema_privilege(%s,%s,'USAGE') AS allowed",(api.OWNER,api.ADMISSION_SCHEMA)).fetchone()['allowed']
 assert c.execute('SELECT to_regprocedure(%s) AS f',(api.END_CHANNEL,)).fetchone()['f'] is None
 trigger=c.execute("SELECT tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='require_complete_authority_end'",(api.ADMISSION_SCHEMA+'.end_authority',)).fetchone()
 assert trigger['tgdeferrable'] and trigger['tginitdeferred']
 facts=pending['immutable']['origin']['immutable']['originalRisk']['originalFacts']
 for purpose,table in [('target','aip_model_eval_budget_reservation'),('judge','aip_model_judge_budget_reservation')]:
  assert c.execute('SELECT count(*) AS n FROM '+table+' WHERE reservation_id=%s',(facts[purpose]['reservationId'],)).fetchone()['n']==0
 assert not c.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname='aos_provider_capacity_occupation'").fetchone()['rolcanlogin']
 assert c.execute("SELECT count(*) AS n FROM pg_auth_members WHERE member='aos_provider_capacity_occupation'::regrole OR roleid='aos_provider_capacity_occupation'::regrole").fetchone()['n']==0
call=cp['initial_call_material'];native_call=cp['initial_call_readback']
assert call['contentHash']=='sha256:'+canonical_hash(call['immutable'])
assert native_call['initialCallAuthorityHash']==call['contentHash']
assert native_call['targetIntentHash']==call['immutable']['targetIntentHash']
assert native_call['judgeDependencyHash']==call['immutable']['judgeDependencyHash']
assert cp['initial_call_negatives']==['raw_input_tamper_rejected','wrong_material_hash_rejected','runtime_table_read_rejected']
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 for statement in api.shared_parent_initial_call_authority_statements():
  match=re.search(r'CREATE FUNCTION ([^(]+)\(.*?\$(call_binding|call_stage|call_read)\$(.*?)\$\2\$',statement,re.S)
  if not match:continue
  name,tag,body=match.groups()
  row=c.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,proconfig,prosecdef FROM pg_proc WHERE pronamespace=(SELECT oid FROM pg_namespace WHERE nspname=%s) AND proname=%s',tuple(name.split('.'))).fetchone()
  assert row['prosrc']==body and row['owner']==api.OWNER and row['proconfig']==['search_path=pg_catalog'] and row['prosecdef']==(tag!='call_binding')
  metadata.append({'name':name,'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'native_body_exact':True,'owner':row['owner']})
 for sig in (api.STAGE_INITIAL_CALL,api.READ_INITIAL_CALL):
  for role in ('aos_runtime','aos_provider_capacity_issuer'):
   assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(role,sig)).fetchone()['allowed']
 for name in ('initial_call_authority','initial_target_obligation','target_intent','judge_dependency'):
  table=api.PHYSICAL_SCHEMA+'.'+name
  assert c.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']==0
  for role in ('aos_runtime','aos_provider_capacity_issuer'):
   for priv in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):
    assert not c.execute('SELECT has_table_privilege(%s,%s,%s) AS allowed',(role,table,priv)).fetchone()['allowed']
 assert c.execute('SELECT to_regprocedure(%s) AS f',(api.PHYSICAL_END,)).fetchone()['f'] is None
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 sql=next(x for x in api.shared_parent_pending_origin_lookup_statements() if x.startswith('CREATE FUNCTION '))
 body=re.search(r'\$lookup\$(.*?)\$lookup\$',sql,re.S).group(1)
 row=c.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,proconfig,prosecdef FROM pg_proc WHERE oid=%s::regprocedure',(api.READ_PENDING,)).fetchone()
 assert row['prosrc']==body and row['owner']==ISSUER_OWNER and row['proconfig']==['search_path=pg_catalog'] and row['prosecdef']
 metadata.append({'name':api.READ_PENDING,'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'native_body_exact':True,'owner':row['owner']})
window=cp['initial_window_obligation']
assert window['contentHash']=='sha256:'+canonical_hash(window['immutable'])
assert window['initialCall']==cp['initial_call_readback']
assert window['immutable']['initialCallAuthorityHash']==cp['initial_call_material']['contentHash']
legacy=cp['legacy_prepared_debit']
assert legacy['physicalRequests']==1 and legacy['physicalTokens']>0
assert legacy['contentHash'].startswith('sha256:')
assert window['immutable']['unresolvedRequests']==2
assert window['immutable']['unresolvedTokenUpperBound']==cp['initial_obligation']['immutable']['tokenUpperBound']+legacy['physicalTokens']
assert window['immutable']['sourceTokenLimit']['mode']=='inflight_upper_bound'
assert window['immutable']['windowExpiryReleasesRisk'] is False
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT count(*) AS n FROM '+api.PHYSICAL_SCHEMA+'.initial_window_obligation').fetchone()['n']==0
 for sql in api.shared_parent_initial_window_obligation_statements():
  match=re.search(r'CREATE FUNCTION ([^(]+)\(.*?\$(window_binding|window_stage)\$(.*?)\$\2\$',sql,re.S)
  if not match:continue
  name,tag,body=match.groups()
  row=c.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,proconfig,prosecdef FROM pg_proc WHERE pronamespace=(SELECT oid FROM pg_namespace WHERE nspname=%s) AND proname=%s',tuple(name.split('.'))).fetchone()
  assert row['prosrc']==body and row['owner']==api.OWNER and row['proconfig']==['search_path=pg_catalog'] and row['prosecdef']==(tag=='window_stage')
  metadata.append({'name':name,'body_sha256':hashlib.sha256(body.encode()).hexdigest(),'native_body_exact':True,'owner':row['owner']})
 for role in ('aos_runtime','aos_provider_capacity_issuer'):
  assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(role,api.STAGE_INITIAL_WINDOW)).fetchone()['allowed']
  for priv in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):
   assert not c.execute('SELECT has_table_privilege(%s,%s,%s) AS allowed',(role,api.PHYSICAL_SCHEMA+'.initial_window_obligation',priv)).fetchone()['allowed']
receipt={'status':'LATE_LEGACY_WRITER_OVERSUBSCRIPTION_NATIVE_RED_OBSERVED','authority':'AOS-001735','database':result['databases'][0],'cluster':lab['cluster'],'native_functions':metadata,'signed_legs':4,'native_caller_aborted':True,'zero_pending_material_and_parent_holds':True,'closed_credentials_field_gate':True,'raw_packet_exported':False,'negative_cases':cp['negative_cases']+cp['initial_call_negatives'],'whole_fixture_pass':result['pytest_exit']==0,'fixed_window_signed_positive':False,'old_unknown_cutover_positive':False,'formal_root_provenance':False,'formal_writes':False,'full_admission_commit':False,'full_task_delivered':False,'execution_allowed':False}
(B/'independent-readback.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'],receipt['database'],receipt['whole_fixture_pass'])
