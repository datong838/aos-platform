"""W7-08 service joining media Jobs to finance authority without side effects."""
from __future__ import annotations

from collections.abc import Callable

from aos_api.aip_media_finance_contracts import (
    BindMediaUsageRequest,
    MediaFinanceEventKind,
    MediaFinanceSnapshot,
    ObserveMediaCancelRequest,
    PrepareMediaFinanceRequest,
    SettleMediaFinanceRequest,
    TransitionMediaCapacityRequest,
)
from aos_api.aip_media_finance_store import AipMediaFinanceStore, MediaFinanceDependencyBlocked
from aos_api.aip_media_provider_job_contracts import MediaJobStatus
from aos_api.aip_media_provider_job_store import AipMediaProviderJobStore
from aos_api.aip_budget_store import AipBudgetAuthorityStore, BudgetStoreError
from aos_api.aip_model_capacity_authority import AipModelCapacityAuthorityStore, CapacityPoolAuthorityError
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.tenant_scope import TenantScope


ExactRefValidator = Callable[[TenantScope, ExactRevisionRef], bool]


class AipMediaFinanceService:
    def __init__(
        self,
        *,
        store: AipMediaFinanceStore | None = None,
        job_store: AipMediaProviderJobStore | None = None,
        capacity_validator: ExactRefValidator | None = None,
        budget_validator: ExactRefValidator | None = None,
        usage_validator: ExactRefValidator | None = None,
        decision_validator: ExactRefValidator | None = None,
        capacity_authority: AipModelCapacityAuthorityStore | None = None,
        budget_authority: AipBudgetAuthorityStore | None = None,
    ) -> None:
        self._store = store or AipMediaFinanceStore()
        self._job_store = job_store or AipMediaProviderJobStore()
        self._capacity_authority = capacity_authority or AipModelCapacityAuthorityStore()
        self._budget_authority = budget_authority or AipBudgetAuthorityStore()
        self._capacity_validator = capacity_validator or self._validate_capacity_ref
        self._budget_validator = budget_validator or self._validate_budget_ref
        self._usage_validator = usage_validator
        self._decision_validator = decision_validator

    def prepare(self, scope: TenantScope, actor: str, key: str, body: PrepareMediaFinanceRequest) -> MediaFinanceSnapshot:
        self._require(scope, body.capacity_pool_ref, self._capacity_validator, "MEDIA_CAPACITY_POOL_REF_BLOCKED")
        self._require(scope, body.budget_revision_ref, self._budget_validator, "MEDIA_BUDGET_REVISION_REF_BLOCKED")
        job = self._job_store.get_job(scope, body.job_id)
        if job.status is not MediaJobStatus.PREPARED:
            raise MediaFinanceDependencyBlocked("MEDIA_FINANCE_PREPARE_REQUIRES_PREPARED_JOB")
        events = self._job_store.list_events(scope, body.job_id)
        return self._store.prepare(scope, actor, key, body, job, events[-1])

    def consume_capacity(self, scope: TenantScope, actor: str, finance_id: str, key: str, body: TransitionMediaCapacityRequest) -> MediaFinanceSnapshot:
        return self._store.append(scope, actor, key, finance_id, MediaFinanceEventKind.CAPACITY_CONSUMED, body)

    def release_capacity(self, scope: TenantScope, actor: str, finance_id: str, key: str, body: TransitionMediaCapacityRequest) -> MediaFinanceSnapshot:
        return self._store.append(scope, actor, key, finance_id, MediaFinanceEventKind.CAPACITY_RELEASED, body)

    def observe_cancel(self, scope: TenantScope, actor: str, finance_id: str, key: str, body: ObserveMediaCancelRequest) -> MediaFinanceSnapshot:
        return self._store.append(scope, actor, key, finance_id, MediaFinanceEventKind.CANCEL_OBSERVED, body)

    def bind_usage(self, scope: TenantScope, actor: str, finance_id: str, key: str, body: BindMediaUsageRequest) -> MediaFinanceSnapshot:
        self._require(scope, body.usage_receipt_ref, self._usage_validator, "MEDIA_USAGE_RECEIPT_REF_BLOCKED")
        return self._store.append(scope, actor, key, finance_id, MediaFinanceEventKind.USAGE_BOUND, body)

    def settle(self, scope: TenantScope, actor: str, finance_id: str, key: str, body: SettleMediaFinanceRequest) -> MediaFinanceSnapshot:
        self._require(scope, body.decision_ref, self._decision_validator, "MEDIA_SETTLEMENT_DECISION_REF_BLOCKED")
        return self._store.append(scope, actor, key, finance_id, MediaFinanceEventKind.SETTLED, body)

    @staticmethod
    def _require(scope: TenantScope, ref: ExactRevisionRef, validator: ExactRefValidator | None, code: str) -> None:
        if validator is None or not validator(scope, ref):
            raise MediaFinanceDependencyBlocked(code)

    def _validate_capacity_ref(self, scope: TenantScope, ref: ExactRevisionRef) -> bool:
        try:
            item = self._capacity_authority.get(scope, ref.resource_id, ref.revision)
        except CapacityPoolAuthorityError:
            return False
        return item.content_hash == ref.content_hash and item.lifecycle == "active"

    def _validate_budget_ref(self, scope: TenantScope, ref: ExactRevisionRef) -> bool:
        try:
            item = self._budget_authority.get(scope, ref.resource_id, ref.revision)
        except BudgetStoreError:
            return False
        return item.content_hash == ref.content_hash and item.lifecycle.value == "active"


__all__ = ["AipMediaFinanceService"]
