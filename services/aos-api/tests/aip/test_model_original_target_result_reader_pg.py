"""Necessary v2 stored proof checks, never a real transport or joint admission."""
import base64
import hashlib
import importlib
import json
import os
import queue
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from tests.aip.test_model_eval_judge_authority_pg import (
    caller, issuer_factory, https_signer, guard_issuer_factory, guard_consumer_factory,
)


def test_original_target_persisted_native_provenance(
        caller, issuer_factory, https_signer, guard_issuer_factory,
        guard_consumer_factory, tmp_path, monkeypatch):
    from aos_api import aip_model_eval_execution_contracts as contract
    from aos_api.aip_model_eval_execution_owner import ModelEvalExecutionOwner
    from aos_api import aip_model_eval_execution_authority as authority
    from aos_api.db import get_dsn
    from tests.aip.test_model_eval_judge_authority_pg import test_exact_signed_rule_new_original_suite
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    reader = importlib.import_module('aos_api.aip_model_original_target_result_reader')
    captured = []
    original = ModelEvalExecutionOwner.validate_original_target_judge_manifest

    def observe(self, conn, scope, manifest, **kwargs):
        result = original(self, conn, scope, manifest, **kwargs)
        if not captured:
            captured.append(contract.ModelEvalTargetJudgeExecutionManifest.model_validate(manifest))
        return result

    monkeypatch.setattr(ModelEvalExecutionOwner, 'validate_original_target_judge_manifest', observe)
    test_exact_signed_rule_new_original_suite(caller, issuer_factory, https_signer,
        guard_issuer_factory, guard_consumer_factory, tmp_path)
    assert len(captured) == 1
    issuer, executor = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    pub = executor.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    body = captured[0].model_dump(mode='json', by_alias=True)
    # Test-owned executor metadata only. Native applications remain unchanged.
    body['cases'][0]['target']['identityKeyHash'] = hashlib.sha256(pub).hexdigest()
    plan = contract.ModelEvalTargetJudgeExecutionManifest.model_validate(body)
    wire, output = b'{"test-only-wire":true}', '  原v2存储🙂\n'.encode()

    def encode(value):
        if hasattr(value, 'model_dump'):
            value = value.model_dump(mode='json', by_alias=True)
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()

    def digest(value):
        return hashlib.sha256(encode(value)).hexdigest()

    def owned(role=authority.ISSUER_OWNER):
        c = psycopg.connect(get_dsn(), row_factory=dict_row)
        c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE')
        c.execute('SET LOCAL ROLE ' + role)
        c.execute("SET LOCAL aos.org_id='org-org'")
        c.execute("SET LOCAL aos.project_id='dev-project'")
        return c

    with psycopg.connect(get_dsn()) as c:
        authority.install_closed_model_identity_authority(c.execute)
        for statement in authority.target_origin_statements():
            c.execute(statement)
        for statement in reader.original_target_identity_statements():
            c.execute(statement)
        c.commit()
    with owned() as c:
        now = c.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        from datetime import datetime
        end = datetime.fromisoformat(plan.judge_request['expiresAt'])
        assert now < end
        root = contract.ModelEvalIssuerVerificationInput.model_validate(dict(
            schemaVersion='aos.model-eval-issuer-verification-input/v1', purpose='model-eval-execution',
            tenant=body['tenant'], issuerId='test-v2-issuer', issuerKeyId='test-v2-root-key',
            publicKeyBase64=base64.b64encode(issuer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode(),
            validFrom=now-timedelta(seconds=5), validUntil=end+timedelta(seconds=1), revokedAt=None))
        c.execute('RESET ROLE'); c.execute('SET LOCAL ROLE ' + authority.OWNER)
        c.execute('INSERT INTO aos_model_eval_execution_private.manifest VALUES (%s,%s,%s,%s,%s)',
            ('org-org', 'dev-project', plan.execution_id, digest(plan), encode(plan)))
        c.execute('RESET ROLE'); c.execute('SET LOCAL ROLE ' + authority.ISSUER_OWNER)
        c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_root(org_id,project_id,issuer_id,key_id,bootstrap_hash,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s,%s)',
            ('org-org','dev-project',root.issuer_id,root.issuer_key_id,'a'*64,digest(root),encode(root)))
        c.execute('INSERT INTO aos_model_eval_issuer_private.issuer_epoch(org_id,project_id,issuer_id,key_id,epoch,root_hash) VALUES (%s,%s,%s,%s,1,%s)',
            ('org-org','dev-project',root.issuer_id,root.issuer_key_id,digest(root)))
        target = plan.judge_request['targetApplication']
        cert = dict(schemaVersion='aos.model-eval-original-target-certificate-signing-input/v2',
            tenant=body['tenant'], executionId=plan.execution_id, manifestHash=digest(plan),
            requestHash=target['requestHash'], caseId=plan.cases[0].case_id, purpose='target',
            candidateRef=target['request']['targetRef'], leg=body['cases'][0]['target'],
            issuerId=root.issuer_id, issuerKeyId=root.issuer_key_id,
            publicKeyBase64=base64.b64encode(pub).decode(), validFrom=now-timedelta(seconds=1), validUntil=min(end,now+timedelta(seconds=8)))
        envelope = contract.ModelOriginalTargetSignedCertificateEnvelope.model_validate(dict(
            schemaVersion='aos.model-eval-original-target-signed-certificate-envelope/v2', certificate=cert,
            signatureBase64=base64.b64encode(issuer.sign(contract.canonical_original_target_certificate_signing_bytes(plan,cert))).decode()))
        c.execute('INSERT INTO aos_model_eval_issuer_private.executor_certificate(org_id,project_id,execution_id,case_id,purpose,attempt,issuer_id,key_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)',
            ('org-org','dev-project',plan.execution_id,plan.cases[0].case_id,'target',root.issuer_id,root.issuer_key_id,digest(envelope),encode(envelope)))
        c.execute('INSERT INTO aos_model_eval_issuer_private.original_target_certificate_identity_binding(org_id,project_id,certificate_hash) VALUES (%s,%s,%s)',
            ('org-org','dev-project',digest(envelope)))
        occurred = c.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        claim = dict(schemaVersion='aos.model-eval-original-target-case-signing-input/v2',
            **{k:cert[k] for k in ('tenant','executionId','manifestHash','requestHash','caseId','purpose','candidateRef','leg')},
            caseInputHash=plan.cases[0].input_hash, inputHash=hashlib.sha256(wire).hexdigest(),
            outputHash=hashlib.sha256(output).hexdigest(), occurredAt=occurred)
        payload = dict(schemaVersion='aos.model-eval-original-target-case-signature-payload/v2', certificateHash=digest(envelope), claim=claim)
        case = contract.ModelOriginalTargetSignedCaseEnvelope.model_validate(dict(
            schemaVersion='aos.model-eval-original-target-signed-case-envelope/v2',payload=payload,
            signatureBase64=base64.b64encode(executor.sign(contract.canonical_original_target_signed_case_bytes(plan,payload,input_bytes=wire,output_bytes=output))).decode()))
        c.execute('RESET ROLE'); c.execute('SET LOCAL ROLE ' + authority.OWNER)
        c.execute('INSERT INTO aos_model_eval_execution_private.case_result VALUES (%s,%s,%s,%s,%s,1,%s,%s)',
            ('org-org','dev-project',plan.execution_id,plan.cases[0].case_id,'target',digest(case),encode(case)))
        producer = c.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        c.execute('RESET ROLE'); c.execute('SET LOCAL ROLE ' + authority.ISSUER_OWNER)
        args = dict(expected_tenant=plan.tenant, execution_id=plan.execution_id,
            manifest_hash=digest(plan), case_id=plan.cases[0].case_id,
            binding=contract.ModelEvalCasePersistenceBinding(caseHash=digest(case),certificateHash=digest(envelope),
                rootHash=digest(root),rootEpoch=1,certificateEpoch=1), expected_identity_epoch=1,
            input_bytes=wire, output_bytes=output)
        with pytest.raises(ValueError, match='committed'):
            reader.validate_persisted_original_target_case(c, **args)
        with pytest.raises(ValueError, match='committed'):
            reader.build_original_target_judge_input(c,expected_output=None,**args)
        c.commit()
    negatives = []
    with owned() as c:
        assert reader.validate_persisted_original_target_case(c, **args) is None
        expected = '  原Judge期望🙂\n保留空白  '.encode('utf-8') if plan.cases[0].expected_hash else None
        if expected is not None:
            assert hashlib.sha256(expected).hexdigest() == plan.cases[0].expected_hash
        raw = reader.build_original_target_judge_input(c,expected_output=expected,**args)
        facts = json.loads(raw)
        assert raw == encode(facts)
        assert facts['schemaVersion'] == 'aos.model-eval-original-target-judge-input/v2'
        assert facts['executionAllowed'] is False
        assert base64.b64decode(facts['actualBase64'],validate=True) == output
        assert facts['actualHash'] == hashlib.sha256(output).hexdigest()
        assert facts['targetCaseHash'] == digest(case)
        assert facts['targetCertificateHash'] == digest(envelope)
        assert facts['manifestHash'] == digest(plan)
        assert facts['judgeRequestHash'] == plan.judge_request_hash
        assert facts['judgeLeg'] == plan.cases[0].judge.model_dump(mode='json',by_alias=True)
        assert facts['expectedHash'] == plan.cases[0].expected_hash
        assert facts['expectedBase64'] == (None if expected is None else base64.b64encode(expected).decode())
        invalid_expected = [b'wrong',bytearray(b'wrong'),b'x'*1048577]
        if expected is not None:
            invalid_expected.append(None)
        for witness in invalid_expected:
            with pytest.raises(ValueError,match='expected'):
                reader.build_original_target_judge_input(c,expected_output=witness,**args)
        with pytest.raises(ValueError):
            reader.build_original_target_judge_input(c,expected_output=expected,**(args|{'output_bytes':output+b' '}))
        c.rollback()
    for fault, change in [('output',{'output_bytes':output+b' '}), ('mutable',{'input_bytes':bytearray(wire)}),
            ('case',{'case_id':'wrong-case'}), ('manifest',{'manifest_hash':'f'*64}),
            ('identity_bool',{'expected_identity_epoch':True}), ('identity_epoch',{'expected_identity_epoch':2}),
            ('canary',{'expected_tenant':type(plan.tenant)(orgId='dev-org',projectId='dev-project')}),
            *[(fault,{'binding':args['binding'].model_dump(mode='json',by_alias=True)|change}) for fault,change in
                [('case_hash',{'caseHash':'f'*64}),('root_hash',{'rootHash':'f'*64}),('certificate_hash',{'certificateHash':'f'*64}),
                 ('root_epoch',{'rootEpoch':2}),('certificate_epoch_bool',{'certificateEpoch':True})]]]:
        with owned() as c:
            with pytest.raises(ValueError): reader.validate_persisted_original_target_case(c, **(args|change))
            c.rollback(); negatives.append(fault)
    with owned('aos_runtime') as c:
        with pytest.raises(ValueError): reader.validate_persisted_original_target_case(c, **args)
        with pytest.raises(ValueError): reader.build_original_target_judge_input(c,expected_output=None,**args)
        c.rollback(); negatives.append('runtime')
    with owned() as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute('DELETE FROM aos_model_eval_issuer_private.original_target_certificate_identity_binding WHERE certificate_hash=%s',(digest(envelope),))
        c.rollback(); negatives.append('binding_immutable')
    with owned('aos_runtime') as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute('SELECT * FROM aos_model_eval_issuer_private.original_target_certificate_identity_binding')
        c.rollback(); negatives.append('binding_runtime_acl')
    with owned() as c:
        withdrawal=dict(schemaVersion='aos.model-eval-identity-withdrawal/v1',tenant=body['tenant'],
            identityId=cert['leg']['identityId'],eventId='test-v2-withdrawal')
        c.execute('INSERT INTO aos_model_eval_issuer_private.identity_withdrawal(org_id,project_id,event_id,identity_id,content_hash,body) VALUES (%s,%s,%s,%s,%s,%s)',
            ('org-org','dev-project',withdrawal['eventId'],withdrawal['identityId'],digest(withdrawal),encode(withdrawal)))
        with pytest.raises(ValueError,match='identity revoked'):
            reader.validate_persisted_original_target_case(c,**args)
        c.rollback(); negatives.append('original_global_identity_withdrawal')
    ready=queue.Queue()
    def consume():
        with owned() as c:
            caller=c.execute('SELECT pg_backend_pid() AS pid,pg_current_xact_id()::text AS xid,clock_timestamp() AS now').fetchone()
            ready.put(caller)
            with pytest.raises(ValueError,match='current contained original Target certificate interval'):
                reader.validate_persisted_original_target_case(c,**args)
            after=c.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            c.rollback()
            return caller,after
    with owned() as blocker, ThreadPoolExecutor(max_workers=1) as pool:
        blocker.execute('SELECT 1 FROM aos_model_eval_issuer_private.identity_epoch WHERE identity_id=%s FOR UPDATE',(cert['leg']['identityId'],))
        blocker_pid=blocker.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
        future=pool.submit(consume)
        current=ready.get(timeout=5)
        try:
            with psycopg.connect(get_dsn(),autocommit=True,row_factory=dict_row) as observer:
                limit=time.monotonic()+5
                while observer.execute('SELECT pg_blocking_pids(%s) AS pids',(current['pid'],)).fetchone()['pids'] != [blocker_pid]:
                    assert time.monotonic()<limit and not future.done()
                    time.sleep(.02)
                assert current['now'] < envelope.certificate.valid_until
                while observer.execute('SELECT clock_timestamp() AS now').fetchone()['now'] < envelope.certificate.valid_until:
                    time.sleep(.02)
        finally:
            blocker.rollback()
        waited,after=future.result(timeout=10)
        assert after>=envelope.certificate.valid_until
    with psycopg.connect(get_dsn(),row_factory=dict_row) as observer:
        assert observer.execute('SELECT pg_xact_status(%s::xid8) AS status',(waited['xid'],)).fetchone()['status']=='aborted'
    negatives.append('actual_identity_lock_wait_past_certificate_end')
    with owned() as c:
        c.execute('UPDATE aos_model_eval_issuer_private.certificate_epoch SET epoch=epoch+1,active_hash=NULL WHERE certificate_hash=%s', (digest(envelope),))
        c.commit()
    with owned() as c:
        with pytest.raises(ValueError,match='certificate epoch'): reader.validate_persisted_original_target_case(c, **args)
        c.rollback(); negatives.append('revoked_certificate')
    with psycopg.connect(get_dsn(),row_factory=dict_row) as c:
        assert c.execute('SELECT pg_xact_status(%s::xid8) AS status',(producer,)).fetchone()['status']=='committed'
        origin=c.execute('SELECT origin_xid::text AS xid,origin_pid AS pid FROM aos_model_eval_issuer_private.target_result_origin WHERE execution_id=%s',(plan.execution_id,)).fetchone()
        assert origin['xid']==producer
    out={'database':get_dsn().split('@')[-1], 'producer_xid':producer,'origin':origin,
        'native_committed_required':True,'negative_cases':negatives,'execution_allowed':False,
        'bootstrap_trusted':False,'actual_transport':False,'joint_admission':False,
        'test_owned_executor_metadata':True,'original_prepared_parents_committed':False}
    out['judge_input']={'schema':facts['schemaVersion'],'sha256':hashlib.sha256(raw).hexdigest(),
        'canonical':True,'actual_bytes_preserved':True,'expected_bytes_preserved':True,
        'manifest_case_certificate_and_judge_leg_bound':True,
        'invalid_expected_cases':len(invalid_expected),'wrong_actual_rejected':True,
        'uncommitted_and_runtime_rejected':True,'execution_allowed':False}
    out['actual_wait']={'caller_xid':waited['xid'],'blocked_pid':waited['pid'],'blocking_pid':blocker_pid,
        'before':waited['now'].isoformat(),'certificate_end':envelope.certificate.valid_until.isoformat(),
        'after':after.isoformat(),'reader_end_status':'aborted'}
    with (Path(os.environ['AOS_ORIGINAL_TARGET_READER_EVIDENCE'])/'native-proof.json').open('x') as f:
        json.dump(out,f,indent=2)
