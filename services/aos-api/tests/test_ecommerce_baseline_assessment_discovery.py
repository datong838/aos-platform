from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

import aos_api.ecommerce_baseline_assessment_discovery as module
from aos_api.automation_occurrence_store import ClaimedOccurrence
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationAnalysisType,
    BusinessInvestigationCaseLifecycle,
    BusinessInvestigationCaseRevision,
)
from aos_api.ecommerce_business_investigation_schedule import (
    BusinessInvestigationScheduleCadence,
    BusinessInvestigationScheduleKind,
    BusinessInvestigationSchedulePolicyRevision,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
INSTALLATION = UUID("11111111-1111-4111-8111-111111111111")
GENERATION = UUID("22222222-2222-4222-8222-222222222222")
OCCURRENCE = UUID("33333333-3333-4333-8333-333333333333")
ATTEMPT = UUID("44444444-4444-4444-8444-444444444444")
GROUP = UUID("55555555-5555-4555-8555-555555555555")
NOW = datetime(2026, 9, 17, 8, tzinfo=UTC)


def ref(kind, identifier, revision=1, digest="a"):
    return InvestigationExactRef(
        resourceType=kind, resourceId=identifier, revision=revision,
        contentHash="sha256:" + digest * 64,
    )


def authorities():
    policy_ref = ref("SchedulePolicyRevision", "baseline-once", digest="b")
    case = BusinessInvestigationCaseRevision.model_construct(
        case_id="case-baseline-once", revision=2, version=2,
        lifecycle=BusinessInvestigationCaseLifecycle.ACTIVE,
        analysis_type=BusinessInvestigationAnalysisType.INITIAL_STORE_ANALYSIS,
        schedule_policy_ref=policy_ref,
    )
    policy = BusinessInvestigationSchedulePolicyRevision.model_construct(
        schedule_policy_id="baseline-once", revision=1, version=1,
        content_hash="sha256:" + "b" * 64,
        case_ref=ref("BusinessInvestigationCaseRevision", case.case_id, revision=2),
        analysis_type=BusinessInvestigationAnalysisType.INITIAL_STORE_ANALYSIS,
        policy_kind=BusinessInvestigationScheduleKind.INITIAL_CHECKUP,
        cadence=BusinessInvestigationScheduleCadence.ONCE,
        enabled=True,
    )
    return case, policy


def claim():
    return ClaimedOccurrence(
        OCCURRENCE, "baseline-once", 1, "ecommerce_growth_schedule_trigger",
        INSTALLATION, GENERATION, 3, "baseline-worker", NOW + timedelta(minutes=5),
        ATTEMPT, "automation-occurrence:" + str(OCCURRENCE),
    )


class Result:
    def __init__(self, *, one=None, many=()):
        self.one, self.many = one, list(many)

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class Connection:
    def __init__(self, *, active=(), plans=(), sources=None, dispatch=None):
        self.active, self.plans = active, plans
        self.dispatch = dispatch or {
            "handler_kind": "extension", "installation_id": INSTALLATION,
            "generation": GENERATION, "execution_epoch": 3, "operation_fence": False,
        }
        self.sources = sources if sources is not None else [{
            "group_id": GROUP, "read_completed_at": NOW - timedelta(minutes=5),
            "run_id": "source-run-1", "actor": "source-reader",
            "control_id": UUID("66666666-6666-4666-8666-666666666666"),
            "control_revision": 4, "control_hash": "sha256:" + "c" * 64,
        }]

    def execute(self, query, _params=()):
        if "run_active_slot" in query:
            return Result(many=self.active)
        if "growth_plan_head" in query:
            return Result(many=self.plans)
        if "operation_id='ecommerce_growth_analysis_advance'" in query:
            return Result(one=self.dispatch)
        if "pipeline_snapshot_group_input" in query:
            return Result(many=self.sources)
        raise AssertionError(query)


def install_authority_fakes(monkeypatch, *, occurrence=None):
    case, policy = authorities()

    class Cases:
        def __init__(self, _factory): pass
        def get(self, _scope, _case_id): return case

    class Policies:
        def __init__(self, _factory): pass
        def get(self, _scope, _policy_id): return policy

    monkeypatch.setattr(module, "BusinessInvestigationCaseStore", Cases)
    monkeypatch.setattr(module, "BusinessInvestigationScheduleStore", Policies)
    current = occurrence or {
        "trigger_source": "schedule", "source_event_id": None,
        "scheduled_at": NOW, "policy_id": policy.schedule_policy_id,
        "policy_revision": policy.revision, "policy_hash": policy.content_hash,
    }
    monkeypatch.setattr(
        HostTransaction, "lock_automation_claim", lambda *_args, **_kwargs: current,
    )
    return case, policy


def test_discovers_one_current_plan_empty_baseline(monkeypatch):
    case, policy = install_authority_fakes(monkeypatch)
    route = module.BaselineAssessmentDiscovery().read(
        HostTransaction(Connection()), SCOPE, claim(), observed_at=NOW,
    )
    assert route.case is case and route.policy is policy
    assert route.source_group_id == GROUP
    assert route.source_run_id == "source-run-1"
    assert route.source_control_ref.resource_id.startswith("pipeline-control-")
    assert route.installation_id == INSTALLATION and route.generation == GENERATION


@pytest.mark.parametrize(
    ("connection", "reason"),
    [
        (Connection(active=[{"run_id": "active"}]), "ACTIVE_BASELINE_RUN_EXISTS"),
        (Connection(plans=[{"lifecycle": "draft"}]), "CURRENT_GROWTH_PLAN_EXISTS"),
    ],
)
def test_existing_run_or_plan_is_not_applicable(monkeypatch, connection, reason):
    install_authority_fakes(monkeypatch)
    with pytest.raises(module.BaselineAssessmentNotApplicable, match=reason):
        module.BaselineAssessmentDiscovery().read(
            HostTransaction(connection), SCOPE, claim(), observed_at=NOW,
        )


def test_route_generation_and_stale_source_fail_closed(monkeypatch):
    install_authority_fakes(monkeypatch)
    changed = {"handler_kind": "extension", "installation_id": INSTALLATION,
               "generation": UUID("77777777-7777-4777-8777-777777777777"),
               "execution_epoch": 3, "operation_fence": False}
    with pytest.raises(module.BaselineAssessmentBlocked, match="analysis route"):
        module.BaselineAssessmentDiscovery().read(
            HostTransaction(Connection(dispatch=changed)), SCOPE, claim(), observed_at=NOW,
        )
    stale = [{
        "group_id": GROUP, "read_completed_at": NOW - timedelta(days=2),
        "run_id": "source-run-1", "actor": "source-reader",
        "control_id": UUID("66666666-6666-4666-8666-666666666666"),
        "control_revision": 4, "control_hash": "sha256:" + "c" * 64,
    }]
    with pytest.raises(module.BaselineAssessmentBlocked, match="stale"):
        module.BaselineAssessmentDiscovery().read(
            HostTransaction(Connection(sources=stale)), SCOPE, claim(), observed_at=NOW,
        )


def test_event_occurrence_never_enters_baseline_path(monkeypatch):
    install_authority_fakes(monkeypatch, occurrence={
        "trigger_source": "event", "source_event_id": "f" * 64,
        "scheduled_at": None, "policy_id": "baseline-once",
        "policy_revision": 1, "policy_hash": "sha256:" + "b" * 64,
    })
    with pytest.raises(module.BaselineAssessmentBlocked, match="schedule slot"):
        module.BaselineAssessmentDiscovery().read(
            HostTransaction(Connection()), SCOPE, claim(), observed_at=NOW,
        )
