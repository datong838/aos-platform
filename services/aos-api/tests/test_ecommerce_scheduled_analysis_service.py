from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import aos_api.ecommerce_scheduled_analysis_service as module
from aos_api.automation_occurrence_store import ClaimedOccurrence
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_baseline_assessment_discovery import BaselineAssessmentDiscovery
from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 9, 17, 8, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
INSTALLATION = UUID("11111111-1111-4111-8111-111111111111")
GENERATION = UUID("22222222-2222-4222-8222-222222222222")
OCCURRENCE = UUID("33333333-3333-4333-8333-333333333333")
GROUP = UUID("44444444-4444-4444-8444-444444444444")


class Result:
    def __init__(self, row): self.row = row
    def fetchone(self): return self.row


class Connection:
    def execute(self, query, _params=()):
        if "clock_timestamp" in query: return Result({"now": NOW})
        if "extension_operation_dispatch_binding" in query:
            return Result({
                "handler_kind": "extension", "revision": 8,
                "installation_id": INSTALLATION, "generation": GENERATION,
                "execution_epoch": 3, "cutover_group_id": UUID("55555555-5555-4555-8555-555555555555"),
                "cutover_group_revision": 6,
            })
        if "aip_action_approval_event" in query:
            return Result({"expires_at": NOW + timedelta(hours=2)})
        raise AssertionError(query)


def ref(kind, identity, digest):
    return InvestigationExactRef(
        resourceType=kind, resourceId=identity, revision=1,
        contentHash="sha256:" + digest * 64,
    )


def test_schedule_phase_builds_non_event_current_context(monkeypatch):
    claim = ClaimedOccurrence(
        OCCURRENCE, "baseline-once", 1, "ecommerce_growth_schedule_trigger",
        INSTALLATION, GENERATION, 3, "baseline-worker", NOW + timedelta(minutes=5),
        UUID("66666666-6666-4666-8666-666666666666"), "automation-occurrence:" + str(OCCURRENCE),
    )
    control = SimpleNamespace(
        approval_ref=ref("ActionApprovalEvent", "approval-1", "a"),
        policy_ref=ref("SchedulePolicyRevision", "baseline-once", "b"),
        model_dump=lambda **_: {
            "receiptRef": ref("SchedulePolicyControlReceipt", "control-1", "c").model_dump(mode="json", by_alias=True),
            "approvalRef": ref("ActionApprovalEvent", "approval-1", "a").model_dump(mode="json", by_alias=True),
        },
    )
    case_payload = {
        "caseId": "case-baseline", "revision": 2, "contentHash": "sha256:" + "d" * 64,
        "analysisType": "initial_store_analysis",
        "investigationProfileRef": ref("InvestigationProfileRevision", "profile-1", "e").model_dump(mode="json", by_alias=True),
    }
    route = SimpleNamespace(
        installation_id=INSTALLATION, generation=GENERATION, execution_epoch=3,
        source_group_id=GROUP, source_run_id="source-run-1", source_actor="source-reader",
        cutoff_at=NOW - timedelta(minutes=10), source_control_ref=PipelineExactRef(
            resourceType="PipelineRuntimeControlRevision", resourceId="pipeline-control-1",
            revision=1, contentHash="sha256:" + "f" * 64),
        source_selection_ref=PipelineExactRef(
            resourceType="SourceSelectionRevision", resourceId="source-selection-1",
            revision=1, contentHash="sha256:" + "1" * 64),
        schedule_control=control, max_source_age_seconds=86400,
        case=SimpleNamespace(model_dump=lambda **_: case_payload),
        policy=SimpleNamespace(revision=1, created_at=NOW - timedelta(minutes=20),
            model_dump=lambda **_: {"schedulePolicyId": "baseline-once", "revision": 1}),
    )
    monkeypatch.setattr(BaselineAssessmentDiscovery, "read", lambda *_args, **_kwargs: route)
    monkeypatch.setattr(module.LockedEcommerceGrowthHostPort, "_lock_and_revalidate", lambda *_: None)
    monkeypatch.setattr(module.AutomationOccurrenceStore, "_lock_claim", lambda *_: {})
    monkeypatch.setattr(module, "_occurrence_payload", lambda *_: {
        "occurrenceId": str(OCCURRENCE), "policyId": "baseline-once", "policyRevision": 1,
        "policyHash": "sha256:" + "b" * 64, "operationId": "ecommerce_growth_schedule_trigger",
        "installationId": str(INSTALLATION), "generation": str(GENERATION), "executionEpoch": 3,
        "scheduledAt": NOW.isoformat(), "localSlot": "2026-09-17T16:00+0800",
        "triggerSource": "schedule", "sourceEventId": None, "status": "running",
        "deadline": (NOW + timedelta(hours=24)).isoformat(),
    })
    journal = SimpleNamespace(_ref=route.source_control_ref, _run_id=route.source_run_id)
    source = SimpleNamespace(
        actor="source-reader", reader=SimpleNamespace(_journal=journal),
        invoker=SimpleNamespace(read_current_in_transaction=lambda _tx: {"packageId": "domain.ecommerce.core"}),
    )
    growth = {"installationRef": {"installationId": str(INSTALLATION)}, "generation": str(GENERATION)}
    analysis = object.__new__(ProductEventAnalysisService)
    analysis.scope = SCOPE
    analysis.source = source
    analysis.invoker = SimpleNamespace(read_current_in_transaction=lambda _tx: growth)
    analysis._source_group = lambda _conn: SimpleNamespace(
        group_id=str(GROUP), actor="source-reader", read_completed_at=route.cutoff_at,
        read_started_at=route.cutoff_at - timedelta(seconds=1), manifest_hash="sha256:" + "2" * 64,
        bindings=((route.source_control_ref, route.source_run_id),),
    )
    observed = {}
    result = module.ScheduledBaselinePhaseOwner().run_current(
        analysis, Connection(), claim,
        lambda snapshot, request, dispatch: observed.update(snapshot=snapshot, request=request, dispatch=dispatch) or "ok",
    )
    assert result == "ok"
    assert observed["snapshot"]["occurrence"]["triggerSource"] == "schedule"
    assert observed["snapshot"]["source"]["events"] == []
    assert observed["snapshot"]["origin"]["sourceGroupId"] == str(GROUP)
    assert observed["request"]["caseRef"]["resourceId"] == "case-baseline"
    assert observed["dispatch"].operation_id == "ecommerce_growth_analysis_advance"
