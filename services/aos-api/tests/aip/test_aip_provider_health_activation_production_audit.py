"""Deterministic production audit entrypoint acceptance."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api.aip_provider_health_activation_audit import ActivationFactSlice
from aos_api.aip_provider_health_activation_authority_readers import (
    ExactActionAuthoritySelection,
    ExactBindingRef,
    ExactBindingSelection,
)
from aos_api.aip_provider_health_activation_production_audit import (
    ProviderHealthProductionAuditRequest,
    run_provider_health_production_audit,
)


TENANT = "org-org/dev-project"
NOW = datetime(2026, 8, 29, 1, 20, tzinfo=UTC)
CUTOFF = NOW - timedelta(minutes=1)
FRESH = NOW + timedelta(minutes=10)
ACTION_HASH = "a" * 64
PROPOSAL_HASH = "b" * 64
DEPENDENCY_HASH = "c" * 64


def _request(*, tenant: str = TENANT) -> ProviderHealthProductionAuditRequest:
    return ProviderHealthProductionAuditRequest(
        tenant=tenant,
        expected_deployed_revision="d0fd17b3",
        expected_action_type_revision_hash=ACTION_HASH,
        action=ExactActionAuthoritySelection(
            proposal_id="proposal-1",
            proposal_hash=PROPOSAL_HASH,
            proposal_version=1,
            lease_id="lease-1",
            lease_owner_id="provider-health-worker",
            action_type_revision_hash=ACTION_HASH,
        ),
        bindings=ExactBindingSelection(
            refs=(
                ExactBindingRef(
                    kind="capability",
                    binding_id="binding-1",
                    version=2,
                    dependency_snapshot_hash=DEPENDENCY_HASH,
                ),
            )
        ),
    )


def _readers(calls: dict[str, int]):
    values = {
        "deployment": {
            "expected_deployed_revision": "d0fd17b3",
            "deployed_revision": "d0fd17b3",
        },
        "environment": {"canonical_environment_exact": True},
        "plugin": {"plugin_installed": True, "action_type_exact": True},
        "authority": {
            "proposal_exact": True,
            "approval_exact": True,
            "lease_exact": True,
            "receipt_authority_exact": True,
            "lease_expires_at": FRESH,
        },
        "health": {
            "healthy_probe_count": 3,
            "required_probe_count": 3,
            "health_expires_at": FRESH,
            "health_cutoff": CUTOFF,
        },
        "source_readiness": {
            "source_ready_count": 12,
            "source_required_count": 12,
            "source_readiness_fresh_until": FRESH,
            "source_readiness_cutoff": CUTOFF,
        },
        "binding": {
            "binding_exact": True,
            "binding_operational": True,
            "binding_expires_at": FRESH,
            "binding_cutoff": CUTOFF,
        },
    }
    readers = {}
    for source_id, fields in values.items():
        calls[source_id] = 0

        def read(tenant, evaluated_at, *, _source=source_id, _fields=fields):
            calls[_source] += 1
            return ActivationFactSlice(_source, tenant, CUTOFF, _fields)

        readers[source_id] = read
    return readers


def test_entrypoint_composes_exact_selections_and_reads_every_source_once(
    monkeypatch,
) -> None:
    import aos_api.aip_provider_health_activation_production_audit as subject

    observed = {}
    calls: dict[str, int] = {}

    def action_builder(selection):
        observed["action"] = selection
        return object()

    def binding_builder(selection):
        observed["bindings"] = selection
        return object()

    def bundle_builder(**kwargs):
        observed["bundle"] = kwargs
        return SimpleNamespace(collected_at=NOW, readers=_readers(calls))

    monkeypatch.setattr(subject, "build_exact_action_authority_owner_reader", action_builder)
    monkeypatch.setattr(subject, "build_exact_binding_owner_reader", binding_builder)
    monkeypatch.setattr(subject, "build_production_activation_fact_readers", bundle_builder)

    request = _request()
    result = run_provider_health_production_audit(request)

    assert observed["action"] is request.action
    assert observed["bindings"] is request.bindings
    assert observed["bundle"]["expected_deployed_revision"] == "d0fd17b3"
    assert observed["bundle"]["expected_action_type_revision_hash"] == ACTION_HASH
    assert result.audit_green is True
    assert result.readiness is not None and result.readiness.pilot_ready is True
    assert all(count == 1 for count in calls.values())
    assert result.as_public_dict()["executionAuthorized"] is False


def test_wrong_tenant_is_rejected_before_any_owner_builder(monkeypatch) -> None:
    import aos_api.aip_provider_health_activation_production_audit as subject

    calls = {"owner": 0}

    def forbidden(*args, **kwargs):
        calls["owner"] += 1
        raise AssertionError("owner must not be read")

    monkeypatch.setattr(subject, "build_exact_action_authority_owner_reader", forbidden)
    monkeypatch.setattr(subject, "build_exact_binding_owner_reader", forbidden)
    monkeypatch.setattr(subject, "build_production_activation_fact_readers", forbidden)

    with pytest.raises(ValueError, match="canonical"):
        run_provider_health_production_audit(_request(tenant="dev-org/dev-project"))

    assert calls == {"owner": 0}


def test_request_rejects_revision_drift_and_empty_deployment_revision() -> None:
    base = _request()
    with pytest.raises(ValueError, match="expected_deployed_revision"):
        ProviderHealthProductionAuditRequest(
            tenant=TENANT,
            expected_deployed_revision=" ",
            expected_action_type_revision_hash=ACTION_HASH,
            action=base.action,
            bindings=base.bindings,
        )
    with pytest.raises(ValueError, match="must match"):
        ProviderHealthProductionAuditRequest(
            tenant=TENANT,
            expected_deployed_revision="d0fd17b3",
            expected_action_type_revision_hash="d" * 64,
            action=base.action,
            bindings=base.bindings,
        )


def test_public_result_does_not_expose_selection_or_callable_surface(monkeypatch) -> None:
    import aos_api.aip_provider_health_activation_production_audit as subject

    monkeypatch.setattr(
        subject,
        "build_exact_action_authority_owner_reader",
        lambda selection: object(),
    )
    monkeypatch.setattr(
        subject,
        "build_exact_binding_owner_reader",
        lambda selection: object(),
    )
    monkeypatch.setattr(
        subject,
        "build_production_activation_fact_readers",
        lambda **kwargs: SimpleNamespace(collected_at=NOW, readers=_readers({})),
    )

    public = run_provider_health_production_audit(_request()).as_public_dict()
    rendered = repr(public).lower()

    assert public["executionAuthorized"] is False
    for forbidden in (
        "proposal-1",
        "lease-1",
        "binding-1",
        "secret",
        "password",
        "token",
        "callback",
        "execute",
        "refresh",
    ):
        assert forbidden not in rendered
