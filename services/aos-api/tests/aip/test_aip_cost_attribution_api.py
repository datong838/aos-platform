from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_eval_authority_store import AipEvalAuthorityConflict
from aos_api.aip_eval_contracts import (
    AttributionSubjectType,
    CapabilityReceipt,
    CapabilityReceiptStatus,
    CostAttributionSummary,
    EvidenceQuality,
    UsageAttribution,
)
from aos_api.routers.aip_cost_attribution import (
    get_aip_cost_attribution_service,
    router,
)
from aos_api.tenant_scope import TenantScope

HASH = "a" * 64
NOW = datetime(2026, 8, 12, tzinfo=UTC)


@pytest.fixture()
def cost_api(client):
    client.app.include_router(router)
    tenant = TenantContext(org_id="dev-org", project_id="dev-project")
    capability = CapabilityReceipt(
        tenant=tenant,
        capability_receipt_id="capability-1",
        provider="runtime",
        provider_receipt_id="provider-cap-1",
        lineage_id="lineage-1",
        task_run_id="run-1",
        step_key="navigate",
        capability=ResourceRef(
            resource_type="capability",
            resource_id="browser.navigate",
            revision="3",
            authority="aos.plan",
        ),
        status=CapabilityReceiptStatus.SUCCEEDED,
        quality=EvidenceQuality.MEASURED,
        input_hash=HASH,
        output_hash=HASH,
        source_hash=HASH,
        observed_at=NOW,
    )
    attribution = UsageAttribution(
        tenant=tenant,
        attribution_id="attribution-1",
        receipt_id="usage-1",
        lineage_id="lineage-1",
        subject_type=AttributionSubjectType.TASK,
        subject=ResourceRef(
            resource_type="task",
            resource_id="task-1",
            revision="plan-1",
            authority="aos.task",
        ),
        quality=EvidenceQuality.MEASURED,
        weight=1,
        source_hash=HASH,
        created_at=NOW,
    )
    summary = CostAttributionSummary(
        tenant=tenant,
        subject_type=AttributionSubjectType.TASK,
        subject_id="task-1",
        subject_revision="plan-1",
        currency="CNY",
        measured_amount=1,
        estimated_amount=0,
        unknown_receipt_count=0,
        receipt_count=1,
        hard_budget_eligible=True,
        hard_budget_amount=1,
    )

    class FakeService:
        def __init__(self) -> None:
            self.calls: list[tuple[str, TenantScope]] = []
            self.error: Exception | None = None

        def _return(self, kind, scope, value):
            self.calls.append((kind, scope))
            if self.error:
                raise self.error
            return value

        def ingest_capability_receipt(self, scope, request):
            return self._return("capability", scope, capability)

        def list_capability_receipts(self, scope, lineage_id):
            return self._return("list-capability", scope, [capability])

        def attribute_usage(self, scope, request):
            return self._return("attribution", scope, attribution)

        def summarize_cost(self, scope, **kwargs):
            return self._return("summary", scope, [summary])

    service = FakeService()
    client.app.dependency_overrides[get_aip_cost_attribution_service] = lambda: service
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    yield client, service, headers
    client.app.dependency_overrides.pop(get_aip_cost_attribution_service, None)


def test_cost_authority_api_uses_authenticated_scope(cost_api) -> None:
    client, service, headers = cost_api
    capability_body = {
        "provider": "runtime",
        "providerReceiptId": "provider-cap-1",
        "lineageId": "lineage-1",
        "taskRunId": "run-1",
        "stepKey": "navigate",
        "capability": {
            "resourceType": "capability",
            "resourceId": "browser.navigate",
            "revision": "3",
            "authority": "aos.plan",
        },
        "status": "succeeded",
        "quality": "measured",
        "inputHash": HASH,
        "outputHash": HASH,
        "sourceHash": HASH,
        "observedAt": NOW.isoformat(),
    }
    assert (
        client.post(
            "/v1/aip/cost-authority/capability-receipts",
            headers=headers,
            json=capability_body,
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/v1/aip/cost-authority/lineages/lineage-1/capability-receipts",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/v1/aip/cost-authority/usage-attributions",
            headers=headers,
            json={
                "receiptId": "usage-1",
                "subjectType": "task",
                "subject": {
                    "resourceType": "task",
                    "resourceId": "task-1",
                    "revision": "plan-1",
                    "authority": "aos.task",
                },
                "quality": "measured",
                "weight": 1,
                "sourceHash": HASH,
            },
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/v1/aip/cost-authority/subjects/task/task-1/cost-summary",
            headers=headers,
            params={"subjectRevision": "plan-1"},
        ).status_code
        == 200
    )
    scope = TenantScope("dev-org", "dev-project")
    assert service.calls == [
        ("capability", scope),
        ("list-capability", scope),
        ("attribution", scope),
        ("summary", scope),
    ]


def test_cost_authority_maps_conflict_and_requires_auth(cost_api) -> None:
    client, service, headers = cost_api
    service.error = AipEvalAuthorityConflict("binding drift")
    response = client.get(
        "/v1/aip/cost-authority/subjects/task/task-1/cost-summary",
        headers=headers,
        params={"subjectRevision": "plan-1"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "AIP_EVAL_AUTHORITY_CONFLICT"
    assert client.get(
        "/v1/aip/cost-authority/subjects/task/task-1/cost-summary",
        params={"subjectRevision": "plan-1"},
    ).status_code in {401, 403}
