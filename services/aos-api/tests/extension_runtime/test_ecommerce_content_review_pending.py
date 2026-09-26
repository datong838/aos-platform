"""Content review candidate is read-only and never constructs missing authority."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from aos_api.aip_eval_contracts import (
    EvalContractRevisionRef, EvalGatePolicyRef, EvalStageAttemptRef, EvalSubjectArtifactRef,
)
from aos_api import ecommerce_content_review_pending as pending_module
from aos_api.ecommerce_content_review_pending import ContentReviewPendingReader
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


def _reader(monkeypatch, *, current=True, reports=(), run_bindings=None):
    queries = []
    proof = SimpleNamespace(reservation_id="reservation-1", run_id="run-1",
                            task_id="task-1", artifact_id="artifact-1",
                            artifact_hash="a" * 64)
    source = SimpleNamespace(
        read=lambda _conn, _scope, _reservation: proof,
        journal=SimpleNamespace(read=lambda *_: {"command": {
            "idempotencyKey": "generate-1", "requestHash": "b" * 64,
        }}),
    )

    class Conn:
        def execute(self, query, params):
            assert params[:2] == SCOPE.key
            queries.append(query)
            if "FROM public.ecommerce_growth_runtime_command_receipt" in query:
                return Cursor([{"request_hash": "b" * 64, "response": {"state": "PENDING"}}] if current else [])
            if "FROM public.aip_step_run" in query:
                return Cursor([{"step_run_id": "step-1", "attempt": 1,
                                "input_hash": "c" * 64, "status": "succeeded"}])
            if "FROM public.aip_eval_report_revision" in query:
                return Cursor(list(reports))
            if "FROM public.aip_eval_run" in query:
                return Cursor([{"status": "succeeded", **(run_bindings or {})}])
            if "FROM public.aip_review_issue" in query:
                return Cursor([])
            raise AssertionError(query)

    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield Conn()

    monkeypatch.setattr(pending_module.ContentGenerationStepOwner, "_readback",
                        staticmethod(lambda *_: {"stepRunId": "step-1"}))
    monkeypatch.setattr(pending_module, "require_current_content_pre_review_gate",
                        lambda *_: SimpleNamespace(resource_id="contract-1", revision=2,
                                                   content_hash="d" * 64))
    monkeypatch.setattr(pending_module, "require_original_content_eval_gate", lambda *_: None)
    return ContentReviewPendingReader(source=source, connect_read=connect), queries


def test_no_formal_report_produces_no_candidate_and_no_write(monkeypatch):
    reader, queries = _reader(monkeypatch)
    assert reader.read_one(SCOPE, "reservation-1") is None
    assert any("aip_eval_report_revision" in query for query in queries)
    assert all(not query.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for query in queries)


def test_old_installation_blocks_before_report(monkeypatch):
    reader, queries = _reader(monkeypatch, current=False)
    with pytest.raises(pending_module.ContentReviewPendingBlocked, match="dispatch"):
        reader.read_one(SCOPE, "reservation-1")
    assert not any("aip_eval_report_revision" in query for query in queries)


def test_duplicate_subject_reports_fail_closed_without_creating_issue(monkeypatch):
    reader, queries = _reader(monkeypatch, reports=({"report_id": "one"}, {"report_id": "two"}))
    with pytest.raises(pending_module.ContentReviewPendingBlocked, match="ambiguous"):
        reader.read_one(SCOPE, "reservation-1")
    assert not any("aip_review_issue" in query for query in queries)


def test_missing_current_eval_gate_blocks_even_with_no_report(monkeypatch):
    reader, _ = _reader(monkeypatch)

    def missing(_conn, _scope):
        raise ValueError("no current contract")

    monkeypatch.setattr(pending_module, "require_current_content_pre_review_gate", missing)
    with pytest.raises(pending_module.ContentReviewPendingBlocked, match="Eval/Plan"):
        reader.read_one(SCOPE, "reservation-1")


def test_requires_exact_trusted_tenant_scope_before_any_query(monkeypatch):
    reader, queries = _reader(monkeypatch)
    with pytest.raises(ValueError, match="exact scoped"):
        reader.read_one(object(), "reservation-1")
    assert queries == []


@pytest.mark.parametrize("passed,expected", [(True, "CANDIDATE"), (False, "BLOCKED")])
def test_only_passed_exact_subject_report_can_be_candidate(monkeypatch, passed, expected):
    contract_ref = EvalContractRevisionRef(resourceId="contract-1", revision=2, contentHash="d" * 64)
    policy_ref = EvalGatePolicyRef(resourceType="EvalContractRevision", resourceId="contract-1",
                                   revision=2, contentHash="d" * 64)
    report = SimpleNamespace(
        report_id="report-1", revision=1, content_hash="e" * 64, run_id="eval-run-1",
        gate_passed=passed, failed=0 if passed else 1,
        subject_artifact_ref=EvalSubjectArtifactRef(resourceId="artifact-1", contentHash="a" * 64),
        stage_attempt_ref=EvalStageAttemptRef(runId="run-1", stepKey="content_generate",
                                              stepRunId="step-1", attempt=1, inputHash="c" * 64),
        eval_contract_ref=contract_ref, gate_policy_ref=policy_ref,
        suite_ref=SimpleNamespace(asset_id="subject-suite", revision="1", content_hash="f" * 64),
    )
    bindings = {
        key: getattr(report, attribute).model_dump(mode="json", by_alias=True)
        for key, attribute in (
            ("eval_contract_ref", "eval_contract_ref"),
            ("subject_artifact_ref", "subject_artifact_ref"),
            ("stage_attempt_ref", "stage_attempt_ref"),
            ("gate_policy_ref", "gate_policy_ref"),
        )
    }
    reader, _ = _reader(monkeypatch, reports=({"report_id": "report-1"},), run_bindings=bindings)
    monkeypatch.setattr(pending_module.AipEvalRunner, "_report_from_row", staticmethod(lambda *_: report))
    monkeypatch.setattr(pending_module, "compute_eval_report_hash", lambda *_: "e" * 64)
    monkeypatch.setattr(pending_module, "AipProductionContractStore", lambda: SimpleNamespace(
        get_eval_contract=lambda *_args, **_kwargs: SimpleNamespace(suite_ref=SimpleNamespace(
            resource_id="subject-suite", revision=1, content_hash="f" * 64,
        )),
    ))
    monkeypatch.setattr(pending_module.AipReleasePublicationService, "_verify_run", staticmethod(lambda *_: None))
    if expected == "BLOCKED":
        with pytest.raises(pending_module.ContentReviewPendingBlocked, match="EvalReport"):
            reader.read_one(SCOPE, "reservation-1")
    else:
        candidate = reader.read_one(SCOPE, "reservation-1")
        assert candidate is not None and candidate.report_id == "report-1"
        assert reader.read_one(SCOPE, "reservation-1") == candidate
