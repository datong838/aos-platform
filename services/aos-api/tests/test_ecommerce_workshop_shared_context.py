from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_shared_context import EcommerceWorkshopSharedContext
from aos_api.ecommerce_workshop_shared_context_contracts import WorkshopNavigationTarget, WorkshopSharedBlocker, WorkshopSharedContext, WorkshopSharedContextEnvelope, WorkshopSharedContextPage, WorkshopSharedRef, WorkshopTimelineEvent
from aos_api.ecommerce_workshop_shared_context_reader import SharedContextObservation
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 24, 8, tzinfo=UTC)
HASH = "sha256:" + "a" * 64
TOKEN = "ctx_" + "a" * 40


def exact(resource_id: str) -> WorkshopSharedRef:
    return WorkshopSharedRef(authority="task-authority", resource_type="TaskRevision", resource_id=resource_id, revision=3, content_hash=HASH, receipt_id="receipt-1")


def ready_context(**changes: object) -> WorkshopSharedContext:
    values = dict(context_id=TOKEN, status="ready", source_module_id="ecommerce.task-cockpit", source_view_id="task", source_route="/workshop/task-cockpit", primary_ref=exact("task-1"), purpose="review", permission_decision_ref=exact("permission-1"), disclosure_policy_ref=exact("policy-1"), markings=["public"], disclosure="allowed", evaluated_at=NOW, data_cutoff=NOW, expires_at=NOW + timedelta(minutes=5), freshness="fresh", readiness="ready")
    values.update(changes)
    return WorkshopSharedContext(**values)


class FakeReader:
    def __init__(self, value: SharedContextObservation) -> None:
        self.value = value
        self.call = None

    def read_context(self, scope: TenantScope, *, context_id: str, cutoff: datetime, limit: int) -> SharedContextObservation:
        self.call = (scope, context_id, cutoff, limit)
        return self.value


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
    context = ready_context(primary_ref=ref)
    later = WorkshopTimelineEvent(event_key="event-2", event_type="task", source_ref=ref, authority_sequence=2, occurred_at=NOW + timedelta(seconds=1), recorded_at=NOW + timedelta(seconds=1), actor_kind="system", safe_summary="task observed", status="completed")
    earlier = WorkshopTimelineEvent(event_key="event-1", event_type="task", source_ref=exact("task-2"), authority_sequence=1, occurred_at=NOW, recorded_at=NOW, actor_kind="system", safe_summary="task accepted", status="accepted")
    with pytest.raises(ValidationError):
        WorkshopSharedContextEnvelope(tenant=TenantContext(org_id="org-org", project_id="dev-project"), context=context, timeline=[later, earlier], page=WorkshopSharedContextPage(count=2))
    with pytest.raises(ValidationError):
        WorkshopTimelineEvent(event_key="event-3", event_type="action", source_ref=ref, authority_sequence=3, occurred_at=NOW, recorded_at=NOW, actor_kind="system", safe_summary="reconciled", status="reconciled", reconciled=True)


def test_bounded_assembler_returns_only_trusted_tenant_context() -> None:
    context = ready_context()
    event = WorkshopTimelineEvent(event_key="event-1", event_type="task", source_ref=context.primary_ref, authority_sequence=1, occurred_at=NOW, recorded_at=NOW, actor_kind="system", safe_summary="task accepted", status="accepted")
    target = WorkshopNavigationTarget(target_id="target_abcdefghijklmnop", status="available", module_id="ecommerce.customer", view_id="customer", route="/workshop/customer", subject_ref=context.primary_ref)
    scope = TenantScope("org-org", "dev-project")
    reader = FakeReader(SharedContextObservation(scope=scope, context=context, timeline=(event,), navigation_targets=(target,), active_routes=(("ecommerce.task-cockpit", "/workshop/task-cockpit"), ("ecommerce.customer", "/workshop/customer"))))
    payload = EcommerceWorkshopSharedContext(reader=reader, clock=lambda: NOW).read(org_id="org-org", project_id="dev-project", context_id=TOKEN)
    assert payload.context.status == "ready"
    assert len(payload.timeline) == len(payload.navigation_targets) == 1
    assert reader.call == (scope, TOKEN, NOW, 100)


@pytest.mark.parametrize("drift", ["tenant", "expired", "route", "timeline"])
def test_bounded_assembler_fails_closed_without_cross_scope_or_ref_disclosure(drift: str) -> None:
    scope = TenantScope("org-org", "dev-project")
    context = ready_context(evaluated_at=NOW - timedelta(minutes=1), data_cutoff=NOW - timedelta(minutes=1), expires_at=NOW) if drift == "expired" else ready_context()
    target = WorkshopNavigationTarget(target_id="target_abcdefghijklmnop", status="available", module_id="ecommerce.customer", view_id="customer", route="/workshop/customer", subject_ref=context.primary_ref)
    event = WorkshopTimelineEvent(event_key="event-1", event_type="task", source_ref=exact("unreachable") if drift == "timeline" else context.primary_ref, authority_sequence=1, occurred_at=NOW, recorded_at=NOW, actor_kind="system", safe_summary="task accepted", status="accepted")
    observation = SharedContextObservation(scope=TenantScope("dev-org", "dev-project") if drift == "tenant" else scope, context=context, timeline=(event,), navigation_targets=(target,), active_routes=(("ecommerce.task-cockpit", "/workshop/task-cockpit"), ("ecommerce.customer", "/workshop/customer-drift" if drift == "route" else "/workshop/customer")))
    payload = EcommerceWorkshopSharedContext(reader=FakeReader(observation), clock=lambda: NOW).read(org_id="org-org", project_id="dev-project", context_id=TOKEN)
    assert payload.context.status == ("forbidden" if drift == "tenant" else "expired" if drift == "expired" else "blocked")
    assert payload.timeline == payload.navigation_targets == []
    assert payload.context.primary_ref is None
