"""Provider Health exact change / rollback packet acceptance."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from aos_api.aip_provider_health_activation_change_packet import (
    build_provider_health_activation_change_packet,
)
from aos_api.aip_provider_health_activation_readiness import (
    ProviderHealthActivationReadiness,
)


NOW = datetime(2026, 8, 28, 15, 45, tzinfo=UTC)


def _readiness(*, loop=False, call=False, pilot=False):
    loop_missing = () if loop else ("PROVIDER_HEALTH_ACTION_PLUGIN_NOT_INSTALLED",)
    call_missing = loop_missing if call else loop_missing + (
        "PROVIDER_HEALTH_LEASE_NOT_EXACT",
    )
    pilot_missing = call_missing if pilot else call_missing + (
        "SOURCE_READINESS_NOT_12_OF_12",
    )
    return ProviderHealthActivationReadiness(
        status="TEST_READINESS",
        evaluated_at=NOW,
        expected_deployed_revision="01782375",
        deployed_revision="01782375" if loop else None,
        loop_ready=loop,
        provider_call_ready=call,
        pilot_ready=pilot,
        loop_missing=loop_missing,
        provider_call_missing=call_missing,
        pilot_missing=pilot_missing,
    )


def test_packet_is_deterministic_and_exact_revision_bound() -> None:
    first = build_provider_health_activation_change_packet(_readiness())
    second = build_provider_health_activation_change_packet(_readiness())

    assert first == second
    assert first.packet_id == second.packet_id
    assert first.expected_deployed_revision == "01782375"
    assert first.tenant == "org-org/dev-project"


def test_change_steps_are_ordered_and_gate_bound() -> None:
    packet = build_provider_health_activation_change_packet(_readiness())

    assert [step.step_id for step in packet.change_steps] == [
        "PHC-01-VERIFY-BASELINE",
        "PHC-02-DEPLOY-EXACT-REVISION",
        "PHC-03-INSTALL-PLUGIN-AND-ACTIONTYPE",
        "PHC-04-CONFIGURE-CANONICAL-STARTUP",
        "PHC-05-RESTART-SINGLE-INSTANCE",
        "PHC-06-VERIFY-LOOP-GATE",
        "PHC-07-ISSUE-EXACT-ACTION-AUTHORITY",
        "PHC-08-VERIFY-PROVIDER-CALL-GATE",
        "PHC-09-RUN-ONE-BOUNDED-HEALTH-ACTION",
        "PHC-10-WAIT-NATURAL-SOURCE-READINESS",
        "PHC-11-VERIFY-REAL-PILOT-GATE",
    ]
    assert packet.change_steps[5].required_gate == "loop_ready"
    assert packet.change_steps[7].required_gate == "provider_call_ready"
    assert packet.change_steps[-1].required_gate == "pilot_ready"
    assert packet.change_steps[8].effect_class == "bounded_external_effect"


def test_rollback_fences_calls_and_closes_loop_before_restoring_state() -> None:
    packet = build_provider_health_activation_change_packet(_readiness())

    rollback_ids = [step.step_id for step in packet.rollback_steps]
    assert rollback_ids == [
        "PHR-01-FENCE-PROVIDER-CALLS",
        "PHR-02-DISABLE-CANONICAL-LOOP",
        "PHR-03-RESTART-SINGLE-INSTANCE-FAIL-CLOSED",
        "PHR-04-VERIFY-LOOP-ABSENT",
        "PHR-05-RESTORE-PLUGIN-ACTIONTYPE-STATE",
        "PHR-06-RESTORE-REVISION-AND-ENV-SNAPSHOT",
        "PHR-07-VERIFY-BASELINE",
    ]
    assert rollback_ids.index("PHR-04-VERIFY-LOOP-ABSENT") < rollback_ids.index(
        "PHR-05-RESTORE-PLUGIN-ACTIONTYPE-STATE"
    )


def test_green_readiness_never_turns_packet_into_execution_authority() -> None:
    packet = build_provider_health_activation_change_packet(
        _readiness(loop=True, call=True, pilot=True)
    )

    assert packet.readiness_status == "TEST_READINESS"
    assert packet.execution_authorized is False
    assert packet.authorization_status == "SEPARATE_EXACT_APPROVAL_REQUIRED"


def test_public_packet_contains_no_secret_or_executable_payload() -> None:
    public = build_provider_health_activation_change_packet(_readiness()).as_public_dict()
    rendered = repr(public).lower()

    assert public["executionAuthorized"] is False
    assert "command" not in rendered
    assert "secret" not in rendered
    assert "credential" not in rendered
    assert "token" not in rendered
    assert "password" not in rendered
    assert "callback" not in rendered


@pytest.mark.parametrize(
    "readiness",
    [
        replace(_readiness(), loop_ready=False, provider_call_ready=True),
        replace(_readiness(), provider_call_ready=False, pilot_ready=True),
    ],
)
def test_inconsistent_gate_progression_is_rejected(readiness) -> None:
    with pytest.raises(ValueError, match="readiness requires"):
        build_provider_health_activation_change_packet(readiness)
