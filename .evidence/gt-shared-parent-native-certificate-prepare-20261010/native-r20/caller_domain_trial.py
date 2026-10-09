"""Actual other backend and valid old-domain signature; no authority repair."""
import base64,copy,json,hashlib
from pathlib import Path
from datetime import datetime
import psycopg,pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from cryptography.exceptions import InvalidSignature
from aos_api.tenant_scope import TenantScope,apply_transaction_scope
from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
from aos_api.aip_model_eval_execution_contracts import canonical_shared_parent_certificate_signing_bytes
from shared_identity_certificate_fixture import ROOT_KEY,public

def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def verify_caller_domain(conn,params,command,manifest,description,proof,evidence_dir):
    packet=_consumption_packet(command);source=Jsonb(command.source_ref.model_dump(mode='json',by_alias=True))
    def fact(c):return dict(c.execute("SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,session_user AS session_user,current_setting('role') AS role,current_setting('transaction_isolation') AS isolation,current_setting('TimeZone') AS timezone,current_setting('aos.org_id') AS org_id,current_setting('aos.project_id') AS project_id").fetchone())
    before=fact(conn);assert (before['xid'],before['pid'])==(description.immutable.caller_xid,description.immutable.caller_pid)
    from aos_api.aip_model_eval_execution_contracts import ModelSharedParentRiskSignedCertificateEnvelope
    certificates=[ModelSharedParentRiskSignedCertificateEnvelope.model_validate(x).model_dump(mode='json',by_alias=True) for x in proof['certificates']];args=(packet,source,description.plan_id,description.content_hash,encoded(certificates));rejections=[]
    with psycopg.connect(**params,row_factory=dict_row) as other:
        other.isolation_level=psycopg.IsolationLevel.SERIALIZABLE
        other.execute("SET LOCAL TimeZone='UTC'");apply_transaction_scope(other,TenantScope('org-org','dev-project'))
        identity=fact(other)
        assert identity['xid']!=before['xid'] and identity['pid']!=before['pid'] and other.pgconn.used_password
        assert all(identity[k]==before[k] for k in ('session_user','role','isolation','timezone','org_id','project_id'))
        with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_DESCRIPTION_RISK_ORIGIN_REQUIRED') as exc:
            with other.transaction():other.execute('SELECT public.prepare_model_shared_parent_certificate_set(%s,%s::jsonb,%s::uuid,%s,%s)',args)
        assert exc.value.diag.message_primary=='SHARED_DESCRIPTION_RISK_ORIGIN_REQUIRED' and exc.value.sqlstate=='23514'
        with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_EXECUTOR_MANIFEST_REQUIRED'):
            with other.transaction():other.execute('SELECT public.read_model_shared_parent_executor_set_facts(%s,%s,%s,%s)',(manifest['executionId'],description.immutable.manifest_hash,description.content_hash,description.immutable.original_risk_hash))
        other.rollback();rejections.append(dict(name='other_native_backend_original_origin',sqlstate=exc.value.sqlstate,message=exc.value.diag.message_primary,caller=identity,scram_password_used=True,manifest_absent=True,transaction_rolled_back=True))
    with conn.transaction(force_rollback=True):
        control=conn.execute('SELECT public.prepare_model_shared_parent_certificate_set(%s,%s::jsonb,%s::uuid,%s,%s) AS fact',args).fetchone()['fact']
        assert len(control['metadata']['certificates'])==4 and control['executionAllowed'] is False
    with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_EXECUTOR_MANIFEST_REQUIRED'):
        with conn.transaction():conn.execute('SELECT public.read_model_shared_parent_executor_set_facts(%s,%s,%s,%s)',(manifest['executionId'],description.immutable.manifest_hash,description.content_hash,description.immutable.original_risk_hash))
    changed=copy.deepcopy(certificates)
    raw=canonical_shared_parent_certificate_signing_bytes(description,changed[0]['certificate'])
    old=raw.replace(b'AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3\n',b'AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v2\n',1)
    assert old!=raw
    signature=ROOT_KEY.sign(old);ROOT_KEY.public_key().verify(signature,old)
    with pytest.raises(InvalidSignature):ROOT_KEY.public_key().verify(signature,raw)
    changed[0]['signatureBase64']=base64.b64encode(signature).decode()
    assert changed[0]['certificate']==certificates[0]['certificate'] and changed[1:]==certificates[1:]
    assert changed[0]['schemaVersion']==certificates[0]['schemaVersion']
    now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    cert=changed[0]['certificate'];root=proof['presented_root'];until=datetime.fromisoformat(cert['validUntil'])
    assert datetime.fromisoformat(cert['validFrom'])<=now<until and now<datetime.fromisoformat(root['validUntil']) and now<datetime.fromisoformat(manifest['judgeRequest']['expiresAt'])
    with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_CERTIFICATE_SIGNATURE_OR_TIME_REQUIRED') as exc:
        with conn.transaction():conn.execute('SELECT public.prepare_model_shared_parent_certificate_set(%s,%s::jsonb,%s::uuid,%s,%s)',(packet,source,description.plan_id,description.content_hash,encoded(changed)))
    after_clock=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'];assert after_clock<until
    assert exc.value.sqlstate=='23514' and exc.value.diag.message_primary=='SHARED_CERTIFICATE_SIGNATURE_OR_TIME_REQUIRED'
    rejections.append(dict(name='valid_old_domain_signature',sqlstate=exc.value.sqlstate,message=exc.value.diag.message_primary,old_domain_crypto_valid=True,v3_domain_crypto_invalid=True,canonical_v3_sql_positive_control=True,only_signature_changed=True,before_clock=now.isoformat(),after_clock=after_clock.isoformat(),certificate_until=until.isoformat(),certificate_set_sha256=hashlib.sha256(encoded(changed)).hexdigest()))
    with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_EXECUTOR_MANIFEST_REQUIRED'):
        with conn.transaction():conn.execute('SELECT public.read_model_shared_parent_executor_set_facts(%s,%s,%s,%s)',(manifest['executionId'],description.immutable.manifest_hash,description.content_hash,description.immutable.original_risk_hash))
    assert fact(conn)==before and conn.info.transaction_status==psycopg.pq.TransactionStatus.INTRANS
    (Path(evidence_dir)/'caller-domain-proof.json').open('x').write(json.dumps(dict(original_caller=before,rejections=rejections,original_caller_unchanged=True,manifest_absent_after_negatives=True,execution_allowed=False,root_provenance_verified=False,full_task_delivered=False),indent=2)+'\n')
