"""W2-03A strict content-campaign contract and shell tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_content_campaign import (
    EcommerceWorkshopContentCampaign,
)
from aos_api.ecommerce_workshop_content_campaign_contracts import (
    ContentCampaignSliceId,
    WorkshopContentCampaignViewEnvelope,
)


NOW = datetime(2026, 8, 24, 13, 0, tzinfo=UTC)


def _body() -> dict[str, object]:
    return EcommerceWorkshopContentCampaign(clock=lambda: NOW).read(
        org_id="org-org", project_id="dev-project"
    ).model_dump(by_alias=True)


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
