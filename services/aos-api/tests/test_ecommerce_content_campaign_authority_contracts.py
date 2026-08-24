"""Strict contract tests for canonical content-campaign authorities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_content_campaign_authority_contracts import (
    CalendarDecisionRevision,
    CalendarEntryRevision,
    CampaignRevision,
    ContentCampaignAuthorityReceipt,
    MasterContentIntentRevision,
)


NOW = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
TENANT = {"orgId": "org-org", "projectId": "dev-project"}


def _ref(resource_type: str, resource_id: str, revision: int = 1) -> dict:
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": revision,
        "contentHash": "a" * 64,
    }


def _campaign(**updates) -> dict:
    body = {
        "tenant": TENANT,
        "campaignId": "campaign-1",
        "revision": 1,
        "version": 1,
        "priorRef": None,
        "lifecycle": "draft",
        "goalPeriodRef": _ref("GoalPeriodRevision", "goal-1"),
        "budgetEnvelopeRef": _ref("BudgetEnvelopeRevision", "budget-1"),
        "offerRef": _ref("OfferRevision", "offer-1"),
        "channelIds": ["wechat", "douyin"],
        "contentHash": "b" * 64,
        "createdBy": "user:operator",
        "createdAt": NOW,
    }
    body.update(updates)
    return body


def _calendar(**updates) -> dict:
    body = {
        "tenant": TENANT,
        "entryId": "calendar-1",
        "revision": 1,
        "version": 1,
        "priorRef": None,
        "lifecycle": "scheduled",
        "campaignRef": _ref("CampaignRevision", "campaign-1"),
        "contentArtifactRefs": [_ref("ArtifactRevision", "artifact-1")],
        "timezone": "Asia/Shanghai",
        "localStart": "2026-08-25T10:00:00",
        "localEnd": "2026-08-25T11:00:00",
        "resolvedStart": NOW + timedelta(days=1, hours=2),
        "resolvedEnd": NOW + timedelta(days=1, hours=3),
        "dstResolution": "exact",
        "conflictDecisionRef": None,
        "cancellationReason": None,
        "contentHash": "c" * 64,
        "createdBy": "user:operator",
        "createdAt": NOW,
    }
    body.update(updates)
    return body


def _intent(**updates) -> dict:
    body = {
        "tenant": TENANT,
        "intentId": "intent-1",
        "revision": 1,
        "version": 1,
        "priorRef": None,
        "lifecycle": "active",
        "campaignRef": _ref("CampaignRevision", "campaign-1"),
        "briefRef": _ref("TaskBriefRevision", "brief-1"),
        "masterArtifactRef": _ref("ArtifactRevision", "artifact-1"),
        "channelIds": ["wechat"],
        "contentHash": "d" * 64,
        "createdBy": "user:operator",
        "createdAt": NOW,
    }
    body.update(updates)
    return body


def test_campaign_revision_is_strict_exact_and_append_only_shaped() -> None:
    item = CampaignRevision.model_validate(_campaign())
    assert item.tenant.org_id == "org-org"
    assert item.channel_ids == ["wechat", "douyin"]

    with pytest.raises(ValidationError):
        CampaignRevision.model_validate(_campaign(prompt="secret body"))
    with pytest.raises(ValidationError):
        CampaignRevision.model_validate(_campaign(channelIds=["wechat", "wechat"]))
    with pytest.raises(ValidationError):
        CampaignRevision.model_validate(_campaign(revision=2, version=2))


def test_revision_successors_require_exact_prior_identity_and_revision() -> None:
    campaign = CampaignRevision.model_validate(
        _campaign(
            revision=2,
            version=2,
            priorRef=_ref("CampaignRevision", "campaign-1", 1),
        )
    )
    assert campaign.prior_ref and campaign.prior_ref.revision == 1

    with pytest.raises(ValidationError):
        MasterContentIntentRevision.model_validate(
            _intent(
                revision=2,
                version=2,
                priorRef=_ref("MasterContentIntentRevision", "other", 1),
            )
        )


def test_calendar_requires_iana_timezone_aware_window_and_artifact_refs() -> None:
    entry = CalendarEntryRevision.model_validate(_calendar())
    assert entry.timezone == "Asia/Shanghai"

    with pytest.raises(ValidationError):
        CalendarEntryRevision.model_validate(_calendar(timezone="Mars/Olympus"))
    with pytest.raises(ValidationError):
        CalendarEntryRevision.model_validate(
            _calendar(resolvedEnd=NOW + timedelta(hours=1))
        )
    with pytest.raises(ValidationError):
        CalendarEntryRevision.model_validate(
            _calendar(contentArtifactRefs=[_ref("ContentVariant", "variant-1")])
        )


def test_calendar_cancel_and_decision_preserve_successor_history() -> None:
    cancelled = CalendarEntryRevision.model_validate(
        _calendar(
            revision=2,
            version=2,
            priorRef=_ref("CalendarEntryRevision", "calendar-1", 1),
            lifecycle="cancelled",
            cancellationReason="campaign withdrawn",
        )
    )
    assert cancelled.lifecycle.value == "cancelled"

    decision = CalendarDecisionRevision.model_validate(
        {
            "tenant": TENANT,
            "decisionId": "decision-1",
            "revision": 1,
            "decisionType": "cancel",
            "fromEntryRef": _ref("CalendarEntryRevision", "calendar-1", 1),
            "toEntryRef": _ref("CalendarEntryRevision", "calendar-1", 2),
            "reason": "campaign withdrawn",
            "contentHash": "e" * 64,
            "createdBy": "user:operator",
            "createdAt": NOW,
        }
    )
    assert decision.to_entry_ref.revision == 2

    with pytest.raises(ValidationError):
        CalendarEntryRevision.model_validate(_calendar(lifecycle="cancelled"))


def test_intent_and_receipt_keep_minimal_exact_refs_only() -> None:
    intent = MasterContentIntentRevision.model_validate(_intent())
    assert intent.master_artifact_ref
    assert intent.master_artifact_ref.resource_type == "ArtifactRevision"

    receipt = ContentCampaignAuthorityReceipt.model_validate(
        {
            "tenant": TENANT,
            "receiptId": "receipt-1",
            "operation": "content_campaign.intent_create",
            "idempotencyKey": "idem-1",
            "requestHash": "f" * 64,
            "resultRef": _ref("MasterContentIntentRevision", "intent-1"),
            "createdBy": "user:operator",
            "createdAt": NOW,
        }
    )
    assert receipt.result_ref.resource_id == "intent-1"

    with pytest.raises(ValidationError):
        MasterContentIntentRevision.model_validate(_intent(body="raw content"))
