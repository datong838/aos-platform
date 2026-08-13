from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_agent_registry_contracts import (
    AgentInstanceOverlay,
    AgentInstanceStatus,
    AgentRunRequest,
    CapabilityBindingRequest,
    HandoffEnvelopeRequest,
    TemplateLifecycle,
    VersionedAssetRef,
)
from aos_api.aip_contracts import ResourceRef

NOW = datetime(2026, 8, 13, tzinfo=UTC)


def ref(kind: str, value: str) -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=value,
        revision="1",
        authority="postgresql",
    )


def asset(kind: str = "AgentTemplate") -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=kind,
        asset_id="asset-1",
        revision=1,
        content_hash="a" * 64,
    )


def test_template_and_instance_lifecycles_are_frozen() -> None:
    assert {value.value for value in TemplateLifecycle} == {
        "draft", "evaluated", "published", "deprecated", "revoked"
    }
    assert {value.value for value in AgentInstanceStatus} == {
        "provisioning", "active", "suspended", "deleted"
    }


def test_versioned_asset_ref_requires_exact_revision_and_hash() -> None:
    with pytest.raises(ValidationError):
        VersionedAssetRef(
            asset_type="AgentTemplate",
            asset_id="asset-1",
            revision=0,
            content_hash="bad",
        )


def test_overlay_is_allowlisted_and_cannot_expand_risk() -> None:
    overlay = AgentInstanceOverlay(
        display_name="栖月汇内容官",
        prompt_revision="prompt-2",
        allowed_capability_ids=["catalog.read", "wiki.search"],
        monthly_budget_minor=10000,
        policy_revision="policy-2",
    )
    assert overlay.display_name == "栖月汇内容官"
    with pytest.raises(ValidationError, match="Extra inputs"):
        AgentInstanceOverlay(
            display_name="bad",
            network_policy="allow-all",
        )


def test_capability_binding_accepts_secret_ref_only() -> None:
    request = CapabilityBindingRequest(
        capability=asset("CapabilityRevision"),
        secret_ref="vault://aos/qyh/content-api",
        network_policy_revision="network-1",
        quota_policy_revision="quota-1",
        timeout_ms=30000,
        max_concurrency=2,
    )
    assert request.secret_ref.startswith("vault://")
    with pytest.raises(ValidationError, match="Extra inputs"):
        CapabilityBindingRequest(
            capability=asset("CapabilityRevision"),
            secret_ref="vault://aos/qyh/content-api",
            network_policy_revision="network-1",
            quota_policy_revision="quota-1",
            timeout_ms=30000,
            max_concurrency=2,
            api_key="plaintext-secret",
        )
    with pytest.raises(ValidationError, match="CapabilityRevision"):
        CapabilityBindingRequest(
            capability=asset("ToolRevision"),
            secret_ref="vault://aos/qyh/content-api",
            network_policy_revision="network-1",
            quota_policy_revision="quota-1",
            timeout_ms=30000,
            max_concurrency=2,
        )


def test_handoff_rejects_tenant_payload_and_unallowlisted_context() -> None:
    envelope = HandoffEnvelopeRequest(
        task_ref=ref("Task", "task-1"),
        run_ref=ref("TaskRun", "run-1"),
        sender_instance=asset("AgentInstance"),
        receiver_instance=VersionedAssetRef(
            asset_type="AgentInstance",
            asset_id="agent-2",
            revision=1,
            content_hash="b" * 64,
        ),
        object_refs=[ref("Order", "order-1")],
        artifact_refs=[ref("Artifact", "artifact-1")],
        evidence_refs=[ref("Evidence", "evidence-1")],
        context={"customerIntent": "查物流"},
        allowed_context_fields=["customerIntent"],
        markings=["internal"],
        expires_at=NOW + timedelta(minutes=10),
    )
    assert envelope.context == {"customerIntent": "查物流"}
    with pytest.raises(ValidationError, match="allowlist"):
        envelope.model_copy(
            update={"context": {"customerIntent": "查物流", "rawConversation": "..."}}
        ).model_validate(
            envelope.model_copy(
                update={"context": {"customerIntent": "查物流", "rawConversation": "..."}}
            ).model_dump()
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        HandoffEnvelopeRequest(**envelope.model_dump(), org_id="dev-org")


def test_agent_run_requires_exact_agent_skill_logic_and_policy() -> None:
    run = AgentRunRequest(
        task_ref=ref("Task", "task-1"),
        plan_ref=ref("PlanRevision", "plan-1"),
        agent_instance=asset("AgentInstance"),
        skill=asset("SkillTemplate"),
        logic=asset("LogicRevision"),
        model_route=asset("ModelRouteRevision"),
        policy=asset("PolicyRevision"),
        input_refs=[ref("Order", "order-1")],
    )
    assert run.skill.revision == 1
    with pytest.raises(ValidationError, match="Extra inputs"):
        AgentRunRequest(**run.model_dump(), project_id="dev-project")
