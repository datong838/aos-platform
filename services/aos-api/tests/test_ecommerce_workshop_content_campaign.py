"""W2-03A strict content-campaign contract and shell tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_content_campaign import (
    EcommerceWorkshopContentCampaign,
)
from aos_api.ecommerce_workshop_content_campaign_contracts import (
    ContentCampaignSliceId,
    WorkshopContentCampaignViewEnvelope,
)
from aos_api.ecommerce_content_campaign_authority_store import (
    ContentCampaignAuthorityObservation,
    ContentCampaignAuthorityReadError,
)


NOW = datetime(2026, 8, 24, 13, 0, tzinfo=UTC)


class _EmptyStore:
    def list_campaigns(self, scope, *, cutoff, limit):
        return []

    def list_calendar_entries(self, scope, *, cutoff, limit):
        return []

    def list_intents(self, scope, *, cutoff, limit):
        return []


class _ObservedStore(_EmptyStore):
    @staticmethod
    def _observation(identity: str, receipt_id: str):
        return ContentCampaignAuthorityObservation(
            revision=SimpleNamespace(
                campaign_id=identity,
                entry_id=identity,
                intent_id=identity,
                revision=1,
                content_hash="a" * 64,
            ),
            receipt_id=receipt_id,
        )

    def list_campaigns(self, scope, *, cutoff, limit):
        return [self._observation("campaign-1", "ccar-campaign-1")]

    def list_calendar_entries(self, scope, *, cutoff, limit):
        return [self._observation("entry-1", "ccar-entry-1")]

    def list_intents(self, scope, *, cutoff, limit):
        return [self._observation("intent-1", "ccar-intent-1")]


class _CalendarFailureStore(_ObservedStore):
    def list_calendar_entries(self, scope, *, cutoff, limit):
        raise ContentCampaignAuthorityReadError("calendar unavailable")


def _body() -> dict[str, object]:
    return EcommerceWorkshopContentCampaign(clock=lambda: NOW).read(
        org_id="org-org", project_id="dev-project"
    ).model_dump(by_alias=True)


def _body_with_store(store) -> dict[str, object]:
    return EcommerceWorkshopContentCampaign(clock=lambda: NOW, store=store).read(
        org_id="org-org", project_id="dev-project"
    ).model_dump(by_alias=True)


def test_trusted_empty_authorities_are_ready_without_synthetic_refs() -> None:
    body = _body_with_store(_EmptyStore())
    assert [item["status"] for item in body["slices"]] == ["ready"] * 3
    assert [item["authorityRefs"] for item in body["slices"]] == [[], [], []]
    assert [item["countLedger"]["eligible"] for item in body["slices"]] == [0, 0, 0]
    assert body["page"]["count"] == 0


def test_observed_authorities_expose_exact_revision_hash_and_receipt() -> None:
    body = _body_with_store(_ObservedStore())
    items = [item["items"][0] for item in body["slices"]]
    assert [item["resourceType"] for item in items] == [
        "CampaignRevision",
        "CalendarEntryRevision",
        "MasterContentIntentRevision",
    ]
    assert [item["resourceId"] for item in items] == [
        "campaign-1",
        "entry-1",
        "intent-1",
    ]
    assert [item["receiptId"] for item in items] == [
        "ccar-campaign-1",
        "ccar-entry-1",
        "ccar-intent-1",
    ]
    assert all(item["revision"] == 1 for item in items)
    assert all(item["contentHash"] == "sha256:" + "a" * 64 for item in items)
    assert body["page"]["count"] == 3


def test_one_reader_failure_blocks_only_its_slice() -> None:
    body = _body_with_store(_CalendarFailureStore())
    assert [item["status"] for item in body["slices"]] == [
        "ready",
        "blocked",
        "ready",
    ]
    assert body["slices"][1]["items"] == []
    assert body["slices"][1]["blockers"][0]["code"] == (
        "CANONICAL_CALENDAR_ENTRY_AUTHORITY_NOT_AVAILABLE"
    )
    assert body["page"]["count"] == 2


def test_shell_is_tenant_bound_canonical_and_honestly_blocked() -> None:
    envelope = WorkshopContentCampaignViewEnvelope.model_validate(_body())
    assert envelope.tenant.org_id == "org-org"
    assert [item.slice_id for item in envelope.slices] == list(
        ContentCampaignSliceId
    )
    assert [item.status.value for item in envelope.slices] == ["blocked"] * 3
    assert [item.count_ledger.eligible for item in envelope.slices] == [0, 0, 0]
    assert [item.items for item in envelope.slices] == [[], [], []]
    assert [item.blockers[0].code for item in envelope.slices] == [
        "CANONICAL_CAMPAIGN_REVISION_AUTHORITY_NOT_AVAILABLE",
        "CANONICAL_CALENDAR_ENTRY_AUTHORITY_NOT_AVAILABLE",
        "CANONICAL_MASTER_CONTENT_INTENT_AUTHORITY_NOT_AVAILABLE",
    ]


def test_contract_rejects_naive_time_wrong_order_and_count_drift() -> None:
    naive = _body()
    naive["evaluatedAt"] = datetime(2026, 8, 24, 13, 0)
    with pytest.raises(ValidationError):
        WorkshopContentCampaignViewEnvelope.model_validate(naive)

    wrong_order = _body()
    wrong_order["slices"] = list(reversed(wrong_order["slices"]))  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        WorkshopContentCampaignViewEnvelope.model_validate(wrong_order)

    drift = _body()
    drift["slices"][0]["countLedger"]["eligible"] = 1  # type: ignore[index]
    with pytest.raises(ValidationError):
        WorkshopContentCampaignViewEnvelope.model_validate(drift)


def test_contract_rejects_false_ready_unverified_items_and_extra_fields() -> None:
    false_ready = _body()
    false_ready["slices"][0]["status"] = "ready"  # type: ignore[index]
    with pytest.raises(ValidationError):
        WorkshopContentCampaignViewEnvelope.model_validate(false_ready)

    unverified = _body()
    unverified["slices"][0]["items"] = [  # type: ignore[index]
        {
            "resourceType": "CampaignRevision",
            "resourceId": "campaign-1",
            "revision": 1,
            "contentHash": "sha256:" + "a" * 64,
            "receiptId": "receipt-1",
        }
    ]
    unverified["slices"][0]["countLedger"]["eligible"] = 1  # type: ignore[index]
    unverified["slices"][0]["countLedger"]["attached"] = 1  # type: ignore[index]
    with pytest.raises(ValidationError):
        WorkshopContentCampaignViewEnvelope.model_validate(unverified)

    extra = _body()
    extra["prompt"] = "must never cross the Workshop contract"
    with pytest.raises(ValidationError):
        WorkshopContentCampaignViewEnvelope.model_validate(extra)
