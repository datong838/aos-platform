"""Read-only Provider Health current readiness audit acceptance."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_provider_health_activation_audit import (
    ActivationFactSlice,
    audit_provider_health_activation,
)


NOW = datetime(2026, 8, 29, 0, 5, tzinfo=UTC)
CUTOFF = NOW - timedelta(minutes=5)
TENANT = "org-org/dev-project"


def _values(*, green: bool = True):
    return {
        "deployment": {
            "expected_deployed_revision": "2c676919",
            "deployed_revision": "2c676919" if green else None,
        },
        "environment": {"canonical_environment_exact": green},
        "plugin": {
            "plugin_installed": green,
            "action_type_exact": green,
        },
        "authority": {
            "proposal_exact": green,
            "approval_exact": green,
            "lease_exact": green,
            "receipt_authority_exact": green,
            "lease_expires_at": NOW + timedelta(minutes=10) if green else None,
        },
        "health": {
            "healthy_probe_count": 3 if green else 0,
            "required_probe_count": 3,
            "health_expires_at": NOW + timedelta(minutes=10) if green else NOW,
            "health_cutoff": CUTOFF,
        },
        "source_readiness": {
            "source_ready_count": 12 if green else 10,
            "source_required_count": 12,
            "source_readiness_fresh_until": (
                NOW + timedelta(minutes=10) if green else NOW
            ),
            "source_readiness_cutoff": CUTOFF,
        },
        "binding": {
            "binding_exact": green,
            "binding_operational": green,
            "binding_expires_at": NOW + timedelta(minutes=10) if green else NOW,
            "binding_cutoff": CUTOFF,
        },
    }


def _readers(*, green: bool = True, counters=None):
    counters = counters if counters is not None else {}
    readers = {}
    for source_id, values in _values(green=green).items():
        counters[source_id] = 0

        def read(tenant, evaluated_at, *, _source=source_id, _values=values):
            counters[_source] += 1
            assert tenant == TENANT
            assert evaluated_at == NOW
            return ActivationFactSlice(
                source_id=_source,
                tenant=tenant,
                observed_at=CUTOFF,
                values=_values,
            )

        readers[source_id] = read
    return readers


def test_each_reader_is_called_once_and_green_facts_compose_packet() -> None:
    calls = {}

    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=NOW,
        readers=_readers(counters=calls),
    )

    assert result.audit_green is True
    assert result.readiness is not None and result.readiness.pilot_ready is True
    assert result.change_packet is not None
    assert result.change_packet.execution_authorized is False
    assert all(count == 1 for count in calls.values())


def test_complete_but_not_ready_facts_are_a_green_audit_not_fake_readiness() -> None:
    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=NOW,
        readers=_readers(green=False),
    )

    assert result.audit_green is True
    assert result.readiness is not None
    assert result.readiness.loop_ready is False
    assert result.readiness.provider_call_ready is False
    assert result.readiness.pilot_ready is False
    assert "SOURCE_READINESS_NOT_12_OF_12" in result.readiness.pilot_missing


def test_wrong_tenant_fails_before_any_reader() -> None:
    calls = {}
    readers = _readers(counters=calls)

    result = audit_provider_health_activation(
        tenant="dev-org/dev-project",
        evaluated_at=NOW,
        readers=readers,
    )

    assert result.audit_codes == ("AUDIT_TENANT_NOT_CANONICAL",)
    assert result.readiness is None
    assert all(count == 0 for count in calls.values())


def test_missing_or_failed_reader_has_stable_code_without_defaulting_to_zero() -> None:
    readers = _readers()
    readers.pop("binding")

    def failed_reader(tenant, evaluated_at):
        raise RuntimeError("credential-shaped internal detail")

    readers["health"] = failed_reader
    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=NOW,
        readers=readers,
    )

    assert result.readiness is None
    assert result.change_packet is None
    assert result.audit_codes == (
        "AUDIT_READER_HEALTH_FAILED",
        "AUDIT_READER_BINDING_MISSING",
    )
    assert "credential-shaped" not in repr(result.as_public_dict())


def test_slice_tenant_and_source_mismatch_fail_closed() -> None:
    readers = _readers()
    original = readers["plugin"]

    def mismatched(tenant, evaluated_at):
        item = original(tenant, evaluated_at)
        return ActivationFactSlice(
            source_id="environment",
            tenant="dev-org/dev-project",
            observed_at=item.observed_at,
            values=item.values,
        )

    readers["plugin"] = mismatched
    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=NOW,
        readers=readers,
    )

    assert result.readiness is None
    assert "AUDIT_READER_PLUGIN_SOURCE_MISMATCH" in result.audit_codes
    assert "AUDIT_READER_PLUGIN_TENANT_MISMATCH" in result.audit_codes


def test_fact_cutoff_drift_is_reported_but_readiness_remains_inspectable() -> None:
    readers = _readers()
    original = readers["binding"]

    def drifted(tenant, evaluated_at):
        item = original(tenant, evaluated_at)
        values = dict(item.values)
        values["binding_cutoff"] = CUTOFF - timedelta(seconds=1)
        return ActivationFactSlice(
            source_id=item.source_id,
            tenant=item.tenant,
            observed_at=item.observed_at,
            values=values,
        )

    readers["binding"] = drifted
    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=NOW,
        readers=readers,
    )

    assert result.audit_codes == ("AUDIT_FACT_CUTOFF_MISMATCH",)
    assert result.readiness is not None
    assert result.readiness.pilot_ready is False


def test_public_output_is_sanitized_and_has_no_executable_surface() -> None:
    public = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=NOW,
        readers=_readers(),
    ).as_public_dict()
    rendered = repr(public).lower()

    assert public["executionAuthorized"] is False
    assert "callback" not in rendered
    assert "command" not in rendered
    assert "password" not in rendered
    assert "secret" not in rendered
    assert "token" not in rendered


def test_fact_slice_copies_values_into_an_immutable_snapshot() -> None:
    source = {"canonical_environment_exact": True}
    item = ActivationFactSlice("environment", TENANT, CUTOFF, source)
    source["canonical_environment_exact"] = False

    assert item.values["canonical_environment_exact"] is True
    with pytest.raises(TypeError):
        item.values["canonical_environment_exact"] = False
