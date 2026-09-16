import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import aos_api.ecommerce_baseline_assessment_worker as module
from aos_api.automation_occurrence_store import ClaimedOccurrence
from aos_api.ecommerce_baseline_assessment_discovery import BaselineAssessmentNotApplicable
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 9, 17, 8, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
INSTALLATION = UUID("11111111-1111-4111-8111-111111111111")
GENERATION = UUID("22222222-2222-4222-8222-222222222222")


def claimed():
    return ClaimedOccurrence(
        UUID("33333333-3333-4333-8333-333333333333"), "baseline-once", 1,
        "ecommerce_growth_schedule_trigger", INSTALLATION, GENERATION, 3,
        "worker", NOW + timedelta(minutes=5),
        UUID("44444444-4444-4444-8444-444444444444"), "automation-occurrence:333",
    )


class Occurrences:
    def __init__(self):
        self.claim = claimed()
        self.accepted = self.skipped = self.held = None
    def reconcile_expired_claims(self, *_args, **_kwargs): return 0
    def read_needs_attention_target(self, *_args, **_kwargs): return None
    def reconcile_target_receipt(self, *_args, **_kwargs): raise AssertionError("not expected")
    def claim_next(self, *_args, **_kwargs): return self.claim
    def record_not_applicable(self, *_args, **kwargs): self.skipped = kwargs
    def mark_needs_attention(self, *_args, **kwargs): self.held = kwargs
    def record_target_receipt(self, *_args, **kwargs): self.accepted = kwargs


def worker():
    factory = object.__new__(PipelineControlServiceFactory)
    directory = object.__new__(LivePreparedJobDirectory)
    result = module.BaselineAssessmentWorker(factory, directory)
    result._occurrences = Occurrences()
    result._now = lambda _scope: NOW
    return result


def test_existing_plan_settles_not_applicable_without_analysis(monkeypatch):
    subject = worker()
    subject._route = lambda *_: (_ for _ in ()).throw(
        BaselineAssessmentNotApplicable("CURRENT_GROWTH_PLAN_EXISTS")
    )
    outcome = asyncio.run(subject._dispatch_one((SCOPE, INSTALLATION, GENERATION), NOW))
    assert outcome == "notApplicable"
    assert subject._occurrences.skipped["receipt_ref"]["resourceType"] == "AutomationDisposition"
    assert subject._occurrences.held is None


def test_current_route_builds_schedule_analysis_and_records_receipt(monkeypatch):
    subject = worker()
    route = SimpleNamespace(
        source_actor="source-reader", source_run_id="source-run-1",
        source_control_ref=object(),
    )
    subject._route = lambda *_: route
    subject._markings = lambda *_: ("internal",)

    class Service:
        async def handle_with_data(self, value):
            assert value is subject._occurrences.claim
            return {"resourceType": "BusinessInvestigationRun", "resourceId": "run-1",
                    "revision": 1, "contentHash": "sha256:" + "a" * 64}

    captured = {}
    monkeypatch.setattr(PipelineControlServiceFactory, "build_scheduled_analysis",
                        lambda *args, **kwargs: captured.update(kwargs) or Service())

    @contextmanager
    def store():
        yield object()

    monkeypatch.setattr(module, "_authoritative_store", store)
    outcome = asyncio.run(subject._dispatch_one((SCOPE, INSTALLATION, GENERATION), NOW))
    assert outcome == "accepted"
    assert captured["run_id"] == "source-run-1"
    assert captured["markings"] == ("internal",)
    assert subject._occurrences.accepted["receipt_ref"]["resourceId"] == "run-1"


def test_unknown_analysis_result_is_held_and_never_marked_accepted(monkeypatch):
    subject = worker()
    subject._route = lambda *_: SimpleNamespace(
        source_actor="source-reader", source_run_id="source-run-1", source_control_ref=object())
    subject._markings = lambda *_: ("internal",)
    class Unknown:
        async def handle_with_data(self, _claim): raise RuntimeError("unknown")
    monkeypatch.setattr(PipelineControlServiceFactory, "build_scheduled_analysis",
                        lambda *_args, **_kwargs: Unknown())

    @contextmanager
    def store(): yield object()
    monkeypatch.setattr(module, "_authoritative_store", store)
    outcome = asyncio.run(subject._dispatch_one((SCOPE, INSTALLATION, GENERATION), NOW))
    assert outcome == "failed"
    assert subject._occurrences.held is not None
    assert subject._occurrences.accepted is None


def test_unknown_with_durable_host_receipt_reconciles_without_redispatch(monkeypatch):
    import aos_api.ecommerce_growth_runtime_adapters as adapters
    subject = worker()
    occurrence = subject._occurrences.claim.occurrence_id
    subject._occurrences.read_needs_attention_target = lambda *_args, **_kwargs: {
        "occurrence_id": occurrence, "target_idempotency_key": "automation-occurrence:333"
    }
    reconciled = {}
    subject._occurrences.reconcile_target_receipt = lambda *_args, **kwargs: reconciled.update(kwargs)

    @contextmanager
    def connect(_scope): yield object()
    monkeypatch.setattr(module, "connect_serializable", connect)
    monkeypatch.setattr(adapters, "_HostAnalysisReceiptStore", lambda *_: SimpleNamespace(read=lambda _key: {
        "phase": "PREPARING", "completed": False,
        "occurrenceRef": {"resourceId": str(occurrence)},
        "receiptRef": {"resourceType": "BusinessInvestigationRun", "resourceId": "run-1",
                       "revision": 1, "contentHash": "sha256:" + "a" * 64},
    }))
    outcome = asyncio.run(subject._dispatch_one((SCOPE, INSTALLATION, GENERATION), NOW))
    assert outcome == "reconciled"
    assert reconciled["occurrence_id"] == occurrence
