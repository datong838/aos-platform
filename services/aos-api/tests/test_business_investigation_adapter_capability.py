"""BI-W9-01 generic disabled-by-default Adapter capability contract tests."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.business_investigation_adapter_capability import (
    AdapterCapabilityMatrix,
    AdapterAvailabilityState,
    AdapterPlatform,
    AdapterReadinessProbe,
    evaluate_adapter_capability_matrix,
    evaluate_adapter_readiness,
)


FIXTURE = Path(__file__).parent / "fixtures/business_investigation/adapter_capability_matrix.json"
HASH_B = f"sha256:{'b' * 64}"


def fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_three_platforms_share_one_disabled_generic_capability_contract() -> None:
    matrix = AdapterCapabilityMatrix.model_validate(fixture_payload())
    receipt = evaluate_adapter_capability_matrix(matrix)

    assert set(item.platform for item in matrix.entries) == set(AdapterPlatform)
    assert len({item.capability_id for item in matrix.entries}) == 1
    assert all(not item.enabled and not item.activation_allowed for item in matrix.entries)
    assert all(item.lifecycle_states == ["declared"] for item in matrix.entries)
    assert all(item.risk_class == "R0_READ_ONLY" for item in matrix.entries)
    assert all(item.supported_facts == [] and item.supported_entities == [] for item in matrix.entries)
    assert receipt.status == "passed" and receipt.entry_count == 3
    assert "NO_ADAPTER_INSTALLATION" in receipt.non_claims


def test_operations_are_read_only_and_activation_operations_stay_forbidden() -> None:
    matrix = AdapterCapabilityMatrix.model_validate(fixture_payload())
    for item in matrix.entries:
        assert set(item.baseline_allowed_operations) == {
            "navigate",
            "wait",
            "scroll",
            "filter",
            "open_detail",
            "read",
        }
        assert set(item.conditionally_allowed_operations) == {"export_read", "schema_discover"}
        assert {
            "create",
            "update",
            "delete",
            "publish",
            "send",
            "reprice",
            "approve",
            "execute",
            "captcha_solve",
            "secret_resolve",
        } <= set(item.forbidden_operations)


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, AdapterAvailabilityState.DISABLED_TERMS_UNVERIFIED),
        ({"termsVerified": True}, AdapterAvailabilityState.DISABLED_NOT_INSTALLED),
        ({"termsVerified": True, "installed": True}, AdapterAvailabilityState.DISABLED_NOT_CONFIGURED),
        ({"termsVerified": True, "installed": True, "configured": True}, AdapterAvailabilityState.BLOCKED_SESSION_NOT_READY),
        ({"termsVerified": True, "installed": True, "configured": True, "sessionReady": True}, AdapterAvailabilityState.BLOCKED_CONTRACT_NOT_TESTED),
        ({"termsVerified": True, "installed": True, "configured": True, "sessionReady": True, "contractTested": True}, AdapterAvailabilityState.BLOCKED_RUNTIME_UNVERIFIED),
        ({"termsVerified": True, "installed": True, "configured": True, "sessionReady": True, "contractTested": True, "runtimeVerified": True, "permissionGranted": False}, AdapterAvailabilityState.BLOCKED_PERMISSION),
        ({"termsVerified": True, "installed": True, "configured": True, "sessionReady": True, "contractTested": True, "runtimeVerified": True, "pageContractCurrent": False}, AdapterAvailabilityState.BLOCKED_PAGE_DRIFT),
        ({"termsVerified": True, "installed": True, "configured": True, "sessionReady": True, "contractTested": True, "runtimeVerified": True, "coverageComplete": False}, AdapterAvailabilityState.PARTIAL_COVERAGE),
        ({"termsVerified": True, "installed": True, "configured": True, "sessionReady": True, "contractTested": True, "runtimeVerified": True, "externalResultKnown": False}, AdapterAvailabilityState.UNKNOWN_RECONCILE),
        ({"termsVerified": True, "installed": True, "configured": True, "sessionReady": True, "contractTested": True, "runtimeVerified": True}, AdapterAvailabilityState.BLOCKED_ACTIVATION_NOT_AUTHORIZED),
    ],
)
def test_readiness_degradation_order_is_deterministic_and_never_activates(changes: dict, expected: AdapterAvailabilityState) -> None:
    probe = AdapterReadinessProbe.model_validate(changes)
    result = evaluate_adapter_readiness(probe)
    assert result.state is expected
    assert result.enabled is False and result.retry_scheduled is False
    assert result.empty_observed is False and result.external_effect is False


def test_hash_drift_and_platform_specific_or_sensitive_fields_fail_closed() -> None:
    entry_drift = fixture_payload()
    entry_drift["entries"][0]["entryHash"] = HASH_B
    with pytest.raises(ValueError, match="entry hash drifted"):
        evaluate_adapter_capability_matrix(AdapterCapabilityMatrix.model_validate(entry_drift))

    matrix_drift = fixture_payload()
    matrix_drift["contentHash"] = HASH_B
    with pytest.raises(ValueError, match="matrix content hash drifted"):
        evaluate_adapter_capability_matrix(AdapterCapabilityMatrix.model_validate(matrix_drift))

    for extra in ({"url": "https://example.invalid"}, {"secretRef": "secret"}, {"menu": "orders"}, {"table": "order"}, {"token": "secret"}):
        payload = fixture_payload()
        payload["entries"][0].update(extra)
        with pytest.raises(ValidationError, match="Extra inputs"):
            AdapterCapabilityMatrix.model_validate(payload)

    platform_field = deepcopy(fixture_payload())
    platform_field["entries"][1]["baselineAllowedOperations"].append("wechat_menu_read")
    with pytest.raises(ValidationError, match="generic baseline operations"):
        AdapterCapabilityMatrix.model_validate(platform_field)


@pytest.mark.parametrize("field", ["enabled", "activationAllowed", "automaticRetry", "emptyObserved"])
def test_disabled_fixture_cannot_claim_activation_retry_or_business_empty(field: str) -> None:
    payload = fixture_payload()
    payload["entries"][0][field] = True
    with pytest.raises(ValidationError):
        AdapterCapabilityMatrix.model_validate(payload)
