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
