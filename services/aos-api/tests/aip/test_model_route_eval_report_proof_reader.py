from datetime import timedelta

import pytest

from aos_api.aip_budget_reservation_contracts import exact_ref_payload
from aos_api.aip_eval_contracts import EvalRunStatus
from aos_api.aip_model_route_eval_report_proof_reader import (
    RouteEvalReportProofRejected,
    read_verified_route_eval_report_from_persistence,
)
from aos_api.tenant_scope import TenantScope
from test_model_route_eval_finalization_native_pg import _prepare_native_case


SCOPE = TenantScope("org-org", "dev-project")


class Rows:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = [] if many is None else many

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class Journal:
    def __init__(self, case):
        self.case = case

    def read(self, _conn, _scope, reservation_id):
        return self.case.journal.get(reservation_id)


class Store:
    schema = "public"

    def __init__(self, case):
        self.case = case
        self.journal = Journal(case)

    def read(self, _conn, _scope, execution_id):
        if execution_id == self.case.proof.execution_id:
            return self.case.proof.model_copy(deep=True)
        return None


def _report_row(report):
    row = report.model_dump()
    row["target_ref"] = row.pop("target")
    row["dataset_ref"] = row.pop("dataset")
    row["judge_ref"] = row.pop("judge")
    return row


def _run_row(case):
    run = case.run.model_copy(
        update={
            "status": EvalRunStatus.SUCCEEDED,
            "version": case.expected_run_version + 1,
            "finished_at": case.event.created_at,
        }
    )
    return {
        "org_id": SCOPE.org_id,
        "project_id": SCOPE.project_id,
        "run_id": run.run_id,
        "suite_id": run.suite_ref.asset_id,
        "suite_revision": int(run.suite_ref.revision),
        "suite_hash": run.suite_ref.content_hash,
        "eval_contract_ref": None if run.eval_contract_ref is None else run.eval_contract_ref.model_dump(mode="json", by_alias=True),
        "subject_artifact_ref": None if run.subject_artifact_ref is None else run.subject_artifact_ref.model_dump(mode="json", by_alias=True),
        "stage_attempt_ref": None if run.stage_attempt_ref is None else run.stage_attempt_ref.model_dump(mode="json", by_alias=True),
        "gate_policy_ref": None if run.gate_policy_ref is None else run.gate_policy_ref.model_dump(mode="json", by_alias=True),
        "evidence_cutoff_at": run.evidence_cutoff_at,
        "target_ref": run.target.model_dump(mode="json", by_alias=True),
        "dataset_ref": run.dataset.model_dump(mode="json", by_alias=True),
        "judge_ref": run.judge.model_dump(mode="json", by_alias=True),
        "status": run.status.value,
        "idempotency_key": run.idempotency_key,
        "created_by": run.created_by,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "version": run.version,
    }


class Connection:
    def __init__(self, case, fault=None):
        self.case = case
        self.fault = fault

    def execute(self, query, params=()):
        sql = " ".join(str(query).split())
        if "current_user AS role" in sql:
            return Rows({
                "role": "aos_runtime",
                "org_id": SCOPE.org_id,
                "project_id": SCOPE.project_id,
                "isolation": "serializable",
                "evaluated_at": self.case.proof.finalized_at + timedelta(seconds=1),
            })
        if "SELECT execution_id FROM public.aip_route_eval_finalization_proof" in sql:
            rows = [{"execution_id": self.case.proof.execution_id}]
            if self.fault == "duplicate_proof":
                rows.append(dict(rows[0]))
            return Rows(many=rows)
        if "FROM public.aip_eval_report_revision" in sql:
            row = _report_row(self.case.report)
            if self.fault == "report":
                row["content_hash"] = "0" * 64
            return Rows(row)
        if "FROM public.aip_eval_run " in sql:
            row = _run_row(self.case)
            if self.fault == "run":
                row["status"] = "running"
                row["finished_at"] = None
            return Rows(row)
        if "FROM public.aip_eval_run_event" in sql:
            return Rows({
                "event_type": "run.succeeded",
                "to_status": "succeeded",
                "payload_hash": self.case.report.content_hash,
                "created_at": self.case.event.created_at,
            })
        if "FROM public.aip_budget_reservation" in sql:
            item = next(value for value in self.case.proof.calls if value.reservation_id == params[-1])
            row = {
                "state": "settled",
                "revision": item.budget_revision,
                "actual_minor": item.actual_minor,
                "usage_receipt_refs": [exact_ref_payload(ref) for ref in item.usage_receipt_refs],
                "provider_request_receipt_ref": exact_ref_payload(item.provider_request_ref),
                "invocation_id": item.reservation_id,
            }
            if self.fault == "budget":
                row["state"] = "unknown"
            return Rows(row)
        if "FROM public.aip_lineage_event" in sql:
            item = next(value for value in self.case.proof.calls if str(value.reservation_id) in params[-1])
            result = self.case.journal[item.reservation_id]["result"]
            row = {
                "event_id": "route-eval-result:" + str(item.reservation_id),
                "lineage_id": str(item.reservation_id),
                "root_type": "capability_invocation",
                "root_id": str(item.reservation_id),
                "sequence": 1,
                "event_type": "model",
                "subject_ref": None,
                "artifact_ref": None,
                "payload_hash": item.result_hash,
                "quality": "measured",
                "occurred_at": result.observed_at,
                "observed_at": result.observed_at,
                "source_kind": "capability_provider_result",
                "source_id": str(item.reservation_id),
                "source_hash": item.result_hash,
            }
            if self.fault == "lineage":
                row["source_hash"] = "0" * 64
            return Rows(row)
        if "FROM public.aip_usage_receipt" in sql:
            for rows in self.case.usage_rows.values():
                for row in rows:
                    if row["receipt_id"] == params[-1]:
                        value = dict(row)
                        if self.fault == "usage":
                            value["quality"] = "estimated"
                        return Rows(value)
            return Rows(None)
        raise AssertionError("unexpected SQL: " + sql)


def test_complete_route_report_proof_is_read_without_writes():
    case = _prepare_native_case()
    result = read_verified_route_eval_report_from_persistence(
        Connection(case), scope=SCOPE, report=case.report, proof_store=Store(case)
    )
    assert result.report_id == case.report.report_id
    assert result.report_hash == case.report.content_hash
    assert result.proof == case.proof
    assert result.proof is not case.proof


@pytest.mark.parametrize("fault", ["duplicate_proof", "report", "run", "budget", "lineage", "usage"])
def test_route_report_reader_fails_closed_on_terminal_drift(fault):
    case = _prepare_native_case()
    with pytest.raises(RouteEvalReportProofRejected, match="exact persisted"):
        read_verified_route_eval_report_from_persistence(
            Connection(case, fault), scope=SCOPE, report=case.report, proof_store=Store(case)
        )


def test_route_report_reader_rejects_other_tenant_before_reads():
    case = _prepare_native_case()
    with pytest.raises(RouteEvalReportProofRejected, match="exact persisted"):
        read_verified_route_eval_report_from_persistence(
            object(),
            scope=TenantScope("dev-org", "dev-project"),
            report=case.report,
            proof_store=Store(case),
        )
