"""Canonical Provider Health activation fact reader acceptance."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from aos_api.aip_provider_health_activation_audit import (
    audit_provider_health_activation,
)
from aos_api.aip_provider_health_activation_fact_readers import (
    ActivationFactOwnerReaders,
    AuthorityFactSnapshot,
    BindingFactSnapshot,
    CANONICAL_ENVIRONMENT,
    CANONICAL_PROVIDER_REVISIONS,
    DeploymentFactSnapshot,
    EnvironmentFactSnapshot,
    HealthFactSnapshot,
    HealthObservationSnapshot,
    PluginFactSnapshot,
    SourceReadinessFactSnapshot,
    build_canonical_activation_fact_readers,
)
from aos_api.aip_provider_health_action import (
    PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
)


TENANT = "org-org/dev-project"
NOW = datetime(2026, 8, 29, 0, 30, tzinfo=UTC)
CUTOFF = NOW - timedelta(minutes=1)
FRESH = NOW + timedelta(minutes=10)
EXPECTED_REVISION = "a262d50c"
EXPECTED_ACTION_HASH = "a" * 64


def _snapshots(*, green: bool = True):
    return {
        "deployment": DeploymentFactSnapshot(
            TENANT, CUTOFF, EXPECTED_REVISION if green else None
        ),
        "environment": EnvironmentFactSnapshot(
            TENANT,
            CUTOFF,
            CANONICAL_ENVIRONMENT if green else {},
        ),
        "plugin": PluginFactSnapshot(
            TENANT,
            CUTOFF,
            "provider-health-probe",
            green,
            PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
            EXPECTED_ACTION_HASH if green else None,
        ),
        "authority": AuthorityFactSnapshot(
            TENANT,
            CUTOFF,
            green,
            green,
            green,
            green,
            FRESH if green else None,
        ),
        "health": HealthFactSnapshot(
            TENANT,
            CUTOFF,
            CUTOFF,
            tuple(
                HealthObservationSnapshot(
                    provider_id,
                    revision,
                    green,
                    FRESH if green else CUTOFF,
                )
                for provider_id, revision in CANONICAL_PROVIDER_REVISIONS.items()
            ),
        ),
        "source_readiness": SourceReadinessFactSnapshot(
            TENANT,
            CUTOFF,
            12 if green else 10,
            12,
            FRESH if green else CUTOFF,
            CUTOFF,
        ),
        "binding": BindingFactSnapshot(
            TENANT,
            CUTOFF,
            green,
            green,
            FRESH if green else None,
            CUTOFF if green else None,
        ),
    }


def _owners(*, green: bool = True, calls=None):
    calls = calls if calls is not None else {}
    snapshots = _snapshots(green=green)
    readers = {}
    for source_id, snapshot in snapshots.items():
        calls[source_id] = 0

        def read(tenant, evaluated_at, *, _source=source_id, _item=snapshot):
            calls[_source] += 1
            return _item

        readers[source_id] = read
    return ActivationFactOwnerReaders(**readers)


def _factory(owners):
    return build_canonical_activation_fact_readers(
        expected_deployed_revision=EXPECTED_REVISION,
        expected_action_type_revision_hash=EXPECTED_ACTION_HASH,
        owners=owners,
    )


def test_all_exact_owner_snapshots_open_readiness_but_not_execution() -> None:
    calls = {}
    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=NOW,
        readers=_factory(_owners(calls=calls)),
    )

    assert result.audit_green is True
    assert result.readiness is not None and result.readiness.pilot_ready is True
    assert result.change_packet is not None
    assert result.change_packet.execution_authorized is False
    assert all(count == 1 for count in calls.values())


def test_current_false_owner_facts_remain_complete_and_not_ready() -> None:
    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=NOW,
        readers=_factory(_owners(green=False)),
    )

    assert result.audit_codes == ("AUDIT_FACT_CUTOFF_MISSING",)
    assert result.readiness is not None
    assert result.readiness.loop_ready is False
    assert result.readiness.pilot_ready is False


def test_environment_requires_exact_keys_and_values() -> None:
    snapshots = _snapshots()
    values = dict(CANONICAL_ENVIRONMENT)
    values["UNRELATED"] = "true"
    snapshots["environment"] = EnvironmentFactSnapshot(TENANT, CUTOFF, values)
    owners = _owners()
    owners = replace(
        owners,
        environment=lambda tenant, evaluated_at: snapshots["environment"],
    )
    result = audit_provider_health_activation(
        tenant=TENANT, evaluated_at=NOW, readers=_factory(owners)
    )

    assert result.readiness is not None
    assert "CANONICAL_ENVIRONMENT_NOT_EXACT" in result.readiness.loop_missing


def test_source_denominator_drift_becomes_stable_reader_failure() -> None:
    owners = _owners()
    bad = replace(
        _snapshots()["source_readiness"], ready_count=10, required_count=11
    )
    owners = replace(
        owners,
        source_readiness=lambda tenant, evaluated_at: bad,
    )
    result = audit_provider_health_activation(
        tenant=TENANT, evaluated_at=NOW, readers=_factory(owners)
    )

    assert result.readiness is None
    assert result.audit_codes == (
        "AUDIT_READER_SOURCE_READINESS_FAILED",
    )


def test_noncanonical_or_duplicate_health_set_fails_reader() -> None:
    owners = _owners()
    health = _snapshots()["health"]
    duplicate = replace(
        health,
        observations=(health.observations[0],) * 3,
    )
    owners = replace(owners, health=lambda tenant, evaluated_at: duplicate)
    result = audit_provider_health_activation(
        tenant=TENANT, evaluated_at=NOW, readers=_factory(owners)
    )

    assert result.readiness is None
    assert result.audit_codes == ("AUDIT_READER_HEALTH_FAILED",)


def test_owner_exception_is_sanitized_by_audit_boundary() -> None:
    owners = replace(
        _owners(),
        authority=lambda tenant, evaluated_at: (_ for _ in ()).throw(
            RuntimeError("password shaped detail")
        ),
    )
    result = audit_provider_health_activation(
        tenant=TENANT, evaluated_at=NOW, readers=_factory(owners)
    )

    assert result.audit_codes == ("AUDIT_READER_AUTHORITY_FAILED",)
    assert "password shaped" not in repr(result.as_public_dict())


def test_factory_has_readers_only_and_no_mutating_surface() -> None:
    readers = _factory(_owners())
    rendered = " ".join([*readers, *(reader.__name__ for reader in readers.values())])

    assert set(readers) == {
        "deployment",
        "environment",
        "plugin",
        "authority",
        "health",
        "source_readiness",
        "binding",
    }
    for forbidden in ("write", "refresh", "execute", "provider", "secret"):
        assert forbidden not in rendered.lower()
