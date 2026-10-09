"""Invoked by the owned fresh Source native node, never a formal root writer."""
import copy
import hashlib
import json
import os
import queue
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from aos_api.aip_contracts import TenantContext
from aos_api import aip_model_eval_execution_authority as authority
from aos_api import aip_model_shared_parent_certificate_identity as api
from aos_api.db import get_dsn


def test_artifact_keeps_runtime_denied():
    text = '\n'.join(api.shared_parent_identity_statements())
    assert 'GRANT ' not in text and 'SECURITY DEFINER' not in text
    assert 'FORCE ROW LEVEL SECURITY' in text
    assert 'identity_epoch' in text and 'shared_parent_certificate_identity_binding' in text
    assert 'aos.model-eval-shared-parent-signed-certificate-envelope/v3' in text
    assert 'aos.model-eval-signed-certificate-envelope/v1' not in text


def verify_native_shared_parent_identity(description, proof, evidence_dir):
    def encode(v):
        return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    def digest(v):return hashlib.sha256(encode(v)).hexdigest()
    def owned(role=authority.ISSUER_OWNER):
        c=psycopg.connect(get_dsn(),row_factory=dict_row)
        c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
        c.execute("SET LOCAL TimeZone='UTC'")
        c.execute('SET LOCAL ROLE '+role)
        c.execute("SET LOCAL aos.org_id='org-org'")
        c.execute("SET LOCAL aos.project_id='dev-project'")
        return c
    from aos_api.aip_model_eval_execution_contracts import ModelEvalIssuerVerificationInput,ModelSharedParentRiskSignedCertificateEnvelope
    plan=description['immutable']['manifest']
    root=ModelEvalIssuerVerificationInput.model_validate(proof['presented_root']).model_dump(mode='json',by_alias=True)
    certs=[ModelSharedParentRiskSignedCertificateEnvelope.model_validate(v).model_dump(mode='json',by_alias=True) for v in proof['certificates']]
    tenant=TenantContext.model_validate(plan['tenant']);args=[]
    negatives=[]
    with owned(authority.OWNER) as c:
        c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',
            ('org-org','dev-project',plan['executionId'],digest(plan),encode(plan)))
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE '+authority.ISSUER_OWNER)
        c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',
            ('org-org','dev-project',root['issuerId'],root['issuerKeyId'],'a'*64,digest(root),encode(root)))
        c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',
            ('org-org','dev-project',root['issuerId'],root['issuerKeyId'],digest(root)))
        for envelope in certs:
            cert=envelope['certificate']
            c.execute('INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',
                ('org-org','dev-project',plan['executionId'],cert['caseId'],cert['purpose'],root['issuerId'],root['issuerKeyId'],digest(envelope),encode(envelope)))
            values=dict(expected_tenant=tenant,description=description,certificate_hash=digest(envelope),root_hash=digest(root),expected_root_epoch=1,expected_certificate_epoch=1)
            # The old domain cannot derive a v3 identity, even with real bytes.
            with c.transaction(force_rollback=True):
                with pytest.raises(psycopg.errors.InsufficientPrivilege,match='MODEL_IDENTITY_CERTIFICATE_BINDING'):
                    c.execute('INSERT INTO aos_model_eval_issuer_private.certificate_identity_binding(org_id,project_id,certificate_hash) VALUES (%s,%s,%s)',
                        ('org-org','dev-project',digest(envelope)))
            api.register_persisted_shared_parent_identity(c,**values)
            before=c.execute('SELECT version FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id=%s',(cert['leg']['identityId'],)).fetchone()
            api.register_persisted_shared_parent_identity(c,**values)
            assert before==c.execute('SELECT version FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id=%s',(cert['leg']['identityId'],)).fetchone()
            api.validate_persisted_shared_parent_identity(c,expected_identity_epoch=1,**values)
            args.append(values)
        producer=c.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid'];c.commit()
    with owned() as c:
        for values in args:api.validate_persisted_shared_parent_identity(c,expected_identity_epoch=1,**values)
        c.rollback()
    first=args[0];identity=certs[0]['certificate']['leg']['identityId']
    for label,change in [('root_hash',dict(root_hash='f'*64)),('certificate_hash',dict(certificate_hash='f'*64)),
            ('root_epoch',dict(expected_root_epoch=2)),('certificate_epoch',dict(expected_certificate_epoch=2)),
            ('epoch_bool',dict(expected_root_epoch=True)),('canary',dict(expected_tenant=TenantContext(orgId='dev-org',projectId='dev-project')))]:
        with owned() as c:
            with pytest.raises(ValueError):api.validate_persisted_shared_parent_identity(c,expected_identity_epoch=1,**(first|change))
            c.rollback();negatives.append(label)
    with owned() as c:
        with pytest.raises(ValueError):api.validate_persisted_shared_parent_identity(c,expected_identity_epoch=True,**first)
        c.rollback();negatives.append('identity_epoch_bool')
    for field in ('callerXid','callerPid','originalRiskHash'):
        changed=copy.deepcopy(description)
        v=changed['immutable']
        if field=='callerPid':v[field]+=1
        elif field=='callerXid':v[field]=str(int(v[field])+1)
        else:v[field]='sha256:'+'e'*64
        changed['contentHash']='sha256:'+digest(v)
        with owned() as c:
            with pytest.raises(ValueError):api.validate_persisted_shared_parent_identity(c,expected_identity_epoch=1,**(first|dict(description=changed)))
            c.rollback();negatives.append('description_'+field)
    with owned('aos_runtime') as c:
        with pytest.raises(ValueError):api.validate_persisted_shared_parent_identity(c,expected_identity_epoch=1,**first)
        c.rollback();negatives.append('runtime_reader_denied')
    with owned() as c:
        for statement in (f"UPDATE {api.TABLE} SET caller_pid=caller_pid+1",f'DELETE FROM {api.TABLE}',f'TRUNCATE {api.TABLE}'):
            with c.transaction(force_rollback=True):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):c.execute(statement)
        c.rollback();negatives.append('binding_immutable')
    # These are client-description negatives, not newly prepared physical origins.
    # Real signatures isolate original global key/purpose/revocation gates.
    def variant(c, mode):
        import base64
        from uuid import uuid4
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
        from aos_api.aip_model_eval_execution_contracts import canonical_shared_parent_certificate_signing_bytes
        d=copy.deepcopy(description);m=d['immutable']['manifest'];m['executionId']=str(uuid4());d['planId']=m['executionId'];d['immutable']['planId']=m['executionId']
        leg=m['cases'][0]['target'];public=certs[0]['certificate']['publicKeyBase64']
        if mode=='key':
            raw=Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
            leg['identityKeyHash']=hashlib.sha256(raw).hexdigest();public=base64.b64encode(raw).decode()
        elif mode=='purpose':
            leg['identityId']=certs[1]['certificate']['leg']['identityId'];leg['identityKeyHash']=certs[1]['certificate']['leg']['identityKeyHash'];public=certs[1]['certificate']['publicKeyBase64']
        d['immutable']['manifestHash']=digest(m);d['contentHash']='sha256:'+digest(d['immutable'])
        key=Ed25519PrivateKey.generate();r=copy.deepcopy(root);r['issuerId']='v3-negative-'+mode;r['issuerKeyId']='v3-negative-key-'+mode
        r['publicKeyBase64']=base64.b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
        claim=copy.deepcopy(certs[0]['certificate']);claim.update(executionId=m['executionId'],manifestHash=digest(m),descriptionHash=d['contentHash'],leg=leg,issuerId=r['issuerId'],issuerKeyId=r['issuerKeyId'],publicKeyBase64=public)
        e=dict(schemaVersion='aos.model-eval-shared-parent-signed-certificate-envelope/v3',certificate=claim,signatureBase64=base64.b64encode(key.sign(canonical_shared_parent_certificate_signing_bytes(d,claim))).decode())
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE '+authority.OWNER)
        c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',('org-org','dev-project',m['executionId'],digest(m),encode(m)))
        c.execute('RESET ROLE');c.execute('SET LOCAL ROLE '+authority.ISSUER_OWNER)
        c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',('org-org','dev-project',r['issuerId'],r['issuerKeyId'],'a'*64,digest(r),encode(r)))
        c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',('org-org','dev-project',r['issuerId'],r['issuerKeyId'],digest(r)))
        c.execute('INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',('org-org','dev-project',m['executionId'],claim['caseId'],'target',r['issuerId'],r['issuerKeyId'],digest(e),encode(e)))
        values=dict(expected_tenant=tenant,description=d,certificate_hash=digest(e),root_hash=digest(r),expected_root_epoch=1,expected_certificate_epoch=1)
        if mode=='deadline':return values
        with pytest.raises(ValueError,match='registration rejected'):
            api.register_persisted_shared_parent_identity(c,**values)
    for mode in ('key','purpose'):
        with owned() as c:
            with c.transaction(force_rollback=True):variant(c,mode)
            c.rollback();negatives.append('native_global_identity_'+mode+'_rebind_rejected')
    # Original global identity withdrawal reaches v3; rollback preserves later wait probe.
    withdrawal=dict(schemaVersion='aos.model-eval-identity-withdrawal/v1',tenant=plan['tenant'],identityId=identity,eventId='v3-test-identity-withdrawal')
    with owned() as c:
        c.execute('INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',
            ('org-org','dev-project',withdrawal['eventId'],identity,digest(withdrawal),encode(withdrawal)))
        with pytest.raises(ValueError,match='revoked'):api.validate_persisted_shared_parent_identity(c,expected_identity_epoch=1,**first)
        with c.transaction(force_rollback=True):variant(c,'revive')
        c.rollback();negatives.append('original_identity_withdrawal');negatives.append('native_global_identity_revive_rejected')
    for kind in ('certificate','root'):
        with owned() as c:
            if kind=='certificate':c.execute('UPDATE aos_model_eval_issuer_private.certificate_epoch SET epoch=epoch+1,active_hash=NULL WHERE certificate_hash=%s',(first['certificate_hash'],))
            else:c.execute('UPDATE aos_model_eval_issuer_private.issuer_epoch SET epoch=epoch+1,root_hash=NULL WHERE issuer_id=%s AND key_id=%s',(root['issuerId'],root['issuerKeyId']))
            with pytest.raises(ValueError):api.validate_persisted_shared_parent_identity(c,expected_identity_epoch=1,**first)
            c.rollback();negatives.append(kind+'_withdrawal_head')
    # A reader retains actual identity SHARE lock; rival native UPDATE is observed blocked.
    ready=queue.Queue()
    def rival():
        with owned() as c:
            pid=c.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'];ready.put(pid)
            c.execute('INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',
                ('org-org','dev-project',withdrawal['eventId'],identity,digest(withdrawal),encode(withdrawal)))
            c.rollback();return pid
    with owned() as consumer,ThreadPoolExecutor(max_workers=1) as pool:
        api.validate_persisted_shared_parent_identity(consumer,expected_identity_epoch=1,**first)
        pid=consumer.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
        future=pool.submit(rival);rival_pid=ready.get(timeout=5)
        try:
            with psycopg.connect(get_dsn(),autocommit=True,row_factory=dict_row) as observer:
                limit=time.monotonic()+5
                while observer.execute('SELECT pg_blocking_pids(%s) AS pids',(rival_pid,)).fetchone()['pids'] != [pid]:
                    assert time.monotonic()<limit and not future.done();time.sleep(.02)
        finally:consumer.rollback()
        assert future.result(timeout=5)==rival_pid
    with owned() as c:
        deadline_args=variant(c,'deadline');c.commit()
    with owned() as c:
        before_version=c.execute('SELECT version FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id=%s',(identity,)).fetchone()['version'];c.rollback()
    register_ready=queue.Queue()
    def wait_register():
        with owned() as c:
            before=c.execute('SELECT pg_backend_pid() AS pid,pg_current_xact_id()::text AS xid,clock_timestamp() AS now').fetchone();register_ready.put(before)
            with pytest.raises(ValueError,match='current contained v3 certificate interval'):
                api.register_persisted_shared_parent_identity(c,**deadline_args)
            # Deliberately commit after rejection: failed binding must be absent.
            assert c.execute('SELECT count(*) AS n FROM '+api.TABLE+' WHERE certificate_hash=%s',(deadline_args['certificate_hash'],)).fetchone()['n']==0
            c.commit();return before
    # A real identity-lock wait crosses the signed certificate end, no clock patch.
    from datetime import datetime
    end=datetime.fromisoformat(certs[0]['certificate']['validUntil'])
    waited_ready=queue.Queue()
    def wait_reader():
        with owned() as c:
            before=c.execute('SELECT pg_backend_pid() AS pid,pg_current_xact_id()::text AS xid,clock_timestamp() AS now').fetchone()
            waited_ready.put(before)
            with pytest.raises(ValueError,match='current contained v3 certificate interval'):
                api.validate_persisted_shared_parent_identity(c,expected_identity_epoch=1,**first)
            after=c.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            c.rollback();return before,after
    with owned() as blocker,ThreadPoolExecutor(max_workers=2) as pool:
        blocker.execute('SELECT 1 FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id=%s FOR UPDATE',(identity,))
        blocking_pid=blocker.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
        future=pool.submit(wait_reader);waiting=waited_ready.get(timeout=5)
        reg_future=pool.submit(wait_register);register_waiting=register_ready.get(timeout=5)
        try:
            with psycopg.connect(get_dsn(),autocommit=True,row_factory=dict_row) as observer:
                limit=time.monotonic()+5
                while observer.execute('SELECT pg_blocking_pids(%s) AS pids',(waiting['pid'],)).fetchone()['pids'] != [blocking_pid]:
                    assert time.monotonic()<limit and not future.done();time.sleep(.02)
                while True:
                    registration_blockers=observer.execute('SELECT pg_blocking_pids(%s) AS pids',(register_waiting['pid'],)).fetchone()['pids']
                    reader_blockers=observer.execute('SELECT pg_blocking_pids(%s) AS pids',(waiting['pid'],)).fetchone()['pids']
                    if blocking_pid in registration_blockers or (waiting['pid'] in registration_blockers and blocking_pid in reader_blockers):break
                    assert time.monotonic()<limit and not reg_future.done();time.sleep(.02)
                (Path(evidence_dir)/'dual-wait-graph.json').open('x').write(json.dumps(dict(registration_pid=register_waiting['pid'],registration_blockers=registration_blockers,reader_pid=waiting['pid'],reader_blockers=reader_blockers,blocker_pid=blocking_pid),indent=2)+'\n')
                assert waiting['now']<end
                while observer.execute('SELECT clock_timestamp() AS now').fetchone()['now']<end:
                    time.sleep(.02)
        finally:blocker.rollback()
        waited,after=future.result(timeout=5);assert after>=end
        failed_registration=reg_future.result(timeout=5)
    negatives.append('native_lock_wait_expired_certificate')
    negatives.append('failed_registration_commit_has_no_binding_or_identity_change')
    out=dict(producer_xid=producer,positive_certificates=4,negative_cases=negatives,
        reader_lock_blocks_identity_withdrawal=True,consumer_pid=pid,rival_pid=rival_pid,
        failed_registration=dict(caller_xid=failed_registration['xid'],caller_pid=failed_registration['pid'],certificate_hash=deadline_args['certificate_hash']),
        actual_wait=dict(before=waited['now'].isoformat(),after=after.isoformat(),certificate_end=end.isoformat(),caller_xid=waited['xid'],waiting_pid=waited['pid'],blocking_pid=blocking_pid),
        root_provenance_verified=False,physical_description_native_origin_proven=False,execution_allowed=False,
        full_task_delivered=False,test_owned_metadata=True)
    with psycopg.connect(get_dsn(),row_factory=dict_row) as c:
        assert c.execute('SELECT pg_xact_status(%s::xid8) AS status',(producer,)).fetchone()['status']=='committed'
        assert c.execute('SELECT pg_xact_status(%s::xid8) AS status',(failed_registration['xid'],)).fetchone()['status']=='committed'
        assert c.execute('SELECT version FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id=%s',(identity,)).fetchone()['version']==before_version
        assert c.execute('SELECT count(*) AS n FROM '+api.TABLE+' WHERE certificate_hash=%s',(deadline_args['certificate_hash'],)).fetchone()['n']==0
        out['binding_count']=c.execute('SELECT count(*) AS n FROM '+api.TABLE).fetchone()['n'];assert out['binding_count']==4
        out['runtime_table_access']=c.execute("SELECT has_table_privilege('aos_runtime',%s,'SELECT') AS read,has_table_privilege('aos_runtime',%s,'INSERT') AS write",(api.TABLE,api.TABLE)).fetchone();assert not any(out['runtime_table_access'].values())
    (Path(evidence_dir)/'native-identity-proof.json').open('x').write(json.dumps(out,indent=2)+'\n')
