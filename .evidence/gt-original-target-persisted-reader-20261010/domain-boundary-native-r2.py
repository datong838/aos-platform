from pathlib import Path
import os,sys,json,hashlib,base64
from datetime import datetime,timezone,timedelta
import psycopg
from psycopg.rows import dict_row
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
B=Path(__file__).resolve().parent;R=B.parents[1];sys.path.insert(0,str(R/'services/aos-api'))
from tests.aip.test_model_eval_execution_contracts import _certificate_input
from aos_api import aip_model_eval_execution_contracts as model
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());db=json.loads((B/'result-r3.json').read_text())['databases'][0]
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
def encode(v):
 if hasattr(v,'model_dump'):v=v.model_dump(mode='json',by_alias=True)
 return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def digest(v):return hashlib.sha256(encode(v)).hexdigest()
_,old,cert,_=_certificate_input();body=old.model_dump(mode='json',by_alias=True);body['executionId']='v1-domain-negative-r2-only';body['cases'][0]['target']['identityId']='legacy-domain-test-only-executor';plan=model.ModelEvalExecutionManifest.model_validate(body)
issuer=Ed25519PrivateKey.generate();now=datetime.now(timezone.utc)
cert=dict(cert,leg=body['cases'][0]['target'],executionId=plan.execution_id,manifestHash=digest(plan),issuerId='v1-domain-test-only',issuerKeyId='v1-domain-test-only-key',validFrom=now-timedelta(seconds=2),validUntil=now+timedelta(seconds=60))
root=model.ModelEvalIssuerVerificationInput.model_validate(dict(schemaVersion='aos.model-eval-issuer-verification-input/v1',purpose='model-eval-execution',tenant=body['tenant'],issuerId=cert['issuerId'],issuerKeyId=cert['issuerKeyId'],publicKeyBase64=base64.b64encode(issuer.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode(),validFrom=cert['validFrom'],validUntil=cert['validUntil'],revokedAt=None))
env=model.ModelEvalSignedCertificateEnvelope.model_validate(dict(schemaVersion='aos.model-eval-signed-certificate-envelope/v1',certificate=cert,signatureBase64=base64.b64encode(issuer.sign(model.canonical_model_certificate_signing_bytes(plan,cert))).decode()))
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=db,passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE');assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 c.execute("SET LOCAL aos.org_id='org-org'");c.execute("SET LOCAL aos.project_id='dev-project'");c.execute('SET LOCAL ROLE aos_model_eval_execution_owner')
 c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,digest(plan),encode(plan)))
 c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
 c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project',root.issuer_id,root.issuer_key_id,'a'*64,digest(root),encode(root)))
 c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',('org-org','dev-project',root.issuer_id,root.issuer_key_id,digest(root)))
 c.execute('INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,cert['caseId'],'target',root.issuer_id,root.issuer_key_id,digest(env),encode(env)))
 c.execute('SAVEPOINT v2_negative')
 try:c.execute('INSERT INTO aos_model_eval_issuer_private.original_target_certificate_identity_binding(org_id,project_id,certificate_hash) VALUES (%s,%s,%s)',('org-org','dev-project',digest(env)))
 except psycopg.errors.InsufficientPrivilege as e:
  assert e.diag.message_primary=='ORIGINAL_TARGET_CERTIFICATE_BINDING';rejected={'sqlstate':e.sqlstate,'message':e.diag.message_primary};c.execute('ROLLBACK TO v2_negative')
 else:raise AssertionError('v1 accepted into v2 binding')
 c.execute('RELEASE v2_negative')
 c.execute('INSERT INTO aos_model_eval_issuer_private.certificate_identity_binding(org_id,project_id,certificate_hash) VALUES (%s,%s,%s)',('org-org','dev-project',digest(env)))
 assert c.execute('SELECT count(*) AS n FROM aos_model_eval_issuer_private.certificate_identity_binding WHERE certificate_hash=%s',(digest(env),)).fetchone()['n']==1
 xid=c.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid'];c.rollback()
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT pg_xact_status(%s::xid8) AS status',(xid,)).fetchone()['status']=='aborted'
 assert c.execute('SELECT count(*) AS n FROM aos_model_eval_execution_private.manifest WHERE execution_id=%s',(plan.execution_id,)).fetchone()['n']==0;c.rollback()
paths=['services/aos-api/aos_api/aip_model_original_target_result_reader.py','services/aos-api/aos_api/aip_model_eval_execution_authority.py','services/aos-api/aos_api/aip_model_eval_execution_reader.py']
out={'database':db,'cluster':lab['cluster'],'caller_xid':xid,'caller_end_status':'aborted','v1_binding_accepted':True,'v2_binding_rejected_v1':rejected,'manifest_rows_after_rollback':0,'file_hashes':{p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in paths},'execution_allowed':False,'actual_transport':False,'full_task_delivered':False}
(B/'domain-boundary-native-result-r2.json').open('x').write(json.dumps(out,indent=2)+'\n');print(rejected)
