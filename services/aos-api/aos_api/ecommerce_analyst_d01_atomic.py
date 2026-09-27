"""Unregistered A1 D01 coordinator: original lineage, sources and Owner share one tx.

This creates a queued AgentRun only.  It is not a Provider, budget, or Host
worker authorization and must not be wired until isolated PG gates pass.
"""
from __future__ import annotations

from datetime import datetime

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
        if (type(scope) is not TenantScope or type(request) is not CreateAgentRunRequest
                or type(packet) is not D01SourcePacket or type(task_run_id) is not str
                or not task_run_id or type(actor) is not str or not actor
                or type(occurred_at) is not datetime or occurred_at.utcoffset() is None
                or self.origin.context.analysis.scope != scope):
            raise ValueError('exact natural D01 issue context required')
        source_actor = getattr(getattr(self.origin.context.analysis, 'source', None), 'actor', None)
        if type(source_actor) is not str or not source_actor.strip() or source_actor != actor:
            raise PermissionError('original analysis actor differs from D01 issuer')
        exact_receipt = _analysis_exact_ref(
            receipt_ref, 'AnalysisRuntimeReceipt', receipt_required=True)
        exact_ref = exact_receipt.model_dump(mode='json', by_alias=True, exclude_none=True)
        with connect_serializable(scope) as conn:
            transaction = HostTransaction(conn)

            def current(origin):
                root = origin['analysisReceipt']
                if (root.get('receiptRef') != exact_ref
                        or root.get('phase') != 'PREPARING'
                        or root.get('taskRunRef', {}).get('resourceType') != 'TaskRun'
                        or root['taskRunRef'].get('resourceId') != task_run_id
                        or root.get('planRef', {}).get('resourceType') != 'PlanRevision'
                        or root['planRef'].get('resourceId') != request.run.plan_ref.resource_id
                        or datetime.fromisoformat(root['cutoffAt']) != packet.cutoff_at):
                    raise ValueError('D01 request differs from original analysis Receipt')
                tasks = AipTaskStore(TransactionBoundConnectFactory(transaction, scope))
                source = origin.get('context', {}).get('source', {})
                policy = source.get('policy', {}) if type(source) is dict else {}
                selected = policy.get('sourceSelectionRef') if type(policy) is dict else None
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
                approved_packet, _approval_receipt = D01SourceSelectionStore().read_current(
                    transaction, scope, task_run_id,
                    request.run.plan_ref.resource_id, actor, occurred_at)
                if (approved_packet.model_dump(mode='json', by_alias=True)
                        != packet.model_dump(mode='json', by_alias=True)):
                    raise ValueError('approved D01 selection differs from requested packet')
                borrowed = _BorrowedOwner(self.owner, transaction)
                issuer = NaturalD01Issuer(
                    tasks, borrowed,
                    # This callback only executes inside AnalysisContinuationOrigin.run_current,
                    # which rechecks the original chain before and after this entire write.
                    require_current_origin=lambda checked_scope, checked_run:
                        checked_scope == scope and checked_run == task_run_id,
                    require_current_sources=lambda checked_scope, checked_request, checked_packet,
                            checked_actor, checked_at: require_current_d01_sources_in_transaction(
                        transaction, checked_scope, checked_request, checked_packet,
                        checked_actor, checked_at),
                )
                result = issuer.issue(scope, task_run_id, request, packet,
                                      actor=actor, occurred_at=occurred_at)
                key = 'natural-d01:' + d01_agent_run_id(
                    scope, task_run_id, request.run.plan_ref.resource_id)
                stored = self.owner._receipt_row(transaction, scope, 'agent_run.create', key)
                if stored is None or self.owner._receipt_from_row(scope, stored) != result[1]:
                    raise ValueError('original D01 Owner Receipt readback differs')
                return result

            result = self.origin.run_current(conn, receipt_ref=exact_ref, execute=current)
            # A commit error is unknown.  Propagate; no second key or resend.
            conn.commit()
            return result
