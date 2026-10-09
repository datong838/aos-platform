"""Delay only after four genuine validations; product reads its own final clock."""
from pathlib import Path
import json,time,hashlib
from datetime import datetime
import pytest,psycopg
from aos_api import aip_shared_parent_executor_set_reader as reader
from aos_api.aip_shared_parent_certificate_prepare import prepare_shared_parent_certificate_set
from aos_api.aip_model_eval_execution_owner import ModelEvalOwnerRejected
from aos_api.tenant_scope import TenantScope

def verify_final_expiry(conn,command,manifest,description,proof,policy,evidence_dir):
    scope=TenantScope('org-org','dev-project')
    original=reader.validate_shared_parent_certificate_signature
    calls=[];termination=[];waits=[]
    def checked(*args,**kw):
        cert=args[1];now=kw['checked_at']
        try:result=original(*args,**kw)
        except ValueError as exc:
            termination.append(dict(call=len(calls)+1,checked_at=now.isoformat(),reason=str(exc)))
            raise
        calls.append(dict(call=len(calls)+1,checked_at=now.isoformat(),certificate_until=cert.certificate.valid_until.isoformat()))
        if len(calls)==4:
            end=cert.certificate.valid_until
            before=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            assert before<end
            bound=kw['issuer_input'].valid_until
            request_end=datetime.fromisoformat(manifest['judgeRequest']['expiresAt'])
            assert end<bound and end<request_end
            while True:
                current=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                if current>=end:break
                time.sleep(min(1.0,max(.01,(end-current).total_seconds())))
            assert current<bound and current<request_end
            waits.append(dict(before=before.isoformat(),after=current.isoformat(),certificate_until=end.isoformat(),root_until=bound.isoformat(),request_until=request_end.isoformat(),clock_mocked=False,checked_at_overridden=False))
        return result
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(reader,'validate_shared_parent_certificate_signature',checked)
        with pytest.raises(ModelEvalOwnerRejected,match='SHARED_CERTIFICATE_NATIVE_PREPARATION_REQUIRED'):
            prepare_shared_parent_certificate_set(conn,scope,command,manifest,proof['certificates'],expected_content_hash=description.content_hash,**policy)
    (Path(evidence_dir)/'final-expiry-observed-before-assert.json').open('x').write(json.dumps(dict(calls=calls,waits=waits,termination=termination),indent=2)+'\n')
    assert len(calls)==4 and len(waits)==1 and len(termination)==1
    assert termination[0]['call']==5 and termination[0]['reason']=='current contained v3 certificate interval and presented issuer required'
    assert datetime.fromisoformat(termination[0]['checked_at'])>=datetime.fromisoformat(waits[0]['certificate_until'])
    live=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
    assert (live['xid'],live['pid'])==(description.immutable.caller_xid,description.immutable.caller_pid)
    assert conn.info.transaction_status==psycopg.pq.TransactionStatus.INTRANS
    with pytest.raises(psycopg.errors.CheckViolation,match='SHARED_EXECUTOR_MANIFEST_REQUIRED'):
        with conn.transaction():
            conn.execute('SELECT public.read_model_shared_parent_executor_set_facts(%s,%s,%s,%s)',(manifest['executionId'],description.immutable.manifest_hash,description.content_hash,description.immutable.original_risk_hash))
    raw=json.dumps(proof['certificates'],sort_keys=True,separators=(',',':')).encode()
    (Path(evidence_dir)/'dedicated-final-expiry-proof.json').open('x').write(json.dumps(dict(certificate_set_sha256=hashlib.sha256(raw).hexdigest(),first_validations=calls,real_clock_wait=waits[0],terminal_validation=termination[0],same_caller=dict(live),manifest_absent_after_savepoint=True,outer_transaction_live=True,root_provenance_verified=False,execution_allowed=False,full_task_delivered=False),indent=2)+'\n')
