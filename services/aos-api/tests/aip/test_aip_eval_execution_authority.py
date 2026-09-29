from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    EvalExecutionReceipt,
    EvalExecutorCertificate,
    JudgeRevisionRef,
)
from aos_api.aip_eval_execution_authority import (
    EvalExecutionRejected,
    EvalIssuerRoot,
    canonical_certificate_bytes,
    canonical_receipt_bytes,
    certificate_hash,
    receipt_identity,
    verify_execution_pair,
)

NOW = datetime(2026, 9, 29, 5, 30, tzinfo=UTC)
TENANT = TenantContext(org_id="org-org", project_id="dev-project")
SUITE = AssetRevisionRef(
    asset_type=AssetType.EVAL_SUITE, asset_id="suite-1", revision="1",
    content_hash="1" * 64,
)
TARGET = AssetRevisionRef(
    asset_type=AssetType.SKILL_TEMPLATE, asset_id="ecommerce.skill.D01",
    revision="1", content_hash="2" * 64,
)
JUDGE = JudgeRevisionRef(judge_id="g2-judge", revision=1, content_hash="3" * 64)
INPUT_HASH, EXPECTED_HASH, ACTUAL_HASH = (c * 64 for c in "456")


def _public_key(private: Ed25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _judge_output_hash(actual_hash, expected_hash, passed, detail_code):
    claim = {"actualHash": actual_hash, "expectedHash": expected_hash,
             "passed": passed, "detailCode": detail_code}
    encoded = json.dumps(claim, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(b"AOS-EVAL-JUDGE-RESULT-v1\n" + encoded).hexdigest()


def _signed_pair():
    issuer = Ed25519PrivateKey.generate()
    target_key = Ed25519PrivateKey.generate()
    judge_key = Ed25519PrivateKey.generate()
    root = EvalIssuerRoot(
        issuer_id="g2-eval-issuer", key_id="issuer-key-1",
        public_key=_public_key(issuer), purpose="eval-execution",
        not_before=NOW - timedelta(days=1), not_after=NOW + timedelta(days=1),
    )

    def certificate(purpose, identity_id, executor_ref, private):
        item = EvalExecutorCertificate(
            identity_id=identity_id, tenant=TENANT, purpose=purpose,
            executor_ref=executor_ref, issuer_id=root.issuer_id,
            issuer_key_id=root.key_id,
            public_key_base64=base64.b64encode(_public_key(private)).decode(),
            valid_from=NOW - timedelta(hours=1),
            valid_until=NOW + timedelta(hours=1),
            signature_base64="pending",
        )
        return item.model_copy(update={
            "signature_base64": base64.b64encode(
                issuer.sign(canonical_certificate_bytes(item))
            ).decode()
        })

    target_cert = certificate("target", "target-identity", TARGET, target_key)
    judge_cert = certificate("judge", "judge-identity", JUDGE, judge_key)

    def receipt(purpose, cert, executor_ref, private, output_hash, **judge_fields):
        item = EvalExecutionReceipt(
            receipt_id=receipt_identity(TENANT, "run-1", "case-1", purpose),
            tenant=TENANT, purpose=purpose, run_id="run-1", suite_ref=SUITE,
            case_id="case-1", identity_id=cert.identity_id,
            certificate_hash=certificate_hash(cert), executor_ref=executor_ref,
            input_hash=INPUT_HASH, output_hash=output_hash,
            occurred_at=NOW, signature_base64="pending", **judge_fields,
        )
        return item.model_copy(update={
            "signature_base64": base64.b64encode(
                private.sign(canonical_receipt_bytes(item))
            ).decode()
        })

    target_receipt = receipt("target", target_cert, TARGET, target_key, ACTUAL_HASH)
    judge_receipt = receipt(
        "judge", judge_cert, JUDGE, judge_key,
        _judge_output_hash(ACTUAL_HASH, EXPECTED_HASH, True, "exact_match"),
        actual_hash=ACTUAL_HASH, expected_hash=EXPECTED_HASH,
        passed=True, detail_code="exact_match",
    )
    return root, (target_cert, target_receipt, target_key), (judge_cert, judge_receipt, judge_key)


def _verify(root, target, judge, **overrides):
    args = dict(
        issuer_roots={(root.issuer_id, root.key_id): root},
        revoked_identity_ids=frozenset(), evaluated_at=NOW,
        expected_tenant=TENANT, expected_run_id="run-1",
        expected_suite_ref=SUITE, expected_case_id="case-1",
        expected_target_ref=TARGET, expected_judge_ref=JUDGE,
        expected_input_hash=INPUT_HASH, expected_expected_hash=EXPECTED_HASH,
        target_certificate=target[0], target_receipt=target[1],
        judge_certificate=judge[0], judge_receipt=judge[1],
    )
    args.update(overrides)
    return verify_execution_pair(**args)


def test_isolated_signed_pair_has_exact_replay_claims():
    root, target, judge = _signed_pair()
    verified = _verify(root, target, judge)
    assert verified.passed is True
    assert verified.target_receipt_id == target[1].receipt_id
    assert verified.judge_receipt_id == judge[1].receipt_id
    assert verified.target_claim_hash != verified.judge_claim_hash


@pytest.mark.parametrize("change", ["tenant", "target", "output", "expected", "receipt_id"])
def test_signed_but_drifted_claims_fail_closed(change):
    root, target, judge = _signed_pair()
    if change == "tenant":
        altered = target[1].model_copy(update={
            "tenant": TenantContext(org_id="other-org", project_id="dev-project")
        })
        target = (target[0], altered, target[2])
    elif change == "target":
        altered = target[1].model_copy(update={
            "executor_ref": TARGET.model_copy(update={"content_hash": "8" * 64})
        })
        target = (target[0], altered, target[2])
    elif change == "output":
        altered = target[1].model_copy(update={"output_hash": "8" * 64})
        target = (target[0], altered, target[2])
    elif change == "expected":
        altered = judge[1].model_copy(update={"expected_hash": "8" * 64})
        judge = (judge[0], altered, judge[2])
    else:
        altered = target[1].model_copy(update={"receipt_id": "replayed-id"})
        target = (target[0], altered, target[2])
    if change in {"tenant", "target", "output", "receipt_id"}:
        target = (target[0], target[1].model_copy(update={
            "signature_base64": base64.b64encode(
                target[2].sign(canonical_receipt_bytes(target[1]))
            ).decode()
        }), target[2])
    else:
        judge = (judge[0], judge[1].model_copy(update={
            "signature_base64": base64.b64encode(
                judge[2].sign(canonical_receipt_bytes(judge[1]))
            ).decode()
        }), judge[2])
    with pytest.raises(EvalExecutionRejected):
        _verify(root, target, judge)


def test_missing_root_revocation_and_bad_signature_fail_closed():
    root, target, judge = _signed_pair()
    with pytest.raises(EvalExecutionRejected):
        _verify(root, target, judge, issuer_roots={})
    with pytest.raises(EvalExecutionRejected):
        _verify(root, target, judge, revoked_identity_ids=None)
    with pytest.raises(EvalExecutionRejected):
        _verify(root, target, judge, revoked_identity_ids=frozenset({"target-identity"}))
    with pytest.raises(EvalExecutionRejected):
        _verify(root, (target[0], target[1].model_copy(update={"signature_base64": "bad"}), target[2]), judge)
    with pytest.raises(EvalExecutionRejected):
        _verify(root, (
            target[0].model_copy(update={"signature_base64": "bad"}),
            target[1], target[2],
        ), judge)


def test_cross_purpose_or_expired_issuer_is_rejected():
    root, target, judge = _signed_pair()
    with pytest.raises(EvalExecutionRejected):
        _verify(root, judge, target)
    with pytest.raises(EvalExecutionRejected):
        _verify(root, target, judge, issuer_roots={(root.issuer_id, root.key_id):
            EvalIssuerRoot(**{**root.__dict__, "not_after": NOW})})


def test_signed_judge_result_digest_must_match_its_verdict():
    root, target, judge = _signed_pair()
    wrong = judge[1].model_copy(update={"output_hash": "7" * 64})
    wrong = wrong.model_copy(update={
        "signature_base64": base64.b64encode(
            judge[2].sign(canonical_receipt_bytes(wrong))
        ).decode()
    })
    with pytest.raises(EvalExecutionRejected):
        _verify(root, target, (judge[0], wrong, judge[2]))


def test_certificate_time_and_receipt_role_shape_fail_closed():
    root, target, judge = _signed_pair()
    expired = target[0].model_copy(update={"valid_until": NOW})
    with pytest.raises(EvalExecutionRejected):
        _verify(root, (expired, target[1], target[2]), judge)
    payload = target[1].model_dump(mode="json", by_alias=True)
    payload["passed"] = True
    with pytest.raises(ValidationError, match="target receipt cannot assert Judge result"):
        EvalExecutionReceipt.model_validate(payload)
    cert_payload = target[0].model_dump(mode="json", by_alias=True)
    cert_payload["purpose"] = "judge"
    with pytest.raises(ValidationError, match="purpose/ref mismatch"):
        EvalExecutorCertificate.model_validate(cert_payload)


def test_judge_can_sign_case_without_expected_artifact():
    root, target, judge = _signed_pair()
    payload = judge[1].model_dump(mode="json", by_alias=True)
    payload["expectedHash"] = None
    payload["outputHash"] = _judge_output_hash(ACTUAL_HASH, None, True, "exact_match")
    receipt = EvalExecutionReceipt.model_validate(payload)
    receipt = receipt.model_copy(update={
        "signature_base64": base64.b64encode(
            judge[2].sign(canonical_receipt_bytes(receipt))
        ).decode()
    })
    verified = _verify(
        root, target, (judge[0], receipt, judge[2]),
        expected_expected_hash=None,
    )
    assert verified.passed is True
