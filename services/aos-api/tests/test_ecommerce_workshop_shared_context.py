from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_shared_context import EcommerceWorkshopSharedContext
from aos_api.ecommerce_workshop_shared_context_contracts import WorkshopNavigationTarget, WorkshopSharedBlocker, WorkshopSharedContext, WorkshopSharedContextEnvelope, WorkshopSharedContextPage, WorkshopSharedRef, WorkshopTimelineEvent

NOW = datetime(2026, 8, 24, 8, tzinfo=UTC)
HASH = "sha256:" + "a" * 64
TOKEN = "ctx_" + "a" * 40


def exact(resource_id: str) -> WorkshopSharedRef:
    return WorkshopSharedRef(authority="task-authority", resource_type="TaskRevision", resource_id=resource_id, revision=3, content_hash=HASH, receipt_id="receipt-1")


def test_shared_context_shell_is_tenant_bound_get_only_and_non_disclosing() -> None:
    payload = EcommerceWorkshopSharedContext(clock=lambda: NOW).read(org_id="org-org", project_id="dev-project", context_id=TOKEN).model_dump(mode="json", by_alias=True)
    assert payload["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert payload["context"]["status"] == "blocked"
    assert payload["timeline"] == payload["navigationTargets"] == []
    serialized = str(payload).lower()
    for forbidden in ("mobile", "openid", "email", "providerid", "returnurl", "evidencebody", "secret"):
        assert forbidden not in serialized


def test_ready_context_requires_exact_fresh_disclosed_authority() -> None:
    with pytest.raises(ValidationError):
        WorkshopSharedContext(context_id=TOKEN, status="ready", disclosure="allowed", evaluated_at=NOW, expires_at=NOW + timedelta(minutes=5), freshness="fresh", readiness="ready")


def test_navigation_target_fails_closed_without_disclosure() -> None:
    blocker = WorkshopSharedBlocker(code="TARGET_FORBIDDEN", dependency="navigation", required_action="re-authorize")
    with pytest.raises(ValidationError):
        WorkshopNavigationTarget(target_id="target_abcdefghijklmnop", status="forbidden", module_id="ecommerce.customer", blockers=[blocker])


def test_timeline_requires_stable_order_and_preserves_unknown_reconcile() -> None:
    ref = exact("task-1")
    context = WorkshopSharedContext(context_id=TOKEN, status="ready", source_module_id="ecommerce.task-cockpit", source_view_id="task", source_route="/workshop/task-cockpit", primary_ref=ref, purpose="review", disclosure="allowed", evaluated_at=NOW, data_cutoff=NOW, expires_at=NOW + timedelta(minutes=5), freshness="fresh", readiness="ready")
    later = WorkshopTimelineEvent(event_key="event-2", event_type="task", source_ref=ref, authority_sequence=2, occurred_at=NOW + timedelta(seconds=1), recorded_at=NOW + timedelta(seconds=1), actor_kind="system", safe_summary="task observed", status="completed")
    earlier = WorkshopTimelineEvent(event_key="event-1", event_type="task", source_ref=exact("task-2"), authority_sequence=1, occurred_at=NOW, recorded_at=NOW, actor_kind="system", safe_summary="task accepted", status="accepted")
    with pytest.raises(ValidationError):
        WorkshopSharedContextEnvelope(tenant=TenantContext(org_id="org-org", project_id="dev-project"), context=context, timeline=[later, earlier], page=WorkshopSharedContextPage(count=2))
    with pytest.raises(ValidationError):
        WorkshopTimelineEvent(event_key="event-3", event_type="action", source_ref=ref, authority_sequence=3, occurred_at=NOW, recorded_at=NOW, actor_kind="system", safe_summary="reconciled", status="reconciled", reconciled=True)
