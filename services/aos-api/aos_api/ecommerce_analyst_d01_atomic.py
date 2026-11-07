"""Unregistered A1 D01 coordinator: original lineage, sources and Owner share one tx.

This creates a queued AgentRun only.  It is not a Provider, budget, or Host
worker authorization and must not be wired until isolated PG gates pass.
"""
from __future__ import annotations

from datetime import datetime
from contextlib import nullcontext

from aos_api.aip_contracts import ResourceRef
from aos_api.aip_agent_registry_contracts import CreateAgentRunRequest
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_analysis_continuation_origin import AnalysisContinuationOrigin
from aos_api.ecommerce_analyst_d01_issuer import (
    D01SourcePacket, NaturalD01Issuer, d01_agent_run_id,
    require_current_d01_sources_in_transaction,
)
from aos_api.ecommerce_analyst_d01_source_selection_store import D01SourceSelectionStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    TransactionBoundConnectFactory, _analysis_exact_ref,
)
from aos_api.ecommerce_growth_runtime_connection import connect_serializable
from aos_api.tenant_scope import TenantScope


def _compile_approved_inputs(request, packet):
    """Compile only the original approved packet, without granting authority."""
    if type(request) is not CreateAgentRunRequest or type(packet) is not D01SourcePacket:
        raise TypeError('exact D01 request and approved packet required')
    if request.run.input_refs:
        raise ValueError('approved D01 compilation requires an empty input template')
    packet = D01SourcePacket.model_validate(packet.model_dump(mode='python'))
    sources = [packet.method_ref, packet.eval_ref,
               *[item.metric_ref for item in packet.metric_sources],
               *[item.result_ref for item in packet.metric_sources],
               *[item.source_request.bundle_ref for item in packet.metric_sources]]
    hashes = {}
    for ref in sources:
        key = (ref.resource_type, ref.resource_id, str(ref.revision), 'postgresql')
        digest = ref.content_hash.removeprefix('sha256:')
        if key in hashes and hashes[key] != digest:
            raise ValueError('conflicting approved D01 source hashes')
        hashes[key] = digest
    value = request.model_dump(mode='python')
    value['run']['input_refs'] = [ResourceRef(resource_type=kind, resource_id=identity,
        revision=revision, authority=authority) for kind, identity, revision, authority
        in sorted(hashes)]
    return CreateAgentRunRequest.model_validate(value)


class _BorrowedOwner:
    def __init__(self, owner: AipAgentRunService, transaction: HostTransaction):
        self.owner, self.transaction = owner, transaction

    def create(self, scope, request, *, idempotency_key, actor, occurred_at):
        return self.owner._create_in_transaction(
            self.transaction, scope, request, idempotency_key=idempotency_key,
            actor=actor, occurred_at=occurred_at,
        )


class NaturalD01AtomicCoordinator:
    def __init__(self, origin: AnalysisContinuationOrigin, owner: AipAgentRunService):
        if type(origin) is not AnalysisContinuationOrigin or type(owner) is not AipAgentRunService:
            raise TypeError('exact original analysis and AIP Owner required')
        self.origin, self.owner = origin, owner

    def issue(self, scope: TenantScope, task_run_id: str, request: CreateAgentRunRequest,
              packet: D01SourcePacket, *, receipt_ref: dict, actor: str,
              occurred_at: datetime):
        if type(packet) is not D01SourcePacket:
            raise ValueError('exact natural D01 issue context required')
        return self._issue(scope, task_run_id, request, packet,
                           receipt_ref=receipt_ref, actor=actor, occurred_at=occurred_at)

    def issue_approved(self, scope: TenantScope, task_run_id: str,
                       request: CreateAgentRunRequest, *, receipt_ref: dict,
                       actor: str, occurred_at: datetime):
        """Read the original approved packet inside the original issue transaction.

        This is not source approval or execution admission. The existing Issuer
        and Owner still revalidate all authority before creating a queued Run.
        """
        return self._issue(scope, task_run_id, request, None,
                           receipt_ref=receipt_ref, actor=actor, occurred_at=occurred_at)

    def issue_approved_with_formal_source(
            self, scope, task_run_id, request, *, source_service, parent_request,
            source_ref, installation_id, installation_revision, installation_etag,
            receipt_ref, actor, occurred_at):
        """Keep original Source locks through the original queued-Run commit."""
        from aos_api.aip_formal_source_disclosure import FormalSourceDisclosureService
        if type(source_service) is not FormalSourceDisclosureService:
            raise TypeError('original formal Source service required')
        with source_service.source_transaction(
                scope, actor, parent_request, source_ref=source_ref,
                installation_id=installation_id,
                installation_revision=installation_revision,
                installation_etag=installation_etag) as (conn, store):
            return self._issue(
                scope, task_run_id, request, None, receipt_ref=receipt_ref,
                actor=actor, occurred_at=occurred_at,
                native_connection=conn, source_store=store)

    def issue_approved_compiled_with_formal_source(
            self, scope, task_run_id, request, *, source_service, parent_request,
            source_ref, installation_id, installation_revision, installation_etag,
            receipt_ref, actor, occurred_at):
        """Compile the approved inventory inside the original Source transaction."""
        from aos_api.aip_formal_source_disclosure import FormalSourceDisclosureService
        if type(source_service) is not FormalSourceDisclosureService:
            raise TypeError('original formal Source service required')
        if type(request) is not CreateAgentRunRequest:
            raise TypeError('exact D01 request template required')
        request = CreateAgentRunRequest.model_validate(request.model_dump(mode='python'))
        if request.run.input_refs:
            raise ValueError('approved D01 compilation requires an empty input template')
        with source_service.source_transaction(
                scope, actor, parent_request, source_ref=source_ref,
                installation_id=installation_id,
                installation_revision=installation_revision,
                installation_etag=installation_etag) as (conn, store):
            return self._issue(
                scope, task_run_id, request, None, receipt_ref=receipt_ref,
                actor=actor, occurred_at=occurred_at,
                native_connection=conn, source_store=store,
                compile_approved_inputs=True)

    def _issue(self, scope, task_run_id, request, packet, *, receipt_ref, actor,
               occurred_at, native_connection=None, source_store=None,
               compile_approved_inputs=False):
        if (type(scope) is not TenantScope or type(request) is not CreateAgentRunRequest
                or (packet is not None and type(packet) is not D01SourcePacket)
                or type(task_run_id) is not str
                or not task_run_id or type(actor) is not str or not actor
                or type(occurred_at) is not datetime or occurred_at.utcoffset() is None
                or self.origin.context.analysis.scope != scope):
            raise ValueError('exact natural D01 issue context required')
        if (type(compile_approved_inputs) is not bool
                or (compile_approved_inputs and (
                    packet is not None or native_connection is None or source_store is None))):
            raise TypeError('approved input compilation requires original formal transaction')
        source_actor = getattr(getattr(self.origin.context.analysis, 'source', None), 'actor', None)
        if type(source_actor) is not str or not source_actor.strip() or source_actor != actor:
            raise PermissionError('original analysis actor differs from D01 issuer')
        exact_receipt = _analysis_exact_ref(
            receipt_ref, 'AnalysisRuntimeReceipt', receipt_required=True)
        exact_ref = exact_receipt.model_dump(mode='json', by_alias=True, exclude_none=True)
        if native_connection is not None:
            from aos_api.aip_metric_query_evidence import _production
            if source_store is None:
                raise TypeError('live original formal Source store required')
            _production(native_connection, scope, source_store)
        elif source_store is not None:
            raise TypeError('original formal Source connection required')
        connection = (nullcontext(native_connection) if native_connection is not None
                      else connect_serializable(scope))
        with connection as conn:
            transaction = HostTransaction(conn)

            def current(origin):
                nonlocal request
                root = origin['analysisReceipt']
                selected_packet = packet
                if selected_packet is None:
                    selected_packet, _approval = D01SourceSelectionStore().read_current(
                        transaction, scope, task_run_id,
                        request.run.plan_ref.resource_id, actor, occurred_at)
                    if type(selected_packet) is not D01SourcePacket:
                        raise ValueError('original approved D01 packet unavailable')
                if compile_approved_inputs:
                    request = _compile_approved_inputs(request, selected_packet)
                if (root.get('receiptRef') != exact_ref
                        or root.get('phase') != 'PREPARING'
                        or root.get('taskRunRef', {}).get('resourceType') != 'TaskRun'
                        or root['taskRunRef'].get('resourceId') != task_run_id
                        or root.get('planRef', {}).get('resourceType') != 'PlanRevision'
                        or root['planRef'].get('resourceId') != request.run.plan_ref.resource_id
                        or datetime.fromisoformat(root['cutoffAt']) != selected_packet.cutoff_at):
                    raise ValueError('D01 request differs from original analysis Receipt')
                tasks = AipTaskStore(TransactionBoundConnectFactory(transaction, scope))
                source = origin.get('context', {}).get('source', {})
                policy = source.get('policy', {}) if type(source) is dict else {}
                selected = policy.get('sourceSelectionRef') if type(policy) is dict else None
                # Existing policy serializers retain the optional null receiptId.
                # Normalize only that representation; keep the strict exact-ref guard.
                if type(selected) is dict and 'receiptId' in selected and selected['receiptId'] is None:
                    selected = {key: value for key, value in selected.items() if key != 'receiptId'}
                try:
                    original_selection = _analysis_exact_ref(
                        selected, 'SourceSelectionRevision')
                except ValueError as exc:
                    raise ValueError('original source selection is unavailable') from exc
                expected_selection = ResourceRef(
                    resourceType='SourceSelectionRevision',
                    resourceId=original_selection.resource_id,
                    revision=str(original_selection.revision),
                    authority='postgresql',
                )
                if tasks.timeline(scope, task_run_id).task.selection_ref != expected_selection:
                    raise ValueError('Task source selection differs from original analysis')
                def approved_selection(checked_scope, checked_run, checked_request,
                                       checked_packet, checked_actor, checked_at):
                    if (checked_scope != scope or checked_run != task_run_id
                            or checked_request != request or checked_actor != actor
                            or checked_at != occurred_at):
                        raise ValueError('approved D01 selection context differs')
                    approved_packet, _approval_receipt = D01SourceSelectionStore().read_current(
                        transaction, scope, task_run_id,
                        request.run.plan_ref.resource_id, actor, occurred_at)
                    if (approved_packet.model_dump(mode='json', by_alias=True)
                            != checked_packet.model_dump(mode='json', by_alias=True)):
                        raise ValueError('approved D01 selection differs from requested packet')
                    return True
                borrowed = _BorrowedOwner(self.owner, transaction)
                issuer = NaturalD01Issuer(
                    tasks, borrowed,
                    # This callback only executes inside AnalysisContinuationOrigin.run_current,
                    # which rechecks the original chain before and after this entire write.
                    require_current_origin=lambda checked_scope, checked_run:
                        checked_scope == scope and checked_run == task_run_id,
                    require_current_selection=approved_selection,
                    require_current_sources=lambda checked_scope, checked_request, checked_packet,
                            checked_actor, checked_at: require_current_d01_sources_in_transaction(
                        transaction, checked_scope, checked_request, checked_packet,
                        checked_actor, checked_at,
                        **({'source_store': source_store} if source_store is not None else {})),
                )
                result = issuer.issue(scope, task_run_id, request, selected_packet,
                                      actor=actor, occurred_at=occurred_at)
                key = 'natural-d01:' + d01_agent_run_id(
                    scope, task_run_id, request.run.plan_ref.resource_id)
                stored = self.owner._receipt_row(transaction, scope, 'agent_run.create', key)
                if stored is None or self.owner._receipt_from_row(scope, stored) != result[1]:
                    raise ValueError('original D01 Owner Receipt readback differs')
                return result

            result = self.origin.run_current(conn, receipt_ref=exact_ref, execute=current)
            if source_store is not None:
                source_store._formal_source_authority.validate_commit(conn, scope)
            # A commit error is unknown.  Propagate; no second key or resend.
            conn.commit()
            return result
