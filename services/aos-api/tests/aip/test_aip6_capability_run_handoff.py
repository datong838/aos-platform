from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_agent_registry_contracts import (
    AgentInstanceOverlay,
    AgentRunRequest,
    AgentRunStatus,
    CapabilityBindingRequest,
    CreateAgentInstanceRequest,
    CreateAgentRunRequest,
    CreateCapabilityBindingRequest,
    HandoffEnvelopeRequest,
    IssueHandoffRequest,
    PublishAgentTemplateRequest,
    PublishSkillTemplateRequest,
    UpdateAgentInstanceRequest,
    UpdateCapabilityBindingRequest,
    UpdateSkillBindingRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryNotFound,
    AipAgentRegistryStore,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_handoff_service import AipHandoffService
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

PRIMARY = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 13, 20, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def asset(kind: str, identifier: str, revision: int = 1, content_hash: str = HASH_A):
    return VersionedAssetRef(
        asset_type=kind,
        asset_id=identifier,
        revision=revision,
        content_hash=content_hash,
    )


def resource(kind: str, identifier: str, *, authority: str = "aip-task-runtime"):
    return ResourceRef(
        resource_type=kind,
        resource_id=identifier,
        revision="1",
        authority=authority,
    )


@pytest.fixture()
def ids():
    suffix = uuid.uuid4().hex[:12]
    values = {
        "template": f"agent-{suffix}",
        "skill": f"skill-{suffix}",
        "sender": f"sender-{suffix}",
        "receiver": f"receiver-{suffix}",
        "binding": f"binding-{suffix}",
        "capability": f"cap-{suffix}",
        "task": f"task-{suffix}",
        "plan": f"plan-{suffix}",
        "task_run": f"run-{suffix}",
        "agent_run": f"agent-run-{suffix}",
        "handoff": f"handoff-{suffix}",
    }
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
        conn.execute(
            """INSERT INTO aip_task
               (org_id,project_id,task_id,task_type,title,status,idempotency_key,
                request_hash,created_by)
               VALUES (%s,%s,%s,'pytest','A6D','approved',%s,%s,'pytest')""",
            (*PRIMARY.key, values["task"], f"task-{suffix}", HASH_A),
        )
        conn.execute(
            """INSERT INTO aip_plan_revision
               (org_id,project_id,plan_revision_id,task_id,revision,content_hash,
                steps,approval_status,idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,1,%s,'[]'::jsonb,'approved',%s,%s,'pytest')""",
            (
                *PRIMARY.key,
                values["plan"],
                values["task"],
                HASH_A,
                f"plan-{suffix}",
                HASH_B,
            ),
        )
        conn.execute(
            """INSERT INTO aip_task_run
               (org_id,project_id,run_id,task_id,plan_revision_id,status,
                idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,%s,'queued',%s,%s,'pytest')""",
            (
                *PRIMARY.key,
                values["task_run"],
                values["task"],
                values["plan"],
                f"run-{suffix}",
                HASH_C,
            ),
        )
        conn.commit()
    return values


def _template(ids):
    return PublishAgentTemplateRequest(
        template_id=ids["template"],
        revision=1,
        display_name="内容官",
        role_key="content_officer",
        lifecycle="published",
        source_ref=resource("SolutionPack", "ecommerce", authority="solution-pack"),
        source_license="internal-authorized",
        manifest={"role": "content_officer"},
        content_hash=HASH_A,
    )


def _skill(ids):
    return PublishSkillTemplateRequest(
        skill_id=ids["skill"],
        revision=1,
        canonical_logic_id="content.plan",
        lifecycle="published",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        tool_allowlist=[],
        required_capabilities=[],
        risk_level="low",
        memory_policy_ref=asset("MemoryPolicy", "memory"),
        handoff_policy_ref=asset("HandoffPolicy", "handoff"),
        source_ref=resource("SolutionPack", "ecommerce", authority="solution-pack"),
        source_license="internal-authorized",
        content_hash=HASH_B,
    )


def _active_instance(ids, key: str):
    store = AipAgentRegistryStore()
    try:
        store.publish_template(_template(ids), actor="pytest")
    except Exception:
        pass
    created, _ = store.create_instance(
        PRIMARY,
        CreateAgentInstanceRequest(
            instance_id=ids[key],
            template=asset("AgentTemplate", ids["template"]),
            overlay=AgentInstanceOverlay(display_name=f"栖月汇-{key}"),
        ),
        idempotency_key=f"create-{ids[key]}",
        actor="pytest",
        occurred_at=NOW,
    )
    active, _ = store.update_instance(
        PRIMARY,
        created.instance_id,
        UpdateAgentInstanceRequest(
            expected_version=1,
            from_status="provisioning",
            to_status="active",
            overlay=created.overlay,
        ),
        idempotency_key=f"activate-{ids[key]}",
        actor="pytest",
        occurred_at=NOW,
    )
    return active


def test_capability_binding_is_secret_ref_only_health_gated_and_scoped(ids):
    service = AipCapabilityBindingService()
    request = CreateCapabilityBindingRequest(
        binding_id=ids["capability"],
        binding=CapabilityBindingRequest(
            capability=asset("CapabilityRevision", "wiki.search"),
            secret_ref="vault://aos/qyh/wiki-search",
            network_policy_revision="network-1",
            quota_policy_revision="quota-1",
            timeout_ms=1000,
            max_concurrency=2,
        ),
    )
    created, receipt = service.create(
        PRIMARY,
        request,
        idempotency_key=f"cap-{ids['capability']}",
        actor="pytest",
        occurred_at=NOW,
    )
    assert created.status == "provisioning" and created.health.value == "unknown"
    assert receipt.status == "applied"
    with pytest.raises(AipAgentRegistryNotFound):
        service.get(CANARY, ids["capability"])
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="healthy"):
        service.update(
            PRIMARY,
            ids["capability"],
            UpdateCapabilityBindingRequest(
                expected_version=1,
                from_status="provisioning",
                to_status="active",
                health="degraded",
                observed_at=NOW,
            ),
            idempotency_key=f"bad-health-{ids['capability']}",
            actor="pytest",
        )
    active, _ = service.update(
        PRIMARY,
        ids["capability"],
        UpdateCapabilityBindingRequest(
            expected_version=1,
            from_status="provisioning",
            to_status="active",
            health="healthy",
            observed_at=NOW,
        ),
        idempotency_key=f"healthy-{ids['capability']}",
        actor="pytest",
    )
    assert active.status == "active" and active.version == 2


def test_agent_run_persists_exact_instance_snapshot_and_blocks_start_without_aip7(ids, monkeypatch):
    instance = _active_instance(ids, "sender")
    skills = AipSkillRegistry()
    skills.publish_skill(_skill(ids), actor="pytest")
    binding, _ = skills.create_binding(
        PRIMARY,
        __import__("aos_api.aip_agent_registry_contracts", fromlist=["CreateSkillBindingRequest"]).CreateSkillBindingRequest(
            binding_id=ids["binding"],
            instance_id=instance.instance_id,
            skill=asset("SkillTemplate", ids["skill"], content_hash=HASH_B),
            budget_policy_ref=asset("BudgetPolicy", "budget"),
        ),
        idempotency_key=f"bind-{ids['binding']}",
        actor="pytest",
        occurred_at=NOW,
    )
    binding, _ = skills.update_binding(
        PRIMARY,
        binding.binding_id,
        UpdateSkillBindingRequest(
            expected_version=1, from_status="provisioning", to_status="active"
        ),
        idempotency_key=f"activate-{ids['binding']}",
        actor="pytest",
        occurred_at=NOW,
    )
    service = AipAgentRunService()
    monkeypatch.setattr(service, "_require_logic", lambda *args: None)
    request = CreateAgentRunRequest(
        agent_run_id=ids["agent_run"],
        task_run_ref=resource("TaskRun", ids["task_run"]),
        skill_binding_id=binding.binding_id,
        run=AgentRunRequest(
            task_ref=resource("Task", ids["task"]),
            plan_ref=resource("PlanRevision", ids["plan"]),
            agent_instance=instance.instance_ref,
            skill=binding.skill,
            logic=asset("LogicRevision", "content.plan"),
            model_route=asset("ModelRouteRevision", "route-default"),
            policy=asset("PolicyRevision", "policy-default"),
        ),
    )
    run, receipt = service.create(
        PRIMARY,
        request,
        idempotency_key=f"agent-run-{ids['agent_run']}",
        actor="pytest",
        occurred_at=NOW,
    )
    assert run.status is AgentRunStatus.QUEUED and receipt.status == "applied"
    with connect(PRIMARY) as conn:
        row = conn.execute(
            """SELECT instance_ref,instance_snapshot FROM aip_agent_run
               WHERE org_id=%s AND project_id=%s AND agent_run_id=%s""",
            (*PRIMARY.key, ids["agent_run"]),
        ).fetchone()
    assert row["instance_ref"] == instance.instance_ref.model_dump(mode="json", by_alias=True)
    assert row["instance_snapshot"]["overlay"]["displayName"] == "栖月汇-sender"
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="AIP-7"):
        service.transition(
            PRIMARY,
            run.agent_run_id,
            expected_version=1,
            from_status=AgentRunStatus.QUEUED,
            to_status=AgentRunStatus.RUNNING,
            actor="pytest",
            occurred_at=NOW,
        )
    cancelled = service.transition(
        PRIMARY,
        run.agent_run_id,
        expected_version=1,
        from_status=AgentRunStatus.QUEUED,
        to_status=AgentRunStatus.CANCELLED,
        actor="pytest",
        occurred_at=NOW,
    )
    assert cancelled.status is AgentRunStatus.CANCELLED


def test_handoff_is_one_time_minimal_and_receiver_reauthorized(ids):
    sender = _active_instance(ids, "sender")
    receiver = _active_instance(ids, "receiver")
    authorized = AipHandoffService(ref_authorizer=lambda scope, ref, instance: True)
    request = IssueHandoffRequest(
        handoff_id=ids["handoff"],
        envelope=HandoffEnvelopeRequest(
            task_ref=resource("Task", ids["task"]),
            run_ref=resource("TaskRun", ids["task_run"]),
            sender_instance=sender.instance_ref,
            receiver_instance=receiver.instance_ref,
            object_refs=[resource("Order", "order-1", authority="ontology")],
            context={"customerIntent": "查物流"},
            allowed_context_fields=["customerIntent"],
            markings=["internal"],
            expires_at=NOW + timedelta(minutes=10),
        ),
    )
    issued = authorized.issue(
        PRIMARY,
        request,
        idempotency_key=f"handoff-{ids['handoff']}",
        actor="pytest",
        occurred_at=NOW,
    )
    assert issued.bearer_token and issued.handoff.status == "issued"
    replay = authorized.issue(
        PRIMARY,
        request,
        idempotency_key=f"handoff-{ids['handoff']}",
        actor="pytest",
        occurred_at=NOW,
    )
    assert replay.bearer_token is None and replay.receipt == issued.receipt
    with connect(PRIMARY) as conn:
        row = conn.execute(
            """SELECT token_hash FROM aip_handoff_envelope
               WHERE org_id=%s AND project_id=%s AND handoff_id=%s""",
            (*PRIMARY.key, ids["handoff"]),
        ).fetchone()
    assert row["token_hash"] != issued.bearer_token
    consumed = authorized.consume(
        PRIMARY,
        ids["handoff"],
        bearer_token=issued.bearer_token,
        receiver_instance=receiver.instance_ref,
        actor="pytest-receiver",
        occurred_at=NOW + timedelta(minutes=1),
    )
    assert consumed.status == "consumed" and consumed.version == 2
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="no longer"):
        authorized.consume(
            PRIMARY,
            ids["handoff"],
            bearer_token=issued.bearer_token,
            receiver_instance=receiver.instance_ref,
            actor="pytest-receiver",
            occurred_at=NOW + timedelta(minutes=2),
        )
    with pytest.raises(AipAgentRegistryNotFound):
        authorized.get(CANARY, ids["handoff"])


def test_handoff_with_refs_fails_closed_without_receiver_authorizer(ids):
    sender = _active_instance(ids, "sender")
    receiver = _active_instance(ids, "receiver")
    service = AipHandoffService()
    issued = service.issue(
        PRIMARY,
        IssueHandoffRequest(
            handoff_id=ids["handoff"],
            envelope=HandoffEnvelopeRequest(
                task_ref=resource("Task", ids["task"]),
                run_ref=resource("TaskRun", ids["task_run"]),
                sender_instance=sender.instance_ref,
                receiver_instance=receiver.instance_ref,
                evidence_refs=[resource("Evidence", "evidence-1", authority="aip-evidence")],
                context={},
                allowed_context_fields=[],
                markings=["internal"],
                expires_at=NOW + timedelta(minutes=10),
            ),
        ),
        idempotency_key=f"handoff-{ids['handoff']}",
        actor="pytest",
        occurred_at=NOW,
    )
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="authorizer"):
        service.consume(
            PRIMARY,
            ids["handoff"],
            bearer_token=issued.bearer_token,
            receiver_instance=receiver.instance_ref,
            actor="pytest-receiver",
            occurred_at=NOW + timedelta(minutes=1),
        )


def test_handoff_wrong_token_expiry_revoke_and_receiver_drift_fail_closed(ids):
    sender = _active_instance(ids, "sender")
    receiver = _active_instance(ids, "receiver")
    service = AipHandoffService(ref_authorizer=lambda scope, ref, instance: True)

    def issue(handoff_id: str, expires_at: datetime):
        return service.issue(
            PRIMARY,
            IssueHandoffRequest(
                handoff_id=handoff_id,
                envelope=HandoffEnvelopeRequest(
                    task_ref=resource("Task", ids["task"]),
                    run_ref=resource("TaskRun", ids["task_run"]),
                    sender_instance=sender.instance_ref,
                    receiver_instance=receiver.instance_ref,
                    context={},
                    allowed_context_fields=[],
                    markings=["internal"],
                    expires_at=expires_at,
                ),
            ),
            idempotency_key=f"issue-{handoff_id}",
            actor="pytest",
            occurred_at=NOW,
        )

    wrong = issue(f"{ids['handoff']}-wrong", NOW + timedelta(minutes=10))
    with pytest.raises(AipAgentRegistryNotFound, match="token"):
        service.consume(
            PRIMARY,
            wrong.handoff.handoff_id,
            bearer_token="x" * 43,
            receiver_instance=receiver.instance_ref,
            actor="pytest-receiver",
            occurred_at=NOW + timedelta(minutes=1),
        )
    assert service.get(PRIMARY, wrong.handoff.handoff_id).status == "issued"

    expired = issue(f"{ids['handoff']}-expired", NOW + timedelta(minutes=1))
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="expired"):
        service.consume(
            PRIMARY,
            expired.handoff.handoff_id,
            bearer_token=expired.bearer_token,
            receiver_instance=receiver.instance_ref,
            actor="pytest-receiver",
            occurred_at=NOW + timedelta(minutes=2),
        )
    assert service.get(PRIMARY, expired.handoff.handoff_id).status == "expired"

    revoked = issue(f"{ids['handoff']}-revoked", NOW + timedelta(minutes=10))
    revoked_view = service.revoke(
        PRIMARY,
        revoked.handoff.handoff_id,
        expected_version=1,
        actor="pytest",
        reason_code="OPERATOR_REVOKED",
        occurred_at=NOW + timedelta(minutes=1),
    )
    assert revoked_view.status == "revoked" and revoked_view.version == 2
    with pytest.raises(AipAgentRegistryTransitionBlocked, match="no longer"):
        service.consume(
            PRIMARY,
            revoked.handoff.handoff_id,
            bearer_token=revoked.bearer_token,
            receiver_instance=receiver.instance_ref,
            actor="pytest-receiver",
            occurred_at=NOW + timedelta(minutes=2),
        )

    drifted = issue(f"{ids['handoff']}-drift", NOW + timedelta(minutes=10))
    changed, _ = AipAgentRegistryStore().update_instance(
        PRIMARY,
        receiver.instance_id,
        UpdateAgentInstanceRequest(
            expected_version=2,
            from_status="active",
            to_status="suspended",
            overlay=receiver.overlay,
        ),
        idempotency_key=f"suspend-{receiver.instance_id}",
        actor="pytest",
        occurred_at=NOW + timedelta(minutes=1),
    )
    assert changed.version == 3
    with pytest.raises(AipAgentRegistryNotFound, match="exact"):
        service.consume(
            PRIMARY,
            drifted.handoff.handoff_id,
            bearer_token=drifted.bearer_token,
            receiver_instance=receiver.instance_ref,
            actor="pytest-receiver",
            occurred_at=NOW + timedelta(minutes=2),
        )
