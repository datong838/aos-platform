"""Tenant-bound, GET-only W2-03A content-campaign shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_content_campaign_contracts import (
    ContentCampaignAuthorityRef,
    ContentCampaignArtifactRef,
    ContentCampaignBlocker,
    ContentCampaignCountLedger,
    ContentCampaignPageInfo,
    ContentCampaignSlice,
    ContentCampaignSliceId,
    ContentCampaignSliceStatus,
    WorkshopContentCampaignViewEnvelope,
    ContentVariantProjection,
)
from aos_api.ecommerce_content_campaign_authority_store import (
    ContentCampaignAuthorityObservation,
    ContentCampaignAuthorityReadError,
    EcommerceContentCampaignAuthorityStore,
)
from aos_api.tenant_scope import TenantScope


Clock = Callable[[], datetime]

_DEPENDENCIES = {
    ContentCampaignSliceId.PLAN: (
        "workshop.w3-11.campaign-revision-authority",
        "CANONICAL_CAMPAIGN_REVISION_AUTHORITY_NOT_AVAILABLE",
    ),
    ContentCampaignSliceId.CALENDAR: (
        "workshop.w3-11.calendar-entry-authority",
        "CANONICAL_CALENDAR_ENTRY_AUTHORITY_NOT_AVAILABLE",
    ),
    ContentCampaignSliceId.CONTENT: (
        "workshop.w3-11.master-content-intent-artifact-authority",
        "CANONICAL_MASTER_CONTENT_INTENT_AUTHORITY_NOT_AVAILABLE",
    ),
}


class EcommerceWorkshopContentCampaign:
    """Expose honest authority gaps without inventing business rows."""

    def __init__(
        self,
        *,
        clock: Clock | None = None,
        store: EcommerceContentCampaignAuthorityStore | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._store = store or EcommerceContentCampaignAuthorityStore()

    def read(
        self, *, org_id: str, project_id: str
    ) -> WorkshopContentCampaignViewEnvelope:
        evaluated_at = self._clock()
        if evaluated_at.utcoffset() is None:
            raise ValueError("content-campaign clock must be timezone-aware")
        scope = TenantScope(org_id=org_id, project_id=project_id)
        readers = {
            ContentCampaignSliceId.PLAN: (
                self._store.list_campaigns,
                "CampaignRevision",
            ),
            ContentCampaignSliceId.CALENDAR: (
                self._store.list_calendar_entries,
                "CalendarEntryRevision",
            ),
            ContentCampaignSliceId.CONTENT: (
                self._store.list_intents,
                "MasterContentIntentRevision",
            ),
        }
        slices = []
        for slice_id in ContentCampaignSliceId:
            reader, resource_type = readers[slice_id]
            try:
                observations = reader(scope, cutoff=evaluated_at, limit=100)
                refs = [
                    self._item_ref(resource_type, observation)
                    for observation in observations
                ]
                items = list(refs)
                if slice_id is ContentCampaignSliceId.CONTENT:
                    variants = self._store.list_content_variants(
                        scope, cutoff=evaluated_at, limit=100
                    )
                    items.extend(self._variant_items(observations, variants))
                slices.append(
                    ContentCampaignSlice(
                        slice_id=slice_id,
                        status=ContentCampaignSliceStatus.READY,
                        data_cutoff=evaluated_at,
                        authority_refs=refs[:20],
                        items=items,
                        blockers=[],
                        count_ledger=ContentCampaignCountLedger(
                            eligible=len(items),
                            attached=len(items),
                            unmatched=0,
                            conflicted=0,
                        ),
                    )
                )
            except ContentCampaignAuthorityReadError:
                dependency, code = _DEPENDENCIES[slice_id]
                slices.append(
                    ContentCampaignSlice(
                        slice_id=slice_id,
                        status=ContentCampaignSliceStatus.BLOCKED,
                        data_cutoff=evaluated_at,
                        authority_refs=[],
                        items=[],
                        blockers=[
                            ContentCampaignBlocker(
                                code=code,
                                dependency=dependency,
                                required_action=(
                                    "provide a tenant-bound canonical reader and exact "
                                    "authority Receipt at the same cutoff"
                                ),
                            )
                        ],
                        count_ledger=ContentCampaignCountLedger(
                            eligible=0,
                            attached=0,
                            unmatched=0,
                            conflicted=0,
                        ),
                    )
                )
        return WorkshopContentCampaignViewEnvelope(
            tenant=TenantContext(org_id=org_id, project_id=project_id),
            evaluated_at=evaluated_at,
            data_cutoff=evaluated_at,
            slices=slices,
            page=ContentCampaignPageInfo(
                limit=100,
                count=sum(item.count_ledger.attached for item in slices),
                has_more=False,
                next_cursor=None,
            ),
        )

    @staticmethod
    def _item_ref(
        resource_type: str,
        observation: ContentCampaignAuthorityObservation,
    ) -> ContentCampaignAuthorityRef:
        revision = observation.revision
        identity = getattr(
            revision,
            {
                "CampaignRevision": "campaign_id",
                "CalendarEntryRevision": "entry_id",
                "MasterContentIntentRevision": "intent_id",
            }[resource_type],
        )
        return ContentCampaignAuthorityRef(
            resource_type=resource_type,
            resource_id=identity,
            revision=revision.revision,
            content_hash="sha256:" + revision.content_hash,
            receipt_id=observation.receipt_id,
        )

    @classmethod
    def _variant_items(cls, intent_observations, variant_observations):
        items = []
        for variant in variant_observations:
            matches = [
                intent
                for intent in intent_observations
                if intent.revision.master_artifact_ref is not None
                and intent.revision.master_artifact_ref.resource_id
                == variant.master_artifact_id
                and intent.revision.master_artifact_ref.content_hash
                == variant.master_content_hash
            ]
            if len(matches) != 1:
                raise ContentCampaignAuthorityReadError(
                    "ContentVariant requires exactly one matching MasterContentIntent"
                )
            intent_ref = cls._item_ref(
                "MasterContentIntentRevision", matches[0]
            )
            items.append(
                ContentVariantProjection(
                    resource_id=variant.variant_artifact_id,
                    content_hash="sha256:" + variant.variant_content_hash,
                    receipt_id=variant.receipt_id,
                    intent_ref=intent_ref,
                    master_artifact_ref=ContentCampaignArtifactRef(
                        artifact_id=variant.master_artifact_id,
                        content_hash="sha256:" + variant.master_content_hash,
                    ),
                    variant_artifact_ref=ContentCampaignArtifactRef(
                        artifact_id=variant.variant_artifact_id,
                        content_hash="sha256:" + variant.variant_content_hash,
                    ),
                    relation_id=variant.relation_id,
                )
            )
        return items


__all__ = ["EcommerceWorkshopContentCampaign"]
