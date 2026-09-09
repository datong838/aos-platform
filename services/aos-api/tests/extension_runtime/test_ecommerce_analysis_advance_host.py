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


def resume_command(**changes):
    body = {
        "operation": "runtime.analysis.resume_data",
        "occurrenceRef": ref("AutomationOccurrence", str(OCCURRENCE_ID)),
        "caseRef": ref("BusinessInvestigationCaseRevision", "case-1"),
        "profileRef": ref("InvestigationProfileRevision", "profile-1"),
        "cutoffAt": CUTOFF.isoformat(),
        "idempotencyKey": "resume-data-1",
        "priorReceiptRef": ref(
            "AnalysisRuntimeReceipt", "prior-waiting-1", receipt="prior-waiting-1"
        ),
        "requirementRef": ref("DataRequirementRevision", "requirement-1"),
        "fulfillmentRef": ref(
            "DataFulfillmentReceipt", "fulfillment-1", receipt="fulfillment-1"
        ),
        "checkpointRef": ref("CheckpointRevision", "checkpoint-1"),
        "priorPlanRef": ref("PlanRevision", "plan-1"),
        "sourceReadinessRef": ref(
            "SourceReadinessEnvelope", "readiness-1", receipt="readiness-1"
        ),
        "mappingRef": ref("SourceMappingRevision", "mapping-1"),
        "evidenceRefs": [ref("EvidenceBundleRevision", "evidence-1")],
        "observedAt": CUTOFF.isoformat(),
    }
    body.update(changes)
    if "requestHash" not in body:
        body["requestHash"] = command_hash(
            {key: value for key, value in body.items() if key != "requestHash"}
        )
    return body


def reconcile_command(**changes):
    body = {
        "operation": "runtime.analysis.reconcile_unknown",
        "occurrenceRef": ref("AutomationOccurrence", str(OCCURRENCE_ID)),
        "caseRef": ref("BusinessInvestigationCaseRevision", "case-1"),
        "profileRef": ref("InvestigationProfileRevision", "profile-1"),
        "cutoffAt": CUTOFF.isoformat(),
        "idempotencyKey": "reconcile-1",
        "priorReceiptRef": ref(
            "AnalysisRuntimeReceipt", "prior-unknown-1", receipt="prior-unknown-1"
        ),
        "requirementRef": None,
        "fulfillmentRef": None,
        "checkpointRef": None,
    }
    body.update(changes)
    if "requestHash" not in body:
        body["requestHash"] = command_hash(
            {key: value for key, value in body.items() if key != "requestHash"}
        )
    return body


def prior_receipt(command, *, phase="WAITING_DATA", action="WAIT_FOR_DATA"):
    body = {
        "requestHash": HASH,
        "occurrenceRef": command["occurrenceRef"],
        "caseRef": command["caseRef"],
        "profileRef": command["profileRef"],
        "cutoffAt": command["cutoffAt"],
        **lineage_refs(),
        "phase": phase,
        "recoverableAction": action,
        "checkpointRef": command.get("checkpointRef") if phase == "WAITING_DATA" else None,
        "priorCheckpointRef": None,
        "requirementRef": command.get("requirementRef") if phase == "WAITING_DATA" else None,
        "fulfillmentRef": None,
        "sourceReadinessRef": None,
        "mappingRef": None,
        "evidenceRefs": [],
        "observedAt": None,
        "targetReceiptRef": (
            ref("RuntimeCommandReceipt", "target-1", receipt="target-1")
            if phase in {"UNKNOWN", "RECONCILING"}
            else None
        ),
        "completed": False,
    }
    receipt = command["priorReceiptRef"]
    body_hash = command_hash(body)
    return {**body, "receiptRef": {**receipt, "contentHash": body_hash}}


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

        def read_exact(self, receipt_ref):
            return journal.get(("exact", receipt_ref["resourceId"]))

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
    with pytest.raises(ValueError, match="invalid envelope"):
        host.revalidate(transaction=transaction, scope=SCOPE, dispatch=dispatch, command=resume)


def test_resume_composes_domain_and_aip_then_persists_running_receipt(monkeypatch):
    import aos_api.ecommerce_growth_runtime_adapters as adapters

    host, journal = wired_host(monkeypatch)
    transaction = HostTransaction(SimpleNamespace())
    dispatch = SimpleNamespace(operation_id="ecommerce_growth_analysis_advance")
    command = resume_command()
    saved = prior_receipt(command)
    command["priorReceiptRef"] = saved["receiptRef"]
    command["requestHash"] = command_hash(
        {key: value for key, value in command.items() if key != "requestHash"}
    )
    journal[("exact", saved["receiptRef"]["resourceId"])] = saved
    host.revalidate(
        transaction=transaction, scope=SCOPE, dispatch=dispatch, command=command
    )
    run = SimpleNamespace(
        authority=SimpleNamespace(run_id="run-1"),
        state=SimpleNamespace(version=3),
    )
    monkeypatch.setattr(
        host,
        "_resume_authorities",
        lambda **_: (
            SimpleNamespace(),
            run,
            SimpleNamespace(),
            SimpleNamespace(),
            None,
            None,
            None,
            None,
            None,
        ),
    )
    resumed_runtime = SimpleNamespace(
        binding_hash="b" * 64,
        task_run_ref=SimpleNamespace(resource_id="task-run-1", version=2),
    )
    monkeypatch.setattr(host, "_runtime_binding_for_task_run", lambda *_: resumed_runtime)
    monkeypatch.setattr(host, "_verify_resume_commit", lambda **values: values["receipt"])

    class FakeSaga:
        def __init__(self, resumer):
            self.resumer = resumer

        def execute(self, *_args, **_kwargs):
            self.resumer.run_state = object()
            return SimpleNamespace(
                task_run_ref=SimpleNamespace(resource_id="task-run-1")
            )

    monkeypatch.setattr(adapters, "BusinessInvestigationFulfillmentResumeSaga", FakeSaga)
    response = host.execute(
        transaction=transaction,
        scope=SCOPE,
        dispatch_ref=dispatch,
        command=command,
        checked_at=NOW,
        occurred_at=NOW,
    )
    assert response["phase"] == "RUNNING"
    assert response["recoverableAction"] == "CONTINUE"
    assert response["taskRunRef"]["revision"] == 2
    assert response["taskRunRef"]["contentHash"] == "sha256:" + "b" * 64
    assert response["checkpointRef"] == command["checkpointRef"]
    assert response["priorCheckpointRef"] is None
    assert response["completed"] is False
    assert host.execute(
        transaction=transaction,
        scope=SCOPE,
        dispatch_ref=dispatch,
        command=command,
        checked_at=NOW,
        occurred_at=NOW,
    ) == response


@pytest.mark.parametrize(
    "drift", ["missing", "phase", "lineage", "bool_revision", "plan", "run_shape"]
)
def test_resume_prior_receipt_drift_fails_closed(drift, monkeypatch):
    host, journal = wired_host(monkeypatch)
    transaction = HostTransaction(SimpleNamespace())
    dispatch = SimpleNamespace(operation_id="ecommerce_growth_analysis_advance")
    command = resume_command()
    saved = prior_receipt(command)
    command["priorReceiptRef"] = saved["receiptRef"]
    if drift == "phase":
        saved = prior_receipt(command, phase="PREPARING", action="CONTINUE")
        command["priorReceiptRef"] = saved["receiptRef"]
    elif drift == "lineage":
        saved["caseRef"] = ref("BusinessInvestigationCaseRevision", "case-other")
    elif drift == "bool_revision":
        command["checkpointRef"] = {**command["checkpointRef"], "revision": True}
    elif drift == "plan":
        command["priorPlanRef"] = ref("PlanRevision", "plan-other")
    elif drift == "run_shape":
        saved["runRef"] = None
        saved["receiptRef"] = {
            **saved["receiptRef"],
            "contentHash": command_hash(
                {key: value for key, value in saved.items() if key != "receiptRef"}
            ),
        }
        command["priorReceiptRef"] = saved["receiptRef"]
    command["requestHash"] = command_hash(
        {key: value for key, value in command.items() if key != "requestHash"}
    )
    if drift != "missing":
        journal[("exact", command["priorReceiptRef"]["resourceId"])] = saved
    with pytest.raises(ValueError):
        host.revalidate(
            transaction=transaction, scope=SCOPE, dispatch=dispatch, command=command
        )


def test_reconcile_reads_same_unknown_target_and_persists_reconciling(monkeypatch):
    import aos_api.ecommerce_growth_runtime_adapters as adapters

    host, journal = wired_host(monkeypatch)
    transaction = HostTransaction(SimpleNamespace())
    dispatch = SimpleNamespace(operation_id="ecommerce_growth_analysis_advance")
    command = reconcile_command()
    saved = prior_receipt(command, phase="UNKNOWN", action="RECONCILE_RECEIPT")
    command["priorReceiptRef"] = saved["receiptRef"]
    command["requestHash"] = command_hash(
        {key: value for key, value in command.items() if key != "requestHash"}
    )
    journal[("exact", saved["receiptRef"]["resourceId"])] = saved
    host.revalidate(
        transaction=transaction, scope=SCOPE, dispatch=dispatch, command=command
    )
    calls = []
    observed_ref = SimpleNamespace(resource_id="run-1")
    uncertain = SimpleNamespace()
    runs = SimpleNamespace()
    monkeypatch.setattr(
        host,
        "_reconcile_authorities",
        lambda **_: (
            runs,
            saved,
            SimpleNamespace(),
            SimpleNamespace(),
            observed_ref,
            uncertain,
            "domain-key",
        ),
    )

    class Coordinator:
        def __init__(self, owner):
            assert owner is runs

        def begin_reconcile(self, *args, **kwargs):
            calls.append((args, kwargs))

    monkeypatch.setattr(adapters, "BusinessInvestigationReconciliationCoordinator", Coordinator)
    monkeypatch.setattr(host, "_verify_reconcile_commit", lambda **values: values["receipt"])
    response = host.execute(
        transaction=transaction,
        scope=SCOPE,
        dispatch_ref=dispatch,
        command=command,
        checked_at=NOW,
        occurred_at=NOW,
    )
    assert response["phase"] == "RECONCILING"
    assert response["recoverableAction"] == "RECONCILE_RECEIPT"
    assert response["targetReceiptRef"] == saved["targetReceiptRef"]
    assert response["completed"] is False
    assert len(calls) == 1
    assert host.execute(
        transaction=transaction,
        scope=SCOPE,
        dispatch_ref=dispatch,
        command=command,
        checked_at=NOW,
        occurred_at=NOW,
    ) == response
    assert len(calls) == 1


@pytest.mark.parametrize("drift", ["late", "duplicate", "wrong_type", "extra"])
def test_resume_evidence_and_time_bounds_fail_closed(drift, monkeypatch):
    from datetime import timedelta

    host, _journal = wired_host(monkeypatch)
    command = resume_command()
    if drift == "late":
        command["observedAt"] = (CUTOFF + timedelta(hours=25)).isoformat()
    elif drift == "duplicate":
        command["evidenceRefs"] = [command["evidenceRefs"][0]] * 2
    elif drift == "wrong_type":
        command["evidenceRefs"] = [ref("FactRevision", "fact-1")]
    else:
        command["evidenceRefs"][0]["unexpected"] = "override"
    command["requestHash"] = command_hash(
        {key: value for key, value in command.items() if key != "requestHash"}
    )
    with pytest.raises(ValueError):
        host.revalidate(
            transaction=HostTransaction(SimpleNamespace()),
            scope=SCOPE,
            dispatch=SimpleNamespace(operation_id="ecommerce_growth_analysis_advance"),
            command=command,
        )


def test_run_and_task_resumer_orders_both_owners_and_stops_on_domain_failure():
    from aos_api.ecommerce_growth_runtime_adapters import _AnalysisRunAndTaskResumer

    calls = []

    class Runs:
        def resume_after_data(self, *_args, **_kwargs):
            calls.append("domain")
            return SimpleNamespace(authority="domain-successor")

    class Tasks:
        def resume_run(self, *_args, **_kwargs):
            calls.append("aip")
            return "aip-successor"

    resumer = _AnalysisRunAndTaskResumer(
        Runs(), Tasks(), ref("DataRequirementRevision", "requirement-1"),
        "run-1", 2, NOW,
    )
    assert resumer.resume_run(
        SCOPE,
        "task-run-1",
        expected_run_version=3,
        expected_task_version=2,
        actor="owner",
        idempotency_key="resume-1",
    ) == "aip-successor"
    assert calls == ["domain", "aip"]
    assert resumer.run_state == "domain-successor"

    class FailedRuns:
        def resume_after_data(self, *_args, **_kwargs):
            calls.append("domain-failed")
            raise ValueError("domain rejected")

    failed = _AnalysisRunAndTaskResumer(
        FailedRuns(), Tasks(), ref("DataRequirementRevision", "requirement-1"),
        "run-1", 2, NOW,
    )
    with pytest.raises(ValueError, match="domain rejected"):
        failed.resume_run(
            SCOPE,
            "task-run-1",
            expected_run_version=3,
            expected_task_version=2,
            actor="owner",
            idempotency_key="resume-2",
        )
    assert calls[-1] == "domain-failed"


def test_resume_receipt_comparison_preserves_json_boolean_and_integer_types():
    from aos_api.ecommerce_growth_runtime_adapters import (
        _analysis_json_equal,
        _strict_resume_control_receipt,
    )

    expected = {
        "operation": "resume",
        "expectedRunVersion": 3,
        "expectedTaskVersion": 2,
        "reason": "bounded resume",
    }
    expected["requestHash"] = command_hash(expected)
    assert _strict_resume_control_receipt(expected)
    assert _analysis_json_equal({"completed": False}, {"completed": False})
    assert not _analysis_json_equal({"completed": False}, {"completed": 0})
    assert not _strict_resume_control_receipt(
        {**expected, "expectedRunVersion": True}
    )
