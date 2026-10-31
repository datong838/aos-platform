"""Read one durable Route Eval Report proof without granting release authority."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aos_api.aip_budget_reservation_contracts import exact_ref_payload
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import AssetType, EvalReportRevision, EvalRunStatus
from aos_api.aip_eval_runner import AipEvalRunner, compute_eval_report_hash
from aos_api.aip_model_route_eval_finalization_proof import (
    RouteEvalFinalizationProof,
    RouteEvalFinalizationProofStore,
)
from aos_api.aip_model_route_eval_finalization_reconcile import (
    _exact_journal,
    _exact_usage,
    _run_matches_report,
)
from aos_api.tenant_scope import TenantScope


class RouteEvalReportProofRejected(RuntimeError):
    """Fail-closed Route Report proof read; never includes sensitive payloads."""


@dataclass(frozen=True)
class VerifiedRouteEvalReportProof:
    report_id: str
    report_hash: str
    proof: RouteEvalFinalizationProof


def _require(ok: bool) -> None:
    if not ok:
        raise RouteEvalReportProofRejected("exact persisted Route Eval Report proof required")


def read_verified_route_eval_report_from_persistence(
    conn: Any,
    *,
    scope: TenantScope,
    report: EvalReportRevision,
    proof_store: RouteEvalFinalizationProofStore | None = None,
) -> VerifiedRouteEvalReportProof:
    """Verify final Route evidence in the caller's tenant transaction.

    This is deliberately narrower than release authority: current Source,
    revocation and publishable-target checks remain separate consumer gates.
    """
    store = proof_store or RouteEvalFinalizationProofStore()
    try:
        _require(
            type(scope) is TenantScope
            and scope.key == ("org-org", "dev-project")
            and type(report) is EvalReportRevision
            and (report.tenant.org_id, report.tenant.project_id) == scope.key
            and report.target.asset_type is AssetType.MODEL_ROUTE
            and compute_eval_report_hash(report) == report.content_hash
        )
        context = conn.execute(
            """SELECT current_user AS role,
                current_setting('aos.org_id',true) AS org_id,
                current_setting('aos.project_id',true) AS project_id,
                current_setting('transaction_isolation') AS isolation,
                transaction_timestamp() AS evaluated_at"""
        ).fetchone()
        _require(
            context is not None
            and context["role"] == "aos_runtime"
            and (context["org_id"], context["project_id"]) == scope.key
            and context["isolation"] in {"repeatable read", "serializable"}
            and context["evaluated_at"].utcoffset() is not None
            and report.created_at <= context["evaluated_at"]
        )

        headers = conn.execute(
            f"""SELECT execution_id FROM {store.schema}.aip_route_eval_finalization_proof
                WHERE org_id=%s AND project_id=%s AND run_id=%s
                  AND report_id=%s AND report_revision=%s AND report_hash=%s""",
            (*scope.key, report.run_id, report.report_id, report.revision, report.content_hash),
        ).fetchall()
        _require(len(headers) == 1)
        proof = store.read(conn, scope, headers[0]["execution_id"])
        _require(
            proof is not None
            and (proof.run_id, proof.report_id, proof.report_revision, proof.report_hash)
            == (report.run_id, report.report_id, report.revision, report.content_hash)
            and proof.finalized_at <= context["evaluated_at"]
        )

        persisted_report = conn.execute(
            f"""SELECT * FROM {store.schema}.aip_eval_report_revision
                WHERE org_id=%s AND project_id=%s AND report_id=%s AND revision=%s""",
            (*scope.key, report.report_id, report.revision),
        ).fetchone()
        _require(persisted_report is not None)
        stored_report = AipEvalRunner._report_from_row(scope, persisted_report)
        _require(
            stored_report == report
            and compute_eval_report_hash(stored_report) == persisted_report["content_hash"]
        )

        run_row = conn.execute(
            f"""SELECT * FROM {store.schema}.aip_eval_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*scope.key, report.run_id),
        ).fetchone()
        _require(run_row is not None)
        run = AipEvalAuthorityStore()._run_from_row(run_row)
        _require(
            run.status is EvalRunStatus.SUCCEEDED
            and run.finished_at is not None
            and _run_matches_report(run, report)
        )
        event = conn.execute(
            f"""SELECT event_type,to_status,payload_hash,created_at
                FROM {store.schema}.aip_eval_run_event
                WHERE org_id=%s AND project_id=%s AND run_id=%s AND sequence=%s""",
            (*scope.key, report.run_id, run.version),
        ).fetchone()
        _require(
            event is not None
            and event["event_type"] == "run.succeeded"
            and event["to_status"] == "succeeded"
            and event["payload_hash"] == report.content_hash
            and event["created_at"] == run.finished_at
            and proof.finalized_at >= event["created_at"]
        )

        indexed = {(item.case_id, item.purpose): item for item in proof.calls}
        result_ids = [item.case_id for item in report.results]
        _require(
            len(indexed) == len(proof.calls) == len(report.results) * 2
            and len(result_ids) == len(set(result_ids))
            and set(result_ids) == {case_id for case_id, _ in indexed}
        )
        for result in report.results:
            judge = indexed[(result.case_id, "judge")].signed_case.claim
            _require(
                (result.actual_hash, result.expected_hash, result.passed, result.detail_code)
                == (
                    judge.target_output_hash,
                    judge.expected_hash,
                    judge.passed,
                    judge.detail_code,
                )
            )

        for item in proof.calls:
            evidence = store.journal.read(conn, scope, item.reservation_id)
            _require(_exact_journal(evidence, item, proof))
            reservation = conn.execute(
                f"""SELECT state,revision,actual_minor,usage_receipt_refs,
                    provider_request_receipt_ref,invocation_id
                    FROM {store.schema}.aip_budget_reservation
                    WHERE org_id=%s AND project_id=%s AND reservation_id=%s""",
                (*scope.key, item.reservation_id),
            ).fetchone()
            _require(
                reservation is not None
                and reservation["state"] == "settled"
                and int(reservation["revision"]) == item.budget_revision
                and int(reservation["actual_minor"]) == item.actual_minor
                and reservation["usage_receipt_refs"]
                == [exact_ref_payload(ref) for ref in item.usage_receipt_refs]
                and reservation["provider_request_receipt_ref"]
                == exact_ref_payload(item.provider_request_ref)
                and len(item.usage_receipt_refs) == 2
            )
            lineage = conn.execute(
                f"""SELECT event_id,lineage_id,root_type,root_id,sequence,event_type,
                    subject_ref,artifact_ref,payload_hash,quality,occurred_at,observed_at,
                    source_kind,source_id,source_hash
                    FROM {store.schema}.aip_lineage_event
                    WHERE org_id=%s AND project_id=%s AND event_id=%s""",
                (*scope.key, "route-eval-result:" + str(item.reservation_id)),
            ).fetchone()
            result = evidence["result"]
            lineage_id = str(reservation["invocation_id"])
            _require(
                lineage is not None
                and lineage["event_id"] == "route-eval-result:" + str(item.reservation_id)
                and lineage["lineage_id"] == lineage_id
                and lineage["root_type"] == "capability_invocation"
                and lineage["root_id"] == lineage_id
                and lineage["sequence"] == 1
                and lineage["event_type"] == "model"
                and lineage["subject_ref"] is None
                and lineage["artifact_ref"] is None
                and lineage["payload_hash"] == item.result_hash
                and lineage["quality"] == "measured"
                and lineage["occurred_at"] == result.observed_at
                and lineage["observed_at"] == result.observed_at
                and lineage["source_kind"] == "capability_provider_result"
                and lineage["source_id"] == str(item.reservation_id)
                and lineage["source_hash"] == item.result_hash
            )
            for index, ref in enumerate(item.usage_receipt_refs):
                usage = conn.execute(
                    f"""SELECT receipt_id,provider,provider_receipt_id,lineage_id,
                        usage_kind,quantity,unit,currency,quality,source_hash,observed_at
                        FROM {store.schema}.aip_usage_receipt
                        WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
                    (*scope.key, ref.resource_id),
                ).fetchone()
                _require(
                    _exact_usage(
                        usage,
                        ref,
                        result=result,
                        reservation=reservation,
                        index=index,
                    )
                )
        return VerifiedRouteEvalReportProof(
            report_id=report.report_id,
            report_hash=report.content_hash,
            proof=proof.model_copy(deep=True),
        )
    except RouteEvalReportProofRejected:
        raise
    except Exception as exc:
        raise RouteEvalReportProofRejected(
            "exact persisted Route Eval Report proof required"
        ) from exc


__all__ = [
    "RouteEvalReportProofRejected",
    "VerifiedRouteEvalReportProof",
    "read_verified_route_eval_report_from_persistence",
]
