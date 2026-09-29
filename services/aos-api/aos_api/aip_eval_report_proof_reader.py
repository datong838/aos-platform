"""Consume every Skill Eval Report case against persisted signed execution proof."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

import psycopg
from psycopg.rows import dict_row

from aos_api.aip_eval_contracts import (
    AssetType, EvalExecutionReceipt, EvalExecutorCertificate, EvalReportRevision,
)
from aos_api.aip_eval_execution_authority import EvalExecutionRejected, VerifiedEvalExecutionPair
from aos_api.aip_eval_persisted_authority_reader import read_persisted_execution_pair
from aos_api.aip_eval_runner import AipEvalRunner, compute_eval_report_hash
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class PresentedEvalCaseProof:
    target_certificate: EvalExecutorCertificate
    target_receipt: EvalExecutionReceipt
    judge_certificate: EvalExecutorCertificate
    judge_receipt: EvalExecutionReceipt


@dataclass(frozen=True)
class VerifiedSkillEvalReportProof:
    report_id: str
    report_hash: str
    cases: tuple[VerifiedEvalExecutionPair, ...]


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise EvalExecutionRejected(reason)


def read_verified_skill_eval_report(
    conn: psycopg.Connection,
    *,
    report: EvalReportRevision,
    evaluated_at: datetime,
    expected_input_hashes: Mapping[str, str],
    presented: Mapping[str, PresentedEvalCaseProof],
) -> VerifiedSkillEvalReportProof:
    """Read one immutable Report and all its case proofs without writing or gating."""
    _require(
        report.target.asset_type is AssetType.SKILL_TEMPLATE
        and evaluated_at.utcoffset() is not None
        and report.created_at <= evaluated_at
        and compute_eval_report_hash(report) == report.content_hash,
        "Skill Eval Report is not an exact current artifact",
    )
    scope = TenantScope(org_id=report.tenant.org_id, project_id=report.tenant.project_id)
    case_ids = [item.case_id for item in report.results]
    case_set = set(case_ids)
    _require(
        len(case_set) == len(case_ids)
        and case_set == set(expected_input_hashes)
        and case_set == set(presented),
        "Skill Eval Report case proof set drifted",
    )
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            context = cur.execute("""SELECT current_user AS role,
                current_setting('aos.org_id',true) AS org_id,
                current_setting('aos.project_id',true) AS project_id,
                current_setting('transaction_isolation') AS isolation""").fetchone()
            _require(
                context["role"] == "aos_runtime"
                and (context["org_id"], context["project_id"]) == scope.key
                and context["isolation"] in ("repeatable read", "serializable"),
                "Skill Eval tenant snapshot is unavailable",
            )
            run = cur.execute("""SELECT * FROM aip_eval_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (*scope.key, report.run_id)).fetchone()
            _require(
                run is not None and run["status"] == "succeeded"
                and run["suite_id"] == report.suite_ref.asset_id
                and str(run["suite_revision"]) == report.suite_ref.revision
                and run["suite_hash"] == report.suite_ref.content_hash
                and run["target_ref"] == report.target.model_dump(mode="json", by_alias=True)
                and run["dataset_ref"] == report.dataset.model_dump(mode="json", by_alias=True)
                and run["judge_ref"] == report.judge.model_dump(mode="json", by_alias=True),
                "Skill Eval Run is not exact and succeeded",
            )
            row = cur.execute("""SELECT * FROM aip_eval_report_revision
                WHERE org_id=%s AND project_id=%s AND report_id=%s AND revision=%s""",
                (*scope.key, report.report_id, report.revision)).fetchone()
            _require(row is not None, "persisted Skill Eval Report is unavailable")
            stored = AipEvalRunner._report_from_row(scope, row)
            _require(
                stored == report and compute_eval_report_hash(stored) == row["content_hash"],
                "persisted Skill Eval Report drifted",
            )
            proof_rows = cur.execute("""SELECT * FROM aip_eval_case_execution_proof
                WHERE org_id=%s AND project_id=%s AND run_id=%s
                  AND report_id=%s AND report_revision=%s""",
                (*scope.key, report.run_id, report.report_id, report.revision)).fetchall()
            _require(
                len(proof_rows) == len(case_ids)
                and {item["case_id"] for item in proof_rows} == case_set,
                "persisted Skill Eval case proof set is incomplete",
            )
    except psycopg.Error as exc:
        raise EvalExecutionRejected("persisted Skill Eval Report read failed") from exc
    indexed = {item["case_id"]: item for item in proof_rows}
    verified_cases: list[VerifiedEvalExecutionPair] = []
    for result in report.results:
        item = presented[result.case_id]
        pair = read_persisted_execution_pair(
            conn, evaluated_at=evaluated_at, expected_tenant=report.tenant,
            expected_run_id=report.run_id, expected_suite_ref=report.suite_ref,
            expected_case_id=result.case_id, expected_target_ref=report.target,
            expected_judge_ref=report.judge,
            expected_input_hash=expected_input_hashes[result.case_id],
            expected_expected_hash=result.expected_hash,
            target_certificate=item.target_certificate,
            target_receipt=item.target_receipt,
            judge_certificate=item.judge_certificate,
            judge_receipt=item.judge_receipt,
        )
        sidecar = indexed[result.case_id]
        _require(
            sidecar["target_receipt_id"] == pair.target_receipt_id
            and sidecar["judge_receipt_id"] == pair.judge_receipt_id
            and sidecar["target_claim_hash"] == pair.target_claim_hash
            and sidecar["judge_claim_hash"] == pair.judge_claim_hash
            and item.target_receipt.output_hash == result.actual_hash
            and item.judge_receipt.actual_hash == result.actual_hash
            and pair.passed == result.passed
            and pair.detail_code == result.detail_code
            and item.judge_receipt.expected_hash == result.expected_hash
            and sidecar["verified_at"] <= sidecar["created_at"] <= evaluated_at,
            "Skill Eval Report case result or proof drifted",
        )
        verified_cases.append(pair)
    return VerifiedSkillEvalReportProof(
        report_id=report.report_id, report_hash=report.content_hash,
        cases=tuple(verified_cases),
    )
