from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api.aip_agent_control_contracts import ActivateAgentInstanceRequest
from aos_api.aip_agent_instance_activation_service import (
    AipAgentInstanceActivationService,
)
from aos_api.aip_agent_registry_contracts import (
    AgentInstanceOverlay,
    AgentInstanceStatus,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryTransitionBlocked
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 17, 13, 30, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")


def _ref(kind: str, asset_id: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=kind,
        asset_id=asset_id,
        revision=1,
        content_hash="a" * 64,
    )


def _instance(status: AgentInstanceStatus = AgentInstanceStatus.PROVISIONING):
    return SimpleNamespace(
        instance_id="ecommerce.data_advisor.default",
        status=status,
        version=1 if status is AgentInstanceStatus.PROVISIONING else 2,
        template=_ref("AgentTemplate", "ecommerce.data_advisor"),
        overlay=AgentInstanceOverlay(),
    )


def _binding(**overrides):
    value = {
        "binding_id": "strategy-plan-qyh",
        "status": "active",
        "health": "healthy",
        "operational_readiness": "available",
        "allow_degraded": False,
        "dependency_snapshot_hash": "b" * 64,
        "readiness_expires_at": NOW + timedelta(minutes=10),
    }
    value.update(overrides)
    return value


class _Store:
    def __init__(self, instance=None):
        self.instance = instance or _instance()
        self.updated = False

    def get_instance(self, *_args):
        return self.instance

    def update_instance(self, *_args, **_kwargs):
        self.updated = True
        return _instance(AgentInstanceStatus.ACTIVE), SimpleNamespace(receipt_id="r1")


class _Connection:
    def __init__(self, bindings):
        self.bindings = bindings

    def execute(self, query, _params):
        if "aip_agent_template_revision" in query:
            return SimpleNamespace(
                fetchone=lambda: {"lifecycle": "published", "content_hash": "a" * 64}
            )
        return SimpleNamespace(fetchall=lambda: self.bindings)


def _connect(bindings):
    @contextmanager
    def factory(_scope):
        yield _Connection(bindings)

    return factory


def _request() -> ActivateAgentInstanceRequest:
    return ActivateAgentInstanceRequest(
        expected_version=1,
        capability_binding_ids=["strategy-plan-qyh"],
    )


def test_activation_requires_and_consumes_fresh_binding() -> None:
    store = _Store()
    service = AipAgentInstanceActivationService(
        connect_factory=_connect([_binding()]), store=store
    )
    instance, _ = service.activate(
        SCOPE,
        "ecommerce.data_advisor.default",
        _request(),
        idempotency_key="activate-d03",
        actor="pytest",
        occurred_at=NOW,
    )
    assert instance.status is AgentInstanceStatus.ACTIVE
    assert store.updated is True


@pytest.mark.parametrize(
    "binding",
    [
        _binding(status="provisioning"),
        _binding(health="unavailable"),
        _binding(operational_readiness="blocked"),
        _binding(readiness_expires_at=NOW),
    ],
)
def test_activation_fails_closed_for_unusable_binding(binding) -> None:
    store = _Store()
    service = AipAgentInstanceActivationService(
        connect_factory=_connect([binding]), store=store
    )
    with pytest.raises(
        AipAgentRegistryTransitionBlocked,
        match="fresh active CapabilityBinding",
    ):
        service.activate(
            SCOPE,
            "ecommerce.data_advisor.default",
            _request(),
            idempotency_key="activate-d03",
            actor="pytest",
            occurred_at=NOW,
        )
    assert store.updated is False


def test_activation_fails_when_binding_is_missing_from_tenant_scope() -> None:
    store = _Store()
    service = AipAgentInstanceActivationService(
        connect_factory=_connect([]), store=store
    )
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="tenant scope"):
        service.activate(
            SCOPE,
            "ecommerce.data_advisor.default",
            _request(),
            idempotency_key="activate-d03",
            actor="pytest",
            occurred_at=NOW,
        )


def test_active_instance_delegates_to_registry_receipt_replay() -> None:
    store = _Store(_instance(AgentInstanceStatus.ACTIVE))
    service = AipAgentInstanceActivationService(
        connect_factory=_connect([]), store=store
    )
    instance, _ = service.activate(
        SCOPE,
        "ecommerce.data_advisor.default",
        _request(),
        idempotency_key="activate-d03",
        actor="pytest",
        occurred_at=NOW,
    )
    assert instance.status is AgentInstanceStatus.ACTIVE
    assert store.updated is True
