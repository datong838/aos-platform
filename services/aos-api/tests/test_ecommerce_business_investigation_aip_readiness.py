"""Exact BI Binding readiness coordination tests."""

from __future__ import annotations

from types import SimpleNamespace
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_agent_registry_contracts import (
    CapabilityReadiness,
    OperationalBindingDependencies,
)
from aos_api.aip_production_contracts import BriefLifecycle, ContractReadiness
from aos_api.ecommerce_business_investigation_aip_authority import selected_skill_refs
from aos_api.ecommerce_business_investigation_aip_readiness import (
    BusinessInvestigationBindingReadinessCoordinator,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 28, 11, 30, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
SNAPSHOT = "sha256:" + "a" * 64


def binding(
    binding_id,
    *,
    instance_id="ecommerce.data_advisor.default",
    skill_id=None,
    revision=1,
    content_hash="sha256:" + "b" * 64,
    capability_ids=(),
    version=3,
    fresh=False,
):
    return SimpleNamespace(
        binding_id=binding_id,
        instance_id=instance_id,
        skill=(
            SimpleNamespace(
                asset_id=skill_id,
                revision=revision,
                content_hash=content_hash,
            )
            if skill_id
            else None
        ),
        capability_binding_ids=list(capability_ids),
        status="active",
        version=version,
        dependencies=OperationalBindingDependencies(),
        dependency_snapshot_hash=SNAPSHOT,
        operational_readiness=CapabilityReadiness.AVAILABLE,
        readiness=CapabilityReadiness.AVAILABLE,
        readiness_reasons=[],
        readiness_expires_at=NOW + timedelta(minutes=10) if fresh else NOW,
    )


class Store:
    def __init__(self, plan):
        self.plan = plan

    def list_responsibility_plans(self, scope):
        assert scope == SCOPE
        return SimpleNamespace(items=[self.plan])


class CapabilityService:
    def __init__(self, items, events, *, blocked=False):
        self.items = {item.binding_id: item for item in items}
        self.events = events
        self.blocked = blocked

    def get(self, scope, binding_id):
        assert scope == SCOPE
        return self.items[binding_id]

    def evaluate(self, scope, binding_id, request, **kwargs):
        self.events.append(("capability", binding_id, request.expected_version))
        before = self.items[binding_id]
        readiness = CapabilityReadiness.BLOCKED if self.blocked else CapabilityReadiness.AVAILABLE
        reasons = ["MODEL_ROUTE_BLOCKED"] if self.blocked else []
        after = SimpleNamespace(
            **{
                **before.__dict__,
                "version": before.version + 1,
                "operational_readiness": readiness,
                "readiness_reasons": reasons,
                "readiness_expires_at": NOW + timedelta(minutes=15),
            }
        )
        self.items[binding_id] = after
        result = SimpleNamespace(
            readiness=readiness,
            reasons=reasons,
            expires_at=after.readiness_expires_at,
        )
        return after, result, SimpleNamespace()


class SkillRegistry:
    def __init__(self, items, events):
        self.items = items
        self.events = events

    def list_bindings(self, scope, limit):
        assert scope == SCOPE and limit == 200
        return self.items

    def evaluate_binding(self, scope, binding_id, request, **kwargs):
        self.events.append(("skill", binding_id, request.expected_version))
        before = next(item for item in self.items if item.binding_id == binding_id)
        after = SimpleNamespace(
            **{
                **before.__dict__,
                "version": before.version + 1,
                "readiness": CapabilityReadiness.AVAILABLE,
                "readiness_reasons": [],
                "readiness_expires_at": NOW + timedelta(minutes=15),
            }
        )
        self.items[self.items.index(before)] = after
        result = SimpleNamespace(
            readiness=CapabilityReadiness.AVAILABLE,
            reasons=[],
            expires_at=after.readiness_expires_at,
        )
        return after, result, SimpleNamespace()


class Materializer:
    def __init__(self, plan, *, frozen=True):
        self.plan = plan
        self.frozen = frozen
        self.calls = []

    def finalize_responsibility_plan(self, scope, plan_id, *, actor):
        self.calls.append((scope, plan_id, actor))
        if self.frozen:
            return SimpleNamespace(
                **{
                    **self.plan.__dict__,
                    "revision": 2,
                    "lifecycle": BriefLifecycle.FROZEN,
                    "readiness": ContractReadiness.READY,
                    "blockers": [],
                }
            )
        return self.plan


def exact_skill_bindings(*, fresh=False):
    return [
        binding(
            f"binding-{skill_id}",
            skill_id=skill_id,
            revision=ref.revision,
            content_hash=ref.content_hash,
            capability_ids=("cap-material", "cap-strategy"),
            fresh=fresh,
        )
        for skill_id, ref in selected_skill_refs().items()
    ]


def plan(*, blocked=False):
    return SimpleNamespace(
        plan_id="plan-1",
        revision=1,
        profile="ecommerce.business-investigation.readonly",
        lifecycle=BriefLifecycle.DRAFT,
        readiness=ContractReadiness.BLOCKED if blocked else ContractReadiness.READY,
        blockers=[SimpleNamespace(code="CAPABILITY_BINDING_NOT_OPERATIONAL")] if blocked else [],
        slots=[
            SimpleNamespace(
                assignee=SimpleNamespace(
                    kind=SimpleNamespace(value="agent_instance"),
                    resource_id="ecommerce.data_advisor.default",
                )
            )
        ],
    )


def test_refreshes_capabilities_before_exact_skills_and_finalizes_plan() -> None:
    events = []
    current_plan = plan()
    coordinator = BusinessInvestigationBindingReadinessCoordinator(
        store=Store(current_plan),
        capabilities=CapabilityService(
            [binding("cap-material"), binding("cap-strategy")], events
        ),
        skills=SkillRegistry(exact_skill_bindings(), events),
        materializer=Materializer(current_plan),
        clock=lambda: NOW,
    )
    result = coordinator.refresh(SCOPE)
    assert [item[0] for item in events] == [
        "capability",
        "capability",
        "skill",
        "skill",
        "skill",
    ]
    assert result.responsibility_plan_lifecycle == "frozen"
    assert result.responsibility_plan_readiness == "ready"
    assert len(result.items) == 5


def test_fresh_dependencies_are_skipped_without_extending_ttl() -> None:
    events = []
    current_plan = plan()
    result = BusinessInvestigationBindingReadinessCoordinator(
        store=Store(current_plan),
        capabilities=CapabilityService(
            [binding("cap-material", fresh=True), binding("cap-strategy", fresh=True)],
            events,
        ),
        skills=SkillRegistry(exact_skill_bindings(fresh=True), events),
        materializer=Materializer(current_plan),
        clock=lambda: NOW,
    ).refresh(SCOPE)
    assert events == []
    assert {item.disposition for item in result.items} == {"fresh-skip"}


def test_blocked_canonical_result_is_preserved_and_plan_stays_draft() -> None:
    events = []
    current_plan = plan(blocked=True)
    result = BusinessInvestigationBindingReadinessCoordinator(
        store=Store(current_plan),
        capabilities=CapabilityService(
            [binding("cap-material"), binding("cap-strategy")], events, blocked=True
        ),
        skills=SkillRegistry(exact_skill_bindings(), events),
        materializer=Materializer(current_plan, frozen=False),
        clock=lambda: NOW,
    ).refresh(SCOPE)
    assert any(item.reasons == ["MODEL_ROUTE_BLOCKED"] for item in result.items)
    assert result.responsibility_plan_lifecycle == "draft"
    assert result.responsibility_plan_blockers == [
        "CAPABILITY_BINDING_NOT_OPERATIONAL"
    ]


def test_missing_exact_selected_skill_binding_fails_closed() -> None:
    events = []
    current_plan = plan()
    skills = exact_skill_bindings()
    skills.pop()
    coordinator = BusinessInvestigationBindingReadinessCoordinator(
        store=Store(current_plan),
        capabilities=CapabilityService(
            [binding("cap-material"), binding("cap-strategy")], events
        ),
        skills=SkillRegistry(skills, events),
        materializer=Materializer(current_plan),
        clock=lambda: NOW,
    )
    with pytest.raises(ValueError, match="exact active SkillBinding unavailable"):
        coordinator.refresh(SCOPE)
