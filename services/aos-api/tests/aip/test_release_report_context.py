"""Report exact-reference preservation and unsupported execution-source fences."""
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_contracts import EvalReportRevision, AssetType, AssetRevisionRef
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.aip_release_publication_models import DeriveReleaseGateRequest, PublishReleaseRequest
from aos_api.aip_release_publication_service import AipReleasePublicationService, AipReleaseGateRejected
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
CONTEXT = ("eval_contract_ref", "subject_artifact_ref", "stage_attempt_ref", "gate_policy_ref", "evidence_cutoff_at")

def asset(kind, name):
    return {"asset_type": kind, "asset_id": name, "revision": "1", "content_hash": "1" * 64}

def report_row(context="legacy", target=AssetType.SKILL_TEMPLATE):
    data = dict(tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        report_id="context-unit", revision=1, content_hash="0" * 64, run_id="no-execution",
        suite_ref=asset("eval_suite", "suite"), target=asset(target, "target"),
        dataset=dict(dataset_id="context-unit", revision=1, content_hash="2" * 64,
            source_hash="3" * 64, redaction_policy=asset("policy", "redaction")),
        judge=dict(judge_id="context-unit", revision=1, content_hash="4" * 64),
        results=[dict(case_id="context-unit", passed=True, actual_hash="5" * 64,
            detail_code="SYNTHETIC_CONTEXT_ONLY", duration_ms=0)], passed=1, failed=0,
        total=1, pass_rate=1, gate_passed=True, created_at=NOW)
    if context != "legacy":
        data["eval_contract_ref"] = dict(resource_id="contract", revision=1, content_hash="6" * 64)
    if context == "media":
        data.update(subject_artifact_ref=dict(resource_id="artifact", content_hash="7" * 64),
            stage_attempt_ref=dict(run_id="run", step_key="step", step_run_id="attempt",
                attempt=1, input_hash="8" * 64),
            gate_policy_ref=dict(resource_id="policy", revision=1, content_hash="9" * 64),
            evidence_cutoff_at=NOW)
    report = EvalReportRevision.model_validate(data)
    report = report.model_copy(update={"content_hash": compute_eval_report_hash(report)})
    row = report.model_dump()
    row.update(target_ref=row.pop("target"), dataset_ref=row.pop("dataset"), judge_ref=row.pop("judge"))
    return report, row

@pytest.mark.parametrize("context", ["legacy", "contract", "media"])
def test_context_roundtrip_preserves_canonical_hash(context):
    original, row = report_row(context)
    restored = AipReleasePublicationService._report_from_row(SCOPE, row)
    assert restored == original
    assert compute_eval_report_hash(restored) == original.content_hash

def test_old_row_without_context_columns_is_compatible():
    original, row = report_row()
    for field in CONTEXT:
        row.pop(field)
    assert AipReleasePublicationService._report_from_row(SCOPE, row) == original

def test_partial_media_context_is_rejected_instead_of_discarded():
    _, row = report_row("media")
    row["stage_attempt_ref"] = None
    with pytest.raises(ValueError, match="must be bound together"):
        AipReleasePublicationService._report_from_row(SCOPE, row)

@pytest.mark.parametrize("kind", [AssetType.REGISTERED_MODEL, AssetType.MODEL_ROUTE])
def test_derive_rejects_unsupported_target_before_run_read_or_gate_write(kind):
    report, row = report_row("contract", kind)
    class Connection:
        def __init__(self):
            self.queries = []
        def execute(self, query, params):
            self.queries.append(query)
            if "FROM aip_eval_report_revision" not in query:
                pytest.fail("unsupported execution source advanced beyond report validation")
            return self
        def fetchone(self):
            return row
    conn = Connection()
    @contextmanager
    def connect(*args, **kwargs):
        yield conn
    service = AipReleasePublicationService(connect)
    service._gate_row = lambda *args: None
    with pytest.raises(AipReleaseGateRejected, match="signed execution"):
        service.derive_gate(SCOPE, actor="unit-only", request=DeriveReleaseGateRequest(
            report_id=report.report_id, report_revision=1, report_hash=report.content_hash,
            idempotency_key="unit-only"))
    assert len(conn.queries) == 1

@pytest.mark.parametrize("kind", [AssetType.SKILL_TEMPLATE, AssetType.LOGIC_GRAPH])
def test_existing_execution_sources_keep_their_original_proof_checks(kind):
    AipReleasePublicationService._require_supported_release_target(
        AssetRevisionRef.model_validate(asset(kind, "target")))

@pytest.mark.parametrize("kind", [AssetType.REGISTERED_MODEL, AssetType.MODEL_ROUTE])
def test_publish_existing_gate_rejects_before_clock_or_event_write(kind):
    from types import SimpleNamespace
    @contextmanager
    def connect(*args, **kwargs):
        # An unsupported gate must be rejected without any further connection use.
        yield object()
    service = AipReleasePublicationService(connect)
    service._event_row = lambda *args: None
    service._gate_row = lambda *args: object()
    service._gate_from_row = lambda *args: SimpleNamespace(
        target=AssetRevisionRef.model_validate(asset(kind, "target")))
    with pytest.raises(AipReleaseGateRejected, match="signed execution"):
        service.publish(SCOPE, actor="unit-only", request=PublishReleaseRequest(
            release_gate_decision_id="old-gate", reason_hash="1" * 64,
            idempotency_key="unit-only"))
