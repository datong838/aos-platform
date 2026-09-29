"""Read one tenant's persisted Eval proof in the caller's repeatable-read transaction."""
from __future__ import annotations

import base64
import binascii
import hashlib
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef, EvalExecutionReceipt, EvalExecutorCertificate,
    JudgeRevisionRef,
)
from aos_api.aip_eval_execution_authority import (
    EvalExecutionRejected, EvalIssuerRoot, VerifiedEvalExecutionPair,
    canonical_receipt_bytes, certificate_hash, verify_execution_pair,
)


def _key(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise EvalExecutionRejected("persisted Eval public key is invalid") from exc
    if len(decoded) != 32:
        raise EvalExecutionRejected("persisted Eval public key length is invalid")
    return decoded


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvalExecutionRejected(message)


def read_persisted_execution_pair(
    conn: psycopg.Connection,
    *,
    evaluated_at: datetime,
    expected_tenant: TenantContext,
    expected_run_id: str,
    expected_suite_ref: AssetRevisionRef,
    expected_case_id: str,
    expected_target_ref: AssetRevisionRef,
    expected_judge_ref: JudgeRevisionRef,
    expected_input_hash: str,
    expected_expected_hash: str | None,
    target_certificate: EvalExecutorCertificate,
    target_receipt: EvalExecutionReceipt,
    judge_certificate: EvalExecutorCertificate,
    judge_receipt: EvalExecutionReceipt,
) -> VerifiedEvalExecutionPair:
    """Bind persisted rows to already presented signatures; never create authority."""
    _require(evaluated_at.utcoffset() is not None, "Eval cutoff must have timezone")
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            context = cur.execute("""SELECT current_user AS role,
                current_setting('aos.org_id',true) AS org_id,
                current_setting('aos.project_id',true) AS project_id,
                current_setting('transaction_isolation') AS isolation""").fetchone()
            _require(
                context["role"] == "aos_runtime"
                and (context["org_id"], context["project_id"])
                    == (expected_tenant.org_id, expected_tenant.project_id)
                and context["isolation"] in ("repeatable read", "serializable"),
                "Eval tenant role or snapshot is unavailable",
            )
            roots: dict[tuple[str, str], EvalIssuerRoot] = {}
            for cert, receipt in (
                (target_certificate, target_receipt),
                (judge_certificate, judge_receipt),
            ):
                scope = (expected_tenant.org_id, expected_tenant.project_id)
                root_key = (cert.issuer_id, cert.issuer_key_id)
                issuer = cur.execute("""SELECT * FROM aip_eval_issuer_root
                    WHERE org_id=%s AND project_id=%s AND issuer_id=%s AND key_id=%s""",
                    (*scope, *root_key)).fetchone()
                _require(issuer is not None, "current Eval issuer root is unavailable")
                issuer_key = _key(issuer["public_key_base64"])
                _require(
                    issuer["purpose"] == "eval-execution"
                    and hashlib.sha256(issuer_key).hexdigest() == issuer["public_key_hash"]
                    and bool(issuer["owner_ref"] and issuer["approval_ref"] and issuer["source_hash"])
                    and issuer["created_at"] <= receipt.occurred_at,
                    "persisted Eval issuer root drifted",
                )
                roots[root_key] = EvalIssuerRoot(
                    issuer_id=cert.issuer_id, key_id=cert.issuer_key_id,
                    public_key=issuer_key, purpose="eval-execution",
                    not_before=issuer["valid_from"], not_after=issuer["valid_until"],
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
                    "persisted Eval executor identity drifted",
                )
                persisted = cur.execute("""SELECT * FROM aip_eval_execution_receipt
                    WHERE org_id=%s AND project_id=%s AND run_id=%s
                      AND case_id=%s AND purpose=%s""",
                    (*scope, expected_run_id, expected_case_id, receipt.purpose),
                ).fetchone()
                _require(persisted is not None, "current Eval execution receipt is unavailable")
                _require(
                    persisted["receipt_id"] == receipt.receipt_id
                    and persisted["identity_id"] == cert.identity_id
                    and persisted["certificate_hash"] == certificate_hash(cert)
                    and persisted["suite_ref"] == receipt.suite_ref.model_dump(mode="json", by_alias=True)
                    and persisted["executor_ref"] == receipt.executor_ref.model_dump(mode="json", by_alias=True)
                    and persisted["claim_hash"] == hashlib.sha256(canonical_receipt_bytes(receipt)).hexdigest()
                    and persisted["input_hash"] == receipt.input_hash
                    and persisted["output_hash"] == receipt.output_hash
                    and persisted["actual_hash"] == receipt.actual_hash
                    and persisted["expected_hash"] == receipt.expected_hash
                    and persisted["passed"] == receipt.passed
                    and persisted["detail_code"] == receipt.detail_code
                    and persisted["occurred_at"] == receipt.occurred_at
                    and persisted["created_at"] <= evaluated_at
                    and persisted["signature_base64"] == receipt.signature_base64,
                    "persisted Eval execution receipt drifted",
                )
            revoked = cur.execute("""SELECT identity_id,issuer_id,issuer_key_id
                FROM aip_eval_authority_revocation
                WHERE org_id=%s AND project_id=%s AND revoked_at<=%s""",
                (expected_tenant.org_id, expected_tenant.project_id, evaluated_at),
            ).fetchall()
            revoked_ids = frozenset(row["identity_id"] for row in revoked if row["identity_id"])
            revoked_roots = {
                (row["issuer_id"], row["issuer_key_id"])
                for row in revoked if row["issuer_id"]
            }
            _require(not revoked_roots.intersection(roots), "current Eval issuer root was revoked")
    except psycopg.Error as exc:
        raise EvalExecutionRejected("persisted Eval authority read failed") from exc
    return verify_execution_pair(
        issuer_roots=roots, revoked_identity_ids=revoked_ids,
        evaluated_at=evaluated_at, expected_tenant=expected_tenant,
        expected_run_id=expected_run_id, expected_suite_ref=expected_suite_ref,
        expected_case_id=expected_case_id, expected_target_ref=expected_target_ref,
        expected_judge_ref=expected_judge_ref, expected_input_hash=expected_input_hash,
        expected_expected_hash=expected_expected_hash,
        target_certificate=target_certificate, target_receipt=target_receipt,
        judge_certificate=judge_certificate, judge_receipt=judge_receipt,
    )
