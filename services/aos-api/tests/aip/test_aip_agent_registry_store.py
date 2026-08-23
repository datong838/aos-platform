from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from aos_api.aip_agent_registry_contracts import (
    AgentInstanceOverlay,
    CapabilityReadiness,
    CreateAgentInstanceRequest,
    CreateSkillBindingRequest,
    EvaluateOperationalBindingRequest,
    OperationalBindingDependencies,
    OperationalBindingReadiness,
    PublishAgentTemplateRequest,
    PublishSkillTemplateRequest,
    UpdateAgentInstanceRequest,
    UpdateSkillBindingRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryStore,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

PRIMARY = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 13, 18, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64


class _ReadySkillBindingService:
    def evaluate(self, _scope, binding, *, evaluated_at):
        return OperationalBindingReadiness(
            readiness=CapabilityReadiness.AVAILABLE,
            reasons=[],
            dependencies=binding.dependencies,
            dependency_snapshot_hash=HASH_D,
            evaluated_at=evaluated_at,
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
        )


def ref(kind: str, identifier: str, revision: int, content_hash: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=kind,
        asset_id=identifier,
        revision=revision,
        content_hash=content_hash,
    )


def resource(kind: str, identifier: str) -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=identifier,
        revision="1",
        authority="solution-pack",
    )


@pytest.fixture()
def identifiers() -> dict[str, str]:
    suffix = uuid.uuid4().hex[:12]
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES ('org-org','栖月汇商贸有限公司') "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            """INSERT INTO twa_workspace(org_id,project_id,name)
               VALUES ('org-org','dev-project','默认工作区')
               ON CONFLICT (org_id,project_id) DO NOTHING"""
        )
        conn.commit()
    return {
        "template": f"content-officer-{suffix}",
        "skill": f"content-strategy-{suffix}",
        "instance": f"content-agent-{suffix}",
        "canary_instance": f"canary-agent-{suffix}",
        "binding": f"content-binding-{suffix}",
    }


def template_request(ids: dict[str, str], *, lifecycle: str = "published"):
    return PublishAgentTemplateRequest(
        template_id=ids["template"],
        revision=1,
        display_name="内容官",
        role_key="content_officer",
        lifecycle=lifecycle,
        source_ref=resource("SolutionPack", "ecommerce-growth"),
        source_license="internal-authorized",
        manifest={"role": "content_officer", "skills": [ids["skill"]]},
        content_hash=HASH_A,
    )


def skill_request(ids: dict[str, str]):
    return PublishSkillTemplateRequest(
        skill_id=ids["skill"],
        revision=1,
        canonical_logic_id="content.strategy.plan",
        lifecycle="evaluated",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        tool_allowlist=[],
        required_capabilities=[],
        risk_level="low",
        memory_policy_ref=ref("MemoryPolicy", "memory-default", 1, HASH_A),
        handoff_policy_ref=ref("HandoffPolicy", "handoff-default", 1, HASH_A),
        source_ref=resource("SolutionPack", "ecommerce-growth"),
        source_license="internal-authorized",
        content_hash=HASH_B,
    )


def insert_governed_published_skill_fixture(ids: dict[str, str]) -> None:
    """Publication behavior is tested separately; this fixture seeds its result."""
    source = skill_request(ids)
    AipSkillRegistry().publish_skill(source, actor="pytest")
    encoded = lambda value: json.dumps(value, separators=(",", ":"))
    with connect() as conn:
        conn.execute(
            """INSERT INTO aip_skill_template_revision
               (skill_id,revision,canonical_logic_id,lifecycle,input_schema,
                output_schema,tool_allowlist,required_capabilities,risk_level,
                memory_policy_ref,handoff_policy_ref,source_ref,source_license,
                parent_ref,publication_tenant,release_gate_ref,publication_ref,
                model_route_ref,runtime_policy_ref,logic_revision_ref,content_hash,created_by)
               VALUES (%s,2,%s,'published',%s::jsonb,%s::jsonb,'[]'::jsonb,
                '[]'::jsonb,'low',%s::jsonb,%s::jsonb,%s::jsonb,%s,
                %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                %s::jsonb,%s,'pytest')""",
            (
                source.skill_id,
                source.canonical_logic_id,
                encoded(source.input_schema),
                encoded(source.output_schema),
                encoded(source.memory_policy_ref.model_dump(mode="json", by_alias=True)),
                encoded(source.handoff_policy_ref.model_dump(mode="json", by_alias=True)),
                encoded(source.source_ref.model_dump(mode="json", by_alias=True)),
                source.source_license,
                encoded(ref("SkillTemplate", source.skill_id, 1, HASH_B).model_dump(mode="json", by_alias=True)),
                encoded({"orgId": PRIMARY.org_id, "projectId": PRIMARY.project_id}),
                encoded(ref("EvalGateDecision", "gate-fixture", 1, HASH_A).model_dump(mode="json", by_alias=True)),
                encoded({"resourceType": "PublicationEvent", "resourceId": "event-fixture", "revision": "publication-fixture", "authority": "postgresql"}),
                encoded(ref("ModelRouteRevision", "route-fixture", 1, HASH_A).model_dump(mode="json", by_alias=True)),
                encoded(ref("RuntimePolicyRevision", "policy-fixture", 1, HASH_A).model_dump(mode="json", by_alias=True)),
                encoded(ref("LogicRevision", source.canonical_logic_id, 1, HASH_A).model_dump(mode="json", by_alias=True)),
                HASH_C,
            ),
        )
        conn.commit()


def publish_and_create(ids: dict[str, str]):
    store = AipAgentRegistryStore()
    store.publish_template(template_request(ids), actor="pytest")
    request = CreateAgentInstanceRequest(
        instance_id=ids["instance"],
        template=ref("AgentTemplate", ids["template"], 1, HASH_A),
        overlay=AgentInstanceOverlay(display_name="栖月汇内容官"),
    )
    return store, request, store.create_instance(
        PRIMARY,
        request,
        idempotency_key=f"create-{ids['instance']}",
        actor="pytest",
        occurred_at=NOW,
    )


def test_template_and_instance_are_restart_safe_idempotent_and_tenant_scoped(identifiers):
    store, request, (instance, receipt) = publish_and_create(identifiers)
    assert instance.status.value == "provisioning"
    assert instance.overlay.display_name == "栖月汇内容官"
    assert receipt.status == "applied"
    replay, replay_receipt = AipAgentRegistryStore().create_instance(
        PRIMARY,
        request,
        idempotency_key=f"create-{identifiers['instance']}",
        actor="pytest",
        occurred_at=NOW,
    )
    assert replay == instance
    assert replay_receipt == receipt
    assert AipAgentRegistryStore().get_instance(PRIMARY, identifiers["instance"]) == instance
    with pytest.raises(AipAgentRegistryNotFound):
        store.get_instance(CANARY, identifiers["instance"])
    assert store.list_instances(CANARY) == []
    with pytest.raises(AipAgentRegistryConflict, match="idempotency"):
        changed = request.model_copy(update={"overlay": AgentInstanceOverlay(display_name="漂移")})
        store.create_instance(
            PRIMARY,
            changed,
            idempotency_key=f"create-{identifiers['instance']}",
            actor="pytest",
            occurred_at=NOW,
        )


def test_instance_cas_and_lifecycle_fail_closed(identifiers):
    store, _, (instance, _) = publish_and_create(identifiers)
    activated, _ = store.update_instance(
        PRIMARY,
        instance.instance_id,
        UpdateAgentInstanceRequest(
            expected_version=1,
            from_status="provisioning",
            to_status="active",
            overlay=instance.overlay,
        ),
        idempotency_key=f"activate-{instance.instance_id}",
        actor="pytest",
        occurred_at=NOW,
    )
    assert activated.version == 2 and activated.status.value == "active"
    with pytest.raises(AipAgentRegistryConflict, match="version"):
        store.update_instance(
            PRIMARY,
            instance.instance_id,
            UpdateAgentInstanceRequest(
                expected_version=1,
                from_status="active",
                to_status="suspended",
                overlay=instance.overlay,
            ),
            idempotency_key=f"stale-{instance.instance_id}",
            actor="pytest",
            occurred_at=NOW,
        )
    with pytest.raises(AipAgentRegistryTransitionBlocked):
        store.update_instance(
            PRIMARY,
            instance.instance_id,
            UpdateAgentInstanceRequest(
                expected_version=2,
                from_status="active",
                to_status="provisioning",
                overlay=instance.overlay,
            ),
            idempotency_key=f"illegal-{instance.instance_id}",
            actor="pytest",
            occurred_at=NOW,
        )


def test_non_published_template_cannot_create_instance(identifiers):
    store = AipAgentRegistryStore()
    store.publish_template(template_request(identifiers, lifecycle="evaluated"), actor="pytest")
    with pytest.raises(AipAgentRegistryTransitionBlocked):
        store.create_instance(
            PRIMARY,
            CreateAgentInstanceRequest(
                instance_id=identifiers["instance"],
                template=ref("AgentTemplate", identifiers["template"], 1, HASH_A),
            ),
            idempotency_key=f"blocked-{identifiers['instance']}",
            actor="pytest",
            occurred_at=NOW,
        )


def test_append_only_revocation_blocks_old_exact_template_for_new_instances(identifiers):
    store = AipAgentRegistryStore()
    published = template_request(identifiers)
    assert store.publish_template(published, actor="pytest").lifecycle.value == "published"
    revoked = PublishAgentTemplateRequest.model_validate(
        {**published.model_dump(), "revision": 2, "lifecycle": "revoked", "content_hash": HASH_B}
    )
    assert store.publish_template(revoked, actor="pytest").lifecycle.value == "revoked"
    assert store.get_template(identifiers["template"], 1).lifecycle.value == "published"
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="revoked"):
        store.create_instance(
            PRIMARY,
            CreateAgentInstanceRequest(
                instance_id=identifiers["instance"],
                template=ref("AgentTemplate", identifiers["template"], 1, HASH_A),
            ),
            idempotency_key=f"revoked-{identifiers['instance']}",
            actor="pytest",
            occurred_at=NOW,
        )


def test_skill_binding_exact_revision_cas_and_tenant_isolation(identifiers):
    store, _, (instance, _) = publish_and_create(identifiers)
    store.update_instance(
        PRIMARY,
        instance.instance_id,
        UpdateAgentInstanceRequest(
            expected_version=1,
            from_status="provisioning",
            to_status="active",
            overlay=instance.overlay,
        ),
        idempotency_key=f"activate-{instance.instance_id}",
        actor="pytest",
        occurred_at=NOW,
    )
    skills = AipSkillRegistry(readiness_service=_ReadySkillBindingService())
    insert_governed_published_skill_fixture(identifiers)
    request = CreateSkillBindingRequest(
        binding_id=identifiers["binding"],
        instance_id=identifiers["instance"],
        skill=ref("SkillTemplate", identifiers["skill"], 2, HASH_C),
        budget_policy_ref=ref("BudgetPolicyRevision", "budget-default", 1, HASH_A),
    )
    binding, receipt = skills.create_binding(
        PRIMARY,
        request,
        idempotency_key=f"bind-{identifiers['binding']}",
        actor="pytest",
        occurred_at=NOW,
    )
    assert binding.status == "provisioning" and receipt.status == "applied"
    assert skills.list_bindings(PRIMARY, instance_id=identifiers["instance"]) == [binding]
    assert skills.list_bindings(CANARY) == []
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="fresh skill binding"):
        skills.update_binding(
            PRIMARY,
            binding.binding_id,
            UpdateSkillBindingRequest(
                expected_version=1,
                from_status="provisioning",
                to_status="active",
            ),
            idempotency_key=f"binding-active-{binding.binding_id}",
            actor="pytest",
            occurred_at=NOW,
        )
    evaluation = EvaluateOperationalBindingRequest(
        expected_version=1,
        dependencies=OperationalBindingDependencies(
            model_route_ref=ref("ModelRouteRevision", "route-fixture", 1, HASH_A),
            runtime_policy_ref=ref(
                "RuntimePolicyRevision", "policy-fixture", 1, HASH_A
            ),
            eval_gate_ref=ref("EvalGateDecision", "gate-fixture", 1, HASH_A),
            budget_policy_ref=request.budget_policy_ref,
        ),
    )
    evaluated, readiness, evaluate_receipt = skills.evaluate_binding(
        PRIMARY,
        binding.binding_id,
        evaluation,
        idempotency_key=f"binding-evaluate-{binding.binding_id}",
        actor="pytest",
        evaluated_at=NOW,
    )
    assert evaluated.version == 2
    assert evaluated.readiness is CapabilityReadiness.AVAILABLE
    assert readiness.dependency_snapshot_hash == HASH_D
    replay, _, replay_receipt = skills.evaluate_binding(
        PRIMARY,
        binding.binding_id,
        evaluation,
        idempotency_key=f"binding-evaluate-{binding.binding_id}",
        actor="pytest",
        evaluated_at=NOW,
    )
    assert replay.version == 2
    assert replay_receipt.receipt_id == evaluate_receipt.receipt_id
    active, _ = skills.update_binding(
        PRIMARY,
        binding.binding_id,
        UpdateSkillBindingRequest(
            expected_version=2,
            from_status="provisioning",
            to_status="active",
        ),
        idempotency_key=f"binding-active-after-eval-{binding.binding_id}",
        actor="pytest",
        occurred_at=NOW,
    )
    assert active.version == 3 and active.status == "active"
    with pytest.raises(AipAgentRegistryConflict):
        skills.update_binding(
            PRIMARY,
            binding.binding_id,
            UpdateSkillBindingRequest(
                expected_version=1,
                from_status="active",
                to_status="suspended",
            ),
            idempotency_key=f"binding-stale-{binding.binding_id}",
            actor="pytest",
            occurred_at=NOW,
        )
