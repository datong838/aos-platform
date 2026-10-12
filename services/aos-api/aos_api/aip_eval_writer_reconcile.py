"""Read-only exact reconciliation after an unknown Skill Eval writer outcome."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

import psycopg
from psycopg.rows import dict_row

from aos_api.aip_eval_contracts import EvalReportRevision
from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from aos_api.aip_eval_report_proof_reader import (
    PresentedEvalCaseProof, VerifiedSkillEvalReportProof,
    read_verified_skill_eval_report,
)


@dataclass(frozen=True)
class EvalWriterReconciliation:
    state: Literal["COMPLETE", "UNKNOWN"]
    proof: VerifiedSkillEvalReportProof | None = None


def reconcile_signed_skill_eval_report(
    conn: psycopg.Connection,
    *,
    report: EvalReportRevision,
    expected_input_hashes: Mapping[str, str],
    presented: Mapping[str, PresentedEvalCaseProof],
) -> EvalWriterReconciliation:
    """Only exact complete proof is conclusive; UNKNOWN never permits resend."""
    unknown = EvalWriterReconciliation(state="UNKNOWN")
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            context = cur.execute("""SELECT current_user AS role,
                current_setting('aos.org_id',true) AS org_id,
                current_setting('aos.project_id',true) AS project_id,
                current_setting('transaction_isolation') AS isolation,
                current_setting('transaction_read_only') AS read_only,
                transaction_timestamp() AS evaluated_at""").fetchone()
        if (
            context["role"] != "aos_runtime"
            or (context["org_id"], context["project_id"])
                != (report.tenant.org_id, report.tenant.project_id)
            or context["isolation"] not in ("repeatable read", "serializable")
            or context["read_only"] != "on"
        ):
            return unknown
        proof = read_verified_skill_eval_report(
            conn, report=report, evaluated_at=context["evaluated_at"],
            expected_input_hashes=expected_input_hashes, presented=presented,
        )
    except (EvalExecutionRejected, psycopg.Error):
        return unknown
    return EvalWriterReconciliation(state="COMPLETE", proof=proof)


def reconcile_signed_skill_eval_intent(
    conn: psycopg.Connection,
    *,
    report: EvalReportRevision,
    expected_input_hashes: Mapping[str, str],
    presented: Mapping[str, PresentedEvalCaseProof],
    intent_id: str,
    expected_request_hash: str,
    expected_intent_version: int,
    expected_run_version: int,
) -> EvalWriterReconciliation:
    """Read complete proof AND its causal dispatch journal; never authorize resend.

    COMPLETE is exact registration evidence at this snapshot, not authority to
    execute, publish, release budget, or declare a business first chain.
    """
    unknown = EvalWriterReconciliation(state="UNKNOWN")
    if (type(expected_intent_version) is not int or expected_intent_version < 1
            or type(expected_run_version) is not int or expected_run_version < 1):
        return unknown
    original = reconcile_signed_skill_eval_report(
        conn, report=report, expected_input_hashes=expected_input_hashes,
        presented=presented,
    )
    if original.state != "COMPLETE":
        return unknown
    scope = (report.tenant.org_id, report.tenant.project_id)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            intent = cur.execute("""SELECT run_id,request_hash,version FROM aip_skill_eval_intent
                WHERE org_id=%s AND project_id=%s AND intent_id=%s""", (*scope,intent_id)).fetchone()
            run = cur.execute("""SELECT version FROM aip_eval_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s""", (*scope,report.run_id)).fetchone()
            if (intent is None or run is None or intent["run_id"] != report.run_id
                    or intent["request_hash"] != expected_request_hash
                    or intent["version"] != expected_intent_version
                    or run["version"] != expected_run_version):
                return unknown
            rows = cur.execute("""SELECT d.case_id,d.purpose,d.input_hash,d.created_at,
                o.result_hash,o.observed_at FROM aip_skill_eval_dispatch d
                LEFT JOIN aip_skill_eval_dispatch_observation o
                ON o.org_id=d.org_id AND o.project_id=d.project_id
                  AND o.dispatch_id=d.dispatch_id AND o.state='result_observed'
                WHERE d.org_id=%s AND d.project_id=%s AND d.intent_id=%s""", (*scope,intent_id)).fetchall()
        expected = {(result.case_id,purpose) for result in report.results for purpose in ("target","judge")}
        indexed = {(row["case_id"],row["purpose"]):row for row in rows}
        if len(rows) != len(expected) or set(indexed) != expected:
            return unknown
        for result in report.results:
            pair = presented[result.case_id]
            for receipt in (pair.target_receipt,pair.judge_receipt):
                row = indexed[(result.case_id,receipt.purpose)]
                if (row["observed_at"] is None
                        or row["input_hash"] != receipt.input_hash
                        or row["result_hash"] != receipt.output_hash
                        or not row["created_at"] <= receipt.occurred_at <= row["observed_at"] <= report.created_at):
                    return unknown
            if indexed[(result.case_id,"target")]["observed_at"] > indexed[(result.case_id,"judge")]["created_at"]:
                return unknown
    except psycopg.Error:
        return unknown
    return original
