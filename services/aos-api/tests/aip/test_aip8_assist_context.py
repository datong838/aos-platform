from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_assist_context_assembler import (
    AipAssistContextAssembler,
    AssistContextBlocked,
)
from aos_api.aip_assist_contracts import AssistAuthorityContext, AssistSubjectRefs
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.tenant_scope import TenantScope


NOW = datetime.now(UTC)


def ref(kind: str, value: str, revision: str = "1") -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=value,
        revision=revision,
        authority="test-authority",
    )


class Reader:
    def __init__(self, context: AssistAuthorityContext) -> None:
        self.context = context

    def resolve(self, scope: TenantScope, subject: AssistSubjectRefs) -> AssistAuthorityContext:
        return self.context


def authority_context() -> AssistAuthorityContext:
    return AssistAuthorityContext(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        task_ref=ref("Task", "task-1"),
        task_run_ref=ref("TaskRun", "run-1"),
        plan_ref=ref("PlanRevision", "plan-1"),
        agent_run_ref=ref("AgentRun", "agent-run-1"),
        agent_instance_ref=ref("AgentInstanceRevision", "agent-1"),
        skill_ref=ref("SkillRevision", "skill-1"),
        logic_ref=ref("LogicRevision", "logic-1"),
        model_route_ref=ref("ModelRouteRevision", "route-1"),
        policy_ref=ref("RuntimePolicyRevision", "policy-1"),
        eval_ref=ref("EvalGateRevision", "eval-1"),
        skill_binding_ref=ref("SkillBinding", "skill-binding-1"),
        capability_binding_refs=[ref("CapabilityBinding", "cap-1")],
        selection_refs=[ref("SelectionRevision", "selection-1")],
        knowledge_citation_refs=[ref("KnowledgeCitation", "citation-1")],
        markings=["public"],
        cutoff_at=NOW,
    )


def subject() -> AssistSubjectRefs:
    return AssistSubjectRefs(
        task_ref=ref("Task", "task-1"),
        task_run_ref=ref("TaskRun", "run-1"),
        agent_run_ref=ref("AgentRun", "agent-run-1"),
        selection_refs=[ref("SelectionRevision", "selection-1")],
        cutoff_at=NOW,
    )


def test_context_assembler_builds_stable_minimal_snapshot() -> None:
    assembler = AipAssistContextAssembler(Reader(authority_context()))
    snapshot = assembler.assemble(
        TenantScope("org-org", "dev-project"),
        subject(),
        principal_markings=["public"],
    )
    assert snapshot.context_hash
    assert snapshot.task_ref.resource_id == "task-1"
    assert snapshot.selection_refs == subject().selection_refs


def test_context_assembler_blocks_exact_ref_drift() -> None:
    context = authority_context()
    context.task_ref = ref("Task", "task-1", revision="2")
    assembler = AipAssistContextAssembler(Reader(context))
    with pytest.raises(AssistContextBlocked, match="ASSIST_CONTEXT_EXACT_REF_DRIFT"):
        assembler.assemble(
            TenantScope("org-org", "dev-project"),
            subject(),
            principal_markings=["public"],
        )


def test_context_assembler_blocks_cross_tenant_and_marking_escalation() -> None:
    context = authority_context()
    context.tenant = TenantContext(org_id="dev-org", project_id="dev-project")
    with pytest.raises(AssistContextBlocked, match="ASSIST_CONTEXT_TENANT_DRIFT"):
        AipAssistContextAssembler(Reader(context)).assemble(
            TenantScope("org-org", "dev-project"),
            subject(),
            principal_markings=["public"],
        )

    context = authority_context()
    context.markings = ["restricted"]
    with pytest.raises(AssistContextBlocked, match="ASSIST_CONTEXT_MARKING_DENIED"):
        AipAssistContextAssembler(Reader(context)).assemble(
            TenantScope("org-org", "dev-project"),
            subject(),
            principal_markings=["public"],
        )
