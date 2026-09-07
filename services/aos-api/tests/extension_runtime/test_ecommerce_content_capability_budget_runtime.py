"""AR2-6 isolated exact capability, budget, Artifact and review contracts."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[4]
SDK_ROOT = ROOT / "packages/aos-extension-sdk/python"
GROWTH_ROOT = ROOT / "bundles/solutions/ecommerce-growth/backend"
for dependency in (SDK_ROOT, GROWTH_ROOT):
    if str(dependency) not in sys.path:
        sys.path.insert(0, str(dependency))

from aos_extension_sdk import DispatchRef
from ecommerce_growth.content_artifact_review import (
    CONTENT_REVIEW_OPERATION,
    ContentReviewRequest,
    ReadableContentArtifact,
    review_content_artifact,
)
from ecommerce_growth.content_capability_runtime import (
    CONTENT_GENERATE_OPERATION,
    ContentCapabilityRequest,
    execute_content_capability,
)
from ecommerce_growth.ecommerce_business_investigation_application import (
    EcommerceGrowthApplication,
)
from ecommerce_growth.ecommerce_business_investigation_review_command import exact_ref_payload
from ecommerce_growth.sdk_ports import ExactRef


HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"


def ref(kind: str, identity: str, *, revision: int = 1, hash_value: str = HASH_A):
    return ExactRef(kind, identity, revision, hash_value)


def dispatch(*, operation=CONTENT_GENERATE_OPERATION, epoch=17, org="org-org"):
    return DispatchRef.from_payload(
        {
            "orgId": org,
            "projectId": "dev-project",
            "operationId": operation,
            "handlerKind": "extension",
            "dispatchRevision": 20,
            "installationId": "11111111-1111-4111-8111-111111111111",
            "generation": "22222222-2222-4222-8222-222222222222",
            "executionEpoch": epoch,
            "cutoverGroupId": "33333333-3333-4333-8333-333333333333",
            "cutoverGroupRevision": 8,
        }
    )


def source_artifacts():
    return tuple(ref("ArtifactRevision", f"source-{index}") for index in range(1, 5))


def capability_request(*, key="capability-1", **overrides):
    values = {
        "handoff_ref": ref("HandoffReceipt", "handoff-1"),
        "task_ref": ref("Task", "task-1"),
        "brief_ref": ref("TaskBriefRevision", "brief-1"),
        "growth_plan_ref": ref("GrowthPlanRevision", "growth-plan-1"),
        "source_artifact_refs": source_artifacts(),
        "fact_source_refs": (
            ref("DataFulfillmentReceipt", "niushop-fulfillment-1"),
            ref("EvidenceBundleRevision", "evidence-1"),
        ),
        "agent_instance_ref": ref("AgentInstanceRevision", "content-agent-1"),
        "responsibility_plan_ref": ref(
            "ResponsibilityPlanRevision", "responsibility-1"
        ),
        "capability_ref": ref("CapabilityRevision", "text-generation-1"),
        "model_route_ref": ref("ModelRouteRevision", "route-1"),
        "budget_ref": ref("BudgetRevision", "budget-1"),
        "pricing_ref": ref("ProviderPriceRevision", "price-1"),
        "approval_ref": ref("ApprovalDecisionRevision", "approval-1"),
        "capacity_reservation_ref": ref("CapacityReservation", "capacity-1"),
        "currency": "CNY",
        "upper_bound_fen": 500,
        "max_input_tokens": 4_000,
        "max_output_tokens": 2_000,
        "idempotency_key": key,
    }
    values.update(overrides)
    return ContentCapabilityRequest(**values)


def artifact_payload(command):
    refs = command["authorityRefs"]
    return {
        "artifactRef": exact_ref_payload(ref("ArtifactRevision", "content-artifact-1")),
        "taskRef": refs["task"],
        "briefRef": refs["brief"],
        "growthPlanRef": refs["growth_plan"],
        "sourceArtifactRefs": command["sourceArtifactRefs"],
        "productNames": ["栖月汇玫瑰精粹面霜"],
        "channels": ["微信小店", "私域社群"],
        "factSourceRefs": command["factSourceRefs"],
        "body": "七夕会员专享：玫瑰精粹面霜库存充足，适合近九十天已购会员复购。",
        "constraintChecks": ["毛利率约束已核对", "库存约束已核对"],
    }


def capability_receipt(command, *, state="COMPLETED", replayed=False, **overrides):
    completed = state == "COMPLETED"
    failed = state == "FAILED_NO_EFFECT"
    value = {
        "receiptRef": exact_ref_payload(
            ref("CapabilityInvocationReceipt", "invocation-receipt-1")
        ),
        "requestHash": command["requestHash"],
        "state": state,
        "authorityRefs": command["authorityRefs"],
        "sourceArtifactRefs": command["sourceArtifactRefs"],
        "budgetReservationRef": exact_ref_payload(
            ref("BudgetReservationRevision", "budget-reservation-1")
        ),
        "budgetState": "SETTLED" if completed else "RELEASED" if failed else "UNKNOWN",
        "providerRequestReceiptRef": None
        if failed
        else exact_ref_payload(ref("ProviderRequestReceipt", "provider-request-1")),
        "providerReceiptRef": exact_ref_payload(ref("ProviderReceipt", "provider-1"))
        if completed
        else None,
        "usageReceiptRefs": [exact_ref_payload(ref("UsageReceipt", "usage-1"))]
        if completed
        else [],
        "artifact": artifact_payload(command) if completed else None,
        "currency": command["currency"],
        "upperBoundFen": command["upperBoundFen"],
        "actualFen": 360 if completed else None,
        "retryDirective": "NONE"
        if completed
        else "RETRYABLE_NO_EFFECT"
        if failed
        else "RECONCILE_ONLY",
        "replayed": replayed,
        "sideEffects": {
            "providerInvocationCount": 0 if failed else 1,
            "approvalCreatedCount": 0,
            "taskRunCreatedCount": 0,
            "externalPublicationCount": 0,
            "externalBusinessMutationCount": 0,
        },
    }
    value.update(overrides)
    return value


class CapabilityPort:
    def __init__(self, responder=capability_receipt, *, epoch=17, org="org-org"):
        self.responder = responder
        self.epoch = epoch
        self.org = org
        self.commands = []
        self.receipts = {}
        self.provider_calls = 0

    def commit(self, *, dispatch_ref, command):
        if dispatch_ref.execution_epoch != self.epoch:
            raise PermissionError("stale execution epoch")
        if (dispatch_ref.org_id, dispatch_ref.project_id) != (self.org, "dev-project"):
            raise PermissionError("tenant isolation")
        assert not {"tenant", "orgId", "projectId", "secret", "providerUrl"}.intersection(
            command
        )
        key = command["idempotencyKey"]
        previous = self.receipts.get(key)
        if previous is not None:
            if previous[0] != command["requestHash"]:
                raise ValueError("idempotency content drift")
            replay = dict(previous[1])
            replay["replayed"] = True
            return replay
        if command["upperBoundFen"] > 1_000:
            raise PermissionError("budget bucket insufficient")
        self.commands.append(command)
        value = self.responder(command)
        self.provider_calls += value["sideEffects"]["providerInvocationCount"]
        self.receipts[key] = (command["requestHash"], value)
        return value


class NoWritePort:
    def commit(self, **_kwargs):
        raise AssertionError("unrelated write port must not receive capability commands")


def test_completed_capability_is_exact_readable_budgeted_and_replayed() -> None:
    port = CapabilityPort()
    item = capability_request()
    first = execute_content_capability(port, dispatch_ref=dispatch(), request=item)
    replay = execute_content_capability(port, dispatch_ref=dispatch(), request=item)
    assert first.state == "COMPLETED" and first.actual_fen == 360
    assert first.artifact.product_names == ("栖月汇玫瑰精粹面霜",)
    assert replay.replayed is True
    assert len(port.commands) == 1 and port.provider_calls == 1


def test_application_routes_capability_without_legacy_write_port() -> None:
    port = CapabilityPort()
    app = EcommerceGrowthApplication(NoWritePort(), capability_port=port)
    result = app.execute_content(dispatch_ref=dispatch(), request=capability_request())
    assert result.artifact.artifact_ref.resource_type == "ArtifactRevision"


@pytest.mark.parametrize(
    ("state", "budget_state", "directive", "calls"),
    (
        ("FAILED_NO_EFFECT", "RELEASED", "RETRYABLE_NO_EFFECT", 0),
        ("UNKNOWN", "UNKNOWN", "RECONCILE_ONLY", 1),
    ),
)
def test_noncompleted_states_preserve_exact_budget_semantics(
    state, budget_state, directive, calls
) -> None:
    port = CapabilityPort(lambda command: capability_receipt(command, state=state))
    result = execute_content_capability(port, dispatch_ref=dispatch(), request=capability_request())
    assert result.budget_state == budget_state and result.retry_directive == directive
    assert result.artifact is None and port.provider_calls == calls


def test_unknown_replay_never_invokes_provider_again_or_releases_hold() -> None:
    port = CapabilityPort(lambda command: capability_receipt(command, state="UNKNOWN"))
    item = capability_request()
    first = execute_content_capability(port, dispatch_ref=dispatch(), request=item)
    replay = execute_content_capability(port, dispatch_ref=dispatch(), request=item)
    assert first.budget_state == replay.budget_state == "UNKNOWN"
    assert replay.replayed is True and port.provider_calls == 1


def test_budget_authority_currency_and_input_bounds_fail_closed() -> None:
    with pytest.raises(ValueError, match="BudgetRevision"):
        capability_request(budget_ref=ref("BudgetPolicyRevision", "budget-1"))
    with pytest.raises(ValueError, match="only supports CNY"):
        capability_request(currency="USD")
    with pytest.raises(ValueError, match="positive bounded risk amount"):
        capability_request(upper_bound_fen=0)
    with pytest.raises(ValueError, match="token bounds"):
        capability_request(max_output_tokens=0)
    with pytest.raises(PermissionError, match="budget bucket insufficient"):
        execute_content_capability(
            CapabilityPort(),
            dispatch_ref=dispatch(),
            request=capability_request(upper_bound_fen=1_001),
        )


def test_same_key_drift_cross_tenant_epoch_and_operation_are_rejected() -> None:
    port = CapabilityPort()
    execute_content_capability(port, dispatch_ref=dispatch(), request=capability_request())
    with pytest.raises(ValueError, match="idempotency content drift"):
        execute_content_capability(
            port,
            dispatch_ref=dispatch(),
            request=capability_request(max_output_tokens=2_001),
        )
    with pytest.raises(PermissionError, match="tenant isolation"):
        execute_content_capability(
            CapabilityPort(),
            dispatch_ref=dispatch(org="dev-org"),
            request=capability_request(),
        )
    with pytest.raises(PermissionError, match="stale execution epoch"):
        execute_content_capability(
            CapabilityPort(),
            dispatch_ref=dispatch(epoch=16),
            request=capability_request(),
        )
    with pytest.raises(PermissionError, match="does not authorize"):
        execute_content_capability(
            CapabilityPort(),
            dispatch_ref=dispatch(operation=CONTENT_REVIEW_OPERATION),
            request=capability_request(),
        )


def test_receipt_over_budget_lineage_and_state_shapes_fail_closed() -> None:
    def over_budget(command):
        return capability_receipt(command, actualFen=command["upperBoundFen"] + 1)

    with pytest.raises(ValueError, match="incomplete or over budget"):
        execute_content_capability(
            CapabilityPort(over_budget), dispatch_ref=dispatch(), request=capability_request()
        )

    def lineage_drift(command):
        refs = dict(command["authorityRefs"])
        refs["pricing"] = exact_ref_payload(ref("ProviderPriceRevision", "other-price"))
        return capability_receipt(command, authorityRefs=refs)

    with pytest.raises(ValueError, match="exact request lineage drifted"):
        execute_content_capability(
            CapabilityPort(lineage_drift),
            dispatch_ref=dispatch(),
            request=capability_request(),
        )

    def unknown_released(command):
        return capability_receipt(command, state="UNKNOWN", budgetState="RELEASED")

    with pytest.raises(ValueError, match="must retain budget and reconcile"):
        execute_content_capability(
            CapabilityPort(unknown_released),
            dispatch_ref=dispatch(),
            request=capability_request(),
        )


def test_empty_or_technical_artifact_content_is_rejected() -> None:
    def empty_body(command):
        artifact = artifact_payload(command)
        artifact["body"] = ""
        return capability_receipt(command, artifact=artifact)

    with pytest.raises(ValueError, match="body must be non-empty"):
        execute_content_capability(
            CapabilityPort(empty_body), dispatch_ref=dispatch(), request=capability_request()
        )

    def technical_body(command):
        artifact = artifact_payload(command)
        artifact["constraintChecks"] = ["执行数据库迁移W7"]
        return capability_receipt(command, artifact=artifact)

    with pytest.raises(ValueError, match="technical text"):
        execute_content_capability(
            CapabilityPort(technical_body),
            dispatch_ref=dispatch(),
            request=capability_request(),
        )


@pytest.mark.parametrize(
    "polluted",
    (
        "业务内容来自 /services/runtime/router.py 请直接采用",
        "业务内容绑定 ArtifactRevision=source-1 请直接采用",
        f"业务内容摘要 sha256:{'c' * 64} 请直接采用",
        "业务内容绑定安装 11111111-1111-4111-8111-111111111111 请直接采用",
    ),
)
def test_technical_paths_exact_types_hashes_and_uuids_are_rejected(polluted) -> None:
    def polluted_body(command):
        artifact = artifact_payload(command)
        artifact["body"] = polluted
        return capability_receipt(command, artifact=artifact)

    with pytest.raises(ValueError, match="technical text"):
        execute_content_capability(
            CapabilityPort(polluted_body),
            dispatch_ref=dispatch(),
            request=capability_request(),
        )


def test_unbound_fact_source_and_legacy_fulfillment_type_fail_closed() -> None:
    def unbound_source(command):
        artifact = artifact_payload(command)
        artifact["factSourceRefs"] = [
            exact_ref_payload(ref("DatasetRevision", "unbound-source-999"))
        ]
        return capability_receipt(command, artifact=artifact)

    with pytest.raises(ValueError, match="incomplete or over budget"):
        execute_content_capability(
            CapabilityPort(unbound_source),
            dispatch_ref=dispatch(),
            request=capability_request(),
        )
    with pytest.raises(ValueError, match="fact-source closure"):
        capability_request(
            fact_source_refs=(ref("FulfillmentReceipt", "legacy-fulfillment"),)
        )


def readable_artifact():
    return ReadableContentArtifact.from_payload(
        artifact_payload(capability_request().command_payload())
    )


def review_request(*, decision="ACCEPT", key="content-review-1"):
    return ContentReviewRequest(
        artifact=readable_artifact(),
        review_issue_ref=ref("ReviewIssueRevision", "content-review-issue-1"),
        reviewer_authority_ref=ref(
            "ReviewerAuthorityRevision", "content-reviewer-1"
        ),
        decision=decision,
        return_stage=None if decision == "ACCEPT" else "content_generation",
        idempotency_key=key,
    )


def review_receipt(command, *, replayed=False, **overrides):
    value = {
        "receiptRef": exact_ref_payload(ref("ContentReviewReceipt", "content-review-1")),
        "requestHash": command["requestHash"],
        "decision": command["decision"],
        "artifactRef": command["artifactRef"],
        "taskRef": command["taskRef"],
        "briefRef": command["briefRef"],
        "reviewIssueRef": command["reviewIssueRef"],
        "reviewerAuthorityRef": command["reviewerAuthorityRef"],
        "returnStage": command["returnStage"],
        "replayed": replayed,
        "sideEffects": {
            "externalPublicationCount": 0,
            "externalBusinessMutationCount": 0,
        },
    }
    value.update(overrides)
    return value


class ContentReviewPort:
    def __init__(self, responder=review_receipt):
        self.responder = responder
        self.receipts = {}
        self.commands = []

    def commit(self, *, dispatch_ref, command):
        if dispatch_ref.execution_epoch != 17:
            raise PermissionError("stale execution epoch")
        if (dispatch_ref.org_id, dispatch_ref.project_id) != ("org-org", "dev-project"):
            raise PermissionError("tenant isolation")
        key = command["idempotencyKey"]
        previous = self.receipts.get(key)
        if previous is not None:
            if previous[0] != command["requestHash"]:
                raise ValueError("idempotency content drift")
            replay = dict(previous[1])
            replay["replayed"] = True
            return replay
        self.commands.append(command)
        value = self.responder(command)
        self.receipts[key] = (command["requestHash"], value)
        return value


@pytest.mark.parametrize("decision", ("ACCEPT", "RETURN"))
def test_content_review_is_exact_replayable_and_never_publishes(decision) -> None:
    port = ContentReviewPort()
    item = review_request(decision=decision)
    first = review_content_artifact(
        port,
        dispatch_ref=dispatch(operation=CONTENT_REVIEW_OPERATION),
        request=item,
    )
    replay = review_content_artifact(
        port,
        dispatch_ref=dispatch(operation=CONTENT_REVIEW_OPERATION),
        request=item,
    )
    assert first.artifact_ref == item.artifact.artifact_ref
    assert replay.replayed is True and len(port.commands) == 1


def test_request_more_review_drift_and_external_publish_fail_closed() -> None:
    with pytest.raises(ValueError, match="no canonical content-review authority"):
        review_request(decision="REQUEST_MORE")

    def artifact_drift(command):
        return review_receipt(
            command,
            artifactRef=exact_ref_payload(ref("ArtifactRevision", "other-artifact")),
        )

    with pytest.raises(ValueError, match="exact lineage drifted"):
        review_content_artifact(
            ContentReviewPort(artifact_drift),
            dispatch_ref=dispatch(operation=CONTENT_REVIEW_OPERATION),
            request=review_request(),
        )

    def publishes(command):
        value = review_receipt(command)
        value["sideEffects"]["externalPublicationCount"] = 1
        return value

    with pytest.raises(ValueError, match="external side-effect boundary"):
        review_content_artifact(
            ContentReviewPort(publishes),
            dispatch_ref=dispatch(operation=CONTENT_REVIEW_OPERATION),
            request=review_request(),
        )


def test_n7_package_files_have_no_platform_network_secret_or_provider_implementation() -> None:
    package = ROOT / "bundles/solutions/ecommerce-growth/backend/ecommerce_growth"
    for name in ("content_capability_runtime.py", "content_artifact_review.py"):
        source = (package / name).read_text(encoding="utf-8")
        for forbidden in (
            "aos_api",
            "psycopg",
            "requests",
            "httpx",
            "subprocess",
            "socket",
            "secretRef",
            "providerUrl",
        ):
            assert forbidden not in source
