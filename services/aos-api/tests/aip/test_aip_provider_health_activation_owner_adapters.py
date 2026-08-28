"""Production read-only Provider Health activation owner adapter acceptance."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api.aip_action_store import AipActionNotFound
from aos_api.aip_provider_health_activation_audit import (
    audit_provider_health_activation,
)
from aos_api.aip_provider_health_activation_fact_readers import (
    AuthorityFactSnapshot,
    BindingFactSnapshot,
    CANONICAL_ENVIRONMENT,
    CANONICAL_PROVIDER_REVISIONS,
)
from aos_api.aip_provider_health_activation_owner_adapters import (
    DEPLOYED_REVISION_ENV,
    build_production_activation_fact_readers,
)


TENANT = "org-org/dev-project"
START = datetime(2026, 8, 29, 0, 40, tzinfo=UTC)
CHECKED = START + timedelta(seconds=1)
COLLECTED = START + timedelta(seconds=2)
FRESH = START + timedelta(minutes=10)
EXPECTED_REVISION = "8f65f206"
EXPECTED_ACTION_HASH = "b" * 64


def _clock():
    values = iter((START, COLLECTED))
    return lambda: next(values)


def _authority(tenant, evaluated_at):
    return AuthorityFactSnapshot(
        tenant, START, True, True, True, True, FRESH
    )


def _binding(tenant, evaluated_at):
    return BindingFactSnapshot(tenant, START, True, True, FRESH, START)


def _health(*, green=True):
    return [
        SimpleNamespace(
            provider=SimpleNamespace(asset_id=provider_id, revision=revision),
            status="healthy" if green else "unhealthy",
            expires_at=FRESH if green else START,
        )
        for provider_id, revision in CANONICAL_PROVIDER_REVISIONS.items()
    ]


def _source(*, ready=12):
    sources = [
        SimpleNamespace(
            status="ready" if index < ready else "failed",
            freshness_expires_at=FRESH,
        )
        for index in range(12)
    ]
    return SimpleNamespace(
        checked_at=CHECKED,
        cutoff_at=START,
        sources=sources,
    )


def _bundle(**overrides):
    config = {
        "expected_deployed_revision": EXPECTED_REVISION,
        "expected_action_type_revision_hash": EXPECTED_ACTION_HASH,
        "authority_reader": _authority,
        "binding_reader": _binding,
        "environ": {
            **CANONICAL_ENVIRONMENT,
            DEPLOYED_REVISION_ENV: EXPECTED_REVISION,
        },
        "clock": _clock(),
        "plugin_catalog_reader": lambda: {
            "items": [
                {
                    "id": "provider-health-probe",
                    "installed": True,
                    "actionTypeId": "aip.provider-health-probe",
                }
            ]
        },
        "action_type_reader": lambda scope, action_type_id: {
            "revisionHash": EXPECTED_ACTION_HASH
        },
        "health_reader": lambda scope: _health(),
        "source_readiness_reader": lambda org_id, project_id: _source(),
    }
    config.update(overrides)
    return build_production_activation_fact_readers(**config)


def test_production_bundle_reads_each_owner_once_and_audits_green() -> None:
    calls = {name: 0 for name in ("plugin", "action", "health", "source")}

    def counted(name, result):
        def read(*args):
            calls[name] += 1
            return result()

        return read

    bundle = _bundle(
        plugin_catalog_reader=counted(
            "plugin",
            lambda: {
                "items": [
                    {
                        "id": "provider-health-probe",
                        "installed": True,
                        "actionTypeId": "aip.provider-health-probe",
                    }
                ]
            },
        ),
        action_type_reader=counted(
            "action", lambda: {"revisionHash": EXPECTED_ACTION_HASH}
        ),
        health_reader=counted("health", lambda: _health()),
        source_readiness_reader=counted("source", lambda: _source()),
    )
    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=bundle.collected_at,
        readers=bundle.readers,
    )

    assert result.audit_green is True
    assert result.readiness is not None and result.readiness.pilot_ready is True
    assert calls == {"plugin": 1, "action": 1, "health": 1, "source": 1}


def test_current_missing_revision_actiontype_and_10_of_12_remain_explicit() -> None:
    def missing_action(scope, action_type_id):
        raise AipActionNotFound("not found")

    bundle = _bundle(
        environ={},
        plugin_catalog_reader=lambda: {
            "items": [
                {
                    "id": "provider-health-probe",
                    "installed": False,
                    "actionTypeId": "aip.provider-health-probe",
                }
            ]
        },
        action_type_reader=missing_action,
        health_reader=lambda scope: _health(green=False),
        source_readiness_reader=lambda org_id, project_id: _source(ready=10),
        authority_reader=lambda tenant, at: AuthorityFactSnapshot(
            tenant, START, False, False, False, False, None
        ),
        binding_reader=lambda tenant, at: BindingFactSnapshot(
            tenant, START, False, False, None, None
        ),
    )
    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=bundle.collected_at,
        readers=bundle.readers,
    )

    assert result.readiness is not None
    assert result.readiness.loop_ready is False
    assert "DEPLOYED_REVISION_NOT_EXACT" in result.readiness.loop_missing
    assert "PROVIDER_HEALTH_ACTION_TYPE_NOT_EXACT" in result.readiness.loop_missing
    assert "SOURCE_READINESS_NOT_12_OF_12" in result.readiness.pilot_missing


def test_action_authority_and_binding_owner_readers_are_mandatory() -> None:
    with pytest.raises(ValueError, match="are required"):
        _bundle(authority_reader=None)
    with pytest.raises(ValueError, match="are required"):
        _bundle(binding_reader=None)


def test_source_readiness_must_return_exact_twelve_sources() -> None:
    bundle = _bundle(
        source_readiness_reader=lambda org_id, project_id: SimpleNamespace(
            checked_at=CHECKED,
            cutoff_at=START,
            sources=_source().sources[:11],
        )
    )
    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=bundle.collected_at,
        readers=bundle.readers,
    )

    assert result.readiness is None
    assert result.audit_codes == (
        "AUDIT_READER_SOURCE_READINESS_FAILED",
    )


def test_missing_exact_health_provider_is_not_defaulted_to_zero() -> None:
    bundle = _bundle(health_reader=lambda scope: _health()[:2])
    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=bundle.collected_at,
        readers=bundle.readers,
    )

    assert result.readiness is None
    assert result.audit_codes == ("AUDIT_READER_HEALTH_FAILED",)


def test_bundle_is_cached_and_contains_no_mutating_dependency() -> None:
    bundle = _bundle()
    first = bundle.readers["plugin"](TENANT, bundle.collected_at)
    second = bundle.readers["plugin"](TENANT, bundle.collected_at)
    rendered = repr(first.values).lower() + " " + repr(bundle.readers).lower()

    assert first == second
    for forbidden in ("password", "secretref", "refresh", "execute", "write"):
        assert forbidden not in rendered


def test_owner_failure_is_sanitized_by_audit_without_secret_detail() -> None:
    secret_detail = "password=must-not-escape"

    def broken_plugin():
        raise RuntimeError(secret_detail)

    bundle = _bundle(plugin_catalog_reader=broken_plugin)
    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=bundle.collected_at,
        readers=bundle.readers,
    )

    assert result.audit_codes == ("AUDIT_READER_PLUGIN_FAILED",)
    assert secret_detail not in repr(result)


def test_multiple_owner_failures_are_collected_without_short_circuit() -> None:
    calls = {name: 0 for name in ("plugin", "health", "source", "authority")}

    def counted(name, result=None, *, fail=False):
        def read(*args):
            calls[name] += 1
            if fail:
                raise RuntimeError("private owner detail")
            return result()

        return read

    bundle = _bundle(
        plugin_catalog_reader=counted(
            "plugin",
            lambda: {
                "items": [
                    {
                        "id": "provider-health-probe",
                        "installed": True,
                        "actionTypeId": "aip.provider-health-probe",
                    }
                ]
            },
        ),
        health_reader=counted("health", lambda: _health()),
        source_readiness_reader=counted("source", fail=True),
        authority_reader=counted("authority", fail=True),
    )
    result = audit_provider_health_activation(
        tenant=TENANT,
        evaluated_at=bundle.collected_at,
        readers=bundle.readers,
    )

    assert result.audit_codes == (
        "AUDIT_READER_AUTHORITY_FAILED",
        "AUDIT_READER_SOURCE_READINESS_FAILED",
    )
    assert calls == {"plugin": 1, "health": 1, "source": 1, "authority": 1}
    assert "private owner detail" not in repr(result)
