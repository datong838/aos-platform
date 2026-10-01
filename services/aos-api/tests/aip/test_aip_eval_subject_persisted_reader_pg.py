"""Subject proof reads use only the disposable session PostgreSQL database."""
import base64
import hashlib
import os
from datetime import timedelta

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aos_api.aip_eval_subject_persisted_reader import read_persisted_subject_pair
from aos_api.aip_eval_subject_proof_authority import claim_hash
from test_aip_eval_subject_signature import NOW, pair


def _json(value):
    return Jsonb(value.model_dump(mode='json', by_alias=True))


def _seed(conn, envelope, root, signed, *, omit=None, fault=None, with_report=False):
    conn.execute("INSERT INTO twa_org (id,name) VALUES ('org-org','subject-test') ON CONFLICT DO NOTHING")
    conn.execute("""INSERT INTO twa_workspace (org_id,project_id,name)
        VALUES ('org-org','dev-project','subject-test') ON CONFLICT DO NOTHING""")
    if omit != 'run':
        conn.execute("""INSERT INTO aip_eval_run
            (org_id,project_id,run_id,suite_id,suite_revision,suite_hash,target_ref,
             dataset_ref,judge_ref,status,idempotency_key,created_by,eval_contract_ref,
             subject_artifact_ref,stage_attempt_ref,gate_policy_ref,evidence_cutoff_at,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'subject-test',%s,%s,%s,%s,%s,%s)""",
            (envelope.tenant.org_id,envelope.tenant.project_id,envelope.eval_run_id,
             envelope.suite_ref.asset_id,int(envelope.suite_ref.revision),
             envelope.suite_ref.content_hash,_json(envelope.generation_skill_ref),
             Jsonb({'testOnly':True}),_json(envelope.judge_ref),
             'failed' if fault=='run_drift' else 'succeeded','subject-test-run',
             _json(envelope.contract_ref),
             Jsonb({'resourceType':'Artifact','resourceId':'other',
                    'contentHash':'f'*64}) if fault=='context_drift' else _json(envelope.subject_artifact_ref),
             _json(envelope.stage_attempt_ref),_json(envelope.policy_ref),envelope.cutoff,
             NOW-timedelta(hours=2)))
    if omit == 'run':
        return
    key=root.trust_root.public_key
    conn.execute("""INSERT INTO aip_eval_issuer_root
        (org_id,project_id,issuer_id,key_id,purpose,public_key_base64,public_key_hash,
         valid_from,valid_until,owner_ref,approval_ref,source_hash,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'subject-test',%s,%s,%s)""",
        (envelope.tenant.org_id,envelope.tenant.project_id,root.trust_root.publisher,
         root.trust_root.key_id,'eval-execution' if fault=='root_purpose' else 'subject-review',
         base64.b64encode(key).decode(),hashlib.sha256(key).hexdigest(),
         root.trust_root.not_before,root.trust_root.not_after,Jsonb({'testOnly':True}),
         'a'*64,NOW-timedelta(hours=2)))
    if omit == 'root':
        return
    for cert,receipt,_ in signed:
        key=base64.b64decode(cert.public_key_base64)
        conn.execute("""INSERT INTO aip_eval_executor_identity
            (org_id,project_id,identity_id,purpose,executor_ref,issuer_id,issuer_key_id,
             certificate_json,certificate_hash,public_key_base64,public_key_hash,
             valid_from,valid_until,owner_ref,approval_ref,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'subject-test',%s,%s)""",
            (envelope.tenant.org_id,envelope.tenant.project_id,cert.identity_id,cert.purpose,
             _json(cert.executor_ref),cert.issuer_id,cert.issuer_key_id,_json(cert),claim_hash(cert),
             cert.public_key_base64,hashlib.sha256(key).hexdigest(),cert.valid_from,cert.valid_until,
             Jsonb({'testOnly':True}),NOW-timedelta(hours=1)))
    if omit == 'identity':
        return
    for cert,receipt,_ in signed:
        if omit == 'judge' and receipt.purpose == 'judge':
            continue
        conn.execute("""INSERT INTO aip_eval_subject_receipt
            (org_id,project_id,receipt_id,eval_run_id,case_id,envelope_hash,purpose,
             identity_id,certificate_hash,claim_hash,source_receipt_hash,structure_passed,
             detail_code,occurred_at,signature_base64,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (envelope.tenant.org_id,envelope.tenant.project_id,receipt.receipt_id,
             envelope.eval_run_id,envelope.case_id,receipt.envelope_hash,receipt.purpose,
             cert.identity_id,receipt.certificate_hash,
             'f'*64 if fault=='receipt_drift' and receipt.purpose=='judge' else claim_hash(receipt),
             receipt.source_receipt_hash,receipt.structure_passed,receipt.detail_code,
             receipt.occurred_at,receipt.signature_base64,
             NOW+timedelta(minutes=2) if fault=='future_receipt' and receipt.purpose=='judge' else NOW))
    if not with_report or omit == 'judge' or fault == 'missing_report':
        return
    judge = signed[1][1]
    conn.execute("""INSERT INTO aip_eval_report_revision
        (org_id,project_id,report_id,revision,content_hash,run_id,suite_ref,
         target_ref,dataset_ref,judge_ref,results,passed,failed,total,pass_rate,
         gate_passed,created_at,eval_contract_ref,subject_artifact_ref,
         stage_attempt_ref,gate_policy_ref,evidence_cutoff_at)
        VALUES ('org-org','dev-project','subject-report',1,%s,%s,%s,%s,%s,%s,
                %s,1,0,1,1.0,true,%s,%s,%s,%s,%s,%s)""",
        ('e'*64,envelope.eval_run_id,_json(envelope.suite_ref),
         Jsonb({'assetType':'skill_template','assetId':'other','revision':'1',
                'contentHash':'0'*64}) if fault=='report_context_drift'
             else _json(envelope.generation_skill_ref),Jsonb({'testOnly':True}),
         _json(envelope.judge_ref),Jsonb([{'caseId':envelope.case_id,
             'passed':fault != 'result_drift',
             'detailCode':'wrong' if fault=='result_drift' else judge.detail_code}]),
         NOW-timedelta(minutes=1) if fault=='report_time_drift' else NOW,
         _json(envelope.contract_ref),_json(envelope.subject_artifact_ref),
         _json(envelope.stage_attempt_ref),_json(envelope.policy_ref),envelope.cutoff))
    if fault == 'missing_sidecar':
        return
    source = signed[0][1]
    conn.execute("""INSERT INTO aip_eval_subject_case_proof
        (org_id,project_id,eval_run_id,case_id,envelope_hash,report_id,
         report_revision,source_receipt_id,source_claim_hash,judge_receipt_id,
         judge_claim_hash,verified_at,created_at)
        VALUES ('org-org','dev-project',%s,%s,%s,'subject-report',1,%s,%s,%s,%s,%s,%s)""",
        (envelope.eval_run_id,envelope.case_id,source.envelope_hash,
         source.receipt_id,claim_hash(source),judge.receipt_id,
         'f'*64 if fault=='receipt_drift' else claim_hash(judge),NOW,NOW))


def _read(conn, envelope, signed, *, tenant=None, report_id='subject-report', report_hash='e'*64):
    return read_persisted_subject_pair(
        conn, expected_envelope=envelope, expected_tenant=tenant or envelope.tenant,
        expected_report_id=report_id, expected_report_revision=1,
        expected_report_hash=report_hash,
        now=NOW+timedelta(minutes=1),source_certificate=signed[0][0],
        source_receipt=signed[0][1],judge_certificate=signed[1][0],judge_receipt=signed[1][1],
    )


@pytest.mark.parametrize('fault',['valid','missing_run','missing_root','missing_identity',
    'missing_judge','wrong_role','cross_tenant','wrong_isolation','revoked','root_revoked',
    'run_drift','context_drift','receipt_drift','future_receipt','root_purpose',
    'missing_report','missing_sidecar','result_drift','report_context_drift',
    'report_time_drift','wrong_report','wrong_hash'])
def test_exact_persisted_subject_authority(fault):
    dsn=os.environ['AOS_DATABASE_URL']
    with psycopg.connect(dsn) as conn:
        assert conn.info.dbname.startswith('aos_test_') and conn.info.dbname.endswith('_ti4_test')
        envelope,root,signed,_=pair()
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        _seed(conn,envelope,root,signed,omit={
            'missing_run':'run','missing_root':'root','missing_identity':'identity',
            'missing_judge':'judge'}.get(fault),fault=fault,with_report=True)
        if fault=='revoked':
            conn.execute("""INSERT INTO aip_eval_authority_revocation
                (org_id,project_id,event_id,identity_id,revoked_at,owner_ref,approval_ref,reason_hash)
                VALUES ('org-org','dev-project','subject-test-revoke','judge',%s,
                        'subject-test',%s,%s)""",(NOW,Jsonb({'testOnly':True}),'f'*64))
        elif fault=='root_revoked':
            conn.execute("""INSERT INTO aip_eval_authority_revocation
                (org_id,project_id,event_id,issuer_id,issuer_key_id,revoked_at,
                 owner_ref,approval_ref,reason_hash)
                VALUES ('org-org','dev-project','subject-test-root-revoke','issuer','root',%s,
                        'subject-test',%s,%s)""",(NOW,Jsonb({'testOnly':True}),'f'*64))
        if fault!='wrong_role':
            conn.execute('SET LOCAL ROLE aos_runtime')
        conn.execute("SELECT set_config('aos.org_id',%s,true)",
                     ('dev-org' if fault=='cross_tenant' else 'org-org',))
        conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
        if fault=='wrong_isolation':
            conn.rollback()
            conn.execute('SET LOCAL ROLE aos_runtime')
            conn.execute("SELECT set_config('aos.org_id','org-org',true)")
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            with pytest.raises(ValueError): _read(conn,envelope,signed)
        elif fault=='valid':
            result=_read(conn,envelope,signed)
            assert result.structure_passed is True
        else:
            with pytest.raises(ValueError):
                _read(conn,envelope,signed,
                    report_id='other-report' if fault=='wrong_report' else 'subject-report',
                    report_hash='0'*64 if fault=='wrong_hash' else 'e'*64)
        conn.rollback()
