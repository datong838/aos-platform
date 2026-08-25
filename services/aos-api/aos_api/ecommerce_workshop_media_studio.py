"""Tenant-bound GET-only W2-05 media-studio contract shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_media_studio_contracts import (
    MEDIA_STUDIO_LIFECYCLE_SCHEMA_VERSION,
    MEDIA_STUDIO_CUMULATIVE_SCHEMA_VERSION,
    MEDIA_STUDIO_PUBLISH_SCHEMA_VERSION,
    MEDIA_STUDIO_PROVIDER_SCHEMA_VERSION,
    MEDIA_STUDIO_SCHEMA_VERSION,
    MediaAxisReadiness,
    MediaBlocker,
    MediaCountLedger,
    MediaFinanceContribution,
    MediaPageInfo,
    MediaProviderExactRef,
    MediaProviderJobContribution,
    MediaReadinessAxis,
    MediaReadinessStatus,
    MediaStudioSlice,
    MediaStudioSliceId,
    WorkshopMediaStudioViewEnvelope,
)
from aos_api.ecommerce_workshop_media_studio_lifecycle import (
    EcommerceWorkshopMediaStudioLifecycle,
    MediaStudioLifecycleConflict,
    MediaStudioLifecycleError,
)
from aos_api.ecommerce_workshop_media_publish import EcommerceWorkshopMediaPublish
from aos_api.ecommerce_workshop_media_cumulative import EcommerceWorkshopMediaCumulative
from aos_api.aip_media_finance_store import AipMediaFinanceStore, MediaFinanceError
from aos_api.aip_media_provider_job_store import AipMediaProviderJobStore, MediaProviderJobError
from aos_api.aip_action_store import AipActionStoreError
from aos_api.aip_production_contract_store import ProductionContractError
from aos_api.ecommerce_workshop_media_studio_reader import (
    MediaStudioCanonicalReader,
    MediaStudioReadError,
    validate_observation,
)
from aos_api.tenant_scope import TenantScope


Clock = Callable[[], datetime]


class EcommerceWorkshopMediaStudio:
    """Describe current authority gaps without promoting target state."""

    def __init__(self, *, reader: MediaStudioCanonicalReader | None = None, provider_job_store: AipMediaProviderJobStore | None = None, media_finance_store: AipMediaFinanceStore | None = None, lifecycle: EcommerceWorkshopMediaStudioLifecycle | None = None, publisher: EcommerceWorkshopMediaPublish | None = None, cumulative: EcommerceWorkshopMediaCumulative | None = None, clock: Clock | None = None) -> None:
        self._reader = reader
        self._provider_job_store = provider_job_store
        self._media_finance_store = media_finance_store
        self._lifecycle = lifecycle
        self._publisher = publisher
        self._cumulative = cumulative
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str) -> WorkshopMediaStudioViewEnvelope:
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("media-studio clock must be timezone-aware")
        scope = TenantScope(org_id=org_id, project_id=project_id)
        methods = {
            MediaStudioSliceId.CONTEXT: "read_context",
            MediaStudioSliceId.EXECUTION: "read_execution",
            MediaStudioSliceId.DELIVERY: "read_delivery",
        }
        slices: list[MediaStudioSlice] = []
        for slice_id in MediaStudioSliceId:
            blockers = [
                MediaBlocker(
                    code=f"MEDIA_{slice_id.value.upper()}_AUTHORITY_NOT_AVAILABLE",
                    dependency=f"workshop.media-studio.{slice_id.value}-authority",
                    required_action="provide tenant-bound exact refs and Receipts at one cutoff",
                )
            ]
            target_axes = [
                MediaAxisReadiness(
                    axis=axis,
                    status=MediaReadinessStatus.TARGET,
                    target_contract_ref=f"ADR-86#{slice_id.value}-{axis.value}",
                    gaps=[f"canonical {axis.value} authority is not attached"],
                    blockers=blockers,
                )
                for axis in MediaReadinessAxis
            ]
            try:
                observation = (
                    getattr(self._reader, methods[slice_id])(scope, cutoff=cutoff, limit=100)
                    if self._reader is not None
                    else None
                )
                if observation is not None:
                    validate_observation(observation, scope=scope, cutoff=cutoff)
            except (MediaStudioReadError, ValueError, TypeError):
                observation = None
            axes = list(observation.readiness_axes) if observation is not None else target_axes
            refs = list(observation.authority_refs) if observation is not None else []
            status_counts = {status: sum(item.status is status for item in axes) for status in MediaReadinessStatus}
            slice_blockers = [] if observation is not None and all(item.status in {MediaReadinessStatus.READY, MediaReadinessStatus.NOT_APPLICABLE} for item in axes) else blockers
            slices.append(
                MediaStudioSlice(
                    slice_id=slice_id,
                    status="ready" if not slice_blockers else "blocked",
                    data_cutoff=cutoff,
                    readiness_axes=axes,
                    authority_refs=refs,
                    blockers=slice_blockers,
                    count_ledger=MediaCountLedger(
                        denominator=6,
                        ready=status_counts[MediaReadinessStatus.READY],
                        target=status_counts[MediaReadinessStatus.TARGET],
                        blocked=status_counts[MediaReadinessStatus.BLOCKED],
                        unknown=status_counts[MediaReadinessStatus.UNKNOWN],
                        conflict=status_counts[MediaReadinessStatus.CONFLICT],
                        not_applicable=status_counts[MediaReadinessStatus.NOT_APPLICABLE],
                    ),
                )
            )
        provider_blockers = [
            MediaBlocker(
                code="MEDIA_PROVIDER_JOB_AUTHORITY_NOT_AVAILABLE",
                dependency="aip.media-provider-jobs",
                required_action="install w7_005 authority and read tenant-bound Provider Jobs",
            )
        ]
        provider_jobs: list[MediaProviderJobContribution] = []
        try:
            jobs = self._provider_job_store.list_jobs(scope, limit=100).items if self._provider_job_store is not None else None
            if jobs is not None:
                provider_blockers = []
                provider_jobs = [
                    MediaProviderJobContribution(
                        jobId=job.job_id,
                        status=job.status.value,
                        sequence=job.sequence,
                        atomicCapabilityRef=MediaProviderExactRef.model_validate(job.binding.capability_ref.model_dump(mode="json", by_alias=True)),
                        logicRef=MediaProviderExactRef.model_validate(job.task_run_ref.model_dump(mode="json", by_alias=True)),
                        colleagueBindingRef=MediaProviderExactRef.model_validate(job.binding.binding_ref.model_dump(mode="json", by_alias=True)),
                        modelRef=MediaProviderExactRef.model_validate(job.binding.model_ref.model_dump(mode="json", by_alias=True)),
                        providerRef=MediaProviderExactRef.model_validate(job.binding.provider_ref.model_dump(mode="json", by_alias=True)),
                        adapterRef=MediaProviderExactRef.model_validate(job.binding.adapter_ref.model_dump(mode="json", by_alias=True)),
                        scanRefs=[MediaProviderExactRef.model_validate(ref.model_dump(mode="json", by_alias=True)) for ref in job.input_scan_refs],
                        blockerCodes=job.blocker_codes,
                    )
                    for job in jobs
                ]
        except (MediaProviderJobError, ValueError, TypeError):
            provider_jobs = []
        finance_blockers = [
            MediaBlocker(
                code="MEDIA_FINANCE_AUTHORITY_NOT_AVAILABLE",
                dependency="aip.media-finance",
                required_action="install w7_006 and read tenant-bound finance authority",
            )
        ]
        media_finance: list[MediaFinanceContribution] = []
        try:
            finances = self._media_finance_store.list(scope, limit=100).items if self._media_finance_store is not None else None
            if finances is not None:
                finance_blockers = []
                media_finance = [
                    MediaFinanceContribution(
                        financeId=item.finance_id,
                        jobId=item.job_ref.resource_id,
                        version=item.version,
                        attemptBindingHash=item.attempt_binding_hash,
                        capacityReservationRef=MediaProviderExactRef.model_validate(item.capacity_reservation_ref.model_dump(mode="json", by_alias=True)),
                        budgetReservationRef=MediaProviderExactRef.model_validate(item.budget_reservation_ref.model_dump(mode="json", by_alias=True)),
                        projectedMinMinor=item.projected_min_minor,
                        projectedMaxMinor=item.projected_max_minor,
                        projectedCurrency=item.projected_currency,
                        reservationsActive=item.reservations_active,
                        cancelOutcome=item.cancel_outcome.value if item.cancel_outcome else None,
                        feeConclusion=item.fee_conclusion.value,
                        settlementStatus=item.settlement_status.value,
                        currencyBuckets=item.currency_buckets,
                        blockerCodes=item.blocker_codes,
                    )
                    for item in finances
                ]
        except (MediaFinanceError, ValueError, TypeError):
            media_finance = []
        lifecycle_blockers = [
            MediaBlocker(
                code="MEDIA_LIFECYCLE_AUTHORITY_NOT_AVAILABLE",
                dependency="aip.production-contracts",
                required_action="provide one tenant-bound production context and canonical lifecycle authorities",
            )
        ]
        lifecycle = None
        if self._lifecycle is not None:
            try:
                lifecycle = self._lifecycle.read(scope, cutoff=cutoff)
                if lifecycle is not None:
                    lifecycle_blockers = []
            except MediaStudioLifecycleConflict:
                lifecycle_blockers = [
                    MediaBlocker(
                        code="MEDIA_PRODUCTION_CONTEXT_SELECTOR_REQUIRED",
                        dependency="aip.production-contexts",
                        required_action="select one exact frozen production context",
                    )
                ]
            except (MediaStudioLifecycleError, ProductionContractError, MediaProviderJobError, MediaFinanceError, ValueError, TypeError):
                lifecycle = None
        publish_contributions = []
        publish_codes = ["MEDIA_PUBLISH_AUTHORITY_NOT_AVAILABLE"]
        if self._publisher is not None:
            try:
                publish_contributions, publish_codes = self._publisher.read(scope, cutoff=cutoff, limit=100)
            except (AipActionStoreError, ProductionContractError, ValueError, TypeError):
                publish_contributions = []
                publish_codes = ["MEDIA_PUBLISH_AUTHORITY_READ_FAILED"]
        publish_blockers = [
            MediaBlocker(
                code=code,
                dependency="aip.production-contracts+aip.actions",
                required_action="provide exact selected Variant, GateSet, ImpactPreview and canonical Action/Receipt at one cutoff",
            )
            for code in publish_codes
        ]
        return WorkshopMediaStudioViewEnvelope(
            schema_version=MEDIA_STUDIO_CUMULATIVE_SCHEMA_VERSION if self._cumulative is not None else (MEDIA_STUDIO_PUBLISH_SCHEMA_VERSION if self._publisher is not None else (MEDIA_STUDIO_LIFECYCLE_SCHEMA_VERSION if self._lifecycle is not None else (MEDIA_STUDIO_SCHEMA_VERSION if self._media_finance_store is not None else MEDIA_STUDIO_PROVIDER_SCHEMA_VERSION))),
            tenant=TenantContext(org_id=org_id, project_id=project_id),
            evaluated_at=cutoff,
            data_cutoff=cutoff,
            slices=slices,
            provider_jobs_status="ready" if not provider_blockers else "blocked",
            provider_jobs=provider_jobs,
            provider_job_blockers=provider_blockers,
            media_finance_status="ready" if not finance_blockers else "blocked",
            media_finance=media_finance,
            media_finance_blockers=finance_blockers,
            lifecycle_status="ready" if lifecycle is not None else "blocked",
            lifecycle=lifecycle,
            lifecycle_blockers=lifecycle_blockers,
            publish_status="ready" if not publish_blockers else "blocked",
            publish_contributions=publish_contributions,
            publish_blockers=publish_blockers,
            cumulative_gate_set=self._cumulative.read(cutoff=cutoff) if self._cumulative is not None else None,
            page=MediaPageInfo(count=sum(len(item.authority_refs) for item in slices)),
        )


__all__ = ["EcommerceWorkshopMediaStudio"]
