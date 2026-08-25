"""W6-01 canonical candidate selection and exact capability readiness."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_assignee_resolution import (
    AssigneeResolutionStatus,
    ResolveAssigneeRequest,
    UpsertToolBindingRequest,
)
from aos_api.aip_assignee_resolution_store import AipAssigneeResolutionStore
from aos_api.aip_production_contracts import AssigneeKind, AssigneeRef
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 25, 4, 0, tzinfo=UTC)


def _capability(identifier: str, content_hash: str = "a" * 64) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type="CapabilityRevision",
        asset_id=identifier,
        revision=1,
        content_hash=content_hash,
    )


def _candidate(kind: AssigneeKind, identifier: str, version: int = 1) -> AssigneeRef:
    return AssigneeRef(kind=kind, resource_id=identifier, version=version)


def _seed_capability_binding(
    binding_id: str,
    capability: VersionedAssetRef,
    *,
    stale: bool = False,
) -> None:
    expires = NOW - timedelta(minutes=1) if stale else NOW + timedelta(hours=1)
    with connect() as conn:
        conn.execute(
            """INSERT INTO aip_capability_binding(
                 org_id,project_id,binding_id,capability_ref,secret_ref,health,
                 network_policy_revision,quota_policy_revision,timeout_ms,max_concurrency,
                 status,version,observed_at,allow_degraded,dependency_snapshot_hash,
                 operational_readiness,last_evaluated_at,readiness_expires_at)
               VALUES(%s,%s,%s,%s::jsonb,'secret://pytest/w6','healthy',
                      'network-w6','quota-w6',30000,1,'active',1,%s,FALSE,%s,
                      'available',%s,%s)""",
            (
                *SCOPE.key,
                binding_id,
                capability.model_dump_json(by_alias=True),
                NOW,
                "b" * 64,
                NOW,
                expires,
            ),
        )
        conn.commit()


def _seed_active_agent(instance_id: str, capability_binding_id: str) -> None:
    suffix = instance_id.rsplit("-", 1)[-1]
    template_id = f"template-w6-{suffix}"
    skill_id = f"skill-w6-{suffix}"
    with connect() as conn:
        conn.execute(
            """INSERT INTO aip_agent_template_revision(
                 template_id,revision,display_name,role_key,lifecycle,source_ref,
                 source_license,manifest,content_hash,created_by)
               VALUES(%s,1,'W6 Agent',%s,'published','{}','internal','{}',%s,'tester')""",
            (template_id, f"role-{suffix}", "e" * 64),
        )
        conn.execute(
            """INSERT INTO aip_agent_instance(
                 org_id,project_id,instance_id,template_id,template_revision,status,
                 overlay,version,created_by)
               VALUES(%s,%s,%s,%s,1,'active','{}',1,'tester')""",
            (*SCOPE.key, instance_id, template_id),
        )
        conn.execute(
            """INSERT INTO aip_skill_template_revision(
                 skill_id,revision,canonical_logic_id,lifecycle,input_schema,output_schema,
                 tool_allowlist,required_capabilities,risk_level,memory_policy_ref,
                 handoff_policy_ref,source_ref,source_license,content_hash,created_by)
               VALUES(%s,1,%s,'draft','{}','{}','[]','[]','low','{}','{}','{}',
                      'internal',%s,'tester')""",
            (skill_id, f"logic-{suffix}", "f" * 64),
        )
        conn.execute(
            """INSERT INTO aip_skill_binding(
                 org_id,project_id,binding_id,instance_id,skill_id,skill_revision,
                 capability_refs,budget_policy_ref,status,version,readiness,
                 dependency_snapshot_hash,last_evaluated_at,readiness_expires_at)
               VALUES(%s,%s,%s,%s,%s,1,%s::jsonb,'{}','active',1,'available',%s,
                      %s,%s)""",
            (
                *SCOPE.key,
                f"skill-binding-{suffix}",
                instance_id,
                skill_id,
                f'["{capability_binding_id}"]',
                "1" * 64,
                NOW,
                NOW + timedelta(hours=1),
            ),
        )
        conn.commit()


def test_request_rejects_duplicate_candidates_and_non_capability_refs() -> None:
    candidate = _candidate(AssigneeKind.HUMAN_PRINCIPAL, "user:owner")
    with pytest.raises(ValueError, match="unique exact refs"):
        ResolveAssigneeRequest(
            subject_id="responsibility:duplicate",
            assignee=candidate,
            candidates=[candidate],
        )
    with pytest.raises(ValueError, match="CapabilityRevision"):
        ResolveAssigneeRequest(
            subject_id="responsibility:invalid-capability",
            candidates=[candidate],
            required_capabilities=[
                VersionedAssetRef(
                    asset_type="ToolRevision",
                    asset_id="tool.invalid",
                    revision=1,
                    content_hash="c" * 64,
                )
            ],
        )


def test_provider_candidates_are_sorted_and_snapshot_hash_is_deterministic() -> None:
    capability = _capability(f"content.review.{uuid4().hex[:8]}")
    first = f"provider-a-{uuid4().hex[:8]}"
    second = f"provider-b-{uuid4().hex[:8]}"
    _seed_capability_binding(first, capability)
    _seed_capability_binding(second, capability)
    store = AipAssigneeResolutionStore()
    candidates = [
        _candidate(AssigneeKind.PROVIDER_CAPABILITY_BINDING, second),
        _candidate(AssigneeKind.PROVIDER_CAPABILITY_BINDING, first),
    ]
    request = ResolveAssigneeRequest(
        subject_id=f"responsibility:provider:{uuid4().hex[:8]}",
        candidates=candidates,
        required_capabilities=[capability],
    )
    receipt = store.resolve(SCOPE, request, "tester", now=NOW)
    replay = store.resolve(
        SCOPE,
        request.model_copy(update={"candidates": list(reversed(candidates))}),
        "tester",
        now=NOW + timedelta(seconds=1),
    )

    assert receipt.status is AssigneeResolutionStatus.RESOLVED
    assert receipt.selected_assignee is not None
    assert receipt.selected_assignee.resource_id == first
    assert [item.assignee.resource_id for item in receipt.candidate_decisions] == [
        first,
        second,
    ]
    assert receipt.snapshot_hash == replay.snapshot_hash
    assert receipt.receipt_id == replay.receipt_id
    assert receipt.required_capabilities == [capability]
    assert {item.asset_type for item in receipt.binding_refs} == {
        "CapabilityBinding"
    }


def test_exact_hash_stale_and_cross_tenant_candidates_fail_closed() -> None:
    capability = _capability(f"copy.generate.{uuid4().hex[:8]}")
    stale_id = f"provider-stale-{uuid4().hex[:8]}"
    _seed_capability_binding(stale_id, capability, stale=True)
    store = AipAssigneeResolutionStore()

    stale = store.resolve(
        SCOPE,
        ResolveAssigneeRequest(
            subject_id=f"responsibility:stale:{uuid4().hex[:8]}",
            candidates=[
                _candidate(AssigneeKind.PROVIDER_CAPABILITY_BINDING, stale_id)
            ],
            required_capabilities=[capability],
        ),
        "tester",
        now=NOW,
    )
    drifted = store.resolve(
        SCOPE,
        ResolveAssigneeRequest(
            subject_id=f"responsibility:drifted:{uuid4().hex[:8]}",
            candidates=[
                _candidate(AssigneeKind.PROVIDER_CAPABILITY_BINDING, stale_id)
            ],
            required_capabilities=[
                capability.model_copy(update={"content_hash": "d" * 64})
            ],
        ),
        "tester",
        now=NOW - timedelta(minutes=2),
    )
    isolated = store.resolve(
        OTHER_SCOPE,
        ResolveAssigneeRequest(
            subject_id=f"responsibility:isolated:{uuid4().hex[:8]}",
            candidates=[
                _candidate(AssigneeKind.PROVIDER_CAPABILITY_BINDING, stale_id)
            ],
            required_capabilities=[capability],
        ),
        "tester",
        now=NOW,
    )

    assert stale.status is AssigneeResolutionStatus.BLOCKED
    assert "CAPABILITY_BINDING_STALE" in stale.blocker_codes
    assert drifted.status is AssigneeResolutionStatus.BLOCKED
    assert "REQUIRED_CAPABILITY_NOT_EXACTLY_COVERED" in drifted.blocker_codes
    assert isolated.status is AssigneeResolutionStatus.BLOCKED
    assert "CAPABILITY_BINDING_MISSING" in isolated.blocker_codes


def test_human_candidate_requires_current_workspace_membership() -> None:
    store = AipAssigneeResolutionStore(
        membership_resolver=lambda org_id, project_id, subject: (
            org_id,
            project_id,
            subject,
        )
        == ("org-org", "dev-project", "user:owner")
    )
    request = ResolveAssigneeRequest(
        subject_id=f"responsibility:human:{uuid4().hex[:8]}",
        candidates=[_candidate(AssigneeKind.HUMAN_PRINCIPAL, "user:owner")],
    )
    resolved = store.resolve(SCOPE, request, "tester", now=NOW)
    blocked = store.resolve(OTHER_SCOPE, request, "tester", now=NOW)

    assert resolved.status is AssigneeResolutionStatus.RESOLVED
    assert blocked.status is AssigneeResolutionStatus.BLOCKED
    assert "HUMAN_PRINCIPAL_NOT_TENANT_MEMBER" in blocked.blocker_codes


def test_agent_and_instance_scoped_tool_require_exact_operational_bindings() -> None:
    capability = _capability(f"strategy.plan.{uuid4().hex[:8]}")
    capability_binding_id = f"cap-agent-{uuid4().hex[:8]}"
    instance_id = f"agent-w6-{uuid4().hex[:8]}"
    tool_binding_id = f"tool-w6-{uuid4().hex[:8]}"
    _seed_capability_binding(capability_binding_id, capability)
    _seed_active_agent(instance_id, capability_binding_id)
    store = AipAssigneeResolutionStore()

    agent = store.resolve(
        SCOPE,
        ResolveAssigneeRequest(
            subject_id=f"responsibility:agent:{uuid4().hex[:8]}",
            candidates=[_candidate(AssigneeKind.AGENT_INSTANCE, instance_id)],
            required_capabilities=[capability],
        ),
        "tester",
        now=NOW,
    )
    store.upsert_tool_binding(
        SCOPE,
        UpsertToolBindingRequest(
            binding_id=tool_binding_id,
            tool_id="tool.query",
            version=1,
            agent_instance_id=instance_id,
            capability_binding_ids=[capability_binding_id],
        ),
        now=NOW,
    )
    tool = store.resolve(
        SCOPE,
        ResolveAssigneeRequest(
            subject_id=f"responsibility:tool:{uuid4().hex[:8]}",
            candidates=[_candidate(AssigneeKind.TOOL_BINDING, tool_binding_id)],
            required_capabilities=[capability],
        ),
        "tester",
        now=NOW,
    )

    assert agent.status is AssigneeResolutionStatus.RESOLVED
    assert {item.asset_type for item in agent.binding_refs} == {
        "AgentTemplate",
        "SkillBinding",
        "CapabilityBinding",
    }
    assert tool.status is AssigneeResolutionStatus.RESOLVED
    assert {item.asset_type for item in tool.binding_refs} == {
        "ToolBinding",
        "CapabilityBinding",
    }
