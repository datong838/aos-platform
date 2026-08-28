"""BI AIP stage, responsibility and Skill-selection authority tests."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from aos_api.aip_production_contracts import (
    BriefLifecycle,
    ContractReadiness,
    ExactRevisionRef,
)
from aos_api.aip_responsibility_template_authority import (
    published_template_ref,
    resolve_responsibility_template,
)
from aos_api.aip_stage_template_authority import (
    published_investigation_profile_source_ref,
    resolve_stage_template_source,
)
from aos_api.ecommerce_business_investigation_aip_authority import (
    BusinessInvestigationAuthorityMaterializer,
    build_responsibility_plan_request,
    build_stage_template_request,
    selected_skill_refs,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
VERSIONS = {
    "ecommerce.data_advisor.default": 3,
    "ecommerce.customer_service.default": 3,
    "ecommerce.content_officer.default": 15,
    "ecommerce.private_domain_manager.default": 5,
    "ecommerce.campaign_planner.default": 4,
    "ecommerce.shopping_advisor.default": 3,
}


def test_skill_selection_is_exact_and_d03_is_explicit_r4() -> None:
    refs = selected_skill_refs()
    assert list(refs) == ["ecommerce.skill.D01", "ecommerce.skill.D02", "ecommerce.skill.D03"]
    assert refs["ecommerce.skill.D03"].revision == 4
    assert refs["ecommerce.skill.D03"].content_hash == (
        "3b60ef1e7147b761d1582d8dd0c62934e24d28a8ad8306caf12b1db02306a704"
    )


def test_stage_blueprint_is_ordered_receipt_first_and_read_only() -> None:
    body = build_stage_template_request()
    assert [stage.stage_id for stage in body.stages] == [
        "portrait",
        "diagnosis",
        "solution-design",
    ]
    assert [stage.depends_on for stage in body.stages] == [[], ["portrait"], ["diagnosis"]]
    assert all(stage.retry_policy == {"automatic": False} for stage in body.stages)
    assert all(stage.compensation_policy == {"externalEffect": "none"} for stage in body.stages)
    assert resolve_stage_template_source(SCOPE, body.source_bundle_ref) is True


def test_six_responsibilities_bind_six_current_coworkers_by_capability() -> None:
    body = build_responsibility_plan_request(VERSIONS)
    assert len(body.slots) == 6
    assert len({slot.slot_id for slot in body.slots}) == 6
    assert len({slot.assignee.resource_id for slot in body.slots}) == 6
    assert all(slot.required_capability_ids for slot in body.slots)
    assert resolve_responsibility_template(SCOPE, body.template_ref) is True


def test_missing_active_coworker_version_fails_closed() -> None:
    versions = dict(VERSIONS)
    versions.pop("ecommerce.shopping_advisor.default")
    with pytest.raises(ValueError, match="active digital coworker versions missing"):
        build_responsibility_plan_request(versions)


def test_code_authorities_reject_hash_drift() -> None:
    stage = published_investigation_profile_source_ref()
    responsibility = published_template_ref("ecommerce.business-investigation.readonly")
    assert resolve_stage_template_source(
        SCOPE, stage.model_copy(update={"content_hash": "0" * 64})
    ) is False
    assert resolve_responsibility_template(
        SCOPE, responsibility.model_copy(update={"content_hash": "0" * 64})
    ) is False


class Result:
    def fetchall(self):
        return [
            {"instance_id": instance_id, "version": version}
            for instance_id, version in VERSIONS.items()
        ]


class Connection:
    def execute(self, sql, params):
        assert "aip_agent_instance" in sql
        assert tuple(params[:2]) == SCOPE.key
        return Result()


class Store:
    def __init__(self, plan_readiness=ContractReadiness.BLOCKED):
        self.plan_readiness = plan_readiness
        self.calls = []
        self.stage = None
        self.plan = None

    def create_stage_template(self, scope, actor, key, body):
        self.calls.append(("create-stage", key, body))
        self.stage = self.stage or SimpleNamespace(
            lifecycle=BriefLifecycle.DRAFT,
            template_id="stage-1",
            version=1,
        )
        return self.stage

    def get_stage_template(self, scope, template_id):
        self.calls.append(("get-stage", template_id))
        return self.stage

    def freeze_stage_template(self, scope, actor, template_id, version, key):
        self.calls.append(("freeze-stage", key, template_id, version))
        self.stage = SimpleNamespace(
            lifecycle=BriefLifecycle.FROZEN,
            template_id=template_id,
            version=2,
        )
        return self.stage

    def create_responsibility_plan(self, scope, actor, key, body):
        self.calls.append(("create-plan", key, body))
        self.plan = self.plan or SimpleNamespace(
            lifecycle=BriefLifecycle.DRAFT,
            readiness=self.plan_readiness,
            plan_id="plan-1",
            version=1,
        )
        return self.plan

    def get_responsibility_plan(self, scope, plan_id):
        self.calls.append(("get-plan", plan_id))
        return self.plan

    def freeze_responsibility_plan(self, scope, actor, plan_id, version, key):
        self.calls.append(("freeze-plan", key, plan_id, version))
        self.plan = SimpleNamespace(
            lifecycle=BriefLifecycle.FROZEN,
            readiness=ContractReadiness.READY,
            plan_id=plan_id,
            version=2,
        )
        return self.plan


def materializer(store):
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Connection()

    return BusinessInvestigationAuthorityMaterializer(
        store=store,
        connect_factory=connect,
    )


def test_materializer_freezes_stage_but_keeps_blocked_plan_draft() -> None:
    store = Store()
    actual = materializer(store).ensure(SCOPE)
    assert actual.stage_template.lifecycle is BriefLifecycle.FROZEN
    assert actual.responsibility_plan.lifecycle is BriefLifecycle.DRAFT
    assert [call[0] for call in store.calls] == [
        "create-stage",
        "get-stage",
        "freeze-stage",
        "create-plan",
        "get-plan",
    ]


def test_materializer_freezes_plan_only_after_canonical_readiness() -> None:
    store = Store(ContractReadiness.READY)
    actual = materializer(store).ensure(SCOPE)
    assert actual.responsibility_plan.lifecycle is BriefLifecycle.FROZEN
    assert [call[0] for call in store.calls][-1] == "freeze-plan"


def test_materializer_reentry_uses_current_heads_and_does_not_refreeze() -> None:
    store = Store(ContractReadiness.READY)
    runner = materializer(store)
    first = runner.ensure(SCOPE)
    first_call_count = len(store.calls)
    second = runner.ensure(SCOPE)
    reentry_calls = store.calls[first_call_count:]
    assert second.stage_template is first.stage_template
    assert second.responsibility_plan is first.responsibility_plan
    assert [call[0] for call in reentry_calls] == [
        "create-stage",
        "get-stage",
        "create-plan",
        "get-plan",
    ]


def test_finalize_responsibility_plan_freezes_only_ready_draft() -> None:
    store = Store(ContractReadiness.READY)
    runner = materializer(store)
    created = runner.ensure(SCOPE)
    store.plan = SimpleNamespace(
        lifecycle=BriefLifecycle.DRAFT,
        readiness=ContractReadiness.READY,
        plan_id=created.responsibility_plan.plan_id,
        version=3,
    )
    actual = runner.finalize_responsibility_plan(SCOPE, store.plan.plan_id)
    assert actual.lifecycle is BriefLifecycle.FROZEN
    assert store.calls[-1][0] == "freeze-plan"


def test_finalize_responsibility_plan_keeps_blocked_draft() -> None:
    store = Store(ContractReadiness.BLOCKED)
    runner = materializer(store)
    runner.ensure(SCOPE)
    before = store.plan
    actual = runner.finalize_responsibility_plan(SCOPE, before.plan_id)
    assert actual is before
    assert store.calls[-1][0] == "get-plan"
