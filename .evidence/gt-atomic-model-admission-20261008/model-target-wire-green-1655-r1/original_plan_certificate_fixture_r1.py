"""Local isolated certificate fixture; never a production role-switch bridge."""
import base64,hashlib,json
from uuid import uuid4
from datetime import timedelta
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from aos_api import aip_model_eval_execution_contracts as contract
from aos_api import aip_model_eval_execution_reader as reader
from aos_api import aip_model_eval_execution_authority as authority
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_runtime_store import canonical_hash

def verify_original_certificate_set(c,original,base,label):
 def dump(v):return v.model_dump(mode='json',by_alias=True)
 def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
 def public(key):return key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
 c.execute('SAVEPOINT original_certificate_fixture')
 before=c.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
 nonce=uuid4().hex;body=dump(original);body['executionId']='original-cert-'+nonce;keys={}
 for case in body['cases']:
  for purpose in ('target','judge'):
   key=Ed25519PrivateKey.generate();keys[case['caseId'],purpose]=key
   case[purpose]['identityId']=nonce+'-'+case['caseId']+'-'+purpose
   case[purpose]['identityKeyHash']=hashlib.sha256(public(key)).hexdigest()
 plan=contract.ModelEvalExecutionManifest.model_validate(body);digest=canonical_hash(dump(plan))
 c.execute('RESET ROLE')
 if c.execute("SELECT to_regclass('aos_model_eval_issuer_private.identity_epoch') AS table").fetchone()['table'] is None:authority.install_closed_model_identity_authority(c.execute)
 c.execute('SET LOCAL ROLE aos_model_eval_execution_owner')
 c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,digest,encode(dump(plan))))
 c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
 now=c.execute('SELECT clock_timestamp() AS now').fetchone()['now'];start=now-timedelta(seconds=1);end=now+timedelta(minutes=5);bindings=[]
 for purpose in ('target','judge'):
  issuer=Ed25519PrivateKey.generate()
  root=contract.ModelEvalIssuerVerificationInput.model_validate(dict(schemaVersion='aos.model-eval-issuer-verification-input/v1',purpose='model-eval-execution',tenant=body['tenant'],issuerId=nonce+'-'+purpose,issuerKeyId='local-key',publicKeyBase64=base64.b64encode(public(issuer)).decode(),validFrom=start,validUntil=end,revokedAt=None))
  rb=encode(dump(root));rh=hashlib.sha256(rb).hexdigest()
  c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project',root.issuer_id,root.issuer_key_id,'a'*64,rh,rb))
  c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',('org-org','dev-project',root.issuer_id,root.issuer_key_id,rh))
  for case in plan.cases:
   cert=contract.ModelEvalExecutorCertificateSigningInput.model_validate(dict(schemaVersion='aos.model-eval-executor-certificate-signing-input/v1',tenant=body['tenant'],executionId=plan.execution_id,manifestHash=digest,requestHash=plan.request_hash,caseId=case.case_id,purpose=purpose,candidateRef=plan.request.target_ref,leg=getattr(case,purpose),issuerId=root.issuer_id,issuerKeyId=root.issuer_key_id,publicKeyBase64=base64.b64encode(public(keys[case.case_id,purpose])).decode(),validFrom=start,validUntil=end))
   env=contract.ModelEvalSignedCertificateEnvelope.model_validate(dict(schemaVersion='aos.model-eval-signed-certificate-envelope/v1',certificate=cert,signatureBase64=base64.b64encode(issuer.sign(contract.canonical_model_certificate_signing_bytes(plan,cert))).decode()))
   raw=encode(dump(env));ch=hashlib.sha256(raw).hexdigest()
   c.execute('INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,case.case_id,purpose,root.issuer_id,root.issuer_key_id,ch,raw))
   reader.register_persisted_model_identity(c,expected_tenant=plan.tenant,execution_id=plan.execution_id,manifest_hash=digest,certificate_hash=ch,root_hash=rh,expected_root_epoch=1,expected_certificate_epoch=1)
   bindings.append(dict(caseId=case.case_id,purpose=purpose,certificateHash=ch,rootHash=rh,rootEpoch=1,certificateEpoch=1,identityEpoch=1))
 assert c.execute('SELECT count(*) AS n FROM aos_model_eval_execution_private.case_result WHERE execution_id=%s',(plan.execution_id,)).fetchone()['n']==0
 evidence=dict(manifest=dump(plan),manifest_hash=digest,bindings=bindings,caller=before,output_count=0,scope='Local signed same original approved Suite/request metadata; Source/Intent/joint and formal bootstrap unverified')
 (base/(label+'-certificate-input.json')).write_text(json.dumps(evidence,indent=2)+'\n')
 assert hasattr(reader,'validate_persisted_model_executor_set'), 'pretransport full certificate set reader missing after four original-plan certificates'
 args=dict(expected_tenant=plan.tenant,execution_id=plan.execution_id,manifest_hash=digest)
 original_item=contract.ModelEvalPersistedExecutorInput.model_validate(bindings[0])
 assert reader.validate_persisted_model_executor_set(c,**args,certificates=tuple(bindings)) is None
 for bad in (tuple(bindings[:3]),(bindings[0],)*4,tuple(bindings)+(bindings[0],),tuple([bindings[0]|dict(certificateHash='f'*64),*bindings[1:]]),tuple([bindings[0]|dict(identityEpoch=True),*bindings[1:]]),tuple([bindings[0]|dict(caseId=' '+bindings[0]['caseId']),*bindings[1:]]),tuple([original_item.model_copy(update={'identity_epoch':True}),*bindings[1:]]),tuple([bindings[0]|dict(executionAllowed=True),*bindings[1:]])):
  with pytest.raises(ValueError):reader.validate_persisted_model_executor_set(c,**args,certificates=bad)
 c.execute('SAVEPOINT extra_executor')
 c.execute("INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) SELECT org_id,project_id,execution_id,'extra',purpose,attempt,issuer_id,key_id,encode(sha256(body||convert_to(' ','UTF8')),'hex'),body||convert_to(' ','UTF8') FROM aos_model_eval_issuer_private.executor_certificate WHERE execution_id=%s AND case_id=%s AND purpose='target'",(plan.execution_id,plan.cases[0].case_id))
 with pytest.raises(ValueError,match='persisted complete executor'):reader.validate_persisted_model_executor_set(c,**args,certificates=tuple(bindings))
 c.execute('ROLLBACK TO SAVEPOINT extra_executor')
 with pytest.raises(ValueError):reader.validate_persisted_model_executor_set(c,**(args|dict(manifest_hash='f'*64)),certificates=tuple(bindings))
 c.execute('SAVEPOINT certificate_canary');c.execute("SET LOCAL aos.org_id='dev-org'")
 with pytest.raises(ValueError,match='private executor-set SERIAL'):reader.validate_persisted_model_executor_set(c,**args,certificates=tuple(bindings))
 c.execute('ROLLBACK TO SAVEPOINT certificate_canary')
 c.execute('RESET ROLE')
 assert hasattr(authority,'runtime_executor_fact_statements'),'runtime original executor fact artifact missing after four certificate prefix'
 for statement in authority.runtime_executor_fact_statements():c.execute(statement)
 c.execute('SET LOCAL ROLE aos_runtime')
 assert hasattr(reader,'validate_runtime_model_executor_set'),'runtime original executor fact reader missing'
 assert reader.validate_runtime_model_executor_set(c,**args,certificates=tuple(bindings)) is None
 for bad in (tuple(bindings[:3]),(bindings[0],)*4,tuple([bindings[0]|dict(rootEpoch=2),*bindings[1:]]),tuple([bindings[0]|dict(rootHash='f'*64),*bindings[1:]]),tuple([bindings[0]|dict(certificateHash='f'*64),*bindings[1:]])):
  with pytest.raises(ValueError):reader.validate_runtime_model_executor_set(c,**args,certificates=bad)
 metadata=c.execute("SELECT proowner::regrole::text AS owner,prosecdef,proconfig FROM pg_proc WHERE oid='public.read_model_executor_set_facts(text,text)'::regprocedure").fetchone()
 assert metadata['owner']=='aos_model_eval_issuer_owner' and metadata['prosecdef'] and metadata['proconfig']==['search_path=pg_catalog']
 for role in ('aos_model_eval_execution_owner','aos_provider_capacity_issuer'):
  assert c.execute("SELECT has_function_privilege(%s,'public.read_model_executor_set_facts(text,text)','EXECUTE') AS allowed",(role,)).fetchone()['allowed'] is False
 (base/(label+'-runtime-fact.json')).write_text(json.dumps(dict(caller=before,manifest_hash=digest,certificate_count=4,output_count=0,function_metadata=metadata,execution_allowed=False),indent=2)+'\n')
 c.execute('SAVEPOINT runtime_canary');c.execute("SET LOCAL aos.org_id='dev-org'")
 with pytest.raises(ValueError,match='runtime executor SERIAL'):reader.validate_runtime_model_executor_set(c,**args,certificates=tuple(bindings))
 c.execute('ROLLBACK TO SAVEPOINT runtime_canary')
 c.execute('SAVEPOINT runtime_replace')
 with pytest.raises(Exception) as cannot_replace:c.execute('DROP FUNCTION public.read_model_executor_set_facts(text,text)')
 assert getattr(cannot_replace.value,'sqlstate',None)=='42501'
 c.execute('ROLLBACK TO SAVEPOINT runtime_replace')
 c.execute('SAVEPOINT private_cert_acl')
 with pytest.raises(Exception) as denied:c.execute('SELECT * FROM aos_model_eval_issuer_private.executor_certificate')
 assert getattr(denied.value,'sqlstate',None)=='42501'
 c.execute('ROLLBACK TO SAVEPOINT private_cert_acl')
 c.execute('SAVEPOINT wrong_runtime_manifest')
 with pytest.raises(ValueError):reader.validate_runtime_model_executor_set(c,**(args|dict(manifest_hash='f'*64)),certificates=tuple(bindings))
 c.execute('ROLLBACK TO SAVEPOINT wrong_runtime_manifest')
 with pytest.raises(ValueError):reader.validate_runtime_model_executor_set(c,**args,certificates=tuple([bindings[0]|dict(identityEpoch=2),*bindings[1:]]))
 with pytest.raises(ValueError,match='private executor-set SERIAL'):reader.validate_persisted_model_executor_set(c,**args,certificates=tuple(bindings))
 from aos_api.aip_model_eval_execution_owner import ModelEvalExecutionOwner
 from aos_api.tenant_scope import TenantScope
 assert ModelEvalExecutionOwner().validate_original_model_plan_suite(c,TenantScope('org-org','dev-project'),plan) is None
 assert c.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()==before
 c.execute('RESET ROLE');c.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
 with pytest.raises(ValueError,match='runtime executor SERIAL'):reader.validate_runtime_model_executor_set(c,**args,certificates=tuple(bindings))
 event=dict(schemaVersion='aos.model-eval-identity-withdrawal/v1',tenant=body['tenant'],identityId=plan.cases[1].judge.identity_id,eventId=nonce+'-withdraw')
 raw=encode(event)
 c.execute('INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',('org-org','dev-project',event['eventId'],event['identityId'],hashlib.sha256(raw).hexdigest(),raw))
 with pytest.raises(ValueError,match='identity'):reader.validate_persisted_model_executor_set(c,**args,certificates=tuple(bindings))
 c.execute('ROLLBACK TO SAVEPOINT original_certificate_fixture')
 assert c.execute('SELECT current_user AS role').fetchone()['role']=='aos_runtime'
