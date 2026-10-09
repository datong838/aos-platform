"""Committed original identity withdrawal; synthetic legacy metadata is not trust."""
import base64,json,hashlib
from pathlib import Path
from datetime import datetime,timezone,timedelta
from uuid import uuid4
import pytest,psycopg
from psycopg.types.json import Jsonb
from tests.aip._runtime_guard_history_fixture import isolated_owner
from tests.aip.test_model_eval_execution_contracts import _certificate_input
from shared_identity_certificate_fixture import ROOT_KEY,EXPERIMENT_KEYS,public
from aos_api import aip_model_eval_execution_reader as reader
from aos_api.aip_model_runtime_store import canonical_hash
from aos_api.aip_contracts import TenantContext
from aos_api.aip_provider_capacity_source_consumer import _consumption_packet

def encoded(value):return json.dumps(value.model_dump(mode='json',by_alias=True) if hasattr(value,'model_dump') else value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()
def publish_and_withdraw(root,evidence_dir):
    module,original,claim,_=_certificate_input();body=original.model_dump(mode='json',by_alias=True);body['executionId']='isolated-visible-'+str(uuid4())
    leg=body['cases'][0]['target'];leg['identityId']='target-identity';leg['identityKeyHash']=digest(public(EXPERIMENT_KEYS['target']))
    plan=module.ModelEvalExecutionManifest.model_validate(body);raw_plan=encoded(plan);plan_hash=digest(raw_plan)
    now=datetime.now(timezone.utc);root_until=datetime.fromisoformat(root['validUntil']);claim.update(executionId=plan.execution_id,manifestHash=plan_hash,leg=leg,issuerId=root['issuerId'],issuerKeyId=root['issuerKeyId'],publicKeyBase64=base64.b64encode(public(EXPERIMENT_KEYS['target'])).decode(),validFrom=(now-timedelta(seconds=1)).isoformat(),validUntil=root_until.isoformat())
    signed=module.ModelEvalSignedCertificateEnvelope.model_validate(dict(schemaVersion='aos.model-eval-signed-certificate-envelope/v1',certificate=claim,signatureBase64=base64.b64encode(ROOT_KEY.sign(module.canonical_model_certificate_signing_bytes(plan,claim))).decode()))
    raw_cert=encoded(signed);cert_hash=digest(raw_cert);root_hash=digest(encoded(root));tenant=TenantContext(orgId='org-org',projectId='dev-project')
    with isolated_owner() as admin:
        admin.execute('SET LOCAL ROLE aos_model_eval_execution_owner');admin.execute("SET LOCAL aos.org_id='org-org'");admin.execute("SET LOCAL aos.project_id='dev-project'")
        admin.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,plan_hash,raw_plan))
        admin.execute('RESET ROLE');admin.execute('SET LOCAL ROLE aos_model_eval_issuer_owner')
        admin.execute('INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',('org-org','dev-project',plan.execution_id,signed.certificate.case_id,'target',root['issuerId'],root['issuerKeyId'],cert_hash,raw_cert))
        reader.register_persisted_model_identity(admin,expected_tenant=tenant,execution_id=plan.execution_id,manifest_hash=plan_hash,certificate_hash=cert_hash,root_hash=root_hash,expected_root_epoch=1,expected_certificate_epoch=1)
        before=admin.execute("SELECT epoch,version,active FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id='target-identity'").fetchone();assert dict(before)==dict(epoch=1,version=1,active=True)
        xid=admin.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
    event=dict(schemaVersion='aos.model-eval-identity-withdrawal/v1',tenant=dict(orgId='org-org',projectId='dev-project'),identityId='target-identity',eventId='isolated-withdraw-'+str(uuid4()));raw_event=encoded(event)
    with isolated_owner() as admin:
        admin.execute('SET LOCAL ROLE aos_model_eval_issuer_owner');admin.execute("SET LOCAL aos.org_id='org-org'");admin.execute("SET LOCAL aos.project_id='dev-project'")
        admin.execute('INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',('org-org','dev-project',event['eventId'],'target-identity',digest(raw_event),raw_event))
        after=admin.execute("SELECT epoch,version,active FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id='target-identity'").fetchone();assert dict(after)==dict(epoch=2,version=2,active=False)
        wxid=admin.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
    proof=dict(identity_xid=xid,withdrawal_xid=wxid,execution_id=plan.execution_id,manifest_hash=plan_hash,certificate_hash=cert_hash,root_hash=root_hash,withdrawal_event=event,withdrawal_hash=digest(raw_event),before=dict(before),after=dict(after),legacy_manifest_synthetic_not_approval=True,root_provenance_verified=False,execution_allowed=False)
    (Path(evidence_dir)/'published-identity-withdrawal.json').open('x').write(json.dumps(proof,indent=2)+'\n');return proof

def verify_withdrawn(conn,command,manifest,description,proof,published,evidence_dir):
    certificates=proof['certificates'];before=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,clock_timestamp() AS now').fetchone()
    assert (before['xid'],before['pid'])==(description.immutable.caller_xid,description.immutable.caller_pid)
    until=min(datetime.fromisoformat(x['certificate']['validUntil']) for x in certificates);assert before['now']<until
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='MODEL_IDENTITY_BOUND_OR_REVOKED') as exc:
        with conn.transaction():conn.execute('SELECT public.prepare_model_shared_parent_certificate_set(%s,%s::jsonb,%s::uuid,%s,%s)',(_consumption_packet(command),Jsonb(command.source_ref.model_dump(mode='json',by_alias=True)),description.plan_id,description.content_hash,encoded(certificates)))
    assert exc.value.sqlstate=='42501' and exc.value.diag.message_primary=='MODEL_IDENTITY_BOUND_OR_REVOKED'
    after=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,clock_timestamp() AS now').fetchone();assert after['now']<until and (before['xid'],before['pid'])==(after['xid'],after['pid'])
    with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_EXECUTOR_MANIFEST_REQUIRED'):
        with conn.transaction():conn.execute('SELECT public.read_model_shared_parent_executor_set_facts(%s,%s,%s,%s)',(manifest['executionId'],description.immutable.manifest_hash,description.content_hash,description.immutable.original_risk_hash))
    assert conn.info.transaction_status==psycopg.pq.TransactionStatus.INTRANS
    (Path(evidence_dir)/'visible-withdrawal-v3-proof.json').open('x').write(json.dumps(dict(published=published,risk_execution=manifest['executionId'],same_caller=dict(xid=before['xid'],pid=before['pid']),before_clock=before['now'].isoformat(),after_clock=after['now'].isoformat(),certificate_until=until.isoformat(),sqlstate=exc.value.sqlstate,message=exc.value.diag.message_primary,manifest_absent_after_savepoint=True,outer_transaction_live=True,execution_allowed=False,root_provenance_verified=False,full_task_delivered=False),indent=2)+'\n')
