from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.aip_provider_health_action import (
    PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
    ProviderHealthActionBlocked,
    ProviderHealthProbeActionAdapter,
    ProviderHealthProbePayload,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def payload(**changes):
    value = {
        "providerId": "agnes-text-qyh-dev",
        "providerRevision": 7,
        "probeCount": 3,
        "outputPolicy": "metadata-only",
    }
    value.update(changes)
    return value


def green_result(**changes):
    value = {
        "status": "PROVIDER_HEALTH_REFRESH_GREEN",
        "observationId": "health-agnes-text-qyh-r2-20260828120000000000",
        "expiresAt": NOW + timedelta(minutes=15),
        "providerCalls": 3,
        "secretPayloadReadsReported": 0,
        "promptOrAnswerBodiesReported": 0,
        "totalTokens": 21,
        "internal": "must-not-project",
    }
    value.update(changes)
    return value


def test_exact_payload_produces_metadata_only_applied_receipt() -> None:
    calls = []
    adapter = ProviderHealthProbeActionAdapter(
        lambda: calls.append(1) or green_result()
    )
    outcome = adapter.execute(payload=payload(), idempotency_key="attempt-hash")
    assert outcome.status == "applied"
    assert outcome.provider_request_id is None
    assert outcome.payload == {
        "observationId": "health-agnes-text-qyh-r2-20260828120000000000",
        "expiresAt": "2026-08-28T12:15:00Z",
        "providerCalls": 3,
        "secretPayloadReadsReported": 0,
        "promptOrAnswerBodiesReported": 0,
    }
    assert calls == [1]


@pytest.mark.parametrize(
    "changes",
    [
        {"providerId": "other-provider"},
        {"providerRevision": 8},
        {"probeCount": 2},
        {"outputPolicy": "full-body"},
        {"authorization": "forbidden"},
    ],
)
def test_payload_drift_is_rejected_before_refresh(changes) -> None:
    called = []
    adapter = ProviderHealthProbeActionAdapter(lambda: called.append(1))
    with pytest.raises(ValidationError):
        adapter.execute(payload=payload(**changes), idempotency_key="attempt-hash")
    assert called == []


def test_missing_idempotency_is_rejected_before_refresh() -> None:
    called = []
    adapter = ProviderHealthProbeActionAdapter(lambda: called.append(1))
    with pytest.raises(ProviderHealthActionBlocked) as exc:
        adapter.execute(payload=payload(), idempotency_key=" ")
    assert exc.value.code == "ACTION_IDEMPOTENCY_REQUIRED"
    assert called == []


def test_non_green_or_unsafe_receipt_fails_closed() -> None:
    with pytest.raises(ProviderHealthActionBlocked) as non_green:
        ProviderHealthProbeActionAdapter(
            lambda: green_result(status="blocked")
        ).execute(payload=payload(), idempotency_key="attempt-hash")
    assert non_green.value.code == "PROVIDER_HEALTH_REFRESH_NOT_GREEN"

    with pytest.raises(ProviderHealthActionBlocked) as unsafe:
        ProviderHealthProbeActionAdapter(
            lambda: green_result(secretPayloadReadsReported=1)
        ).execute(payload=payload(), idempotency_key="attempt-hash")
    assert unsafe.value.code == "PROVIDER_HEALTH_RECEIPT_INVALID"


def test_reconcile_is_unknown_without_automatic_retry() -> None:
    result = ProviderHealthProbeActionAdapter(green_result).reconcile(
        provider_request_id="provider-request-redacted",
        request_fingerprint="sha256",
    )
    assert result.status == "unknown"
    assert result.payload == {
        "errorType": "PROVIDER_HEALTH_RECONCILIATION_UNAVAILABLE",
        "automaticRetry": False,
    }


def test_action_has_r2_maker_checker_risk_floor() -> None:
    decision = classify_action_risk(
        PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
        {
            "name": "文本 Provider 健康探测",
            "objectType": "ProviderHealthObservation",
        },
        ProviderHealthProbePayload.model_validate(payload()).model_dump(
            mode="json", by_alias=True
        ),
        ActionRiskLevel.R0,
    )
    assert decision.floor is ActionRiskLevel.R2
    assert decision.level is ActionRiskLevel.R2
    assert decision.reasons == ("provider_external_health_probe",)
    assert decision.approval_policy == {
        "makerChecker": True,
        "minimumApprovals": 1,
        "executionAllowed": True,
        "draftOnly": False,
    }

