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
