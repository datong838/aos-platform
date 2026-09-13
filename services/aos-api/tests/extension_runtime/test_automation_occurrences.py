from __future__ import annotations

import importlib.util
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from aos_api.aip_logic_automation_scheduler import run_due_schedule_binding
from aos_api.automation_dispatcher import dispatch_one_occurrence
from aos_api.automation_occurrence_store import ClaimedOccurrence, ScheduleBinding
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseRevision
from aos_api.ecommerce_business_investigation_schedule import BusinessInvestigationSchedulePolicyRevision
from aos_api.tenant_scope import TenantScope


ROOT = Path(__file__).resolve().parents[4]
GROWTH_BACKEND = ROOT / "bundles/solutions/ecommerce-growth/backend"


def _growth_modules():
    sdk_root = ROOT / "packages/aos-extension-sdk/python"
    sys.path[:0] = [str(GROWTH_BACKEND), str(sdk_root)]
    try:
        from ecommerce_growth.ecommerce_business_investigation_case import (
            AnalysisType,
            BusinessInvestigationCase,
            CASE_SCHEMA,
            CaseLifecycle,
            canonical_hash,
        )
        from ecommerce_growth.ecommerce_business_investigation_schedule import (
            SCHEDULE_SCHEMA,
            ScheduleCadence,
            ScheduleKind,
            SchedulePolicy,
        )
        from ecommerce_growth.sdk_ports import ExactRef, TenantRef

        return SimpleNamespace(**locals())
    finally:
        sys.path[:2] = []


def _ref(module, kind: str, identifier: str):
    return module.ExactRef(kind, identifier, 1, "sha256:" + "a" * 64)


def _contract_hash(module, fields):
    def ref(value):
        if value is None:
            return None
        return {
            "resourceType": value.resource_type, "resourceId": value.resource_id,
            "revision": value.revision, "contentHash": value.content_hash, "receiptId": value.receipt_id,
        }

    tenant = {"orgId": fields["tenant"].org_id, "projectId": fields["tenant"].project_id}
    created_at = fields["created_at"].isoformat().replace("+00:00", "Z")
    if "case_id" in fields:
        payload = {
            "schemaVersion": fields["schema_version"], "tenant": tenant, "caseId": fields["case_id"],
            "revision": fields["revision"], "version": fields["version"], "priorRef": ref(fields["prior_ref"]),
            "lifecycle": fields["lifecycle"].value, "analysisType": fields["analysis_type"].value,
            "title": fields["title"], "purposeCode": fields["purpose_code"],
            "channelRef": ref(fields["channel_ref"]), "businessEntityRef": ref(fields["business_entity_ref"]),
            "entityChannelBindingRef": ref(fields["entity_channel_binding_ref"]),
            "investigationProfileRef": ref(fields["investigation_profile_ref"]), "scopeRef": ref(fields["scope_ref"]),
            "schedulePolicyRef": ref(fields["schedule_policy_ref"]), "createdBy": fields["created_by"],
            "createdAt": created_at,
        }
    else:
        payload = {
            "schemaVersion": fields["schema_version"], "tenant": tenant,
            "schedulePolicyId": fields["policy_id"], "revision": fields["revision"],
            "version": fields["version"], "priorRef": ref(fields["prior_ref"]), "caseRef": ref(fields["case_ref"]),
            "analysisType": fields["analysis_type"].value, "policyKind": fields["policy_kind"].value,
            "cadence": fields["cadence"].value, "enabled": fields["enabled"],
            "overlapPolicy": fields["overlap_policy"], "timezone": fields["timezone"],
            "weeklyDay": fields["weekly_day"], "localTime": fields["local_time"],
            "createdBy": fields["created_by"], "createdAt": created_at,
        }
    return module.canonical_hash(payload)


def _rehash_authority(module, payload):
    value = dict(payload)
    value.pop("contentHash", None)
    value["contentHash"] = module.canonical_hash(value)
    return value


def test_growth_n1_contracts_are_platform_independent_and_exact():
    module = _growth_modules()
    tenant = module.TenantRef("org-org", "dev-project")
    fields = {
        "schema_version": module.CASE_SCHEMA,
        "tenant": tenant,
        "case_id": "case-weekly",
        "revision": 1,
        "version": 1,
        "lifecycle": module.CaseLifecycle.DRAFT,
        "analysis_type": module.AnalysisType.WEEKLY_BUSINESS_REVIEW,
        "title": "栖月汇微商城每周经营复盘",
        "purpose_code": "weekly.review",
        "channel_ref": _ref(module, "ChannelRevision", "niushop"),
        "business_entity_ref": _ref(module, "BusinessEntityRevision", "qiyuehui"),
        "entity_channel_binding_ref": _ref(module, "BusinessEntityChannelBindingRevision", "binding"),
        "investigation_profile_ref": _ref(module, "InvestigationProfileRevision", "profile"),
        "scope_ref": _ref(module, "InvestigationScopeRevision", "scope"),
        "schedule_policy_ref": None,
        "prior_ref": None,
        "created_by": "operator",
        "created_at": datetime(2026, 9, 7, 12, tzinfo=UTC),
    }
    digest = _contract_hash(module, fields)
    case = module.BusinessInvestigationCase(**fields, content_hash=digest)
    assert case.title == "栖月汇微商城每周经营复盘"
    assert module.BusinessInvestigationCase.from_authority(case.authority_payload()) == case
    old_case = BusinessInvestigationCaseRevision.model_validate(case.authority_payload())
    assert old_case.calculated_content_hash() == case.content_hash
    assert "aos_api" not in (GROWTH_BACKEND / "ecommerce_growth/ecommerce_business_investigation_case.py").read_text()
    with pytest.raises(ValueError, match="hash drifted"):
        module.BusinessInvestigationCase(**fields, content_hash="sha256:" + "0" * 64)


def test_weekly_policy_requires_exact_case_and_natural_slot():
    module = _growth_modules()
    tenant = module.TenantRef("org-org", "dev-project")
    fields = {
        "schema_version": module.SCHEDULE_SCHEMA,
        "tenant": tenant,
        "policy_id": "weekly-qyh",
        "revision": 1,
        "version": 1,
        "prior_ref": None,
        "case_ref": _ref(module, "BusinessInvestigationCaseRevision", "case-weekly"),
        "analysis_type": module.AnalysisType.WEEKLY_BUSINESS_REVIEW,
        "policy_kind": module.ScheduleKind.WEEKLY_REVIEW,
        "cadence": module.ScheduleCadence.WEEKLY,
        "enabled": False,
        "overlap_policy": "skip",
        "timezone": "Asia/Shanghai",
        "weekly_day": 1,
        "local_time": "08:00",
        "created_by": "operator",
        "created_at": datetime(2026, 9, 1, tzinfo=UTC),
    }
    digest = _contract_hash(module, fields)
    policy = module.SchedulePolicy(**fields, content_hash=digest)
    assert policy.slot_at(datetime(2026, 9, 7, tzinfo=UTC)) == datetime(2026, 9, 7, tzinfo=UTC)
    assert module.SchedulePolicy.from_authority(policy.authority_payload()) == policy
    old_policy = BusinessInvestigationSchedulePolicyRevision.model_validate(policy.authority_payload())
    assert old_policy.calculated_content_hash() == policy.content_hash


def test_growth_contract_acceptance_is_not_wider_than_legacy_authority():
    module = _growth_modules()
    tenant = module.TenantRef("org-org", "dev-project")
    case_fields = {
        "schema_version": module.CASE_SCHEMA,
        "tenant": tenant,
        "case_id": "case-weekly",
        "revision": 1,
        "version": 1,
        "lifecycle": module.CaseLifecycle.DRAFT,
        "analysis_type": module.AnalysisType.WEEKLY_BUSINESS_REVIEW,
        "title": "栖月汇微商城每周经营复盘",
        "purpose_code": "weekly.review",
        "channel_ref": _ref(module, "ChannelRevision", "niushop"),
        "business_entity_ref": _ref(module, "BusinessEntityRevision", "qiyuehui"),
        "entity_channel_binding_ref": _ref(module, "BusinessEntityChannelBindingRevision", "binding"),
        "investigation_profile_ref": _ref(module, "InvestigationProfileRevision", "profile"),
        "scope_ref": _ref(module, "InvestigationScopeRevision", "scope"),
        "schedule_policy_ref": None,
        "prior_ref": None,
        "created_by": "operator",
        "created_at": datetime(2026, 9, 7, 12, tzinfo=UTC),
    }
    valid_case = module.BusinessInvestigationCase(
        **case_fields, content_hash=_contract_hash(module, case_fields)
    )
    for field, value in (("caseId", "c" * 201), ("title", "t" * 501), ("createdBy", "")):
        payload = _rehash_authority(module, {**valid_case.authority_payload(), field: value})
        with pytest.raises(ValueError):
            module.BusinessInvestigationCase.from_authority(payload)
        with pytest.raises(ValueError):
            BusinessInvestigationCaseRevision.model_validate(payload)

    schedule_fields = {
        "schema_version": module.SCHEDULE_SCHEMA,
        "tenant": tenant,
        "policy_id": "weekly-qyh",
        "revision": 1,
        "version": 1,
        "prior_ref": None,
        "case_ref": _ref(module, "BusinessInvestigationCaseRevision", "case-weekly"),
        "analysis_type": module.AnalysisType.WEEKLY_BUSINESS_REVIEW,
        "policy_kind": module.ScheduleKind.WEEKLY_REVIEW,
        "cadence": module.ScheduleCadence.WEEKLY,
        "enabled": False,
        "overlap_policy": "skip",
        "timezone": "Asia/Shanghai",
        "weekly_day": 1,
        "local_time": "08:00",
        "created_by": "operator",
        "created_at": datetime(2026, 9, 1, tzinfo=UTC),
    }
    valid_schedule = module.SchedulePolicy(
        **schedule_fields, content_hash=_contract_hash(module, schedule_fields)
    )
    for field, value in (
        ("schedulePolicyId", "p" * 201),
        ("createdBy", "c" * 201),
        ("localTime", "8:00"),
    ):
        payload = _rehash_authority(module, {**valid_schedule.authority_payload(), field: value})
        with pytest.raises(ValueError):
            module.SchedulePolicy.from_authority(payload)
        with pytest.raises(ValueError):
            BusinessInvestigationSchedulePolicyRevision.model_validate(payload)

    for field, value in (
        ("resourceType", "r" * 121),
        ("resourceId", "i" * 241),
        ("receiptId", "x" * 241),
    ):
        payload = {
            "resourceType": "ChannelRevision",
            "resourceId": "niushop",
            "revision": 1,
            "contentHash": "sha256:" + "a" * 64,
            "receiptId": "receipt-1",
            field: value,
        }
        with pytest.raises(ValueError):
            module.ExactRef(
                payload["resourceType"], payload["resourceId"], payload["revision"],
                payload["contentHash"], payload["receiptId"],
            )
        with pytest.raises(ValueError):
            InvestigationExactRef.model_validate(payload)


def test_growth_contracts_reject_identity_lifecycle_and_exact_hash_drift():
    module = _growth_modules()
    tenant = module.TenantRef("org-org", "dev-project")
    base = {
        "schema_version": module.CASE_SCHEMA,
        "tenant": tenant,
        "case_id": "case-weekly",
        "revision": 1,
        "version": 1,
        "prior_ref": None,
        "lifecycle": module.CaseLifecycle.DRAFT,
        "analysis_type": module.AnalysisType.WEEKLY_BUSINESS_REVIEW,
        "title": "栖月汇微商城每周经营复盘",
        "purpose_code": "weekly.review",
        "channel_ref": _ref(module, "ChannelRevision", "niushop"),
        "business_entity_ref": _ref(module, "BusinessEntityRevision", "qiyuehui"),
        "entity_channel_binding_ref": _ref(module, "BusinessEntityChannelBindingRevision", "binding"),
        "investigation_profile_ref": _ref(module, "InvestigationProfileRevision", "profile"),
        "scope_ref": _ref(module, "InvestigationScopeRevision", "scope"),
        "schedule_policy_ref": None,
        "created_by": "operator",
        "created_at": datetime(2026, 9, 7, 12, tzinfo=UTC),
    }
    first = module.BusinessInvestigationCase(**base, content_hash=_contract_hash(module, base))
    successor = {
        **base,
        "revision": 2,
        "version": 2,
        "lifecycle": module.CaseLifecycle.CLOSED,
        "prior_ref": module.ExactRef(
            "BusinessInvestigationCaseRevision", first.case_id, 1, "sha256:" + "0" * 64
        ),
    }
    second = module.BusinessInvestigationCase(
        **successor, content_hash=_contract_hash(module, successor)
    )
    with pytest.raises(ValueError, match="exact prior"):
        second.validate_successor(first)
    invalid = {**successor, "prior_ref": module.ExactRef(
        "BusinessInvestigationCaseRevision", first.case_id, 1, first.content_hash
    ), "lifecycle": module.CaseLifecycle.DRAFT}
    second = module.BusinessInvestigationCase(**invalid, content_hash=_contract_hash(module, invalid))
    with pytest.raises(ValueError, match="lifecycle"):
        second.validate_successor(first)

    bad_schedule = {
        "schema_version": module.SCHEDULE_SCHEMA,
        "tenant": tenant,
        "policy_id": "weekly-qyh",
        "revision": 1,
        "version": 1,
        "prior_ref": None,
        "case_ref": _ref(module, "BusinessInvestigationCaseRevision", "case-weekly"),
        "analysis_type": module.AnalysisType.WEEKLY_BUSINESS_REVIEW,
        "policy_kind": module.ScheduleKind.TOPIC_ANALYSIS,
        "cadence": module.ScheduleCadence.WEEKLY,
        "enabled": False,
        "overlap_policy": "skip",
        "timezone": "Asia/Shanghai",
        "weekly_day": 1,
        "local_time": "08:00",
        "created_by": "operator",
        "created_at": datetime(2026, 9, 1, tzinfo=UTC),
    }
    with pytest.raises(ValueError, match="kind/cadence"):
        module.SchedulePolicy(**bad_schedule, content_hash=_contract_hash(module, bad_schedule))


def _binding() -> ScheduleBinding:
    return ScheduleBinding(
        policy_id="weekly-qyh",
        policy_revision=1,
        policy_hash="sha256:" + "b" * 64,
        operation_id="ecommerce_growth_schedule_trigger",
        installation_id=UUID("11111111-1111-4111-8111-111111111111"),
        generation=UUID("22222222-2222-4222-8222-222222222222"),
        execution_epoch=3,
        cadence="weekly",
        effective_from=datetime(2026, 8, 1, tzinfo=UTC),
        weekly_day=1,
        local_time="08:00",
        approved=True,
        enabled=True,
    )


def test_scheduler_records_all_slots_and_only_latest_24h_slot_is_pending():
    captured = {}

    class Store:
        def record_due_batch(self, scope, binding, **kwargs):
            captured.update(kwargs)

    result = run_due_schedule_binding(
        TenantScope("org-org", "dev-project"),
        _binding(),
        watermark=datetime(2026, 8, 9, tzinfo=UTC),
        now=datetime(2026, 8, 31, 1, tzinfo=UTC),
        store=Store(),
    )
    assert result == {"due": 4, "pending": 1, "missed": 3}
    assert [slot[3] for slot in captured["slots"]] == ["missed", "missed", "missed", "pending"]
    assert captured["new_watermark"] == datetime(2026, 8, 31, 1, tzinfo=UTC)


def test_schedule_binding_rejects_noncanonical_operation_and_runtime_identity():
    with pytest.raises(ValueError, match="operation id"):
        ScheduleBinding(**{**asdict(_binding()), "operation_id": "bad.operation"})
    with pytest.raises(ValueError, match="canonical UUID"):
        ScheduleBinding(**{**asdict(_binding()), "installation_id": "not-a-uuid"})


def test_dispatcher_holds_unknown_result_for_receipt_reconciliation():
    claim = ClaimedOccurrence(
        UUID("33333333-3333-4333-8333-333333333333"),
        "weekly-qyh",
        1,
        "ecommerce_growth_schedule_trigger",
        _binding().installation_id,
        _binding().generation,
        3,
        "worker-1",
        datetime(2026, 9, 7, 12, 5, tzinfo=UTC),
        UUID("44444444-4444-4444-8444-444444444444"),
        "automation-occurrence:33333333-3333-4333-8333-333333333333",
    )
    events = []

    class Store:
        def reconcile_expired_claims(self, *args, **kwargs):
            return 0

        def claim_next(self, *args, **kwargs):
            return claim

        def mark_needs_attention(self, *args, **kwargs):
            events.append("needs_attention")

        def record_target_receipt(self, *args, **kwargs):
            events.append("accepted")

    assert not dispatch_one_occurrence(
        TenantScope("org-org", "dev-project"),
        owner="worker-1",
        occurred_at=datetime(2026, 9, 7, 12, tzinfo=UTC),
        handler=lambda _: (_ for _ in ()).throw(TimeoutError()),
        store=Store(),
    )
    assert events == ["needs_attention"]


def test_dispatcher_reconciles_expired_attempt_without_second_handler_call():
    events = []

    class Store:
        def reconcile_expired_claims(self, *args, **kwargs):
            events.append("reconciled")
            return 1

        def claim_next(self, *args, **kwargs):
            return None

    assert not dispatch_one_occurrence(
        TenantScope("org-org", "dev-project"),
        owner="worker-2",
        occurred_at=datetime(2026, 9, 7, 12, tzinfo=UTC),
        handler=lambda _: events.append("handler-called"),
        store=Store(),
    )
    assert events == ["reconciled"]


def test_occurrence_migration_is_rls_scoped_atomic_outbox_and_retain_only():
    path = ROOT / "services/aos-api/alembic/versions/ar2_002_automation_occurrence.py"
    spec = importlib.util.spec_from_file_location("ar2_002_test", path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    statements = []
    migration.op = SimpleNamespace(execute=statements.append)
    migration.upgrade()
    sql = "\n".join(statements)
    assert "CREATE TABLE automation_occurrence" in sql
    assert "CREATE TABLE automation_occurrence_outbox" in sql
    assert "CREATE TABLE automation_occurrence_dispatch_attempt" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "automation_occurrence_schedule_unique" in sql
    assert "automation_occurrence_event_unique" in sql
    with pytest.raises(RuntimeError, match="must be retained"):
        migration.downgrade()


def test_claim_target_rejects_noncanonical_identity_before_database():
    from uuid import uuid4
    from aos_api.automation_occurrence_store import ClaimTarget

    for args in (('', uuid4(), uuid4()), ('operation ', uuid4(), uuid4()),
                 ('operation', str(uuid4()), uuid4()), ('operation', uuid4(), None)):
        with pytest.raises(ValueError):
            ClaimTarget(*args)
