"""Default-off caller-owned Route ending; never dispatches a Provider."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json

from psycopg import sql

from aos_api.aip_budget_reservation_contracts import BudgetExactRef,BudgetReservationState
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore,canonical_hash
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import (
    AssetType,EvalReportRevision,EvalRunAuthorityRecord,EvalRunEvent,EvalRunStatus,LineageEvent,
    UsageReceiptIngestRequest,
)
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.aip_eval_writer_atomic import _persist_eval_report_revision_with_connection
from aos_api.aip_model_route_eval_finalization_proof import (
    RouteEvalFinalizationConflict,RouteEvalFinalizationProof,
    RouteEvalFinalizationProofStore,canonical_route_eval_finalization_proof,
)
from aos_api.aip_model_route_eval_execution_journal import _canonical
from aos_api.aip_model_route_eval_owner import (
    PresentedRouteEvalCase,_require_native_connection,
    prepare_route_eval_presented_case_bundle,
)
from aos_api.aip_model_route_eval_signatures import _manifest
from aos_api.aip_telemetry_usage_service import AipTelemetryUsageService
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope


class RouteEvalAtomicFinalizationConflict(RuntimeError):
    """Fail-closed category; never embeds Provider payloads or credentials."""


def _payload(value):
    if type(value) is str:return json.loads(value)
    return value


def _preflight_report(proof,manifest_bytes,report,event,expected_run_version):
    try:
        canonical_route_eval_finalization_proof(proof)
        if (type(report) is not EvalReportRevision or type(event) is not EvalRunEvent
            or type(expected_run_version) is not int or isinstance(expected_run_version,bool)
            or expected_run_version<1 or report.target.asset_type is not AssetType.MODEL_ROUTE
            or compute_eval_report_hash(report)!=report.content_hash
            or (proof.run_id,proof.report_id,proof.report_revision,proof.report_hash)
               !=(report.run_id,report.report_id,report.revision,report.content_hash)
            or event.run_id!=report.run_id or event.from_status is not EvalRunStatus.RUNNING
            or event.to_status is not EvalRunStatus.SUCCEEDED
            or event.event_type!='run.succeeded' or event.payload_hash!=report.content_hash
            or event.tenant!=report.tenant or event.created_at.utcoffset() is None
            or report.created_at.utcoffset() is None
            or report.created_at>event.created_at or proof.finalized_at<event.created_at):
            raise ValueError
        body=_manifest(manifest_bytes);context=body['context']
        run=EvalRunAuthorityRecord.model_validate(context['run'])
        if ('routeApplication' not in body
            or body['executionId']!=proof.execution_id
            or hashlib.sha256(manifest_bytes).hexdigest()!=proof.manifest_hash
            or body['contextBindingHash']!=proof.context_binding_hash
            or expected_run_version!=run.version or event.sequence!=run.version+1
            or (report.tenant.org_id,report.tenant.project_id)!=('org-org','dev-project')
            or (report.run_id,report.suite_ref.model_dump(mode='json',by_alias=True),
                None if report.eval_contract_ref is None else report.eval_contract_ref.model_dump(mode='json',by_alias=True),
                None if report.subject_artifact_ref is None else report.subject_artifact_ref.model_dump(mode='json',by_alias=True),
                None if report.stage_attempt_ref is None else report.stage_attempt_ref.model_dump(mode='json',by_alias=True),
                None if report.gate_policy_ref is None else report.gate_policy_ref.model_dump(mode='json',by_alias=True),
                report.evidence_cutoff_at,
                report.target.model_dump(mode='json',by_alias=True),
                report.dataset.model_dump(mode='json',by_alias=True),
                report.judge.model_dump(mode='json',by_alias=True))
               !=(run.run_id,run.suite_ref.model_dump(mode='json',by_alias=True),
                  None if run.eval_contract_ref is None else run.eval_contract_ref.model_dump(mode='json',by_alias=True),
                  None if run.subject_artifact_ref is None else run.subject_artifact_ref.model_dump(mode='json',by_alias=True),
                  None if run.stage_attempt_ref is None else run.stage_attempt_ref.model_dump(mode='json',by_alias=True),
                  None if run.gate_policy_ref is None else run.gate_policy_ref.model_dump(mode='json',by_alias=True),
                  run.evidence_cutoff_at,
                  run.target.model_dump(mode='json',by_alias=True),
                  run.dataset.model_dump(mode='json',by_alias=True),
                  run.judge.model_dump(mode='json',by_alias=True))):
            raise ValueError
        indexed={(item.case_id,item.purpose):item for item in proof.calls}
        result_ids=[result.case_id for result in report.results]
        if (len(report.results)*2!=len(proof.calls)
            or len(set(result_ids))!=len(result_ids)
            or set(result_ids)!={item.case_id for item in proof.calls}):
            raise ValueError
        for result in report.results:
            judge=indexed[(result.case_id,'judge')].signed_case.claim
            if (
                result.actual_hash,
                result.expected_hash,
                result.passed,
                result.detail_code,
            ) != (
                judge.target_output_hash,
                judge.expected_hash,
                judge.passed,
                judge.detail_code,
            ):
                raise ValueError
        return body
    except (ValueError,TypeError,KeyError,AttributeError,json.JSONDecodeError):
        raise RouteEvalAtomicFinalizationConflict(
            'exact Route Report and success event required') from None


class RouteEvalUsageRecorder:
    """Derive exact per-invocation token facts from one persisted r5 result."""

    def __init__(self,proof_store):self.proof_store=proof_store

    def record(self,conn,scope,item,evidence,reservation):
        result=evidence['result'];_,result_hash=_canonical(result)
        lineage=str(reservation['invocation_id']);at=result.observed_at
        bound=TransactionBoundConnectFactory(HostTransaction(conn),scope)
        owner=AipEvalAuthorityStore(bound)
        owner.append_lineage_event(scope,LineageEvent(
            tenant={'orgId':scope.org_id,'projectId':scope.project_id},
            eventId='route-eval-result:'+str(item.reservation_id),lineageId=lineage,
            rootType='capability_invocation',rootId=lineage,sequence=1,eventType='model',
            payloadHash=result_hash,quality='measured',occurredAt=at,observedAt=at,
            sourceKind='capability_provider_result',sourceId=str(item.reservation_id),
            sourceHash=result_hash))
        service=AipTelemetryUsageService(owner);refs=[]
        values=(('input_token',result.prompt_tokens),('output_token',result.completion_tokens))
        for index,(kind,quantity) in enumerate(values):
            receipt=service.ingest_usage(scope,UsageReceiptIngestRequest(
                provider=result.provider_id,
                providerReceiptId=f'{result.provider_result_id}:{index}:{kind}',
                lineageId=lineage,usageKind=kind,quantity=quantity,unit='token',
                quality='measured',sourceHash=result_hash,observedAt=at))
            row=conn.execute(f'''SELECT receipt_id,provider,provider_receipt_id,lineage_id,
                usage_kind,quantity,unit,currency,quality,source_hash,observed_at
                FROM {self.proof_store.schema}.aip_usage_receipt
                WHERE org_id=%s AND project_id=%s AND receipt_id=%s''',
                (*scope.key,receipt.receipt_id)).fetchone()
            if row is None:raise RouteEvalAtomicFinalizationConflict('Route Usage readback required')
            refs.append(BudgetExactRef(resourceType='UsageReceipt',resourceId=receipt.receipt_id,
                revision=1,contentHash=canonical_hash(dict(row),prefixed=True)))
        return result_hash,tuple(refs)


def finish_route_eval_with_connection(conn,*,expected_database,scope,proof,
        manifest_bytes,presented_cases,checked_at,revoked_identity_ids,
        report,event,expected_run_version,proof_store=None):
    """Finish existing Route results in one savepoint; caller owns outer commit.

    Provider dispatch is intentionally absent. Commit uncertainty must use the
    separate read-only reconciliation path and must never call this again.
    """
    store=proof_store or RouteEvalFinalizationProofStore()
    try:
        if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
            or type(proof) is not RouteEvalFinalizationProof
            or type(expected_database) is not str or not expected_database
            or type(presented_cases) is not tuple
            or any(type(x) is not PresentedRouteEvalCase for x in presented_cases)
            or getattr(conn,'autocommit',None) is not False):
            raise ValueError
        _require_native_connection(conn)
        context=conn.execute("""SELECT current_database() AS database,session_user AS login,
            current_user AS role,current_setting('transaction_isolation') AS isolation,
            current_setting('transaction_read_only') AS readonly,
            current_setting('aos.org_id',true) AS org_id,
            current_setting('aos.project_id',true) AS project_id,
            transaction_timestamp() AS evaluated_at""").fetchone()
        if (context is None or context['database']!=expected_database
            or context['role']!='aos_runtime' or context['isolation']!='serializable'
            or context['readonly']!='off' or (context['org_id'],context['project_id'])!=scope.key
            or type(context['login']) is not str or not context['login']):
            raise ValueError
        _preflight_report(proof,manifest_bytes,report,event,expected_run_version)
        prepare_route_eval_presented_case_bundle(manifest_bytes,checked_at=checked_at,
            revoked_identity_ids=revoked_identity_ids,cases=presented_cases)
        indexed={(x.envelope.claim.case_id,x.envelope.claim.purpose):x for x in presented_cases}
        if len(indexed)!=len(presented_cases):raise ValueError
        with conn.transaction():
            prepared=[]
            for item in sorted(proof.calls,key=lambda x:str(x.reservation_id)):
                evidence=store.journal.read(conn,scope,item.reservation_id)
                if evidence is None or evidence['result'] is None:raise ValueError
                reservation=conn.execute(f'''SELECT * FROM {store.schema}.aip_budget_reservation
                    WHERE org_id=%s AND project_id=%s AND reservation_id=%s FOR UPDATE''',
                    (*scope.key,item.reservation_id)).fetchone()
                if reservation is None or reservation['state'] not in {'submitted','unknown'}:
                    raise ValueError
                price_ref=BudgetExactRef.model_validate(_payload(reservation['pricing_ref']))
                price=conn.execute(f'''SELECT payload FROM {store.schema}.aip_model_price_snapshot_revision
                    WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s AND revision=%s''',
                    (*scope.key,price_ref.resource_id,price_ref.revision)).fetchone()
                price_payload={} if price is None else _payload(price['payload'])
                if price is None or price_payload.get('developmentCostAuthorization') is not None:
                    raise ValueError
                if (item.case_id,item.purpose) not in indexed:raise ValueError
                prepared.append((item,evidence,reservation))
            recorder=RouteEvalUsageRecorder(store);derived=[]
            for item,evidence,reservation in prepared:
                result_hash,refs=recorder.record(conn,scope,item,evidence,reservation)
                derived.append((item,evidence,reservation,result_hash,refs))
            bound=TransactionBoundConnectFactory(HostTransaction(conn),scope)
            budget=AipBudgetReservationStore(bound,authority_schema=store.schema)
            for item,evidence,reservation,result_hash,refs in derived:
                actual=budget._actual_from_usage(conn,scope,reservation,refs)
                evidence_ref=BudgetExactRef(resourceType='RouteEvalExecutionResult',
                    resourceId=str(item.reservation_id),revision=1,
                    contentHash='sha256:'+result_hash)
                result=budget.settle(scope,item.reservation_id,actual_minor=actual,
                    provider_result_hash=result_hash,usage_receipt_refs=refs,
                    evidence_refs=(evidence_ref,),actor='aos-route-eval-finalizer')
                if (result.state is not BudgetReservationState.SETTLED
                    or result.reservation_ref.revision!=item.budget_revision
                    or result.actual_minor!=item.actual_minor
                    or tuple(result.usage_receipt_refs)!=item.usage_receipt_refs
                    or refs!=item.usage_receipt_refs):
                    raise RouteEvalAtomicFinalizationConflict(
                        'Route settlement differs from expected proof')
            authority=AipEvalAuthorityStore()
            authority._transition_eval_run_with_connection(conn,scope,event,
                expected_version=expected_run_version)
            _persist_eval_report_revision_with_connection(conn,report)
            conn.execute('SET LOCAL ROLE aos_route_eval_finalizer')
            stored=store.persist(conn,scope,proof,manifest_bytes=manifest_bytes,
                presented_cases=presented_cases,checked_at=checked_at,
                revoked_identity_ids=revoked_identity_ids)
            conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(context['login'])))
            if stored!=proof:raise RouteEvalAtomicFinalizationConflict('Route proof readback drifted')
        return stored
    except RouteEvalAtomicFinalizationConflict:
        raise
    except (ValueError,TypeError,KeyError,AttributeError,RuntimeError,json.JSONDecodeError) as exc:
        raise RouteEvalAtomicFinalizationConflict(
            'atomic Route finalization prerequisites changed') from exc
