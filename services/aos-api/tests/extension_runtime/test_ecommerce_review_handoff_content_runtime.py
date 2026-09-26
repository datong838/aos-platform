"""AR2-5 package-owned review, Handoff and internal content-task contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[4]
SDK_ROOT = ROOT / "packages/aos-extension-sdk/python"
GROWTH_ROOT = ROOT / "bundles/solutions/ecommerce-growth/backend"
for dependency in (SDK_ROOT, GROWTH_ROOT):
    if str(dependency) not in sys.path:
        sys.path.insert(0, str(dependency))

from aos_extension_sdk import DispatchRef
import aos_api.ecommerce_growth_runtime_adapters as runtime_adapters
from aos_api.ecommerce_growth_runtime_adapters import ReviewAdvanceHostService
from ecommerce_growth.ecommerce_business_investigation_application import (
    EcommerceGrowthApplication,
)
from ecommerce_growth.ecommerce_business_investigation_review_command import (
    ARTIFACT_FAMILIES,
    ArtifactBinding,
    ReviewHandoffRequest,
    exact_ref_payload,
)
from ecommerce_growth.ecommerce_content_campaign_workflow import (
    REVIEW_HANDOFF_OPERATION,
    advance_review_handoff,
)
from ecommerce_growth.ecommerce_content_campaign_workflow_contracts import ContentTaskSpec
from ecommerce_growth.sdk_ports import ExactRef


HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"
CUTOFF = datetime(2026, 9, 8, 1, tzinfo=UTC)


def ref(kind: str, identity: str, *, revision: int = 1, hash_value: str = HASH_A):
    return ExactRef(kind, identity, revision, hash_value)


def dispatch(*, operation=REVIEW_HANDOFF_OPERATION, epoch=9, org="org-org"):
    return DispatchRef.from_payload(
        {
            "orgId": org,
            "projectId": "dev-project",
            "operationId": operation,
            "handlerKind": "extension",
            "dispatchRevision": 12,
            "installationId": "11111111-1111-4111-8111-111111111111",
            "generation": "22222222-2222-4222-8222-222222222222",
            "executionEpoch": epoch,
            "cutoverGroupId": "33333333-3333-4333-8333-333333333333",
            "cutoverGroupRevision": 6,
        }
    )


def artifacts():
    return tuple(
        ArtifactBinding(family, ref("ArtifactRevision", f"artifact-{family}"))
        for family in ARTIFACT_FAMILIES
    )


def request(*, decision="ACCEPT", key="review-1", **overrides):
    bindings = overrides.pop("artifact_bindings", artifacts())
    plan = overrides.pop("growth_plan_ref", ref("GrowthPlanRevision", "growth-plan-1"))
    task = None
    accept = decision == "ACCEPT"
    if accept:
        task = ContentTaskSpec(
            title="制定七夕会员复购活动方案",
            objective="围绕栖月汇微商城会员设计七夕复购活动",
            channels=("微信小店", "私域社群"),
            audience="近九十天已购会员",
            time_window="七夕活动前七天至活动后三天",
            constraints=("毛利率不低于百分之十五", "库存不足商品不得主推"),
            growth_plan_ref=plan,
            artifact_refs=tuple(item.artifact_ref for item in bindings),
        )
    values = {
        "occurrence_ref": ref("AutomationOccurrence", "occurrence-1"),
        "case_ref": ref("BusinessInvestigationCaseRevision", "case-1"),
        "run_ref": ref("BusinessInvestigationRun", "run-1"),
        "analysis_receipt_ref": ref("AnalysisRuntimeReceipt", "analysis-receipt-1"),
        "current_plan_ref": ref("PlanRevision", "plan-1"),
        "growth_plan_ref": plan,
        "review_issue_ref": ref("ReviewIssueRevision", "issue-1"),
        "eval_report_ref": ref("EvalReportRevision", "eval-1"),
        "artifact_bindings": bindings,
        "decision": decision,
        "idempotency_key": key,
        "cutoff_at": CUTOFF,
        "return_stage": None if accept else "diagnosis",
        "target_module_id": "ecommerce.content-campaign" if accept else None,
        "source_slot_id": "analyst.solution" if accept else None,
        "target_slot_id": "content.plan" if accept else None,
        "markings": ("internal",) if accept else (),
        "expires_at": CUTOFF + timedelta(days=1) if accept else None,
        "content_task": task,
    }
    values.update(overrides)
    return ReviewHandoffRequest(**values)


def receipt_payload(command, *, replayed=False, **overrides):
    accepted = command["decision"] == "ACCEPT"
    value = {
        "receiptRef": exact_ref_payload(ref("ReviewDecisionReceipt", "review-receipt-1")),
        "requestHash": command["requestHash"],
        "decision": command["decision"],
        "occurrenceRef": command["occurrenceRef"],
        "caseRef": command["caseRef"],
        "runRef": command["runRef"],
        "analysisReceiptRef": command["analysisReceiptRef"],
        "currentPlanRef": command["currentPlanRef"],
        "reviewIssueRef": command["reviewIssueRef"],
        "evalReportRef": command["evalReportRef"],
        "growthPlanRef": command["growthPlanRef"],
        "artifactBindings": command["artifactBindings"],
        "returnStage": command["returnStage"],
        "handoffRef": exact_ref_payload(ref("HandoffReceipt", "handoff-1")) if accepted else None,
        "taskRef": exact_ref_payload(ref("Task", "task-1")) if accepted else None,
        "briefRef": exact_ref_payload(ref("TaskBriefRevision", "brief-1")) if accepted else None,
        "cutoffAt": command["cutoffAt"],
        "replayed": replayed,
        "sideEffects": {
            "externalEffectsAllowed": False,
            "providerInvocationCount": 0,
            "approvalCreatedCount": 0,
            "taskRunCreatedCount": 0,
            "externalPublicationCount": 0,
            "externalBusinessMutationCount": 0,
        },
    }
    value.update(overrides)
    return value


class ReviewPort:
    def __init__(
        self,
        responder=receipt_payload,
        *,
        epoch=9,
        org="org-org",
        host_decided_at=CUTOFF + timedelta(minutes=1),
    ):
        self.responder = responder
        self.epoch = epoch
        self.org = org
        self.host_decided_at = host_decided_at
        self.commands = []
        self.receipts = {}

    def commit(self, *, dispatch_ref, command):
        if dispatch_ref.execution_epoch != self.epoch:
            raise PermissionError("stale execution epoch")
        if (dispatch_ref.org_id, dispatch_ref.project_id) != (self.org, "dev-project"):
            raise PermissionError("tenant isolation")
        assert not {"tenant", "orgId", "projectId", "dispatchRef"}.intersection(command)
        key = command["idempotencyKey"]
        previous = self.receipts.get(key)
        if previous is not None:
            if previous[0] != command["requestHash"]:
                raise ValueError("idempotency content drift")
            replay = dict(previous[1])
            replay["replayed"] = True
            return replay
        cutoff = datetime.fromisoformat(command["cutoffAt"])
        if self.host_decided_at < cutoff:
            raise PermissionError("host transaction clock precedes cutoff")
        if command["decision"] == "ACCEPT":
            expires_at = datetime.fromisoformat(command["expiresAt"])
            if self.host_decided_at >= expires_at:
                raise PermissionError("Handoff expired at host transaction time")
        self.commands.append(command)
        value = self.responder(command)
        value.setdefault("decidedAt", self.host_decided_at.isoformat())
        self.receipts[key] = (command["requestHash"], value)
        return value


class WritePort:
    def commit(self, **_kwargs):
        raise AssertionError("N1 write port must not receive N5/N6 commands")


def test_accept_creates_one_handoff_task_and_brief_and_replays() -> None:
    port = ReviewPort()
    item = request()
    first = advance_review_handoff(port, dispatch_ref=dispatch(), request=item)
    replay = advance_review_handoff(port, dispatch_ref=dispatch(), request=item)
    assert first.decision == "ACCEPT" and first.handoff_ref is not None
    assert first.task_ref is not None and first.brief_ref is not None
    assert replay.replayed is True and len(port.commands) == 1
    assert port.commands[0]["taskSpec"]["title"] == "制定七夕会员复购活动方案"


def test_application_routes_review_without_n1_write_port() -> None:
    port = ReviewPort()
    app = EcommerceGrowthApplication(WritePort(), review_port=port)
    result = app.advance_review(dispatch_ref=dispatch(), request=request())
    assert result.brief_ref.resource_type == "TaskBriefRevision"


def test_v2_handoff_enqueues_one_content_run_intent_in_original_transaction(monkeypatch):
    class Tx:
        calls = []

        def execute(self, query, params=()):
            self.calls.append((query, params))
            return Result("intent" if "FROM public.ecommerce_growth_content_taskrun_intent" in query else "put")

    class Result:
        def __init__(self, kind):
            self.kind = kind

        def fetchone(self):
            if self.kind == "put":
                return {"inserted": True}
            return {
                "review_receipt_ref": exact_ref_payload(ref("ReviewDecisionReceipt", "receipt-v2")),
                "task_id": "task-v2", "brief_id": "brief-v2",
                "origin_request_hash": HASH_A, "state": "pending", "attempt": 0,
                "claim_token": None, "plan_revision_id": None, "run_id": None,
            }

    class Receipts:
        def read(self, _key):
            return None

        def put(self, _key, payload, **_kwargs):
            return payload

    monkeypatch.setattr(runtime_adapters, "_strict_review_accept_command", lambda _command: ("review-v2", None, None))
    monkeypatch.setattr(ReviewAdvanceHostService, "_components", staticmethod(lambda *_: (None, None, Receipts())))
    monkeypatch.setattr(ReviewAdvanceHostService, "_revalidate_growth_plan", staticmethod(lambda **_: SimpleNamespace(sales_weapon_method=object())))
    monkeypatch.setattr(ReviewAdvanceHostService, "_require_sales_weapon_method", staticmethod(lambda **_: None))
    monkeypatch.setattr(ReviewAdvanceHostService, "_review_lineage", lambda self, **_: {
        "taskRef": exact_ref_payload(ref("Task", "task-v2")),
        "briefRef": exact_ref_payload(ref("TaskBriefRevision", "brief-v2")),
    })
    monkeypatch.setattr(ReviewAdvanceHostService, "_accept_receipt", lambda self, *_: {
        "receiptRef": exact_ref_payload(ref("ReviewDecisionReceipt", "receipt-v2")),
        "requestHash": HASH_A,
    })
    transaction = Tx()
    result = ReviewAdvanceHostService().execute(
        transaction=transaction, scope=SimpleNamespace(key=("org-org", "dev-project")), dispatch_ref=None,
        command={}, checked_at=CUTOFF, occurred_at=CUTOFF,
    )
    assert result["receiptRef"]["resourceId"] == "receipt-v2"
    assert len(transaction.calls) == 2
    assert "ecommerce_growth_content_taskrun_intent_put_a0v_101" in transaction.calls[0][0]
    assert transaction.calls[0][1] == ("review-v2",)


def test_return_creates_no_handoff_task_or_brief() -> None:
    result = advance_review_handoff(
        ReviewPort(), dispatch_ref=dispatch(), request=request(decision="RETURN")
    )
    assert result.return_stage == "diagnosis"
    assert result.handoff_ref is result.task_ref is result.brief_ref is None


def test_request_more_and_noncurrent_authority_fail_closed() -> None:
    with pytest.raises(ValueError, match="no canonical authority"):
        request(decision="REQUEST_MORE")
    with pytest.raises(ValueError, match="current APPROVED"):
        request(growth_plan_current=False)
    with pytest.raises(ValueError, match="current APPROVED"):
        request(review_issue_status="CLOSED")


def test_artifact_set_expiry_and_technical_task_text_fail_closed() -> None:
    with pytest.raises(ValueError, match="canonical family order"):
        request(artifact_bindings=tuple(reversed(artifacts())))
    with pytest.raises(ValueError, match="bounded content Handoff"):
        request(expires_at=CUTOFF + timedelta(days=8))
    bad_task = ContentTaskSpec(
        title="开发任务 AR2-5",
        objective="完成技术方案波次",
        channels=("微信小店",),
        audience="商城会员",
        time_window="本周",
        constraints=(),
        growth_plan_ref=ref("GrowthPlanRevision", "growth-plan-1"),
        artifact_refs=tuple(item.artifact_ref for item in artifacts()),
    )
    with pytest.raises(ValueError, match="Chinese business text"):
        request(content_task=bad_task)
    with pytest.raises(ValueError, match="idempotency key"):
        request(key=1)
    with pytest.raises(ValueError, match="bounded content Handoff"):
        request(source_slot_id=1)
    with pytest.raises(ValueError, match="bounded content Handoff"):
        request(markings=("external_publish_authorized",))

    polluted_constraint = ContentTaskSpec(
        title="制定栖月汇会员活动",
        objective="围绕商城会员设计复购活动",
        channels=("微信小店",),
        audience="近九十天已购会员",
        time_window="本周",
        constraints=("执行数据库迁移W5",),
        growth_plan_ref=ref("GrowthPlanRevision", "growth-plan-1"),
        artifact_refs=tuple(item.artifact_ref for item in artifacts()),
    )
    with pytest.raises(ValueError, match="Chinese business text"):
        request(content_task=polluted_constraint)

    adjacent_identifier = ContentTaskSpec(
        title="制定栖月汇AR2活动",
        objective="围绕商城会员设计复购活动",
        channels=("微信小店",),
        audience="近九十天已购会员",
        time_window="本周",
        constraints=(),
        growth_plan_ref=ref("GrowthPlanRevision", "growth-plan-1"),
        artifact_refs=tuple(item.artifact_ref for item in artifacts()),
    )
    with pytest.raises(ValueError, match="Chinese business text"):
        request(content_task=adjacent_identifier)


def test_host_decision_time_rejects_an_already_expired_handoff() -> None:
    historical = request(
        cutoff_at=datetime(2020, 1, 1, tzinfo=UTC),
        expires_at=datetime(2020, 1, 2, tzinfo=UTC),
    )
    with pytest.raises(PermissionError, match="expired at host transaction time"):
        advance_review_handoff(
            ReviewPort(host_decided_at=CUTOFF),
            dispatch_ref=dispatch(),
            request=historical,
        )


def test_replay_keeps_original_host_decision_time_after_expiry() -> None:
    port = ReviewPort(host_decided_at=CUTOFF + timedelta(minutes=1))
    item = request(expires_at=CUTOFF + timedelta(minutes=2))
    first = advance_review_handoff(port, dispatch_ref=dispatch(), request=item)
    assert "decidedAt" not in port.commands[0]
    port.host_decided_at = CUTOFF + timedelta(days=1)
    replay = advance_review_handoff(port, dispatch_ref=dispatch(), request=item)
    assert replay.replayed is True
    assert replay.decided_at == first.decided_at == CUTOFF + timedelta(minutes=1)
    assert len(port.commands) == 1


@pytest.mark.parametrize(
    "polluted",
    (
        "栖月汇A\u200bR2活动",
        "执行src/jobs/publish.ts",
        r"读取C:\work\task.py",
        r"读取C:\\work\\task.py",
    ),
)
def test_hidden_identifier_and_file_paths_cannot_enter_business_brief(polluted) -> None:
    task = ContentTaskSpec(
        title="制定栖月汇会员活动",
        objective="围绕商城会员设计复购活动",
        channels=("微信小店",),
        audience="近九十天已购会员",
        time_window="本周",
        constraints=(polluted,),
        growth_plan_ref=ref("GrowthPlanRevision", "growth-plan-1"),
        artifact_refs=tuple(item.artifact_ref for item in artifacts()),
    )
    with pytest.raises(ValueError, match="Chinese business text"):
        request(content_task=task)


def test_content_task_contract_rejects_incomplete_artifact_lineage() -> None:
    with pytest.raises(ValueError, match="four unique Artifact"):
        ContentTaskSpec(
            title="制定会员复购活动方案",
            objective="围绕商城会员设计复购活动",
            channels=("微信小店",),
            audience="近九十天已购会员",
            time_window="本周",
            constraints=(),
            growth_plan_ref=ref("GrowthPlanRevision", "growth-plan-1"),
            artifact_refs=tuple(item.artifact_ref for item in artifacts()[:3]),
        )


def test_same_key_content_drift_is_rejected() -> None:
    port = ReviewPort()
    advance_review_handoff(port, dispatch_ref=dispatch(), request=request())
    with pytest.raises(ValueError, match="idempotency content drift"):
        advance_review_handoff(
            port,
            dispatch_ref=dispatch(),
            request=request(growth_plan_ref=ref("GrowthPlanRevision", "growth-plan-2")),
        )


def test_cross_tenant_stale_epoch_and_wrong_operation_are_rejected() -> None:
    with pytest.raises(PermissionError, match="stale execution epoch"):
        advance_review_handoff(ReviewPort(), dispatch_ref=dispatch(epoch=8), request=request())
    with pytest.raises(PermissionError, match="tenant isolation"):
        advance_review_handoff(
            ReviewPort(), dispatch_ref=dispatch(org="dev-org"), request=request()
        )
    with pytest.raises(PermissionError, match="does not authorize"):
        advance_review_handoff(
            ReviewPort(),
            dispatch_ref=dispatch(operation="ecommerce_growth_analysis_advance"),
            request=request(),
        )


def test_receipt_exact_lineage_shape_and_side_effects_fail_closed() -> None:
    def partial(command):
        return receipt_payload(command, taskRef=None)

    with pytest.raises(ValueError, match="requires Handoff, Task and Brief"):
        advance_review_handoff(ReviewPort(partial), dispatch_ref=dispatch(), request=request())

    def drift(command):
        return receipt_payload(
            command,
            growthPlanRef=exact_ref_payload(ref("GrowthPlanRevision", "other")),
        )

    with pytest.raises(ValueError, match="exact lineage drifted"):
        advance_review_handoff(ReviewPort(drift), dispatch_ref=dispatch(), request=request())

    def upstream_drift(command):
        return receipt_payload(
            command,
            runRef=exact_ref_payload(ref("BusinessInvestigationRun", "other-run")),
        )

    with pytest.raises(ValueError, match="exact lineage drifted"):
        advance_review_handoff(
            ReviewPort(upstream_drift), dispatch_ref=dispatch(), request=request()
        )

    def cutoff_drift(command):
        return receipt_payload(command, cutoffAt=(CUTOFF + timedelta(seconds=1)).isoformat())

    with pytest.raises(ValueError, match="exact lineage drifted"):
        advance_review_handoff(
            ReviewPort(cutoff_drift), dispatch_ref=dispatch(), request=request()
        )

    def decision_time_drift(command):
        return receipt_payload(command, decidedAt=(CUTOFF - timedelta(seconds=1)).isoformat())

    with pytest.raises(ValueError, match="precedes cutoff"):
        advance_review_handoff(
            ReviewPort(decision_time_drift), dispatch_ref=dispatch(), request=request()
        )

    def side_effect(command):
        value = receipt_payload(command)
        value["sideEffects"]["providerInvocationCount"] = 1
        return value

    with pytest.raises(ValueError, match="side-effect boundary drifted"):
        advance_review_handoff(
            ReviewPort(side_effect), dispatch_ref=dispatch(), request=request()
        )


def test_extra_authority_fields_are_rejected() -> None:
    def extra_receipt(command):
        return receipt_payload(command, orgId="org-org")

    with pytest.raises(ValueError, match="Receipt fields drifted"):
        advance_review_handoff(
            ReviewPort(extra_receipt), dispatch_ref=dispatch(), request=request()
        )

    def extra_ref(command):
        issue = dict(command["reviewIssueRef"])
        issue["tenant"] = "org-org"
        return receipt_payload(command, reviewIssueRef=issue)

    with pytest.raises(ValueError, match="reference fields drifted"):
        advance_review_handoff(ReviewPort(extra_ref), dispatch_ref=dispatch(), request=request())


def test_n5_n6_package_files_have_no_platform_or_side_effect_imports() -> None:
    package = ROOT / "bundles/solutions/ecommerce-growth/backend/ecommerce_growth"
    for name in (
        "ecommerce_business_investigation_review_command.py",
        "ecommerce_business_investigation_handoff.py",
        "ecommerce_content_campaign_workflow_contracts.py",
        "ecommerce_content_campaign_workflow.py",
    ):
        source = (package / name).read_text(encoding="utf-8")
        for forbidden in (
            "aos_api",
            "psycopg",
            "requests",
            "httpx",
            "subprocess",
            "socket",
        ):
            assert forbidden not in source
