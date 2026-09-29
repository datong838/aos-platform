"""Check current signed Eval authority inside the caller's writer transaction."""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Mapping

import psycopg
from psycopg.rows import dict_row

from aos_api.aip_eval_contracts import AssetType, EvalReportRevision
from aos_api.aip_eval_execution_authority import (
    EvalExecutionRejected, EvalIssuerRoot, VerifiedEvalExecutionPair,
    certificate_hash, verify_execution_pair,
)
from aos_api.aip_eval_persisted_authority_reader import _key
from aos_api.aip_eval_report_proof_reader import (
    PresentedEvalCaseProof, VerifiedSkillEvalReportProof,
)
from aos_api.aip_eval_runner import compute_eval_report_hash


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise EvalExecutionRejected(reason)


def preflight_skill_eval_writer_authority(
    conn: psycopg.Connection,
    *,
    report: EvalReportRevision,
    evaluated_at: datetime,
    expected_input_hashes: Mapping[str, str],
    presented: Mapping[str, PresentedEvalCaseProof],
) -> VerifiedSkillEvalReportProof:
    """Read current authority before INSERT; caller must write in this transaction."""
    _require(
        report.target.asset_type is AssetType.SKILL_TEMPLATE
        and evaluated_at.utcoffset() is not None
        and report.created_at <= evaluated_at
        and compute_eval_report_hash(report) == report.content_hash,
        "Skill Eval Report is not an exact artifact",
    )
    case_ids = [case.case_id for case in report.results]
    _require(
        len(case_ids) == len(set(case_ids))
        and bool(case_ids)
        and set(case_ids) == set(expected_input_hashes) == set(presented),
        "Skill Eval case set is incomplete",
    )
    passed = sum(case.passed for case in report.results)
    _require(
        report.passed == passed
        and report.failed == len(case_ids) - passed
        and report.total == len(case_ids)
        and abs(report.pass_rate - passed / len(case_ids)) < 1e-12,
        "Skill Eval Report summary drifted from cases",
    )
    scope = (report.tenant.org_id, report.tenant.project_id)
    roots: dict[tuple[str, str], EvalIssuerRoot] = {}
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            context = cur.execute("""SELECT current_user AS role,
                current_setting('aos.org_id',true) AS org_id,
                current_setting('aos.project_id',true) AS project_id,
                current_setting('transaction_isolation') AS isolation""").fetchone()
            _require(
                context["role"] == "aos_aip_eval_writer"
                and (context["org_id"], context["project_id"]) == scope
                and context["isolation"] == "serializable",
                "Eval writer tenant or serializable snapshot is unavailable",
            )
            run = cur.execute("""SELECT * FROM aip_eval_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (*scope, report.run_id)).fetchone()
            _require(
                run is not None and run["status"] == "succeeded"
                and run["suite_id"] == report.suite_ref.asset_id
                and str(run["suite_revision"]) == report.suite_ref.revision
                and run["suite_hash"] == report.suite_ref.content_hash
                and run["target_ref"] == report.target.model_dump(mode="json", by_alias=True)
                and run["dataset_ref"] == report.dataset.model_dump(mode="json", by_alias=True)
                and run["judge_ref"] == report.judge.model_dump(mode="json", by_alias=True),
                "Skill Eval Run and Report drifted",
            )
            for item in presented.values():
                for cert, receipt in (
                    (item.target_certificate, item.target_receipt),
                    (item.judge_certificate, item.judge_receipt),
                ):
                    root_key = (cert.issuer_id, cert.issuer_key_id)
                    root = cur.execute("""SELECT * FROM aip_eval_issuer_root
                        WHERE org_id=%s AND project_id=%s AND issuer_id=%s AND key_id=%s""",
                        (*scope, *root_key)).fetchone()
                    _require(root is not None, "current Eval issuer root is unavailable")
                    public_key = _key(root["public_key_base64"])
                    _require(
                        root["purpose"] == "eval-execution"
                        and root["public_key_hash"] == hashlib.sha256(public_key).hexdigest()
                        and bool(root["owner_ref"] and root["approval_ref"] and root["source_hash"])
                        and root["created_at"] <= receipt.occurred_at,
                        "current Eval issuer root drifted",
                    )
                    roots[root_key] = EvalIssuerRoot(
                        issuer_id=cert.issuer_id, key_id=cert.issuer_key_id,
                        public_key=public_key, purpose="eval-execution",
                        not_before=root["valid_from"], not_after=root["valid_until"],
                    )
                    identity = cur.execute("""SELECT * FROM aip_eval_executor_identity
                        WHERE org_id=%s AND project_id=%s AND identity_id=%s""",
                        (*scope, cert.identity_id)).fetchone()
                    _require(identity is not None, "current Eval executor identity is unavailable")
                    executor_key = _key(identity["public_key_base64"])
                    _require(
                        identity["purpose"] == cert.purpose
                        and identity["issuer_id"] == cert.issuer_id
                        and identity["issuer_key_id"] == cert.issuer_key_id
                        and identity["certificate_json"] == cert.model_dump(mode="json", by_alias=True)
                        and identity["certificate_hash"] == certificate_hash(cert)
                        and identity["public_key_base64"] == cert.public_key_base64
                        and identity["public_key_hash"] == hashlib.sha256(executor_key).hexdigest()
                        and identity["executor_ref"] == cert.executor_ref.model_dump(mode="json", by_alias=True)
                        and identity["valid_from"] == cert.valid_from
                        and identity["valid_until"] == cert.valid_until
                        and identity["created_at"] <= receipt.occurred_at
                        and bool(identity["owner_ref"] and identity["approval_ref"]),
                        "current Eval executor identity drifted",
                    )
            revoked = cur.execute("""SELECT identity_id,issuer_id,issuer_key_id
                FROM aip_eval_authority_revocation
                WHERE org_id=%s AND project_id=%s AND revoked_at<=%s""",
                (*scope, evaluated_at)).fetchall()
    except psycopg.Error as exc:
        raise EvalExecutionRejected("current Eval writer authority read failed") from exc
    revoked_ids = frozenset(row["identity_id"] for row in revoked if row["identity_id"])
    revoked_roots = {(row["issuer_id"], row["issuer_key_id"])
                     for row in revoked if row["issuer_id"]}
    _require(not revoked_roots.intersection(roots), "current Eval issuer root was revoked")
    verified: list[VerifiedEvalExecutionPair] = []
    for result in report.results:
        item = presented[result.case_id]
        pair = verify_execution_pair(
            issuer_roots=roots, revoked_identity_ids=revoked_ids,
            evaluated_at=evaluated_at, expected_tenant=report.tenant,
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
        _require(
            item.target_receipt.output_hash == result.actual_hash
            and item.judge_receipt.actual_hash == result.actual_hash
            and pair.passed == result.passed
            and pair.detail_code == result.detail_code,
            "Skill Eval case result drifted",
        )
        verified.append(pair)
    return VerifiedSkillEvalReportProof(
        report_id=report.report_id, report_hash=report.content_hash,
        cases=tuple(verified),
    )
