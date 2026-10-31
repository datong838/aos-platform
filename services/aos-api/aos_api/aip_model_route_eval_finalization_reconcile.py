"""Read-only Route finalization reconciliation; never authorizes a retry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from aos_api.aip_budget_reservation_contracts import exact_ref_payload
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import (
    AssetType,EvalReportRevision,EvalRunEvent,EvalRunStatus,
)
from aos_api.aip_eval_runner import AipEvalRunner,compute_eval_report_hash
from aos_api.aip_model_route_eval_execution_journal import _canonical
from aos_api.aip_model_route_eval_finalization_proof import (
    RouteEvalFinalizationProof,RouteEvalFinalizationProofStore,
    canonical_route_eval_finalization_proof,
)
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class RouteEvalFinalizationReconciliation:
    state: Literal['COMPLETE','UNKNOWN','CONTRADICTORY']
    proof: RouteEvalFinalizationProof | None=None


def _native_read_only(conn) -> bool:
    return bool(type(conn) is psycopg.Connection and not conn.closed
        and conn.autocommit is False and conn.read_only is True
        and conn.row_factory is dict_row
        and conn.info.transaction_status==TransactionStatus.INTRANS
        and conn.pgconn.used_password
        and conn.info.get_parameters().get('require_auth')=='scram-sha-256')


def _exact_journal(evidence,item,proof):
    if evidence is None or evidence['result'] is None:return False
    command,result=evidence['command'],evidence['result'];claim=item.signed_case.claim
    _,command_hash=_canonical(command);_,result_hash=_canonical(result)
    if (command_hash!=item.command_hash or result_hash!=item.result_hash
        or (command.tenant,command.execution_id,command.case_id,command.purpose,
            command.call_key,command.target_call_key,command.manifest_hash,
            command.context_binding_hash,command.admission_hash,
            command.budget_request.approval_ref,command.reservation_ref)
           !=(item.tenant,item.execution_id,item.case_id,item.purpose,item.call_key,
              item.target_call_key,claim.manifest_hash,claim.context_binding_hash,
              proof.admission_hash,item.approval_ref,item.reservation_ref)
        or (result.provider_request_ref,result.provider_result_id)
           !=(item.provider_request_ref,item.provider_result_id)
        or command.input_hash!=claim.wire_input_hash
        or result.output_hash!=claim.output_hash):
        raise ValueError
    return True


def _exact_usage(row,ref,*,result,reservation,index):
    kind=('input_token','output_token')[index]
    quantity=(result.prompt_tokens,result.completion_tokens)[index]
    return bool(row is not None
        and row['receipt_id']==ref.resource_id
        and ref.content_hash==canonical_hash(dict(row),prefixed=True)
        and row['provider']==result.provider_id
        and row['provider_receipt_id']==f'{result.provider_result_id}:{index}:{kind}'
        and row['lineage_id']==str(reservation['invocation_id'])
        and row['usage_kind']==kind and row['quantity']==quantity
        and row['unit']=='token' and row['currency'] is None
        and row['quality']=='measured' and row['source_hash']==_canonical(result)[1]
        and row['observed_at']==result.observed_at)


def _run_matches_report(run,report):
    return bool(run.run_id==report.run_id and run.suite_ref==report.suite_ref
        and run.eval_contract_ref==report.eval_contract_ref
        and run.subject_artifact_ref==report.subject_artifact_ref
        and run.stage_attempt_ref==report.stage_attempt_ref
        and run.gate_policy_ref==report.gate_policy_ref
        and run.evidence_cutoff_at==report.evidence_cutoff_at
        and run.target==report.target and run.dataset==report.dataset and run.judge==report.judge)


def reconcile_route_eval_finalization(conn,*,expected_database,scope,proof,report,event,
        expected_run_version,proof_store=None):
    """Classify one expected durable outcome; UNKNOWN never permits resend."""
    unknown=RouteEvalFinalizationReconciliation('UNKNOWN')
    conflict=RouteEvalFinalizationReconciliation('CONTRADICTORY')
    store=proof_store or RouteEvalFinalizationProofStore()
    try:
        if (not _native_read_only(conn) or type(scope) is not TenantScope
            or scope.key!=('org-org','dev-project')
            or type(expected_database) is not str or not expected_database
            or type(proof) is not RouteEvalFinalizationProof
            or type(report) is not EvalReportRevision or type(event) is not EvalRunEvent
            or type(expected_run_version) is not int or isinstance(expected_run_version,bool)
            or expected_run_version<1):
            return conflict
        canonical_route_eval_finalization_proof(proof)
        if ((proof.tenant.org_id,proof.tenant.project_id)!=scope.key
            or (report.tenant.org_id,report.tenant.project_id)!=scope.key
            or report.target.asset_type is not AssetType.MODEL_ROUTE
            or compute_eval_report_hash(report)!=report.content_hash
            or (proof.run_id,proof.report_id,proof.report_revision,proof.report_hash)
               !=(report.run_id,report.report_id,report.revision,report.content_hash)
            or event.tenant!=report.tenant or event.run_id!=report.run_id
            or event.sequence!=expected_run_version+1
            or event.from_status is not EvalRunStatus.RUNNING
            or event.to_status is not EvalRunStatus.SUCCEEDED
            or event.event_type!='run.succeeded' or event.payload_hash!=report.content_hash
            or event.created_at<report.created_at or proof.finalized_at<event.created_at):
            return conflict
        context=conn.execute("""SELECT current_database() AS database,current_user AS role,
            current_setting('aos.org_id',true) AS org_id,
            current_setting('aos.project_id',true) AS project_id,
            current_setting('transaction_isolation') AS isolation,
            current_setting('transaction_read_only') AS readonly""").fetchone()
        if (context is None or context['database']!=expected_database
            or context['role']!='aos_runtime'
            or (context['org_id'],context['project_id'])!=scope.key
            or context['isolation'] not in {'repeatable read','serializable'}
            or context['readonly']!='on'):
            return conflict

        terminal=False;all_journal=True;all_lineage=True;all_settled=True;all_usage=True
        for item in proof.calls:
            evidence=store.journal.read(conn,scope,item.reservation_id)
            journal_complete=_exact_journal(evidence,item,proof);all_journal&=journal_complete
            reservation=conn.execute(f'''SELECT state,revision,actual_minor,usage_receipt_refs,
                provider_request_receipt_ref,invocation_id FROM {store.schema}.aip_budget_reservation
                WHERE org_id=%s AND project_id=%s AND reservation_id=%s''',
                (*scope.key,item.reservation_id)).fetchone()
            settled=reservation is not None and reservation['state']=='settled'
            if reservation is not None and reservation['state'] not in {'submitted','unknown','settled'}:
                return conflict
            lineage=conn.execute(f'''SELECT event_id,lineage_id,root_type,root_id,sequence,
                event_type,subject_ref,artifact_ref,payload_hash,quality,occurred_at,
                observed_at,source_kind,source_id,source_hash
                FROM {store.schema}.aip_lineage_event
                WHERE org_id=%s AND project_id=%s AND event_id=%s''',
                (*scope.key,'route-eval-result:'+str(item.reservation_id))).fetchone()
            lineage_complete=bool(journal_complete and reservation is not None and lineage is not None
                and lineage['event_id']=='route-eval-result:'+str(item.reservation_id)
                and lineage['lineage_id']==str(reservation['invocation_id'])
                and lineage['root_type']=='capability_invocation'
                and lineage['root_id']==str(reservation['invocation_id'])
                and lineage['sequence']==1 and lineage['event_type']=='model'
                and lineage['subject_ref'] is None and lineage['artifact_ref'] is None
                and lineage['payload_hash']==item.result_hash and lineage['quality']=='measured'
                and lineage['occurred_at']==evidence['result'].observed_at
                and lineage['observed_at']==evidence['result'].observed_at
                and lineage['source_kind']=='capability_provider_result'
                and lineage['source_id']==str(item.reservation_id)
                and lineage['source_hash']==item.result_hash)
            if lineage is not None:
                terminal=True
                if not lineage_complete:return conflict
            all_lineage&=lineage_complete
            if settled:
                terminal=True
                if (int(reservation['revision'])!=item.budget_revision
                    or int(reservation['actual_minor'])!=item.actual_minor
                    or reservation['usage_receipt_refs']!=[
                        exact_ref_payload(ref) for ref in item.usage_receipt_refs]
                    or reservation['provider_request_receipt_ref']!=exact_ref_payload(
                        item.provider_request_ref)):
                    return conflict
            all_settled&=settled
            call_usage=[]
            for index,ref in enumerate(item.usage_receipt_refs):
                row=conn.execute(f'''SELECT receipt_id,provider,provider_receipt_id,lineage_id,
                    usage_kind,quantity,unit,currency,quality,source_hash,observed_at
                    FROM {store.schema}.aip_usage_receipt
                    WHERE org_id=%s AND project_id=%s AND receipt_id=%s''',
                    (*scope.key,ref.resource_id)).fetchone()
                if row is not None:terminal=True
                complete=bool(journal_complete and reservation is not None
                    and _exact_usage(row,ref,result=evidence['result'],
                        reservation=reservation,index=index))
                if row is not None and not complete:return conflict
                call_usage.append(complete)
            usage_complete=bool(call_usage and all(call_usage))
            if any(call_usage) and not usage_complete:return conflict
            all_usage&=usage_complete

        run_row=conn.execute(f'''SELECT * FROM {store.schema}.aip_eval_run
            WHERE org_id=%s AND project_id=%s AND run_id=%s''',
            (*scope.key,proof.run_id)).fetchone()
        run_complete=False
        if run_row is not None:
            run=AipEvalAuthorityStore()._run_from_row(run_row)
            if not _run_matches_report(run,report):return conflict
            if run.status is EvalRunStatus.SUCCEEDED:
                terminal=True;run_complete=(run.version==expected_run_version+1
                    and run.finished_at==event.created_at)
                if not run_complete:return conflict
            elif run.status is EvalRunStatus.RUNNING:
                if run.version!=expected_run_version or run.finished_at is not None:return conflict
            else:return conflict

        event_row=conn.execute(f'''SELECT event_id,run_id,sequence,event_type,from_status,
            to_status,payload_hash,actor,created_at FROM {store.schema}.aip_eval_run_event
            WHERE org_id=%s AND project_id=%s AND run_id=%s AND sequence=%s''',
            (*scope.key,event.run_id,event.sequence)).fetchone()
        event_complete=False
        if event_row is not None:
            terminal=True
            stored_event=EvalRunEvent(tenant=report.tenant,**event_row)
            event_complete=stored_event==event
            if not event_complete:return conflict

        report_row=conn.execute(f'''SELECT * FROM {store.schema}.aip_eval_report_revision
            WHERE org_id=%s AND project_id=%s AND report_id=%s AND revision=%s''',
            (*scope.key,report.report_id,report.revision)).fetchone()
        report_complete=False
        if report_row is not None:
            terminal=True;stored_report=AipEvalRunner._report_from_row(scope,report_row)
            report_complete=(stored_report==report
                and compute_eval_report_hash(stored_report)==report_row['content_hash'])
            if not report_complete:return conflict

        header=store._header(conn,scope,proof.execution_id)
        calls=store._calls(conn,scope,proof.execution_id)
        sidecar_complete=False
        if header is not None or calls:
            terminal=True
            if header is None or not calls:return conflict
            sidecar_complete=store.read(conn,scope,proof.execution_id)==proof
            if not sidecar_complete:return conflict

        complete=(all_journal and all_lineage and all_settled and all_usage and run_complete
            and event_complete and report_complete and sidecar_complete)
        if complete:return RouteEvalFinalizationReconciliation('COMPLETE',proof.model_copy(deep=True))
        return conflict if terminal else unknown
    except Exception:
        return conflict


__all__=['RouteEvalFinalizationReconciliation','reconcile_route_eval_finalization']
