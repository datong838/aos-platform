from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from aos_api.aip_agent_registry_contracts import (
    AgentInstanceOverlay,
    CreateAgentInstanceRequest,
    PublishAgentTemplateRequest,
    UpdateAgentInstanceRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_contracts import ArtifactRef, ResourceRef
from aos_api.aip_memory_contracts import (
    GovernanceApprovalRef,
    KnowledgeScope,
    KnowledgeSourceRef,
    MemoryCandidateStatus,
    SubmitMemoryCandidateRequest,
)
from aos_api.aip_memory_projection_contracts import (
    ChangeMemoryProjectionStatusRequest,
    CreateMemoryProjectionRequest,
    MemoryDisclosureMode,
    MemoryProjectionKind,
    MemoryProjectionStatus,
    MemoryRevisionExactRef,
)
from aos_api.aip_memory_projection_store import (
    AipMemoryProjectionBlocked,
    AipMemoryProjectionConflict,
    AipMemoryProjectionNotFound,
    AipMemoryProjectionStore,
)
from aos_api.aip_memory_store import AipMemoryStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

PRIMARY = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def exact_ref(kind: str, identifier: str, revision: int, content_hash: str):
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
        authority="postgresql",
    )


def governance() -> GovernanceApprovalRef:
    return GovernanceApprovalRef(
        eval_report=ArtifactRef(
            artifact_id="e7-eval-report",
            artifact_type="eval_report",
            revision="1",
            content_hash=HASH_C,
        ),
        draft=resource("aip.draft", "e7-draft"),
        approval_event=resource("aip.approval_event", "e7-approval"),
    )


@pytest.fixture()
def authority_chain() -> dict[str, object]:
    suffix = uuid.uuid4().hex[:12]
    ids = {
        "template": f"e7-agent-template-{suffix}",
        "owner": f"e7-owner-{suffix}",
        "recipient": f"e7-recipient-{suffix}",
        "task": f"e7-task-{suffix}",
        "plan": f"e7-plan-{suffix}",
        "run": f"e7-run-{suffix}",
        "source": f"e7-source-{suffix}",
        "candidate": f"e7-candidate-{suffix}",
        "memory": f"e7-memory-{suffix}",
        "projection": f"e7-projection-{suffix}",
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
            """INSERT INTO aip_task (
               org_id,project_id,task_id,task_type,title,status,idempotency_key,
               request_hash,current_plan_revision_id,created_by)
               VALUES (%s,%s,%s,'memory','E7 memory','executing',%s,%s,%s,'pytest')""",
            (*PRIMARY.key, ids["task"], ids["task"], HASH_A, ids["plan"]),
        )
        conn.execute(
            """INSERT INTO aip_plan_revision (
               org_id,project_id,plan_revision_id,task_id,revision,content_hash,
               steps,approval_status,idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,1,%s,%s::jsonb,'approved',%s,%s,'pytest')""",
            (
                *PRIMARY.key,
                ids["plan"],
                ids["task"],
                HASH_A,
                json.dumps([]),
                ids["plan"],
                HASH_A,
            ),
        )
        conn.execute(
            """INSERT INTO aip_task_run (
               org_id,project_id,run_id,task_id,plan_revision_id,status,
               idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,%s,'running',%s,%s,'pytest')""",
            (
                *PRIMARY.key,
                ids["run"],
                ids["task"],
                ids["plan"],
                ids["run"],
                HASH_A,
            ),
        )
        conn.commit()

    agents = AipAgentRegistryStore()
    agents.publish_template(
        PublishAgentTemplateRequest(
            template_id=ids["template"],
            revision=1,
            display_name="E7 数字同事",
            role_key="e7_memory_agent",
            lifecycle="published",
            source_ref=resource("SolutionPack", "ecommerce-growth"),
            source_license="internal-authorized",
            manifest={"role": "e7_memory_agent"},
            content_hash=HASH_A,
        ),
        actor="pytest",
    )
    instance_refs = []
    for instance_id in (ids["owner"], ids["recipient"]):
        instance, _ = agents.create_instance(
            PRIMARY,
            CreateAgentInstanceRequest(
                instance_id=instance_id,
                template=exact_ref("AgentTemplate", ids["template"], 1, HASH_A),
                overlay=AgentInstanceOverlay(display_name=instance_id),
            ),
            idempotency_key=f"create-{instance_id}",
            actor="pytest",
            occurred_at=NOW,
        )
        active, _ = agents.update_instance(
            PRIMARY,
            instance_id,
            UpdateAgentInstanceRequest(
                expected_version=1,
                from_status="provisioning",
                to_status="active",
                overlay=instance.overlay,
            ),
            idempotency_key=f"activate-{instance_id}",
            actor="pytest",
            occurred_at=NOW + timedelta(minutes=1),
        )
        instance_refs.append(active.instance_ref)

    memory = AipMemoryStore()
    source = KnowledgeSourceRef(
        source_kind="authorized_document",
        source_uri=f"urn:aip5:e7:{suffix}",
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=30),
        license_id="internal-authorized",
        usage_policy="summary-and-citation",
        content_hash=HASH_A,
        provider="pytest",
        provider_version="1",
        applicability=["vertical:ecommerce", "task:content"],
    )
    memory.create_source_revision(PRIMARY, ids["source"], 1, source, actor="pytest")
    candidate = memory.submit_candidate(
        PRIMARY,
        ids["candidate"],
        SubmitMemoryCandidateRequest(
            candidate_layer="semantic",
            task_id=ids["task"],
            run_id=ids["run"],
            subject=resource("ecom.product", f"product-{suffix}"),
            payload=ArtifactRef(
                artifact_id=f"memory-payload-{suffix}",
                artifact_type="memory_candidate",
                revision="1",
                content_hash=HASH_B,
            ),
            source=source,
            confidence=0.91,
            marking=["internal", "ecommerce"],
        ),
        source_id=ids["source"],
        source_revision=1,
        knowledge_scope=KnowledgeScope.WORKSPACE,
        actor="pytest",
        occurred_at=NOW + timedelta(minutes=2),
    )
    approved = memory.transition_candidate(
        PRIMARY,
        candidate.candidate_id,
        to_status=MemoryCandidateStatus.APPROVED,
        expected_version=1,
        actor="pytest",
        occurred_at=NOW + timedelta(minutes=3),
        governance=governance(),
    )
    _, _, revision = memory.promote_candidate(
        PRIMARY,
        approved.candidate_id,
        memory_item_id=ids["memory"],
        expected_version=2,
        actor="pytest",
        occurred_at=NOW + timedelta(minutes=4),
        expires_at=NOW + timedelta(days=20),
    )
    return {
        "ids": ids,
        "owner_ref": instance_refs[0],
        "recipient_ref": instance_refs[1],
        "memory_ref": MemoryRevisionExactRef(
            memory_item_id=ids["memory"],
            revision=revision.revision,
            content_hash=revision.content_hash,
        ),
        "agents": agents,
    }


def projection_request(chain, *, expires_at=None):
    ids = chain["ids"]
    return CreateMemoryProjectionRequest(
        projection_id=ids["projection"],
        kind=MemoryProjectionKind.SHARED,
        owner_instance_ref=chain["owner_ref"],
        memory_ref=chain["memory_ref"],
        recipient_instance_refs=[chain["recipient_ref"]],
        allowed_purposes=["vertical:ecommerce"],
        allowed_markings=["internal"],
        disclosure=MemoryDisclosureMode.CITATION_ONLY,
        effective_at=NOW + timedelta(minutes=5),
        expires_at=expires_at or NOW + timedelta(days=10),
    )


def create_projection(chain, *, expires_at=None):
    request = projection_request(chain, expires_at=expires_at)
    return request, AipMemoryProjectionStore().create_projection(
        PRIMARY,
        request,
        idempotency_key=f"create-{request.projection_id}",
        actor="pytest",
        occurred_at=NOW + timedelta(minutes=5),
    )


def test_shared_projection_is_restart_safe_reference_only_and_tenant_scoped(
    authority_chain,
):
    request, (projection, receipt) = create_projection(authority_chain)
    assert projection.status is MemoryProjectionStatus.ACTIVE
    assert projection.recipient_instance_refs == request.recipient_instance_refs
    assert receipt.result_ref == projection.projection_ref
    restarted = AipMemoryProjectionStore()
    assert restarted.get_projection(PRIMARY, request.projection_id) == projection
    assert restarted.list_projections(
        PRIMARY, recipient_instance_id=authority_chain["recipient_ref"].asset_id
    ) == [projection]
    with pytest.raises(AipMemoryProjectionNotFound):
        restarted.get_projection(CANARY, request.projection_id)
    assert restarted.list_projections(CANARY) == []
    with connect(PRIMARY) as conn:
        row = conn.execute(
            """SELECT memory_ref,owner_instance_ref,disclosure
               FROM aip_memory_agent_projection
               WHERE org_id=%s AND project_id=%s AND projection_id=%s""",
            (*PRIMARY.key, request.projection_id),
        ).fetchone()
    serialized = json.dumps(dict(row), ensure_ascii=False, default=str)
    assert "memory-payload" not in serialized
    assert row["disclosure"] == "citation_only"


def test_create_replay_is_idempotent_and_rejects_request_drift(authority_chain):
    request, first = create_projection(authority_chain)
    replay = AipMemoryProjectionStore().create_projection(
        PRIMARY,
        request,
        idempotency_key=f"create-{request.projection_id}",
        actor="pytest",
        occurred_at=NOW + timedelta(hours=1),
    )
    assert replay == first
    changed = request.model_copy(update={"allowed_purposes": ["task:content"]})
    with pytest.raises(AipMemoryProjectionConflict, match="idempotency"):
        AipMemoryProjectionStore().create_projection(
            PRIMARY,
            changed,
            idempotency_key=f"create-{request.projection_id}",
            actor="pytest",
            occurred_at=NOW + timedelta(hours=1),
        )


def test_status_cas_preserves_recipients_and_events_exact_projection_hash(
    authority_chain,
):
    request, (created, _) = create_projection(authority_chain)
    store = AipMemoryProjectionStore()
    suspended, _ = store.change_status(
        PRIMARY,
        request.projection_id,
        ChangeMemoryProjectionStatusRequest(
            expected_version=1,
            from_status="active",
            to_status="suspended",
            reason_hash=HASH_C,
        ),
        idempotency_key=f"suspend-{request.projection_id}",
        actor="pytest",
        occurred_at=NOW + timedelta(hours=1),
    )
    assert suspended.projection_ref.version == 2
    assert suspended.projection_ref.content_hash != created.projection_ref.content_hash
    assert suspended.recipient_instance_refs == request.recipient_instance_refs
    reactivated, _ = store.change_status(
        PRIMARY,
        request.projection_id,
        ChangeMemoryProjectionStatusRequest(
            expected_version=2,
            from_status="suspended",
            to_status="active",
            reason_hash=HASH_C,
        ),
        idempotency_key=f"reactivate-{request.projection_id}",
        actor="pytest",
        occurred_at=NOW + timedelta(hours=2),
    )
    events = store.list_events(PRIMARY, request.projection_id)
    assert [event.sequence for event in events] == [1, 2, 3]
    assert [event.projection_ref.version for event in events] == [1, 2, 3]
    assert events[-1].projection_ref == reactivated.projection_ref
    assert all(event.projection_ref.content_hash != "0" * 64 for event in events)
    with pytest.raises(AipMemoryProjectionConflict, match="version"):
        store.change_status(
            PRIMARY,
            request.projection_id,
            ChangeMemoryProjectionStatusRequest(
                expected_version=2,
                from_status="active",
                to_status="revoked",
                reason_hash=HASH_C,
            ),
            idempotency_key=f"stale-{request.projection_id}",
            actor="pytest",
            occurred_at=NOW + timedelta(hours=3),
        )


def test_reactivation_revalidates_time_and_exact_agent_dependencies(authority_chain):
    request, _ = create_projection(authority_chain, expires_at=NOW + timedelta(days=1))
    store = AipMemoryProjectionStore()
    suspended, _ = store.change_status(
        PRIMARY,
        request.projection_id,
        ChangeMemoryProjectionStatusRequest(
            expected_version=1,
            from_status="active",
            to_status="suspended",
            reason_hash=HASH_C,
        ),
        idempotency_key=f"suspend-{request.projection_id}",
        actor="pytest",
        occurred_at=NOW + timedelta(hours=1),
    )
    with pytest.raises(AipMemoryProjectionBlocked, match="effective interval"):
        store.change_status(
            PRIMARY,
            request.projection_id,
            ChangeMemoryProjectionStatusRequest(
                expected_version=suspended.projection_ref.version,
                from_status="suspended",
                to_status="active",
                reason_hash=HASH_C,
            ),
            idempotency_key=f"expired-{request.projection_id}",
            actor="pytest",
            occurred_at=NOW + timedelta(days=2),
        )

    recipient = authority_chain["recipient_ref"]
    agents = authority_chain["agents"]
    agents.update_instance(
        PRIMARY,
        recipient.asset_id,
        UpdateAgentInstanceRequest(
            expected_version=recipient.revision,
            from_status="active",
            to_status="suspended",
            overlay=agents.get_instance(PRIMARY, recipient.asset_id).overlay,
        ),
        idempotency_key=f"suspend-agent-{recipient.asset_id}",
        actor="pytest",
        occurred_at=NOW + timedelta(hours=2),
    )
    with pytest.raises(AipMemoryProjectionConflict, match="version/hash"):
        store.change_status(
            PRIMARY,
            request.projection_id,
            ChangeMemoryProjectionStatusRequest(
                expected_version=suspended.projection_ref.version,
                from_status="suspended",
                to_status="active",
                reason_hash=HASH_C,
            ),
            idempotency_key=f"drift-{request.projection_id}",
            actor="pytest",
            occurred_at=NOW + timedelta(hours=3),
        )
