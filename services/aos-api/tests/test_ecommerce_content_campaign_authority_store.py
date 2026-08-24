"""Fake-connection tests for the content-campaign authority Store."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.ecommerce_content_campaign_authority_contracts import (
    CalendarDecisionRevision,
    CalendarEntryRevision,
    CampaignRevision,
    MasterContentIntentRevision,
)
from aos_api.ecommerce_content_campaign_authority_store import (
    ContentCampaignAuthorityConflict,
    ContentCampaignAuthorityIdempotencyConflict,
    ContentCampaignAuthorityReadError,
    EcommerceContentCampaignAuthorityStore,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 24, tzinfo=UTC)
HASH = "a" * 64
SCOPE = TenantScope(org_id="org-org", project_id="dev-project")


class Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.row


class Connection:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []
        self.commits = 0

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, params))
        row = self.rows.pop(0) if normalized.startswith("SELECT") else None
        return Cursor(row)

    def commit(self):
        self.commits += 1


def factory(connection):
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection

    return connect


def ref(resource_type, resource_id, revision=1):
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": revision,
        "contentHash": HASH,
    }


def campaign(*, org="org-org", revision=1):
    return CampaignRevision.model_validate(
        {
            "tenant": {"orgId": org, "projectId": "dev-project"},
            "campaignId": "campaign-1",
            "revision": revision,
            "version": revision,
            "priorRef": (
                ref("CampaignRevision", "campaign-1", revision - 1)
                if revision > 1
                else None
            ),
            "lifecycle": "draft",
            "goalPeriodRef": ref("GoalPeriodRevision", "goal-1"),
            "budgetEnvelopeRef": ref("BudgetEnvelopeRevision", "budget-1"),
            "channelIds": ["wechat"],
            "contentHash": HASH,
            "createdBy": "user:operator",
            "createdAt": NOW,
        }
    )


def calendar():
    return CalendarEntryRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "entryId": "entry-1",
            "revision": 1,
            "version": 1,
            "lifecycle": "scheduled",
            "campaignRef": ref("CampaignRevision", "campaign-1"),
            "contentArtifactRefs": [ref("ArtifactRevision", "artifact-1")],
            "timezone": "Asia/Shanghai",
            "localStart": "2026-08-25T10:00:00",
            "localEnd": "2026-08-25T11:00:00",
            "resolvedStart": NOW + timedelta(days=1),
            "resolvedEnd": NOW + timedelta(days=1, hours=1),
            "dstResolution": "exact",
            "contentHash": HASH,
            "createdBy": "user:operator",
            "createdAt": NOW,
        }
    )


def intent():
    return MasterContentIntentRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "intentId": "intent-1",
            "revision": 1,
            "version": 1,
            "lifecycle": "active",
            "campaignRef": ref("CampaignRevision", "campaign-1"),
            "briefRef": ref("TaskBriefRevision", "brief-1"),
            "masterArtifactRef": ref("ArtifactRevision", "artifact-1"),
            "channelIds": ["wechat"],
            "contentHash": HASH,
            "createdBy": "user:operator",
            "createdAt": NOW,
        }
    )


def test_publish_campaign_creates_head_revision_receipt_and_commit() -> None:
    connection = Connection(rows=[None, None])
    store = EcommerceContentCampaignAuthorityStore(factory(connection))
    result = store.publish_campaign(
        SCOPE, "user:operator", "key-1", campaign(), expected_version=0
    )
    assert result.resource_type == "CampaignRevision"
    assert connection.commits == 1
    sql = "\n".join(call[0] for call in connection.calls)
    assert "INSERT INTO ecommerce_campaign_head" in sql
    assert "INSERT INTO ecommerce_campaign_revision" in sql
    assert "INSERT INTO ecommerce_content_campaign_authority_receipt" in sql
    assert all("org-org" not in statement for statement, _ in connection.calls)


def test_publish_campaign_enforces_cas_and_idempotency() -> None:
    stale = Connection(rows=[None, {"current_revision": 1, "version": 1}])
    with pytest.raises(ContentCampaignAuthorityConflict):
        EcommerceContentCampaignAuthorityStore(factory(stale)).publish_campaign(
            SCOPE, "user:operator", "key-2", campaign(), expected_version=0
        )

    conflict = Connection(rows=[{"request_hash": "b" * 64, "result_ref": {}}])
    with pytest.raises(ContentCampaignAuthorityIdempotencyConflict):
        EcommerceContentCampaignAuthorityStore(factory(conflict)).publish_campaign(
            SCOPE, "user:operator", "key-2", campaign(), expected_version=0
        )


def test_same_idempotency_request_returns_exact_original_ref() -> None:
    result = ref("CampaignRevision", "campaign-1")
    probe = Connection(rows=[None, None])
    store = EcommerceContentCampaignAuthorityStore(factory(probe))
    store.publish_campaign(SCOPE, "user:operator", "key-3", campaign(), expected_version=0)
    request_hash = probe.calls[0][1]
    assert request_hash[-1] == "key-3"
    receipt_insert = probe.calls[-1][1]
    replay = Connection(
        rows=[{"request_hash": receipt_insert[5], "result_ref": result}]
    )
    exact = EcommerceContentCampaignAuthorityStore(factory(replay)).publish_campaign(
        SCOPE, "user:operator", "key-3", campaign(), expected_version=0
    )
    assert exact.resource_id == "campaign-1"
    assert replay.commits == 0


def test_cross_tenant_and_actor_drift_fail_before_database_access() -> None:
    connection = Connection()
    store = EcommerceContentCampaignAuthorityStore(factory(connection))
    with pytest.raises(ContentCampaignAuthorityConflict, match="tenant"):
        store.publish_campaign(
            SCOPE,
            "user:operator",
            "key-4",
            campaign(org="dev-org"),
            expected_version=0,
        )
    with pytest.raises(ContentCampaignAuthorityConflict, match="actor"):
        store.publish_campaign(
            SCOPE, "user:other", "key-5", campaign(), expected_version=0
        )
    assert connection.calls == []


def test_calendar_intent_and_decision_use_typed_append_paths() -> None:
    calendar_connection = Connection(rows=[None, None])
    store = EcommerceContentCampaignAuthorityStore(factory(calendar_connection))
    store.publish_calendar_entry(
        SCOPE, "user:operator", "calendar-key", calendar(), expected_version=0
    )
    sql = "\n".join(call[0] for call in calendar_connection.calls)
    assert "INSERT INTO ecommerce_content_calendar_entry_revision" in sql
    assert "timezone,resolved_start,resolved_end" in sql

    intent_connection = Connection(rows=[None, None])
    EcommerceContentCampaignAuthorityStore(factory(intent_connection)).publish_intent(
        SCOPE, "user:operator", "intent-key", intent(), expected_version=0
    )
    assert "INSERT INTO ecommerce_master_content_intent_revision" in "\n".join(
        call[0] for call in intent_connection.calls
    )

    decision = CalendarDecisionRevision.model_validate(
        {
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "decisionId": "decision-1",
            "revision": 1,
            "decisionType": "reschedule",
            "fromEntryRef": ref("CalendarEntryRevision", "entry-1", 1),
            "toEntryRef": ref("CalendarEntryRevision", "entry-1", 2),
            "reason": "capacity",
            "contentHash": HASH,
            "createdBy": "user:operator",
            "createdAt": NOW,
        }
    )
    decision_connection = Connection(rows=[None])
    EcommerceContentCampaignAuthorityStore(
        factory(decision_connection)
    ).append_calendar_decision(
        SCOPE, "user:operator", "decision-key", decision
    )
    decision_sql = "\n".join(call[0] for call in decision_connection.calls)
    assert "INSERT INTO ecommerce_content_calendar_decision_revision" in decision_sql
    assert "UPDATE ecommerce_content_calendar_decision_revision" not in decision_sql


@pytest.mark.parametrize(
    ("method", "item", "identity"),
    [
        ("list_campaigns", campaign(), "campaign-1"),
        ("list_calendar_entries", calendar(), "entry-1"),
        ("list_intents", intent(), "intent-1"),
    ],
)
def test_bounded_readers_are_repeatable_read_tenant_scoped(
    method, item, identity
) -> None:
    payload = item.model_dump(mode="json", by_alias=True)
    connection = Connection(
        rows=[
            [
                {
                    "org_id": "org-org",
                    "project_id": "dev-project",
                    "authority_data": payload,
                }
            ]
        ]
    )
    store = EcommerceContentCampaignAuthorityStore(factory(connection))
    rows = getattr(store, method)(SCOPE, cutoff=NOW, limit=1)
    assert len(rows) == 1
    assert identity in str(rows[0].model_dump())
    assert "REPEATABLE READ READ ONLY" in connection.calls[0][0]
    assert connection.calls[1][1] == ("org-org", "dev-project", NOW, 1)


def test_reader_fails_closed_on_row_tenant_drift() -> None:
    connection = Connection(
        rows=[
            [
                {
                    "org_id": "dev-org",
                    "project_id": "dev-project",
                    "authority_data": campaign().model_dump(
                        mode="json", by_alias=True
                    ),
                }
            ]
        ]
    )
    store = EcommerceContentCampaignAuthorityStore(factory(connection))
    with pytest.raises(ContentCampaignAuthorityReadError):
        store.list_campaigns(SCOPE, cutoff=NOW)
