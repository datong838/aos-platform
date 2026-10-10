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
result=json.loads((B/'result-r2.json').read_text());assert len(result['databases'])==1
proof=json.loads((B/'component-native-proof.json').read_text());cp=proof['certificate_proof'];pending=cp['result'];material=cp['retained_authority']
assert proof['actual_commit_rejected'] and material['contentHash']=='sha256:'+canonical_hash(material['immutable'])
assert material['immutable']['pendingOriginHash']==pending['contentHash']
assert cp['retained_readback']==pending|{'authorityMaterialHash':material['contentHash']}
assert cp['negative_cases']==['extra_authentication_field_rejected_before_retention','different_caller_xid','wrong_pending_hash','runtime_private_material_read','authorized_caller_canary_denied','existing_material_update_denied','existing_material_delete_denied']
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
receipt={'status':'RETAINED_AUTHORITY_NATIVE_REVALIDATION_AND_COMMIT_REJECTION_COMPONENT_PASS','authority':'AOS-001729','database':result['databases'][0],'cluster':lab['cluster'],'native_functions':metadata,'signed_legs':4,'native_caller_aborted':True,'zero_pending_material_and_parent_holds':True,'closed_credentials_field_gate':True,'raw_packet_exported':False,'negative_cases':cp['negative_cases'],'whole_fixture_pass':result['pytest_exit']==0,'formal_root_provenance':False,'formal_writes':False,'full_admission_commit':False,'full_task_delivered':False,'execution_allowed':False}
(B/'independent-readback.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'],receipt['database'],receipt['whole_fixture_pass'])
