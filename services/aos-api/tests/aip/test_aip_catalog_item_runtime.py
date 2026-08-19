from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from aos_api.aip_agent_registry_contracts import (
    AgentInstanceStatus,
    CapabilityReadiness,
    TemplateLifecycle,
    VersionedAssetRef,
)
from aos_api.aip_ecommerce_agent_installer import compute_catalog_item_runtime

NOW = datetime(2026, 8, 18, 13, 30, tzinfo=UTC)
HASH = "a" * 64


def skill(*, published: bool = True, caps=("strategy.plan",)):
    return SimpleNamespace(
        skill_id="ecommerce.skill.D03",
        revision=4,
        lifecycle=TemplateLifecycle.PUBLISHED if published else TemplateLifecycle.EVALUATED,
        required_capabilities=list(caps),
    )


def instance(*, status=AgentInstanceStatus.ACTIVE):
    return SimpleNamespace(
        instance_id="ecommerce.data_advisor.default",
        status=status,
    )


def skill_binding(*, fresh: bool = True, status="active"):
    return SimpleNamespace(
        instance_id="ecommerce.data_advisor.default",
        status=status,
        readiness=CapabilityReadiness.AVAILABLE,
        readiness_expires_at=NOW + timedelta(minutes=10) if fresh else NOW - timedelta(minutes=1),
        skill=VersionedAssetRef(
            assetType="SkillTemplate",
            assetId="ecommerce.skill.D03",
            revision=4,
            contentHash=HASH,
        ),
    )


def cap_binding(*, fresh: bool = True, status="active"):
    return SimpleNamespace(
        status=status,
        operational_readiness=CapabilityReadiness.AVAILABLE,
        readiness_expires_at=NOW + timedelta(minutes=10) if fresh else NOW - timedelta(minutes=1),
        capability=VersionedAssetRef(
            assetType="CapabilityRevision",
            assetId="strategy.plan",
            revision=2,
            contentHash=HASH,
        ),
    )


def test_active_pilot_with_fresh_bindings_is_runnable() -> None:
    readiness, blockers = compute_catalog_item_runtime(
        instance=instance(),
        role_skills=[skill()],
        skill_bindings=[skill_binding()],
        capability_bindings=[cap_binding()],
        now=NOW,
    )
    assert readiness == "runnable"
    assert blockers == []


def test_provisioning_colleague_stays_blocked() -> None:
    readiness, blockers = compute_catalog_item_runtime(
        instance=instance(status=AgentInstanceStatus.PROVISIONING),
        role_skills=[skill(published=False)],
        skill_bindings=[],
        capability_bindings=[],
        now=NOW,
    )
    assert readiness == "blocked"
    assert "agent_instance_not_active" in blockers
    assert "skill_templates_not_published" in blockers
    assert "skill_binding_unavailable" in blockers
    assert "capability_bindings_unavailable" in blockers


def test_stale_skill_binding_is_not_runnable() -> None:
    readiness, blockers = compute_catalog_item_runtime(
        instance=instance(),
        role_skills=[skill()],
        skill_bindings=[skill_binding(fresh=False)],
        capability_bindings=[cap_binding()],
        now=NOW,
    )
    assert readiness == "blocked"
    assert "skill_binding_readiness_stale" in blockers
    assert blockers != []


def test_refresh_binding_readiness_soft_fails_and_continues() -> None:
    from aos_api.aip_ecommerce_agent_installer import AipEcommerceAgentInstaller
    from aos_api.auth import Principal

    principal = Principal(
        subject="pytest",
        org_id="org-org",
        project_id="dev-project",
        roles=["owner"],
    )
    stale_cap = SimpleNamespace(
        binding_id="cap-stale",
        status="active",
        version=2,
        operational_readiness=CapabilityReadiness.BLOCKED,
        readiness_expires_at=NOW - timedelta(minutes=1),
        dependencies=SimpleNamespace(),
    )
    fresh_cap = SimpleNamespace(
        binding_id="cap-fresh",
        status="active",
        version=1,
        operational_readiness=CapabilityReadiness.AVAILABLE,
        readiness_expires_at=NOW + timedelta(minutes=10),
        dependencies=SimpleNamespace(),
    )
    stale_skill = SimpleNamespace(
        binding_id="skill-stale",
        status="active",
        version=3,
        readiness=CapabilityReadiness.BLOCKED,
        readiness_expires_at=NOW - timedelta(minutes=1),
        dependencies=SimpleNamespace(),
    )

    class Caps:
        def list_bindings(self, scope, limit=200):
            return [stale_cap, fresh_cap]

        def evaluate(self, *args, **kwargs):
            raise RuntimeError("provider_http_error")

    class Skills:
        def list_bindings(self, scope, limit=200):
            return [stale_skill]

        def evaluate_binding(self, *args, **kwargs):
            raise RuntimeError("capability_not_ready")

    calls = {"runtime": 0}

    installer = AipEcommerceAgentInstaller(
        capability_bindings=Caps(),
        skills=Skills(),
        clock=lambda: NOW,
    )

    def runtime_readiness(_principal):
        calls["runtime"] += 1
        return SimpleNamespace(ok=True)

    installer.runtime_readiness = runtime_readiness  # type: ignore[method-assign]
    result = installer.refresh_binding_readiness(principal, idempotency_key="pytest-soft")
    assert result.ok is True
    assert calls["runtime"] == 1
