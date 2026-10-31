from contextlib import contextmanager
from datetime import timedelta
import json
from types import SimpleNamespace

import pytest

import aos_api.aip_model_route_eval_atomic_finalizer as subject
from aos_api.aip_budget_reservation_contracts import BudgetExactRef, BudgetReservationState
from aos_api.aip_eval_contracts import (
    EvalCaseResultEvidence,
    EvalReportRevision,
    EvalRunAuthorityRecord,
    EvalRunEvent,
    EvalRunStatus,
)
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.aip_model_route_eval_finalization_proof import RouteEvalFinalizationProof
from aos_api.aip_model_route_eval_signatures import _manifest
from aos_api.tenant_scope import TenantScope
from test_model_route_eval_finalization_proof import NOW, finalization_fixture


class Rows:
    def __init__(self, one=None):
        self.one = one

    def fetchone(self):
        return self.one


class FakeConnection:
    autocommit = False

    def __init__(self, proof, *, deferred=False):
        self.proof = proof
        self.deferred = deferred
        self.log = []
        self.transaction_failed = False

    def execute(self, query, params=()):
        text = " ".join(str(query).split())
        if "SELECT current_database()" in text:
            return Rows({"database":"aos", "login":"aos_login", "role":"aos_runtime",
                "isolation":"serializable", "readonly":"off", "org_id":"org-org",
                "project_id":"dev-project", "evaluated_at":NOW})
        if "FROM public.aip_budget_reservation" in text:
            item = next(item for item in self.proof.calls if item.reservation_id == params[-1])
            return Rows({"reservation_id":item.reservation_id, "state":"submitted",
                "pricing_ref":{"resourceType":"ModelPriceSnapshotRevision",
                    "resourceId":"price", "revision":1,
                    "contentHash":"sha256:" + "1" * 64},
                "invocation_id":str(item.reservation_id), "upper_bound_minor":3})
        if "FROM public.aip_model_price_snapshot_revision" in text:
            payload = {"tokenUnit":1000, "inputTokenPrice":"0.1",
                "outputTokenPrice":"0.1"}
            if self.deferred:
                payload["developmentCostAuthorization"] = {"mode":"deferred"}
            return Rows({"payload":payload})
        if "SET LOCAL ROLE" in text:
            self.log.append("role")
            return Rows()
        raise AssertionError("unexpected SQL: " + text)

    @contextmanager
    def transaction(self):
        self.log.append("transaction")
        try:
            yield
        except Exception:
            self.transaction_failed = True
            raise

    def commit(self):
        raise AssertionError("finalizer cannot commit")

    rollback = commit


class FakeProofStore:
    schema = "public"

    def __init__(self, journal, log, *, fail=False):
        self.journal = journal
        self.log = log
        self.fail = fail

    def persist(self, conn, scope, proof, **kwargs):
        self.log.append("sidecar")
        if self.fail:
            raise RuntimeError("late sidecar failure")
        return proof


def fixture():
    proof, manifest, target, judge, journal = finalization_fixture()
    run = EvalRunAuthorityRecord.model_validate(_manifest(manifest)["context"]["run"])
    claim = judge.envelope.claim
    result = EvalCaseResultEvidence(caseId=claim.case_id, passed=claim.passed,
        actualHash=claim.target_output_hash, expectedHash=claim.expected_hash,
        detailCode=claim.detail_code, durationMs=1)
    report = EvalReportRevision(tenant=run.tenant, reportId="report", revision=1,
        contentHash="0" * 64, runId=run.run_id, suiteRef=run.suite_ref,
        evalContractRef=run.eval_contract_ref,
        subjectArtifactRef=run.subject_artifact_ref,
        stageAttemptRef=run.stage_attempt_ref,
        gatePolicyRef=run.gate_policy_ref,
        evidenceCutoffAt=run.evidence_cutoff_at,
        target=run.target, dataset=run.dataset, judge=run.judge, results=[result],
        passed=int(result.passed), failed=int(not result.passed), total=1,
        passRate=float(result.passed), gatePassed=result.passed,
        createdAt=NOW + timedelta(seconds=2))
    report = report.model_copy(update={"content_hash":compute_eval_report_hash(report)})
    event = EvalRunEvent(tenant=run.tenant, eventId="route-succeeded", runId=run.run_id,
        sequence=run.version + 1, eventType="run.succeeded",
        fromStatus=EvalRunStatus.RUNNING, toStatus=EvalRunStatus.SUCCEEDED,
        payloadHash=report.content_hash, actor="unit-test",
        createdAt=NOW + timedelta(seconds=2))
    proof = RouteEvalFinalizationProof.model_validate(proof.model_dump(
        mode="json", by_alias=True) | {"reportHash":report.content_hash,
            "reportId":report.report_id, "reportRevision":report.revision,
            "runId":report.run_id})
    return proof, manifest, (target, judge), journal, report, event, run.version


def install_fakes(monkeypatch, proof, log, *, settlement_drift=False):
    def record(self, conn, scope, item, evidence, reservation):
        log.append("usage-" + item.purpose)
        return item.result_hash, item.usage_receipt_refs

    class Budget:
        def __init__(self, *args, **kwargs):
            pass

        def _actual_from_usage(self, conn, scope, reservation, refs):
            return next(item.actual_minor for item in proof.calls
                if item.reservation_id == reservation["reservation_id"])

        def settle(self, scope, reservation_id, **kwargs):
            item = next(item for item in proof.calls if item.reservation_id == reservation_id)
            log.append("settle-" + item.purpose)
            return SimpleNamespace(state=BudgetReservationState.SETTLED,
                reservation_ref=BudgetExactRef(
                    resourceType="BudgetReservationRevision",
                    resourceId=str(item.reservation_id),
                    revision=item.budget_revision + int(settlement_drift),
                    contentHash="sha256:" + "f" * 64,
                ),
                actual_minor=item.actual_minor, usage_receipt_refs=item.usage_receipt_refs)

    class Authority:
        def _transition_eval_run_with_connection(self, *args, **kwargs):
            log.append("run")

    monkeypatch.setattr(subject.RouteEvalUsageRecorder, "record", record)
    monkeypatch.setattr(subject, "_require_native_connection", lambda conn: None)
    monkeypatch.setattr(subject, "AipBudgetReservationStore", Budget)
    monkeypatch.setattr(subject, "AipEvalAuthorityStore", Authority)
    monkeypatch.setattr(subject, "_persist_eval_report_revision_with_connection",
        lambda conn, report: log.append("report"))


def finish(conn, store, values):
    proof, manifest, presented, _, report, event, version = values
    return subject.finish_route_eval_with_connection(conn, expected_database="aos",
        scope=TenantScope("org-org", "dev-project"), proof=proof,
        manifest_bytes=manifest, presented_cases=presented,
        checked_at=NOW + timedelta(seconds=2), revoked_identity_ids=frozenset(),
        report=report, event=event, expected_run_version=version, proof_store=store)


def test_atomic_route_finalizer_preserves_exact_order_without_owning_commit(monkeypatch):
    values = fixture(); proof, _, _, journal, *_ = values; log = []
    install_fakes(monkeypatch, proof, log)
    conn = FakeConnection(proof); store = FakeProofStore(journal, log)
    assert finish(conn, store, values) == proof
    assert log == ["usage-target", "usage-judge", "settle-target", "settle-judge",
        "run", "report", "sidecar"]
    assert conn.log == ["transaction", "role", "role"]


@pytest.mark.parametrize("fault", ["report", "deferred", "settlement", "sidecar"])
def test_atomic_route_finalizer_fails_closed_and_never_returns_partial(monkeypatch, fault):
    values = fixture(); proof, _, _, journal, report, _, _ = values; log = []
    install_fakes(monkeypatch, proof, log, settlement_drift=fault == "settlement")
    conn = FakeConnection(proof, deferred=fault == "deferred")
    store = FakeProofStore(journal, log, fail=fault == "sidecar")
    if fault == "report":
        values = (*values[:4], report.model_copy(update={"target":report.suite_ref}), *values[5:])
    with pytest.raises(subject.RouteEvalAtomicFinalizationConflict):
        finish(conn, store, values)
    if fault == "report":
        assert log == [] and conn.log == []
    else:
        assert conn.transaction_failed is True
    if fault == "deferred":
        assert log == [] and conn.log == ["transaction"]
    if fault == "settlement":
        assert "run" not in log and "report" not in log and "sidecar" not in log
    if fault == "sidecar":
        assert log[-3:] == ["run", "report", "sidecar"]


def test_atomic_route_finalizer_contains_no_provider_dispatch_or_commit_surface():
    source = open(subject.__file__, encoding="utf-8").read()
    assert ".commit(" not in source and ".rollback(" not in source
    assert "provider dispatch" in source.lower()


def test_atomic_route_finalizer_rejects_non_native_connection_before_sql():
    values = fixture(); proof, _, _, journal, *_ = values
    conn = FakeConnection(proof)
    with pytest.raises(subject.RouteEvalAtomicFinalizationConflict):
        finish(conn, FakeProofStore(journal, []), values)
    assert conn.log == []
