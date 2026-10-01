"""Check current signed Eval authority inside the caller's writer transaction."""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Mapping

import psycopg
from psycopg.rows import dict_row

from pydantic import ValidationError

from aos_api.aip_eval_contracts import (
    AssetType, DatasetSourceKind, EvalDatasetManifest, EvalReportRevision,
)
from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityError, AipEvalAuthorityStore,
)
from aos_api.aip_eval_execution_authority import (
    EvalExecutionRejected, EvalIssuerRoot, VerifiedEvalExecutionPair,
    certificate_hash, verify_execution_pair,
)
from aos_api.aip_eval_persisted_authority_reader import _key
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_eval_report_proof_reader import (
    PresentedEvalCaseProof, VerifiedSkillEvalReportProof,
)
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.aip_eval_report_context import require_same_eval_context
from aos_api.tenant_scope import TenantScope


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
        and report.created_at.utcoffset() is not None
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
        and report.pass_rate == round(passed / len(case_ids), 6),
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
            require_same_eval_context(report, run)
            dataset = cur.execute("""SELECT * FROM aip_eval_dataset_revision
                WHERE org_id=%s AND project_id=%s AND dataset_id=%s AND revision=%s""",
                (*scope, report.dataset.dataset_id, report.dataset.revision)).fetchone()
            _require(dataset is not None, "persisted Eval Dataset is unavailable")
            _require(
                dataset["content_hash"] == report.dataset.content_hash
                and dataset["source_hash"] == report.dataset.source_hash
                and dataset["redaction_policy_ref"] == report.dataset.redaction_policy.model_dump(
                    mode="json", by_alias=True),
                "persisted Eval Dataset drifted",
            )
            try:
                manifest = EvalDatasetManifest.model_validate(dataset["manifest"])
            except ValidationError as exc:
                raise EvalExecutionRejected("persisted Eval Dataset manifest is invalid") from exc
            _require(
                manifest.source_hash == report.dataset.source_hash
                and manifest.case_count >= len(case_ids)
                and manifest.captured_at.utcoffset() is not None
                and manifest.captured_at <= dataset["created_at"]
                and dataset["created_at"] <= evaluated_at,
                "persisted Eval Dataset source drifted",
            )
            if manifest.source_kind is DatasetSourceKind.ARTIFACT_SNAPSHOT:
                try:
                    AipEvalAuthorityStore._assert_artifact_snapshot_source(
                        cur, TenantScope(*scope), manifest,
                    )
                except AipEvalAuthorityError as exc:
                    raise EvalExecutionRejected(
                        "current Eval Artifact snapshot or redaction metadata drifted"
                    ) from exc
            _require(
                report.suite_ref.revision.isdecimal()
                and str(int(report.suite_ref.revision)) == report.suite_ref.revision,
                "Eval Suite revision must be canonical integer",
            )
            suite_row = cur.execute("""SELECT * FROM aip_eval_suite_revision
                WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s""",
                (*scope, report.suite_ref.asset_id, int(report.suite_ref.revision))).fetchone()
            _require(suite_row is not None, "persisted Eval Suite is unavailable")
            try:
                suite = AipEvalPackRegistry._suite_from_row(suite_row)
            except ValidationError as exc:
                raise EvalExecutionRejected("persisted Eval Suite is invalid") from exc
            _require(
                suite.content_hash == report.suite_ref.content_hash
                and compute_eval_suite_hash(suite) == suite.content_hash
                and suite.target == report.target
                and suite.dataset == report.dataset
                and suite.judge == report.judge
                and dataset["created_at"] <= suite_row["created_at"]
                and suite_row["created_at"] <= run["created_at"]
                and run["created_at"] <= report.created_at <= evaluated_at
                and {case.case_id for case in suite.cases} == set(case_ids)
                and report.gate_passed == (passed / len(case_ids) >= suite.gate_threshold),
                "persisted Eval Suite or gate threshold drifted",
            )
            for case in suite.cases:
                result = next(item for item in report.results if item.case_id == case.case_id)
                _require(
                    case.input_artifact.content_hash == expected_input_hashes[case.case_id]
                    and (case.expected_artifact.content_hash if case.expected_artifact else None)
                        == result.expected_hash,
                    "persisted Eval case input or expected artifact drifted",
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
