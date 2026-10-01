"""Default-off atomic registration of signed Skill Eval evidence."""
from __future__ import annotations

from typing import Mapping

import psycopg
from psycopg.types.json import Jsonb

from aos_api.aip_eval_contracts import EvalReportRevision
from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from aos_api.aip_eval_report_proof_reader import (
    PresentedEvalCaseProof, VerifiedSkillEvalReportProof,
)
from aos_api.aip_eval_writer_authority_preflight import preflight_skill_eval_writer_authority
from aos_api.aip_eval_writer_connection import configured_eval_writer_connection


def persist_signed_skill_eval_report(
    *,
    expected_database: str,
    report: EvalReportRevision,
    expected_input_hashes: Mapping[str, str],
    presented: Mapping[str, PresentedEvalCaseProof],
) -> VerifiedSkillEvalReportProof:
    """Register one exact proof set; failure rolls back, with no retry or Gate change."""
    connector = configured_eval_writer_connection()
    if connector is None:
        raise EvalExecutionRejected("independent Eval writer identity is unavailable")
    try:
        with connector(expected_database=expected_database) as conn:
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                conn.execute("SET LOCAL ROLE aos_aip_eval_writer")
                conn.execute("SELECT set_config('aos.org_id',%s,true)",
                             (report.tenant.org_id,))
                conn.execute("SELECT set_config('aos.project_id',%s,true)",
                             (report.tenant.project_id,))
                evaluated_at = conn.execute(
                    "SELECT transaction_timestamp() AS evaluated_at"
                ).fetchone()["evaluated_at"]
                proof = preflight_skill_eval_writer_authority(
                    conn, report=report, evaluated_at=evaluated_at,
                    expected_input_hashes=expected_input_hashes, presented=presented,
                )
                scope = (report.tenant.org_id, report.tenant.project_id)
                for result, pair in zip(report.results, proof.cases, strict=True):
                    item = presented[result.case_id]
                    for cert, receipt, claim_hash in (
                        (item.target_certificate, item.target_receipt,
                         pair.target_claim_hash),
                        (item.judge_certificate, item.judge_receipt,
                         pair.judge_claim_hash),
                    ):
                        conn.execute("""INSERT INTO aip_eval_execution_receipt
                            (org_id,project_id,receipt_id,run_id,case_id,purpose,
                             identity_id,certificate_hash,suite_ref,executor_ref,
                             claim_hash,input_hash,output_hash,actual_hash,expected_hash,
                             passed,detail_code,occurred_at,signature_base64,created_at)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (*scope, receipt.receipt_id, receipt.run_id,
                             receipt.case_id, receipt.purpose, cert.identity_id,
                             receipt.certificate_hash,
                             Jsonb(receipt.suite_ref.model_dump(mode="json", by_alias=True)),
                             Jsonb(receipt.executor_ref.model_dump(mode="json", by_alias=True)),
                             claim_hash, receipt.input_hash, receipt.output_hash,
                             receipt.actual_hash, receipt.expected_hash, receipt.passed,
                             receipt.detail_code, receipt.occurred_at,
                             receipt.signature_base64, evaluated_at))
                conn.execute("""INSERT INTO aip_eval_report_revision
                    (org_id,project_id,report_id,revision,content_hash,run_id,
                     suite_ref,target_ref,dataset_ref,judge_ref,results,passed,
                     failed,total,pass_rate,gate_passed,created_at,
                     eval_contract_ref,subject_artifact_ref,stage_attempt_ref,
                     gate_policy_ref,evidence_cutoff_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (*scope, report.report_id, report.revision, report.content_hash,
                     report.run_id,
                     Jsonb(report.suite_ref.model_dump(mode="json", by_alias=True)),
                     Jsonb(report.target.model_dump(mode="json", by_alias=True)),
                     Jsonb(report.dataset.model_dump(mode="json", by_alias=True)),
                     Jsonb(report.judge.model_dump(mode="json", by_alias=True)),
                     Jsonb([case.model_dump(mode="json", by_alias=True)
                            for case in report.results]),
                     report.passed, report.failed, report.total, report.pass_rate,
                     report.gate_passed, report.created_at,
                     *(None if ref is None else Jsonb(ref.model_dump(mode="json", by_alias=True))
                       for ref in (report.eval_contract_ref, report.subject_artifact_ref,
                                   report.stage_attempt_ref, report.gate_policy_ref)),
                     report.evidence_cutoff_at))
                for result, pair in zip(report.results, proof.cases, strict=True):
                    conn.execute("""INSERT INTO aip_eval_case_execution_proof
                        (org_id,project_id,run_id,case_id,report_id,report_revision,
                         target_receipt_id,target_claim_hash,judge_receipt_id,
                         judge_claim_hash,verified_at,created_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (*scope, report.run_id, result.case_id, report.report_id,
                         report.revision, pair.target_receipt_id,
                         pair.target_claim_hash, pair.judge_receipt_id,
                         pair.judge_claim_hash, evaluated_at, evaluated_at))
        return proof
    except (psycopg.Error, RuntimeError) as exc:
        raise EvalExecutionRejected("atomic Skill Eval evidence registration failed") from exc
