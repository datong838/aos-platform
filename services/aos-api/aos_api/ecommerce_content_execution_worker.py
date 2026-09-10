"""One committed Provider submission per durable content reservation."""
from dataclasses import dataclass, field
from typing import Callable

from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, canonical_hash
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal, ContentExecutionConflict
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory


@dataclass(frozen=True)
class PreparedContentInvocation:
    resolution: ModelRouteResolution
    prompt: str = field(repr=False)
    data_classification: str


class ContentExecutionFailure(RuntimeError):
    pass


class ContentExecutionWorker:
    def __init__(self, connect_factory, *, prepare: Callable, invoke: Callable, storage_schema='public'):
        self.connect = connect_factory
        self.prepare = prepare
        self.invoke = invoke
        self.journal = ContentExecutionJournal(storage_schema=storage_schema)
        self.schema = storage_schema

    def _budget(self, conn, scope):
        return AipBudgetReservationStore(
            TransactionBoundConnectFactory(HostTransaction(conn), scope),
            authority_schema=self.schema,
        )

    def run_one(self, scope, reservation_id):
        with self.connect(scope) as conn:
            reservation = self.journal._reservation(conn, scope, reservation_id)
            evidence = self.journal.read(conn, scope, reservation_id)
            if evidence is None:
                raise ContentExecutionConflict('content command unavailable')
            if evidence['result'] is not None:
                return {'status': 'RESULT_RECORDED', 'result': evidence['result']}
            if reservation['state'] in {'submitted', 'unknown'}:
                return {'status': 'RECONCILE_ONLY', 'result': None}
            if reservation['state'] != 'held':
                raise ContentExecutionConflict('content reservation cannot be submitted')
            prepared = self.prepare(conn, scope, evidence['command'])
            if not isinstance(prepared, PreparedContentInvocation):
                raise ContentExecutionConflict('trusted preparation required')
            resolution = prepared.resolution
            if resolution.readiness is not ModelRuntimeReadiness.READY or not prepared.prompt.strip() or not prepared.data_classification.strip():
                raise ContentExecutionConflict('prepared content is not ready')
            if (resolution.tenant.org_id, resolution.tenant.project_id) != scope.key:
                raise ContentExecutionConflict('prepared content tenant drifted')
            price = resolution.selected_price_snapshot
            stored_price = BudgetExactRef.model_validate(reservation['pricing_ref'])
            if price is None or (price.asset_id, price.revision, price.content_hash.removeprefix('sha256:')) != (
                stored_price.resource_id, stored_price.revision, stored_price.content_hash.removeprefix('sha256:')
            ):
                raise ContentExecutionConflict('prepared content price drifted')
            provider = resolution.selected_provider
            if provider is None:
                raise ContentExecutionConflict('prepared content provider unavailable')
            provider_ref = BudgetExactRef(resourceType=provider.asset_type, resourceId=provider.asset_id,
                revision=provider.revision, contentHash='sha256:'+provider.content_hash.removeprefix('sha256:'))
            submitted = self._budget(conn, scope).submit(scope, reservation_id, provider_ref=provider_ref,
                provider_idempotency_hash=canonical_hash({'command': evidence['command'], 'provider': provider.model_dump(mode='json',by_alias=True)}),
                actor='ecommerce-content-worker')
            if submitted.replayed:
                return {'status': 'RECONCILE_ONLY', 'result': None}
            request_ref = submitted.provider_request_receipt_ref.model_dump(mode='json',by_alias=True,exclude_none=True)
            conn.commit()
        # No caller-owned transaction remains open across the remote request.
        try:
            result = self.invoke(resolution, prepared.prompt, prepared.data_classification)
        except Exception:
            try:
                with self.connect(scope) as conn:
                    self._budget(conn, scope).mark_unknown(scope, reservation_id, actor='ecommerce-content-worker')
            except Exception:
                raise ContentExecutionFailure('provider outcome unknown; reconciliation persistence failed') from None
            raise ContentExecutionFailure('provider outcome unknown; reconciliation required') from None
        try:
            with self.connect(scope) as conn:
                recorded = self.journal.record_result(conn, scope, reservation_id,
                    provider_request_ref=request_ref, result=result)
                conn.commit()
        except Exception:
            raise ContentExecutionFailure('provider result persistence failed; do not resubmit') from None
        return {'status': 'RESULT_RECORDED', 'result': recorded}
