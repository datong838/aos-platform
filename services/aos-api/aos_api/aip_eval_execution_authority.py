"""Pure signed Skill Eval execution proof; no issuer or persistence is installed here."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Mapping

from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    EvalExecutionReceipt,
    EvalExecutorCertificate,
    JudgeRevisionRef,
)
from aos_api.asset_registry.signature import (
    FrozenTrustRootProvider,
    TrustRoot,
    verify_ed25519,
)


class EvalExecutionRejected(ValueError):
    """The presented execution claims do not prove current authority."""


@dataclass(frozen=True)
class EvalIssuerRoot:
    issuer_id: str
    key_id: str
    public_key: bytes
    purpose: Literal["eval-execution"]
    not_before: datetime
    not_after: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class VerifiedEvalExecutionPair:
    target_receipt_id: str
    judge_receipt_id: str
    target_claim_hash: str
    judge_claim_hash: str
    passed: bool
    detail_code: str


def _canonical_bytes(domain: str, value) -> bytes:
    payload = value.model_dump(
        mode="json", by_alias=True, exclude={"signature_base64"}
    )
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return domain.encode("ascii") + b"\n" + encoded


def canonical_certificate_bytes(certificate: EvalExecutorCertificate) -> bytes:
    return _canonical_bytes("AOS-EVAL-EXECUTOR-CERTIFICATE-v1", certificate)


def canonical_receipt_bytes(receipt: EvalExecutionReceipt) -> bytes:
    return _canonical_bytes("AOS-EVAL-EXECUTION-RECEIPT-v1", receipt)


def certificate_hash(certificate: EvalExecutorCertificate) -> str:
    return hashlib.sha256(canonical_certificate_bytes(certificate)).hexdigest()


def receipt_identity(
    tenant: TenantContext, run_id: str, case_id: str, purpose: Literal["target", "judge"]
) -> str:
    payload = [tenant.org_id, tenant.project_id, run_id, case_id, purpose]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(("AOS-EVAL-RECEIPT-ID-v1\n" + encoded).encode()).hexdigest()


def _judge_result_hash(receipt: EvalExecutionReceipt) -> str:
    claim = {
        "actualHash": receipt.actual_hash,
        "expectedHash": receipt.expected_hash,
        "passed": receipt.passed,
        "detailCode": receipt.detail_code,
    }
    encoded = json.dumps(claim, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(b"AOS-EVAL-JUDGE-RESULT-v1\n" + encoded).hexdigest()


def _valid_interval(checked_at: datetime, start: datetime, end: datetime) -> bool:
    return (
        checked_at.utcoffset() is not None
        and start.utcoffset() is not None
        and end.utcoffset() is not None
        and start <= checked_at < end
    )


def _verify_one(
    certificate: EvalExecutorCertificate,
    receipt: EvalExecutionReceipt,
    *,
    root: EvalIssuerRoot,
    revoked_identity_ids: frozenset[str],
    evaluated_at: datetime,
) -> None:
    if (
        root.purpose != "eval-execution"
        or root.issuer_id != certificate.issuer_id
        or root.key_id != certificate.issuer_key_id
        or certificate.identity_id in revoked_identity_ids
        or not _valid_interval(evaluated_at, certificate.valid_from, certificate.valid_until)
        or not _valid_interval(receipt.occurred_at, certificate.valid_from, certificate.valid_until)
        or receipt.occurred_at > evaluated_at
        or receipt.identity_id != certificate.identity_id
        or receipt.certificate_hash != certificate_hash(certificate)
        or receipt.tenant != certificate.tenant
        or receipt.purpose != certificate.purpose
        or receipt.executor_ref != certificate.executor_ref
    ):
        raise EvalExecutionRejected("Eval executor identity or receipt drifted")
    if root.revoked_at is not None and root.revoked_at <= evaluated_at:
        raise EvalExecutionRejected("Eval issuer root was revoked")
    if not _valid_interval(evaluated_at, root.not_before, root.not_after):
        raise EvalExecutionRejected("Eval issuer root is not current")
    if not _valid_interval(receipt.occurred_at, root.not_before, root.not_after):
        raise EvalExecutionRejected("Eval issuer root was not valid at execution")
    issuer_root = TrustRoot(
        publisher=root.issuer_id, key_id=root.key_id,
        public_key=root.public_key,
        revision="sha256:" + hashlib.sha256(root.public_key).hexdigest(),
        not_before=root.not_before, not_after=root.not_after,
        revoked_at=root.revoked_at,
    )
    if not verify_ed25519(
        payload=canonical_certificate_bytes(certificate),
        signature_b64=certificate.signature_base64,
        publisher=root.issuer_id, key_id=root.key_id,
        trust_roots=FrozenTrustRootProvider({(root.issuer_id, root.key_id): issuer_root}),
        verified_at=evaluated_at,
    ):
        raise EvalExecutionRejected("Eval executor certificate signature is invalid")
    try:
        public_key = base64.b64decode(certificate.public_key_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise EvalExecutionRejected("Eval executor public key is invalid") from exc
    if len(public_key) != 32:
        raise EvalExecutionRejected("Eval executor public key length is invalid")
    executor_root = TrustRoot(
        publisher=certificate.identity_id, key_id=certificate.identity_id,
        public_key=public_key,
        revision="sha256:" + hashlib.sha256(public_key).hexdigest(),
        not_before=certificate.valid_from, not_after=certificate.valid_until,
    )
    if not verify_ed25519(
        payload=canonical_receipt_bytes(receipt),
        signature_b64=receipt.signature_base64,
        publisher=certificate.identity_id, key_id=certificate.identity_id,
        trust_roots=FrozenTrustRootProvider({
            (certificate.identity_id, certificate.identity_id): executor_root
        }),
        verified_at=evaluated_at,
    ):
        raise EvalExecutionRejected("Eval execution receipt signature is invalid")


def verify_execution_pair(
    *,
    issuer_roots: Mapping[tuple[str, str], EvalIssuerRoot],
    revoked_identity_ids: frozenset[str] | None,
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
    """Verify exact claims only; durable replay/Owner authority is a later gate."""
    if not isinstance(revoked_identity_ids, frozenset) or evaluated_at.utcoffset() is None:
        raise EvalExecutionRejected("current Eval revocation snapshot is required")
    issuer_roots = dict(issuer_roots)
    if (
        target_certificate.purpose != "target"
        or judge_certificate.purpose != "judge"
        or target_receipt.purpose != "target"
        or judge_receipt.purpose != "judge"
        or target_certificate.identity_id == judge_certificate.identity_id
        or target_certificate.public_key_base64 == judge_certificate.public_key_base64
    ):
        raise EvalExecutionRejected("distinct Target and Judge identities are required")
    for certificate, receipt, expected_ref in (
        (target_certificate, target_receipt, expected_target_ref),
        (judge_certificate, judge_receipt, expected_judge_ref),
    ):
        if (
            certificate.tenant != expected_tenant
            or certificate.executor_ref != expected_ref
            or receipt.tenant != expected_tenant
            or receipt.executor_ref != expected_ref
            or receipt.run_id != expected_run_id
            or receipt.suite_ref != expected_suite_ref
            or receipt.case_id != expected_case_id
            or receipt.input_hash != expected_input_hash
            or receipt.receipt_id != receipt_identity(
                expected_tenant, expected_run_id, expected_case_id, receipt.purpose
            )
        ):
            raise EvalExecutionRejected("Eval execution exact claim drifted")
        root = issuer_roots.get((certificate.issuer_id, certificate.issuer_key_id))
        if not isinstance(root, EvalIssuerRoot):
            raise EvalExecutionRejected("current Eval issuer root is unavailable")
        _verify_one(
            certificate, receipt, root=root,
            revoked_identity_ids=revoked_identity_ids,
            evaluated_at=evaluated_at,
        )
    if (
        judge_receipt.actual_hash != target_receipt.output_hash
        or judge_receipt.expected_hash != expected_expected_hash
        or type(judge_receipt.passed) is not bool
        or not isinstance(judge_receipt.detail_code, str)
        or not judge_receipt.detail_code
        or judge_receipt.output_hash != _judge_result_hash(judge_receipt)
    ):
        raise EvalExecutionRejected("Judge result is not bound to Target output")
    return VerifiedEvalExecutionPair(
        target_receipt_id=target_receipt.receipt_id,
        judge_receipt_id=judge_receipt.receipt_id,
        target_claim_hash=hashlib.sha256(canonical_receipt_bytes(target_receipt)).hexdigest(),
        judge_claim_hash=hashlib.sha256(canonical_receipt_bytes(judge_receipt)).hexdigest(),
        passed=judge_receipt.passed,
        detail_code=judge_receipt.detail_code,
    )
