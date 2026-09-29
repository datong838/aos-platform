"""Rollback-only test-only PG proof of all-case Skill Eval Report consumption."""
from __future__ import annotations

import hashlib
import os

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aos_api.aip_eval_contracts import (
    AssetRevisionRef, AssetType, DatasetRevisionRef, EvalCaseResultEvidence,
    EvalReportRevision,
)
from aos_api.aip_eval_execution_authority import (
    EvalExecutionRejected, canonical_receipt_bytes,
)
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.aip_eval_report_proof_reader import (
    PresentedEvalCaseProof, read_verified_skill_eval_report,
)
from test_aip_eval_execution_authority import (
    ACTUAL_HASH, EXPECTED_HASH, INPUT_HASH, JUDGE, NOW, SUITE, TARGET, TENANT,
    _signed_pair,
)
from test_aip_eval_persisted_authority_reader import _seed


@pytest.fixture()
def connection():
    dsn = os.getenv("AOS_BG00AF_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("isolated BG-00af PostgreSQL URL required")
    with psycopg.connect(dsn) as conn:
        assert conn.info.dbname == "aos_bg00ad_schema_v2_20260929"
        assert conn.info.port == 5433
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        yield conn
        conn.rollback()


def _report():
    policy=AssetRevisionRef(asset_type=AssetType.POLICY,asset_id="test-redaction",
                            revision="1",content_hash="7"*64)
    dataset=DatasetRevisionRef(dataset_id="test-dataset",revision=1,
                               content_hash="8"*64,source_hash="9"*64,
                               redaction_policy=policy)
    result=EvalCaseResultEvidence(case_id="case-1",passed=True,
                                  actual_hash=ACTUAL_HASH,expected_hash=EXPECTED_HASH,
                                  detail_code="exact_match",duration_ms=0)
    report=EvalReportRevision(tenant=TENANT,report_id="bg00af-report",revision=1,
        content_hash="0"*64,run_id="run-1",suite_ref=SUITE,target=TARGET,
        dataset=dataset,judge=JUDGE,results=[result],passed=1,failed=0,total=1,
        pass_rate=1.0,gate_passed=True,created_at=NOW)
    return report.model_copy(update={"content_hash":compute_eval_report_hash(report)})


def _seed_report(conn, report):
    conn.execute("""UPDATE aip_eval_run SET status='succeeded',
        target_ref=%s,dataset_ref=%s,judge_ref=%s WHERE run_id='run-1'""",
        (Jsonb(report.target.model_dump(mode='json',by_alias=True)),
         Jsonb(report.dataset.model_dump(mode='json',by_alias=True)),
         Jsonb(report.judge.model_dump(mode='json',by_alias=True))))
    conn.execute("""INSERT INTO aip_eval_report_revision
      (org_id,project_id,report_id,revision,content_hash,run_id,suite_ref,
       target_ref,dataset_ref,judge_ref,results,passed,failed,total,pass_rate,
       gate_passed,created_at)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
      (TENANT.org_id,TENANT.project_id,report.report_id,report.revision,
       report.content_hash,report.run_id,
       Jsonb(report.suite_ref.model_dump(mode="json",by_alias=True)),
       Jsonb(report.target.model_dump(mode="json",by_alias=True)),
       Jsonb(report.dataset.model_dump(mode="json",by_alias=True)),
       Jsonb(report.judge.model_dump(mode="json",by_alias=True)),
       Jsonb([item.model_dump(mode="json",by_alias=True) for item in report.results]),
       report.passed,report.failed,report.total,report.pass_rate,report.gate_passed,
       report.created_at))


def _seed_sidecar(conn, target, judge, *, bad_hash=False):
    target_hash=hashlib.sha256(canonical_receipt_bytes(target[1])).hexdigest()
    judge_hash=hashlib.sha256(canonical_receipt_bytes(judge[1])).hexdigest()
    if bad_hash:
        target_hash="f"*64
    conn.execute("""INSERT INTO aip_eval_case_execution_proof
      (org_id,project_id,run_id,case_id,report_id,report_revision,
       target_receipt_id,target_claim_hash,judge_receipt_id,judge_claim_hash,
       verified_at,created_at)
      VALUES (%s,%s,'run-1','case-1','bg00af-report',1,%s,%s,%s,%s,%s,%s)""",
      (TENANT.org_id,TENANT.project_id,target[1].receipt_id,target_hash,
       judge[1].receipt_id,judge_hash,NOW,NOW))


def _read(conn, report, target, judge):
    return read_verified_skill_eval_report(conn,report=report,evaluated_at=NOW,
       expected_input_hashes={"case-1":INPUT_HASH},
       presented={"case-1":PresentedEvalCaseProof(
           target_certificate=target[0],target_receipt=target[1],
           judge_certificate=judge[0],judge_receipt=judge[1])})


@pytest.mark.parametrize("missing", ["report", "sidecar"])
def test_missing_report_or_sidecar_rejects(connection, missing):
    root,target,judge=_signed_pair()
    _seed(connection,root,target,judge)
    report=_report()
    if missing != "report":
        _seed_report(connection,report)
    connection.execute("SET LOCAL ROLE aos_runtime")
    connection.execute("SELECT set_config('aos.org_id','org-org',true)")
    connection.execute("SELECT set_config('aos.project_id','dev-project',true)")
    with pytest.raises(EvalExecutionRejected):
        _read(connection,report,target,judge)


def test_complete_report_proof_is_read_and_wrong_input_or_tenant_rejected(connection):
    root,target,judge=_signed_pair()
    _seed(connection,root,target,judge)
    report=_report()
    _seed_report(connection,report)
    _seed_sidecar(connection,target,judge)
    connection.execute("SET LOCAL ROLE aos_runtime")
    connection.execute("SELECT set_config('aos.org_id','org-org',true)")
    connection.execute("SELECT set_config('aos.project_id','dev-project',true)")
    proof=_read(connection,report,target,judge)
    assert proof.report_id == report.report_id
    assert len(proof.cases) == 1
    with pytest.raises(EvalExecutionRejected):
        read_verified_skill_eval_report(connection,report=report,evaluated_at=NOW,
            expected_input_hashes={"case-1":"f"*64},
            presented={"case-1":PresentedEvalCaseProof(target_certificate=target[0],
              target_receipt=target[1],judge_certificate=judge[0],judge_receipt=judge[1])})
    connection.execute("SELECT set_config('aos.org_id','dev-org',true)")
    with pytest.raises(EvalExecutionRejected):
        _read(connection,report,target,judge)


@pytest.mark.parametrize("scenario", ["revoked", "report_drift", "missing_input"])
def test_current_revocation_report_drift_and_incomplete_input_reject(connection, scenario):
    root,target,judge=_signed_pair()
    _seed(connection,root,target,judge)
    report=_report()
    _seed_report(connection,report)
    _seed_sidecar(connection,target,judge)
    if scenario == "revoked":
        connection.execute("""INSERT INTO aip_eval_authority_revocation
          (org_id,project_id,event_id,identity_id,revoked_at,owner_ref,
           approval_ref,reason_hash)
          VALUES ('org-org','dev-project','bg00af-revoked',%s,%s,%s,%s,%s)""",
          (target[0].identity_id,NOW,'bg00af-test-owner',
           Jsonb({'testOnly':True}),'e'*64))
    connection.execute("SET LOCAL ROLE aos_runtime")
    connection.execute("SELECT set_config('aos.org_id','org-org',true)")
    connection.execute("SELECT set_config('aos.project_id','dev-project',true)")
    proof=PresentedEvalCaseProof(target_certificate=target[0],target_receipt=target[1],
        judge_certificate=judge[0],judge_receipt=judge[1])
    if scenario == "report_drift":
        changed=report.model_copy(update={'results':[
            report.results[0].model_copy(update={'actual_hash':'f'*64})]})
        report=changed.model_copy(update={'content_hash':compute_eval_report_hash(changed)})
    with pytest.raises(EvalExecutionRejected):
        read_verified_skill_eval_report(connection,report=report,evaluated_at=NOW,
            expected_input_hashes={} if scenario=="missing_input" else {'case-1':INPUT_HASH},
            presented={'case-1':proof})


def test_two_case_report_cannot_consume_one_sidecar(connection):
    root,target,judge=_signed_pair()
    _seed(connection,root,target,judge)
    base=_report()
    second=base.results[0].model_copy(update={'case_id':'case-2'})
    changed=base.model_copy(update={'results':[base.results[0],second],
        'passed':2,'total':2,'failed':0,'pass_rate':1.0})
    report=changed.model_copy(update={'content_hash':compute_eval_report_hash(changed)})
    _seed_report(connection,report)
    _seed_sidecar(connection,target,judge)
    connection.execute("SET LOCAL ROLE aos_runtime")
    connection.execute("SELECT set_config('aos.org_id','org-org',true)")
    connection.execute("SELECT set_config('aos.project_id','dev-project',true)")
    proof=PresentedEvalCaseProof(target_certificate=target[0],target_receipt=target[1],
        judge_certificate=judge[0],judge_receipt=judge[1])
    with pytest.raises(EvalExecutionRejected,match='incomplete'):
        read_verified_skill_eval_report(connection,report=report,evaluated_at=NOW,
            expected_input_hashes={'case-1':INPUT_HASH,'case-2':INPUT_HASH},
            presented={'case-1':proof,'case-2':proof})
