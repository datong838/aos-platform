"""BI-W8-02 SchedulePolicy, Case binding and scheduled trigger tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_business_investigation_application import (
    CreateBusinessInvestigationRunRequest,
    EcommerceBusinessInvestigationApplication,
)
from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationCaseLifecycle,
    BusinessInvestigationCaseRevision,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunRecord,
    BusinessInvestigationRunRequestOutcome,
    BusinessInvestigationRunStateRevision,
    BusinessInvestigationRunView,
    BusinessInvestigationRunWrite,
)
from aos_api.ecommerce_business_investigation_schedule import (
    BusinessInvestigationSchedulePolicyRevision,
    BusinessInvestigationSchedulePolicyWrite,
    PutBusinessInvestigationSchedulePolicyRequest,
    TriggerBusinessInvestigationScheduleRequest,
    scheduled_trigger_key,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 27, 1, 0, tzinfo=UTC)
TENANT = TenantContext(org_id="org-org", project_id="dev-project")
SCOPE = TenantScope("org-org", "dev-project")
HASH = "sha256:" + "a" * 64


def ref(kind: str, identity: str, revision: int = 1, content_hash: str = HASH) -> dict:
    return {
        "resourceType": kind,
        "resourceId": identity,
        "revision": revision,
        "contentHash": content_hash,
    }


def case(*, revision: int = 2, schedule_ref: dict | None = None) -> BusinessInvestigationCaseRevision:
    payload = {
        "schemaVersion": "aos.ecommerce.business-investigation-case/v1",
        "tenant": TENANT.model_dump(by_alias=True, mode="json"),
        "caseId": "case-1",
        "revision": revision,
        "version": revision,
        "priorRef": ref("BusinessInvestigationCaseRevision", "case-1", revision - 1),
        "contentHash": HASH,
        "lifecycle": "ACTIVE",
        "analysisType": "weekly_business_review",
        "title": "每周经营复盘",
        "purposeCode": "business.investigation.weekly",
        "channelRef": ref("ChannelRevision", "private-mall"),
        "businessEntityRef": ref("BusinessEntityRevision", "store-1"),
        "entityChannelBindingRef": ref("BusinessEntityChannelBindingRevision", "binding-1"),
        "investigationProfileRef": ref("InvestigationProfileRevision", "profile-1"),
        "scopeRef": ref("InvestigationScopeRevision", "scope-1"),
        "schedulePolicyRef": schedule_ref,
        "createdBy": "owner",
        "createdAt": NOW,
    }
    item = BusinessInvestigationCaseRevision.model_validate(payload)
    payload["contentHash"] = item.calculated_content_hash()
    return BusinessInvestigationCaseRevision.model_validate(payload)


def policy_payload(**changes) -> dict:
    payload = {
        "schemaVersion": "aos.ecommerce.business-investigation-schedule-policy/v1",
        "tenant": TENANT.model_dump(by_alias=True, mode="json"),
        "schedulePolicyId": "schedule-1",
        "revision": 1,
        "version": 1,
        "contentHash": HASH,
        "caseRef": ref("BusinessInvestigationCaseRevision", "case-1", 2, case().content_hash),
        "analysisType": "weekly_business_review",
        "policyKind": "weekly_review",
        "cadence": "weekly",
        "enabled": True,
        "overlapPolicy": "skip",
        "timezone": "Asia/Shanghai",
        "weeklyDay": 1,
        "localTime": "09:00",
        "createdBy": "owner",
        "createdAt": NOW,
    }
    payload.update(changes)
    return payload


def policy(**changes) -> BusinessInvestigationSchedulePolicyRevision:
    payload = policy_payload(**changes)
    item = BusinessInvestigationSchedulePolicyRevision.model_validate(payload)
    payload["contentHash"] = item.calculated_content_hash()
    return BusinessInvestigationSchedulePolicyRevision.model_validate(payload)


@pytest.mark.parametrize(
    ("kind", "cadence", "analysis_type", "weekly_day", "local_time"),
    [
        ("initial_checkup", "once", "initial_store_analysis", None, None),
        ("weekly_review", "weekly", "weekly_business_review", 1, "09:00"),
        ("topic_analysis", "on_demand", "creator_sales", None, None),
    ],
)
def test_policy_contract_freezes_three_safe_kinds(kind, cadence, analysis_type, weekly_day, local_time) -> None:
    item = policy(
        policyKind=kind,
        cadence=cadence,
        analysisType=analysis_type,
        weeklyDay=weekly_day,
        localTime=local_time,
    )
    assert item.policy_kind.value == kind and item.overlap_policy == "skip"
    assert item.calculated_content_hash() == item.content_hash


def test_policy_contract_rejects_mismatch_weekly_fields_and_unknowns() -> None:
    with pytest.raises(ValidationError):
        BusinessInvestigationSchedulePolicyRevision.model_validate(
            policy_payload(policyKind="weekly_review", cadence="once")
        )
    with pytest.raises(ValidationError):
        BusinessInvestigationSchedulePolicyRevision.model_validate(
            policy_payload(weeklyDay=None, localTime=None)
        )
    with pytest.raises(ValidationError):
        BusinessInvestigationSchedulePolicyRevision.model_validate(
            {**policy_payload(), "cron": "* * * * *"}
        )


def test_server_trigger_key_is_canonical_bounded_and_revision_sensitive() -> None:
    first = policy()
    at = datetime(2026, 9, 1, 1, 0, tzinfo=UTC)
    assert scheduled_trigger_key(first, at) == scheduled_trigger_key(first, at)
    assert len(scheduled_trigger_key(first, at)) == 73
    successor = first.model_copy(update={"revision": 2, "version": 2})
    assert scheduled_trigger_key(first, at) != scheduled_trigger_key(successor, at)


class FakeCaseStore:
    def __init__(self, authority: BusinessInvestigationCaseRevision) -> None:
        self.authority = authority

    def get(self, scope, case_id):
        assert scope == SCOPE and case_id == self.authority.case_id
        return self.authority


class FakeScheduleStore:
    def __init__(self) -> None:
        self.authority = None
        self.put = None
        self.receipt = None

    def find_put_receipt(self, scope, idempotency_key):
        assert scope == SCOPE
        return self.receipt

    def get(self, scope, schedule_policy_id):
        assert scope == SCOPE and schedule_policy_id == "schedule-1"
        return self.authority

    def put_and_bind_case(self, scope, authority, case_authority, **kwargs):
        self.put = (scope, authority, case_authority, kwargs)
        self.authority = authority
        return BusinessInvestigationSchedulePolicyWrite(authority, case_authority, False)


class FakeRunStore:
    def __init__(self, outcome=BusinessInvestigationRunRequestOutcome.SKIPPED_OVERLAP) -> None:
        self.outcome = outcome
        self.requested = None

    def request(self, scope, run, *, idempotency_key):
        self.requested = (scope, run, idempotency_key)
        return BusinessInvestigationRunWrite(run, self.outcome, False)

    def get(self, scope, run_id):
        run: BusinessInvestigationRunRecord = self.requested[1]
        state = BusinessInvestigationRunStateRevision.model_validate(
            {
                "tenant": TENANT.model_dump(by_alias=True, mode="json"),
                "runId": run_id,
                "version": 1,
                "lifecycle": "PREPARING",
                "control": "RUNNING",
                "eventSequence": 1,
                "contentHash": HASH,
                "createdBy": "owner",
                "createdAt": NOW,
            }
        )
        return BusinessInvestigationRunView(authority=run, state=state)


def put_request(authority: BusinessInvestigationCaseRevision) -> PutBusinessInvestigationSchedulePolicyRequest:
    return PutBusinessInvestigationSchedulePolicyRequest.model_validate(
        {
            "schedulePolicyId": "schedule-1",
            "caseRef": ref(
                "BusinessInvestigationCaseRevision",
                authority.case_id,
                authority.revision,
                authority.content_hash,
            ),
            "analysisType": "weekly_business_review",
            "policyKind": "weekly_review",
            "cadence": "weekly",
            "enabled": True,
            "weeklyDay": 1,
            "localTime": "09:00",
        }
    )


def test_application_atomically_builds_policy_and_case_successor() -> None:
    current_case = case()
    schedules = FakeScheduleStore()
    application = EcommerceBusinessInvestigationApplication(
        case_store=FakeCaseStore(current_case),
        run_store=FakeRunStore(),
        schedule_store=schedules,
    )
    response = application.put_schedule_policy(
        SCOPE,
        "case-1",
        put_request(current_case),
        expected_policy_revision=0,
        expected_case_version=2,
        idempotency_key="schedule-create",
        actor="owner",
        occurred_at=NOW,
    )
    assert response.authority.revision == 1
    assert response.case_authority.revision == 3
    assert response.case_authority.lifecycle is BusinessInvestigationCaseLifecycle.ACTIVE
    assert response.case_authority.schedule_policy_ref.content_hash == response.authority.content_hash


def test_trigger_uses_server_key_and_preserves_overlap_skip_receipt_outcome() -> None:
    schedule = policy()
    schedule_ref = ref("SchedulePolicyRevision", "schedule-1", 1, schedule.content_hash)
    current_case = case(revision=3, schedule_ref=schedule_ref)
    schedule = schedule.model_copy(
        update={
            "case_ref": schedule.case_ref.model_copy(
                update={"content_hash": case().content_hash}
            )
        }
    )
    schedules = FakeScheduleStore()
    schedules.authority = schedule
    runs = FakeRunStore()
    application = EcommerceBusinessInvestigationApplication(
        case_store=FakeCaseStore(current_case), run_store=runs, schedule_store=schedules
    )
    response = application.trigger_schedule_policy(
        SCOPE,
        "schedule-1",
        TriggerBusinessInvestigationScheduleRequest.model_validate(
            {
                "runId": "run-scheduled-1",
                "schedulePolicyRef": schedule_ref,
                "scheduledAt": "2026-09-01T01:00:00Z",
            }
        ),
        expected_policy_revision=1,
        idempotency_key="schedule-trigger",
        actor="owner",
        occurred_at=NOW,
    )
    assert response.outcome is BusinessInvestigationRunRequestOutcome.SKIPPED_OVERLAP
    requested = runs.requested[1]
    assert requested.trigger_key == scheduled_trigger_key(schedule, datetime(2026, 9, 1, 1, 0, tzinfo=UTC))
    assert requested.trigger_kind.value == "scheduled"


def test_trigger_rejects_disabled_stale_policy_and_bad_time_before_run_write() -> None:
    schedule = policy(enabled=False)
    schedule_ref = ref("SchedulePolicyRevision", "schedule-1", 1, schedule.content_hash)
    current_case = case(revision=3, schedule_ref=schedule_ref)
    schedules = FakeScheduleStore()
    schedules.authority = schedule
    runs = FakeRunStore()
    application = EcommerceBusinessInvestigationApplication(
        case_store=FakeCaseStore(current_case), run_store=runs, schedule_store=schedules
    )
    request = TriggerBusinessInvestigationScheduleRequest.model_validate(
        {
            "runId": "run-disabled",
            "schedulePolicyRef": schedule_ref,
            "scheduledAt": "2026-09-01T01:00:00Z",
        }
    )
    with pytest.raises(ValueError, match="disabled"):
        application.trigger_schedule_policy(
            SCOPE,
            "schedule-1",
            request,
            expected_policy_revision=1,
            idempotency_key="disabled",
            actor="owner",
            occurred_at=NOW,
        )
    schedules.authority = policy()
    with pytest.raises(ValueError, match="current policy"):
        application.trigger_schedule_policy(
            SCOPE,
            "schedule-1",
            request,
            expected_policy_revision=2,
            idempotency_key="stale",
            actor="owner",
            occurred_at=NOW,
        )
    with pytest.raises(ValidationError, match="UTC with second precision"):
        TriggerBusinessInvestigationScheduleRequest.model_validate(
            {
                "runId": "run-bad-time",
                "schedulePolicyRef": schedule_ref,
                "scheduledAt": "2026-09-01T09:00:00+08:00",
            }
        )
    assert runs.requested is None


def test_generic_run_create_rejects_scheduled_bypass() -> None:
    application = EcommerceBusinessInvestigationApplication(
        case_store=FakeCaseStore(case()), run_store=FakeRunStore(), schedule_store=FakeScheduleStore()
    )
    with pytest.raises(ValueError, match="canonical SchedulePolicy"):
        application.create_run(
            SCOPE,
            "case-1",
            CreateBusinessInvestigationRunRequest.model_validate(
                {
                    "runId": "run-bypass",
                    "caseRef": ref("BusinessInvestigationCaseRevision", "case-1", 2, case().content_hash),
                    "analysisType": "weekly_business_review",
                    "triggerKind": "scheduled",
                    "triggerKey": "client-forged",
                }
            ),
            idempotency_key="bypass",
            actor="owner",
            occurred_at=NOW,
        )
