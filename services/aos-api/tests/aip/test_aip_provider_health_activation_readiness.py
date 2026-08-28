"""Provider Health deployment and activation readiness acceptance."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_provider_health_activation_readiness import (
    ProviderHealthActivationFacts,
    evaluate_provider_health_activation_readiness,
)


NOW = datetime(2026, 8, 28, 15, 30, tzinfo=UTC)
CUTOFF = datetime(2026, 8, 28, 15, 0, tzinfo=UTC)


def _all_green() -> ProviderHealthActivationFacts:
    return ProviderHealthActivationFacts(
        evaluated_at=NOW,
        expected_deployed_revision="2cd75ff4",
        deployed_revision="2cd75ff4",
        canonical_environment_exact=True,
        plugin_installed=True,
        action_type_exact=True,
        proposal_exact=True,
        approval_exact=True,
        lease_exact=True,
        receipt_authority_exact=True,
        lease_expires_at=NOW + timedelta(minutes=10),
        healthy_probe_count=3,
        required_probe_count=3,
        health_expires_at=NOW + timedelta(minutes=15),
        health_cutoff=CUTOFF,
        source_ready_count=12,
        source_required_count=12,
        source_readiness_fresh_until=NOW + timedelta(minutes=20),
        source_readiness_cutoff=CUTOFF,
        binding_exact=True,
        binding_operational=True,
        binding_expires_at=NOW + timedelta(minutes=20),
        binding_cutoff=CUTOFF,
    )


def test_missing_deployment_prerequisites_fail_all_gates_with_stable_codes() -> None:
    facts = replace(
        _all_green(),
        deployed_revision="older",
        canonical_environment_exact=False,
        plugin_installed=False,
        action_type_exact=False,
    )

    result = evaluate_provider_health_activation_readiness(facts)

    assert result.loop_ready is False
    assert result.provider_call_ready is False
    assert result.pilot_ready is False
    assert result.loop_missing == (
        "DEPLOYED_REVISION_NOT_EXACT",
        "CANONICAL_ENVIRONMENT_NOT_EXACT",
        "PROVIDER_HEALTH_ACTION_PLUGIN_NOT_INSTALLED",
        "PROVIDER_HEALTH_ACTION_TYPE_NOT_EXACT",
    )
    assert result.provider_call_missing == result.loop_missing
    assert result.pilot_missing[:4] == result.loop_missing


def test_loop_ready_does_not_imply_provider_call_without_exact_authority() -> None:
    facts = replace(
        _all_green(),
        proposal_exact=False,
        approval_exact=False,
        lease_exact=False,
        receipt_authority_exact=False,
        lease_expires_at=None,
    )

    result = evaluate_provider_health_activation_readiness(facts)

    assert result.loop_ready is True
    assert result.loop_missing == ()
    assert result.provider_call_ready is False
    assert result.provider_call_missing == (
        "PROVIDER_HEALTH_PROPOSAL_NOT_EXACT",
        "PROVIDER_HEALTH_APPROVAL_NOT_EXACT",
        "PROVIDER_HEALTH_LEASE_NOT_EXACT",
        "PROVIDER_HEALTH_RECEIPT_AUTHORITY_NOT_EXACT",
        "PROVIDER_HEALTH_LEASE_NOT_FRESH",
    )
    assert result.pilot_ready is False


def test_stale_health_and_source_readiness_10_of_12_keep_pilot_closed() -> None:
    facts = replace(
        _all_green(),
        health_expires_at=NOW,
        source_ready_count=10,
    )

    result = evaluate_provider_health_activation_readiness(facts)

    assert result.loop_ready is True
    assert result.provider_call_ready is True
    assert result.pilot_ready is False
    assert "PROVIDER_HEALTH_NOT_FRESH" in result.pilot_missing
    assert "SOURCE_READINESS_NOT_12_OF_12" in result.pilot_missing


def test_binding_and_same_cutoff_are_independent_pilot_requirements() -> None:
    facts = replace(
        _all_green(),
        binding_exact=False,
        binding_operational=False,
        binding_expires_at=NOW,
        binding_cutoff=CUTOFF - timedelta(minutes=1),
    )

    result = evaluate_provider_health_activation_readiness(facts)

    assert result.provider_call_ready is True
    assert result.pilot_ready is False
    assert result.pilot_missing[-4:] == (
        "PROVIDER_HEALTH_BINDING_NOT_EXACT",
        "PROVIDER_HEALTH_BINDING_NOT_OPERATIONAL",
        "PROVIDER_HEALTH_BINDING_NOT_FRESH",
        "PROVIDER_HEALTH_PILOT_CUTOFF_MISMATCH",
    )


def test_all_exact_fresh_same_cutoff_facts_open_all_gates() -> None:
    result = evaluate_provider_health_activation_readiness(_all_green())

    assert result.status == "PROVIDER_HEALTH_ACTIVATION_READINESS_GREEN"
    assert result.loop_ready is True
    assert result.provider_call_ready is True
    assert result.pilot_ready is True
    assert result.loop_missing == ()
    assert result.provider_call_missing == ()
    assert result.pilot_missing == ()


def test_public_result_carries_no_secret_or_credential_values() -> None:
    result = evaluate_provider_health_activation_readiness(_all_green())
    public = result.as_public_dict()
    rendered = repr(public).lower()

    assert set(public) == {
        "status",
        "evaluatedAt",
        "expectedDeployedRevision",
        "deployedRevision",
        "loopReady",
        "providerCallReady",
        "pilotReady",
        "loopMissing",
        "providerCallMissing",
        "pilotMissing",
    }
    assert "secret" not in rendered
    assert "credential" not in rendered
    assert "token" not in rendered
    assert "password" not in rendered


@pytest.mark.parametrize(
    ("field", "value"),
    [("required_probe_count", 2), ("source_required_count", 11)],
)
def test_canonical_gate_denominators_cannot_be_reduced(field, value) -> None:
    with pytest.raises(ValueError, match="canonical"):
        replace(_all_green(), **{field: value})
