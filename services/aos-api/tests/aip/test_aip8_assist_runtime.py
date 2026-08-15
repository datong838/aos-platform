from __future__ import annotations

from datetime import UTC, datetime

from aos_api.aip_assist_context_assembler import (
    AipAssistContextAssembler,
    AssistContextBlocked,
)
from aos_api.aip_assist_contracts import (
    AssistAuthorityContext,
    AssistEventType,
    AssistSubjectRefs,
)
from aos_api.aip_assist_runtime import ExactAipAssistRuntime
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_llm_adapter import LLMRuntimeBlocked
from aos_api.tenant_scope import TenantScope


NOW = datetime.now(UTC)
HASH = "a" * 64


def ref(kind: str, value: str) -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=value,
        revision="1",
        authority="test-authority",
    )


def subject() -> AssistSubjectRefs:
    return AssistSubjectRefs(
        task_ref=ref("Task", "task-1"),
        task_run_ref=ref("TaskRun", "run-1"),
        agent_run_ref=ref("AgentRun", "agent-run-1"),
        selection_refs=[],
        cutoff_at=NOW,
    )


def context() -> AssistAuthorityContext:
    return AssistAuthorityContext(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        task_ref=ref("Task", "task-1"),
        task_run_ref=ref("TaskRun", "run-1"),
        plan_ref=ref("PlanRevision", "plan-1"),
        agent_run_ref=ref("AgentRun", "agent-run-1"),
        agent_instance_ref=ref("AgentInstanceRevision", "instance-1"),
        skill_ref=ref("SkillRevision", "skill-1"),
        logic_ref=ref("LogicRevision", "logic-1"),
        model_route_ref=ref("ModelRouteRevision", "route-1"),
        policy_ref=ref("RuntimePolicyRevision", "policy-1"),
        eval_ref=ref("EvalGateDecision", "eval-1"),
        skill_binding_ref=ref("SkillBinding", "binding-1"),
        markings=["public"],
        cutoff_at=NOW,
    )


class Reader:
    def resolve(self, scope, requested_subject):
        return context()


class BlockedReader:
    def resolve(self, scope, requested_subject):
        raise AssistContextBlocked("ASSIST_AGENT_RUN_NOT_RUNNING")


def asset(kind: str, value: str) -> dict:
    return {
        "assetType": kind,
        "assetId": value,
        "revision": 1,
        "contentHash": HASH,
    }


class ReadyLLM:
    def chat_exact(self, scope, route_id, query, *, lineage_id, system_prompt=""):
        assert scope.key == ("org-org", "dev-project")
        assert route_id == "route-1" and lineage_id == "turn-1"
        assert query == "核查订单风险" and "不得补造" in system_prompt
        return {
            "answer": "基于权威上下文，当前没有可确认的新增风险。",
            "tokens": 12,
            "usageReceiptIds": ["usage-1"],
            "routeRef": asset("ModelRouteRevision", "route-1"),
            "policyRef": asset("RuntimePolicyRevision", "policy-1"),
            "modelRef": asset("RegisteredModelRevision", "model-1"),
            "providerRef": asset("ProviderInstanceRevision", "provider-1"),
            "priceSnapshotRef": asset("ModelPriceSnapshotRevision", "price-1"),
        }


class BlockedLLM:
    def chat_exact(self, *args, **kwargs):
        raise LLMRuntimeBlocked("provider_invoker_authority_unavailable")


def test_exact_runtime_emits_context_delta_done_with_usage_and_lineage() -> None:
    runtime = ExactAipAssistRuntime(AipAssistContextAssembler(Reader()), ReadyLLM())
    events = runtime.execute(
        TenantScope("org-org", "dev-project"),
        subject(),
        "核查订单风险",
        principal_markings=["public"],
        thread_id="thread-1",
        turn_id="turn-1",
        first_sequence=2,
    )
    assert [event.event_type for event in events] == [
        AssistEventType.CONTEXT,
        AssistEventType.DELTA,
        AssistEventType.DONE,
    ]
    assert [event.sequence for event in events] == [2, 3, 4]
    assert events[-1].usage_refs[0].resource_id == "usage-1"
    assert len(events[-1].lineage_refs) == 5


def test_exact_runtime_persists_honest_context_and_provider_blockers() -> None:
    context_blocked = ExactAipAssistRuntime(
        AipAssistContextAssembler(BlockedReader()), ReadyLLM()
    ).execute(
        TenantScope("org-org", "dev-project"),
        subject(),
        "核查订单风险",
        principal_markings=["public"],
        thread_id="thread-1",
        turn_id="turn-1",
        first_sequence=2,
    )
    assert [event.event_type for event in context_blocked] == [AssistEventType.BLOCKED]
    assert context_blocked[0].blocker.code == "ASSIST_AGENT_RUN_NOT_RUNNING"

    provider_blocked = ExactAipAssistRuntime(
        AipAssistContextAssembler(Reader()), BlockedLLM()
    ).execute(
        TenantScope("org-org", "dev-project"),
        subject(),
        "核查订单风险",
        principal_markings=["public"],
        thread_id="thread-1",
        turn_id="turn-1",
        first_sequence=2,
    )
    assert [event.event_type for event in provider_blocked] == [
        AssistEventType.CONTEXT,
        AssistEventType.BLOCKED,
    ]
    assert provider_blocked[-1].blocker.code == "PROVIDER_INVOKER_AUTHORITY_UNAVAILABLE"
