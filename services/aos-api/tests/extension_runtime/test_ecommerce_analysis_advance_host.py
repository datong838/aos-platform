from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 9, 9, 2, 22, tzinfo=UTC)
HASH = "sha256:" + "a" * 64
OCCURRENCE_ID = UUID("11111111-1111-4111-8111-111111111111")
CUTOFF = datetime(2026, 9, 8, 0, tzinfo=UTC)


def ref(kind, identity, *, receipt=None, revision=1):
    value = {
        "resourceType": kind,
        "resourceId": identity,
        "revision": revision,
        "contentHash": HASH,
    }
    if receipt is not None:
        value["receiptId"] = receipt
    return value


def command_hash(payload):
    import hashlib
    import json

    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def start_command(**changes):
    body = {
        "operation": "runtime.analysis.start",
        "occurrenceRef": ref("AutomationOccurrence", str(OCCURRENCE_ID)),
        "caseRef": ref("BusinessInvestigationCaseRevision", "case-1"),
        "profileRef": ref("InvestigationProfileRevision", "profile-1"),
        "cutoffAt": CUTOFF.isoformat(),
        "idempotencyKey": "occurrence-start-1",
        "priorReceiptRef": None,
        "requirementRef": None,
        "fulfillmentRef": None,
        "checkpointRef": None,
    }
    body.update(changes)
    if "requestHash" not in body:
        body["requestHash"] = command_hash({key: value for key, value in body.items() if key != "requestHash"})
    return body


def lineage_refs():
    return {
        "runRef": ref("BusinessInvestigationRun", "run-1"),
        "compilationRef": ref("BusinessInvestigationCompilationReceipt", "compilation-1"),
        "planRef": ref("PlanRevision", "plan-1"),
        "taskRunRef": ref("TaskRun", "task-run-1"),
    }


def wired_host(monkeypatch, *, occurrence_hash=HASH):
    from aos_api.ecommerce_growth_runtime_adapters import AnalysisAdvanceHostService

    journal = {}
    occurrence = {
        "occurrenceId": str(OCCURRENCE_ID),
        "policyId": "policy-1",
        "policyRevision": 1,
        "policyHash": HASH,
        "operationId": "ecommerce_growth_analysis_advance",
        "installationId": "11111111-1111-4111-8111-111111111111",
        "generation": "22222222-2222-4222-8222-222222222222",
        "executionEpoch": 7,
        "scheduledAt": CUTOFF.isoformat(),
        "localSlot": "2026-09-08T00:00:00+08:00",
        "triggerSource": "schedule",
        "sourceEventId": None,
        "status": "claimed",
        "deadline": CUTOFF.isoformat(),
    }
    case = SimpleNamespace(
        case_id="case-1",
        revision=1,
        content_hash=HASH,
        investigation_profile_ref=SimpleNamespace(
            model_dump=lambda **_: ref("InvestigationProfileRevision", "profile-1")
        ),
    )

    class Cases:
        def __init__(self, _factory=None):
            pass

        def get(self, _scope, case_id):
            if case_id != "case-1":
                raise ValueError("case missing")
            return case

    class Receipts:
        def put(self, key, payload, **_kwargs):
            existing = journal.get(key)
            if existing is not None:
                if existing != payload:
                    raise ValueError("analysis runtime Receipt idempotency content drift")
                return existing
            journal[key] = payload
            return payload

        def read(self, key):
            return journal.get(key)

    host = AnalysisAdvanceHostService()
    monkeypatch.setattr(
        host,
        "_components",
        lambda *_: (
            lambda occurrence_id: {**occurrence, "occurrenceId": str(occurrence_id)},
            Cases(),
            Receipts(),
        ),
    )
    monkeypatch.setattr(host, "_occurrence_content_hash", lambda _payload: occurrence_hash)
    monkeypatch.setattr(host, "_start_lineage", lambda **_: lineage_refs())
    return host, journal


def test_analysis_advance_host_is_the_runtime_registry_service():
    from aos_api.ecommerce_growth_runtime_adapters import AnalysisAdvanceHostService

    assert AnalysisAdvanceHostService.executor_identity == "ecommerce-growth-analysis-host"


@pytest.mark.parametrize(
    "mutation",
    ["extra", "resume", "hash_drift", "prior_receipt", "tenant"],
)
def test_start_command_rejects_unknown_mode_and_drift(mutation, monkeypatch):
    from aos_api.ecommerce_growth_runtime_adapters import _strict_analysis_start_command

    value = start_command()
    if mutation == "extra":
        value["mode"] = "START"
    if mutation == "resume":
        value["operation"] = "runtime.analysis.resume_data"
        value["requestHash"] = command_hash({k: v for k, v in value.items() if k != "requestHash"})
    if mutation == "hash_drift":
        value["requestHash"] = "sha256:" + "b" * 64
    if mutation == "prior_receipt":
        value["priorReceiptRef"] = ref("AnalysisRuntimeReceipt", "prior-1")
        value["requestHash"] = command_hash({k: v for k, v in value.items() if k != "requestHash"})
    if mutation == "tenant":
        value["tenant"] = {"orgId": "org-org", "projectId": "dev-project"}
        value["requestHash"] = command_hash({k: v for k, v in value.items() if k != "requestHash"})
    with pytest.raises(ValueError):
        _strict_analysis_start_command(value)


def test_revalidate_rejects_case_or_profile_drift(monkeypatch):
    from aos_api.ecommerce_growth_runtime_adapters import AnalysisAdvanceHostService

    host, _journal = wired_host(monkeypatch)
    transaction = HostTransaction(SimpleNamespace())
    dispatch = SimpleNamespace(operation_id="ecommerce_growth_analysis_advance")
    host.revalidate(transaction=transaction, scope=SCOPE, dispatch=dispatch, command=start_command())
    drifted = start_command(profileRef=ref("InvestigationProfileRevision", "profile-2"))
    with pytest.raises(ValueError, match="profile"):
        host.revalidate(transaction=transaction, scope=SCOPE, dispatch=dispatch, command=drifted)


def test_start_returns_incomplete_preparing_receipt_and_rereads(monkeypatch):
    host, journal = wired_host(monkeypatch)
    transaction = HostTransaction(SimpleNamespace())
    dispatch = SimpleNamespace(operation_id="ecommerce_growth_analysis_advance")
    command = start_command()
    host.revalidate(transaction=transaction, scope=SCOPE, dispatch=dispatch, command=command)
    response = host.execute(
        transaction=transaction,
        scope=SCOPE,
        dispatch_ref=dispatch,
        command=command,
        checked_at=NOW,
        occurred_at=NOW,
    )
    assert response["phase"] == "PREPARING"
    assert response["recoverableAction"] == "CONTINUE"
    assert response["completed"] is False
    assert response["runRef"]["resourceId"] == "run-1"
    assert response["checkpointRef"] is None
    assert response["evidenceRefs"] == []
    assert set(response) >= {"receiptRef", "requestHash", "occurrenceRef", "caseRef", "profileRef"}
    assert response["receiptRef"]["resourceType"] == "AnalysisRuntimeReceipt"
    assert "tenant" not in response
    assert journal[command["idempotencyKey"]] == response
    assert (
        host.verify_receipt(
            transaction=transaction,
            scope=SCOPE,
            dispatch=dispatch,
            command=command,
            receipt=response,
        )
        == response
    )


def test_resume_and_reconcile_fail_closed_until_wired(monkeypatch):
    host, _journal = wired_host(monkeypatch)
    transaction = HostTransaction(SimpleNamespace())
    dispatch = SimpleNamespace(operation_id="ecommerce_growth_analysis_advance")
    resume = start_command(operation="runtime.analysis.resume_data")
    resume["requestHash"] = command_hash({k: v for k, v in resume.items() if k != "requestHash"})
    with pytest.raises(ValueError, match="not wired"):
        host.revalidate(transaction=transaction, scope=SCOPE, dispatch=dispatch, command=resume)
