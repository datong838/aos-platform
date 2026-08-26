"""BI-W3-07 disabled connector failure and restart contract tests."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.business_investigation_connector_contract import (
    ConnectorFailureFixtureMatrix,
    ConnectorOutcomeStatus,
    ConnectorPlatform,
    ConnectorScenario,
    EXPECTED_OUTCOME,
    evaluate_connector_fixture_matrix,
)


FIXTURE = Path(__file__).parent / "fixtures/business_investigation/connector_failure_matrix.json"
HASH_B = f"sha256:{'b' * 64}"


def fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_disabled_matrix_covers_all_platforms_scenarios_and_exact_hashes() -> None:
    matrix = ConnectorFailureFixtureMatrix.model_validate(fixture_payload())
    receipt = evaluate_connector_fixture_matrix(matrix)

    assert receipt.status == "passed"
    assert receipt.scenario_count == receipt.passed_count == 10
    assert receipt.failed_count == 0
    assert set(receipt.platforms) == set(ConnectorPlatform)
    assert set(case.scenario for case in matrix.cases) == set(ConnectorScenario)
    assert all(case.outcome_status is EXPECTED_OUTCOME[case.scenario] for case in matrix.cases)
    assert all(not case.enabled and not case.retry_scheduled and not case.external_effect for case in matrix.cases)
    assert receipt.outcome_counts[ConnectorOutcomeStatus.RESUMED_FROM_CHECKPOINT] == 1
    assert "NO_REAL_PLATFORM_ACCESS" in receipt.non_claims


def test_hash_drift_fails_closed_at_case_and_matrix_boundaries() -> None:
    case_drift = fixture_payload()
    case_drift["cases"][0]["fixtureHash"] = HASH_B
    with pytest.raises(ValueError, match="fixture hash drifted"):
        evaluate_connector_fixture_matrix(ConnectorFailureFixtureMatrix.model_validate(case_drift))

    matrix_drift = fixture_payload()
    matrix_drift["contentHash"] = HASH_B
    with pytest.raises(ValueError, match="matrix content hash drifted"):
        evaluate_connector_fixture_matrix(ConnectorFailureFixtureMatrix.model_validate(matrix_drift))


@pytest.mark.parametrize(
    ("field", "value"),
    [("enabled", True), ("retryScheduled", True), ("emptyObserved", True), ("captchaAutoSolved", True)],
)
def test_fixture_cannot_enable_execute_retry_or_disguise_failure_as_empty(field: str, value: bool) -> None:
    payload = fixture_payload()
    payload["cases"][0][field] = value
    with pytest.raises(ValidationError):
        ConnectorFailureFixtureMatrix.model_validate(payload)


def test_scenario_status_and_tenant_boundary_cannot_drift() -> None:
    wrong_status = fixture_payload()
    wrong_status["cases"][0]["outcomeStatus"] = "blocked_permission"
    with pytest.raises(ValidationError, match="scenario outcome status drifted"):
        ConnectorFailureFixtureMatrix.model_validate(wrong_status)

    mixed_tenant = fixture_payload()
    mixed_tenant["cases"][1]["tenant"] = {"orgId": "dev-org", "projectId": "dev-project"}
    with pytest.raises(ValidationError, match="one tenant boundary"):
        ConnectorFailureFixtureMatrix.model_validate(mixed_tenant)


def test_restart_requires_same_session_exact_checkpoint_without_second_attempt() -> None:
    payload = fixture_payload()
    restart = next(case for case in payload["cases"] if case["scenario"] == "process_restart")
    assert restart["attemptNumber"] == 1 and restart["retryScheduled"] is False

    cross_session = deepcopy(payload)
    changed = next(case for case in cross_session["cases"] if case["scenario"] == "process_restart")
    changed["checkpointSessionRef"]["resourceId"] = "another-session"
    with pytest.raises(ValidationError, match="same observation session"):
        ConnectorFailureFixtureMatrix.model_validate(cross_session)

    second_attempt = deepcopy(payload)
    changed = next(case for case in second_attempt["cases"] if case["scenario"] == "process_restart")
    changed["attemptNumber"] = 2
    with pytest.raises(ValidationError):
        ConnectorFailureFixtureMatrix.model_validate(second_attempt)


@pytest.mark.parametrize("extra", [{"token": "secret"}, {"url": "https://example.invalid"}, {"rawPayload": {}}])
def test_fixture_rejects_sensitive_or_runtime_payload_fields(extra: dict) -> None:
    payload = fixture_payload()
    payload["cases"][0].update(extra)
    with pytest.raises(ValidationError, match="Extra inputs"):
        ConnectorFailureFixtureMatrix.model_validate(payload)
