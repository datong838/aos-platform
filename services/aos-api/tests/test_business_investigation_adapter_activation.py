"""BI-W9-06 fail-closed Adapter activation decision contract tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.business_investigation_adapter_activation import (
    AdapterActivationCandidate,
    AdapterActivationMatrix,
    AdapterActivationStatus,
    evaluate_activation_candidate,
    evaluate_activation_matrix,
)


FIXTURE = Path(__file__).parent / "fixtures/business_investigation/adapter_activation_matrix.json"
NOW = datetime(2026, 8, 27, 6, 0, tzinfo=timezone.utc)
HASH_B = f"sha256:{'b' * 64}"


def fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_real_fixture_covers_three_platforms_and_stays_disabled() -> None:
    matrix = AdapterActivationMatrix.model_validate(fixture_payload())
    decisions = evaluate_activation_matrix(matrix, "org-org", "dev-project", NOW)

    assert set(decisions) == {"niushop", "wechat_store", "douyin_store"}
    assert all(item.status is AdapterActivationStatus.DISABLED for item in decisions.values())
    assert all("PLATFORM_TERMS_UNVERIFIED" in item.blockers for item in decisions.values())
    assert all(not item.activation_executed and not item.external_effect for item in decisions.values())
    assert all(not item.automatic_retry for item in decisions.values())


def test_cross_tenant_is_invisible_and_fails_closed() -> None:
    candidate = AdapterActivationMatrix.model_validate(fixture_payload()).candidates[0]
    decision = evaluate_activation_candidate(candidate, "dev-org", "dev-project", NOW)

    assert decision.status is AdapterActivationStatus.DISABLED
    assert decision.candidate_ref is None and decision.platform is None
    assert decision.blockers == ["TENANT_SCOPE_MISMATCH"]


def _eligible_candidate_payload() -> dict:
    payload = deepcopy(fixture_payload()["candidates"][0])
    payload.update(
        capabilityEnabled=True,
        profileEnabled=True,
        overlayEnabled=True,
        installationActive=True,
        versionCompatible=True,
        activationAuthorized=True,
    )
    payload["terms"].update(
        status="accepted",
        acceptedBy="synthetic-owner",
        acceptedAt="2026-08-27T04:00:00Z",
        expiresAt="2026-08-28T04:00:00Z",
        subjectId="synthetic-account",
        expectedSubjectId="synthetic-account",
    )
    payload["health"].update(
        status="ready",
        passedChecks=3,
        requiredChecks=3,
        scopedAtStart=True,
        evaluatedAt="2026-08-27T05:59:00Z",
        validUntil="2026-08-27T06:10:00Z",
    )
    payload["sourceReadiness"].update(state="ready", current=True)
    payload["candidateHash"] = "sha256:" + "0" * 64
    return payload


def test_fully_green_synthetic_candidate_is_only_dry_run_eligible() -> None:
    payload = _eligible_candidate_payload()
    candidate = AdapterActivationCandidate.model_validate(payload)
    payload["candidateHash"] = candidate.calculated_hash()
    candidate = AdapterActivationCandidate.model_validate(payload)

    decision = evaluate_activation_candidate(candidate, "org-org", "dev-project", NOW)
    assert decision.status is AdapterActivationStatus.ELIGIBLE_DRY_RUN_ONLY
    assert decision.blockers == []
    assert not decision.activation_executed and not decision.external_effect


@pytest.mark.parametrize(
    ("path", "value", "blocker"),
    [
        (("terms", "status"), "unverified", "PLATFORM_TERMS_UNVERIFIED"),
        (("terms", "expiresAt"), "2026-08-27T05:59:59Z", "PLATFORM_TERMS_EXPIRED"),
        (("terms", "subjectId"), "other-account", "PLATFORM_TERMS_SUBJECT_MISMATCH"),
        (("health", "passedChecks"), 2, "HEALTH_NOT_3_OF_3"),
        (("health", "validUntil"), "2026-08-27T05:59:59Z", "HEALTH_STALE"),
        (("sourceReadiness", "state"), "blocked", "SOURCE_READINESS_NOT_READY"),
        (("sourceReadiness", "current"), False, "SOURCE_READINESS_STALE"),
        (("versionCompatible",), False, "ADAPTER_VERSION_INCOMPATIBLE"),
    ],
)
def test_each_gate_fails_closed_independently(path: tuple, value: object, blocker: str) -> None:
    payload = _eligible_candidate_payload()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    unsealed = AdapterActivationCandidate.model_validate(payload)
    payload["candidateHash"] = unsealed.calculated_hash()
    candidate = AdapterActivationCandidate.model_validate(payload)

    decision = evaluate_activation_candidate(candidate, "org-org", "dev-project", NOW)
    assert decision.status is AdapterActivationStatus.DISABLED
    assert blocker in decision.blockers


def test_one_platform_failure_does_not_pollute_other_decisions() -> None:
    baseline = fixture_payload()
    matrix = AdapterActivationMatrix.model_validate(baseline)
    before = evaluate_activation_matrix(matrix, "org-org", "dev-project", NOW)

    changed = deepcopy(baseline)
    changed["candidates"][0]["health"].update(
        status="ready",
        passedChecks=3,
        scopedAtStart=True,
        validUntil="2026-08-27T06:10:00Z",
    )
    candidate_type = type(matrix.candidates[0])
    changed_candidate = candidate_type.model_validate(changed["candidates"][0])
    changed["candidates"][0]["candidateHash"] = changed_candidate.calculated_hash()
    changed_matrix = AdapterActivationMatrix.model_validate(changed)
    changed["contentHash"] = changed_matrix.calculated_hash()
    after = evaluate_activation_matrix(AdapterActivationMatrix.model_validate(changed), "org-org", "dev-project", NOW)

    assert after["niushop"].blockers != before["niushop"].blockers
    assert after["wechat_store"] == before["wechat_store"]
    assert after["douyin_store"] == before["douyin_store"]


def test_hash_ref_and_sensitive_extra_drift_fail_closed() -> None:
    hash_drift = fixture_payload()
    hash_drift["candidates"][0]["candidateHash"] = HASH_B
    with pytest.raises(ValueError, match="candidate hash drifted"):
        evaluate_activation_matrix(AdapterActivationMatrix.model_validate(hash_drift), "org-org", "dev-project", NOW)

    wrong_ref = fixture_payload()
    wrong_ref["candidates"][0]["terms"]["termsRef"]["resourceType"] = "DocumentRevision"
    with pytest.raises(ValueError, match="termsRef"):
        AdapterActivationMatrix.model_validate(wrong_ref)

    for extra in ({"token": "secret"}, {"cookie": "secret"}, {"url": "https://example.invalid"}):
        payload = fixture_payload()
        payload["candidates"][0].update(extra)
        with pytest.raises(ValidationError, match="Extra inputs"):
            AdapterActivationMatrix.model_validate(payload)
