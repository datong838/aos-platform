from copy import deepcopy

import pytest

import aos_api.aip_model_route_eval_finalization_reconcile as subject
from aos_api.aip_budget_reservation_contracts import BudgetExactRef,exact_ref_payload
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_model_route_eval_execution_journal import _canonical
from aos_api.aip_model_route_eval_finalization_proof import RouteEvalFinalizationProof
from aos_api.aip_model_route_eval_signatures import _manifest
from aos_api.tenant_scope import TenantScope
from test_model_route_eval_atomic_finalizer import fixture as atomic_fixture


class Rows:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = many

    def fetchone(self):
        return deepcopy(self.one)

    def fetchall(self):
        return deepcopy(self.many or [])


def report_row(report):
    return dict(org_id=report.tenant.org_id, project_id=report.tenant.project_id,
        report_id=report.report_id, revision=report.revision,
        content_hash=report.content_hash, run_id=report.run_id,
        suite_ref=report.suite_ref.model_dump(mode="json", by_alias=True),
        target_ref=report.target.model_dump(mode="json", by_alias=True),
        dataset_ref=report.dataset.model_dump(mode="json", by_alias=True),
        judge_ref=report.judge.model_dump(mode="json", by_alias=True),
        results=[item.model_dump(mode="json", by_alias=True) for item in report.results],
        passed=report.passed, failed=report.failed, total=report.total,
        pass_rate=report.pass_rate, gate_passed=report.gate_passed,
        created_at=report.created_at,
        eval_contract_ref=None if report.eval_contract_ref is None else
            report.eval_contract_ref.model_dump(mode="json", by_alias=True),
        subject_artifact_ref=None if report.subject_artifact_ref is None else
            report.subject_artifact_ref.model_dump(mode="json", by_alias=True),
        stage_attempt_ref=None if report.stage_attempt_ref is None else
            report.stage_attempt_ref.model_dump(mode="json", by_alias=True),
        gate_policy_ref=None if report.gate_policy_ref is None else
            report.gate_policy_ref.model_dump(mode="json", by_alias=True),
        evidence_cutoff_at=report.evidence_cutoff_at)


class FakeConnection:
    def __init__(self, proof, report, event, run, journal):
        self.calls = []
        self.context = dict(database="aos", role="aos_runtime", org_id="org-org",
            project_id="dev-project", isolation="repeatable read", readonly="on")
        self.budgets = {}; self.lineage = {}; self.usage = {}
        updated = []
        for item in proof.calls:
            result = journal.items[item.reservation_id]["result"]
            invocation_id = str(item.reservation_id)
            refs = []
            for index, (kind, quantity, old_ref) in enumerate(zip(
                    ("input_token", "output_token"),
                    (result.prompt_tokens, result.completion_tokens),
                    item.usage_receipt_refs, strict=True)):
                row = dict(receipt_id=old_ref.resource_id, provider=result.provider_id,
                    provider_receipt_id=f"{result.provider_result_id}:{index}:{kind}",
                    lineage_id=invocation_id, usage_kind=kind, quantity=quantity,
                    unit="token", currency=None, quality="measured",
                    source_hash=_canonical(result)[1], observed_at=result.observed_at)
                ref = BudgetExactRef(resourceType="UsageReceipt",resourceId=old_ref.resource_id,
                    revision=1,contentHash=canonical_hash(row,prefixed=True))
                refs.append(ref); self.usage[ref.resource_id] = row
            updated.append(item.model_copy(update={"usage_receipt_refs":tuple(refs)}))
        self.proof = RouteEvalFinalizationProof.model_validate(proof.model_dump(
            mode="json", by_alias=True) | {"calls":[item.model_dump(
                mode="json",by_alias=True) for item in updated]})
        for item in self.proof.calls:
            self.budgets[item.reservation_id] = dict(state="settled",
                revision=item.budget_revision, actual_minor=item.actual_minor,
                usage_receipt_refs=[exact_ref_payload(ref) for ref in item.usage_receipt_refs],
                provider_request_receipt_ref=exact_ref_payload(item.provider_request_ref),
                invocation_id=str(item.reservation_id))
            result=journal.items[item.reservation_id]["result"]
            event_id="route-eval-result:"+str(item.reservation_id)
            self.lineage[event_id]=dict(event_id=event_id,
                lineage_id=str(item.reservation_id),root_type="capability_invocation",
                root_id=str(item.reservation_id),sequence=1,event_type="model",
                subject_ref=None,artifact_ref=None,payload_hash=item.result_hash,
                quality="measured",occurred_at=result.observed_at,
                observed_at=result.observed_at,source_kind="capability_provider_result",
                source_id=str(item.reservation_id),source_hash=item.result_hash)
        self.run = dict(org_id=run.tenant.org_id,project_id=run.tenant.project_id,
            run_id=run.run_id,suite_id=run.suite_ref.asset_id,
            suite_revision=int(run.suite_ref.revision),suite_hash=run.suite_ref.content_hash,
            eval_contract_ref=None if run.eval_contract_ref is None else run.eval_contract_ref.model_dump(mode="json",by_alias=True),
            subject_artifact_ref=None,stage_attempt_ref=None,gate_policy_ref=None,
            evidence_cutoff_at=None,target_ref=run.target.model_dump(mode="json",by_alias=True),
            dataset_ref=run.dataset.model_dump(mode="json",by_alias=True),
            judge_ref=run.judge.model_dump(mode="json",by_alias=True),status="succeeded",
            idempotency_key=run.idempotency_key,created_by=run.created_by,
            created_at=run.created_at,started_at=run.started_at,
            finished_at=event.created_at,version=run.version+1)
        self.event = event.model_dump(mode="python",by_alias=False)
        self.event.pop("tenant")
        self.report = report_row(report)

    def execute(self, query, params=()):
        text = " ".join(str(query).split())
        assert text.startswith("SELECT ") and not any(word in text for word in (
            " FOR UPDATE", " FOR SHARE", "INSERT ", "UPDATE ", "DELETE "))
        self.calls.append(text)
        if "SELECT current_database()" in text:return Rows(self.context)
        if "aip_budget_reservation" in text:return Rows(self.budgets.get(params[-1]))
        if "aip_lineage_event" in text:return Rows(self.lineage.get(params[-1]))
        if "aip_usage_receipt" in text:return Rows(self.usage.get(params[-1]))
        if "aip_eval_run_event" in text:return Rows(self.event)
        if "aip_eval_run" in text:return Rows(self.run)
        if "aip_eval_report_revision" in text:return Rows(self.report)
        raise AssertionError("unexpected SQL: " + text)

    def commit(self):
        raise AssertionError("reconciliation cannot commit")

    rollback = commit


class FakeStore:
    schema = "public"

    def __init__(self, journal, proof, *, sidecar="complete"):
        self.journal = journal
        self.proof = proof
        self.sidecar = sidecar

    def _header(self, conn, scope, execution_id):
        return None if self.sidecar == "missing" else {"execution_id":execution_id}

    def _calls(self, conn, scope, execution_id):
        return [] if self.sidecar in {"missing", "partial"} else [
            {"case_id":item.case_id,"purpose":item.purpose} for item in self.proof.calls]

    def read(self, conn, scope, execution_id):
        if self.sidecar == "drift":return self.proof.model_copy(update={"report_hash":"f"*64})
        return self.proof


def values():
    proof, manifest, _, journal, report, event, version = atomic_fixture()
    run_body = _manifest(manifest)["context"]["run"]
    from aos_api.aip_eval_contracts import EvalRunAuthorityRecord
    run = EvalRunAuthorityRecord.model_validate(run_body)
    conn = FakeConnection(proof,report,event,run,journal)
    return conn,journal,report,event,version,run


def reconcile(monkeypatch, conn, journal, report, event, version, *, sidecar="complete"):
    monkeypatch.setattr(subject,"_native_read_only",lambda value:True)
    store=FakeStore(journal,conn.proof,sidecar=sidecar)
    return subject.reconcile_route_eval_finalization(conn,expected_database="aos",
        scope=TenantScope("org-org","dev-project"),proof=conn.proof,report=report,
        event=event,expected_run_version=version,proof_store=store)


def test_complete_requires_every_exact_durable_fact_and_is_read_only(monkeypatch):
    conn,journal,report,event,version,_ = values()
    result=reconcile(monkeypatch,conn,journal,report,event,version)
    assert result.state=="COMPLETE" and result.proof==conn.proof
    assert conn.calls and all(call.startswith("SELECT ") for call in conn.calls)


def test_legal_preterminal_snapshot_is_unknown_and_never_writes(monkeypatch):
    conn,journal,report,event,version,run = values()
    for row in conn.budgets.values():row["state"]="submitted"
    conn.lineage={};conn.usage={};conn.event=None;conn.report=None
    conn.run.update(status="running",version=run.version,finished_at=None)
    result=reconcile(monkeypatch,conn,journal,report,event,version,sidecar="missing")
    assert result.state=="UNKNOWN" and result.proof is None


@pytest.mark.parametrize("fault",["lineage","usage","budget","run","event","report","partial","sidecar"])
def test_drift_or_partial_atomic_terminal_is_contradictory(monkeypatch,fault):
    conn,journal,report,event,version,run = values();sidecar="complete"
    if fault=="lineage":next(iter(conn.lineage.values()))["payload_hash"]="f"*64
    elif fault=="usage":next(iter(conn.usage.values()))["quantity"]+=1
    elif fault=="budget":next(iter(conn.budgets.values()))["actual_minor"]+=1
    elif fault=="run":conn.run["version"]+=1
    elif fault=="event":conn.event["payload_hash"]="f"*64
    elif fault=="report":conn.report["content_hash"]="f"*64
    elif fault=="sidecar":sidecar="drift"
    else:
        first=next(iter(conn.budgets.values()));first["state"]="submitted"
        conn.lineage={};conn.usage={};conn.event=None;conn.report=None
        conn.run.update(status="running",version=run.version,finished_at=None)
        sidecar="partial"
    assert reconcile(monkeypatch,conn,journal,report,event,version,
        sidecar=sidecar).state=="CONTRADICTORY"


def test_wrong_identity_rejects_before_business_reads(monkeypatch):
    conn,journal,report,event,version,_ = values();conn.context["role"]="other"
    result=reconcile(monkeypatch,conn,journal,report,event,version)
    assert result.state=="CONTRADICTORY" and len(conn.calls)==1


def test_non_native_connection_and_source_have_no_retry_or_write_surface():
    conn,journal,report,event,version,_ = values()
    result=subject.reconcile_route_eval_finalization(conn,expected_database="aos",
        scope=TenantScope("org-org","dev-project"),proof=conn.proof,report=report,
        event=event,expected_run_version=version,
        proof_store=FakeStore(journal,conn.proof))
    assert result.state=="CONTRADICTORY" and conn.calls==[]
    source=open(subject.__file__,encoding="utf-8").read()
    assert all(token not in source for token in (".persist(",".settle(",".commit(",".rollback("))
