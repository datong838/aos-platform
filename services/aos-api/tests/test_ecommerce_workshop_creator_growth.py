"""W2-04A strict creator-growth contract and shell tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_creator_growth import EcommerceWorkshopCreatorGrowth
from aos_api.ecommerce_workshop_creator_growth_contracts import (
    CreatorBusinessStage,
    CreatorGrowthCountLedger,
    CreatorWorkflowPhase,
    WorkshopCreatorGrowthViewEnvelope,
)


NOW = datetime(2026, 8, 24, 16, 0, tzinfo=UTC)


def _body() -> dict[str, object]:
    return EcommerceWorkshopCreatorGrowth(clock=lambda: NOW).read(
        org_id="org-org", project_id="dev-project"
    ).model_dump(by_alias=True)


def test_shell_preserves_two_axes_five_stages_and_fails_closed() -> None:
    body = _body()
    assert body["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert [item["businessStage"] for item in body["slices"]] == [
        item.value for item in CreatorBusinessStage
    ]
    assert all(item["workflowPhases"] == [phase.value for phase in CreatorWorkflowPhase] for item in body["slices"])
    assert all(item["status"] == "blocked" and item["authorityRefs"] == [] for item in body["slices"])
    assert body["page"] == {"limit": 100, "count": 0, "hasMore": False, "nextCursor": None}


def test_population_ledger_is_conservative() -> None:
    ledger = CreatorGrowthCountLedger(
        input=10, eligible=3, excluded=2, needs_review=1, unknown=1, deduplicated=3
    )
    assert ledger.input == 10
    with pytest.raises(ValidationError):
        CreatorGrowthCountLedger(
            input=9, eligible=3, excluded=2, needs_review=1, unknown=1, deduplicated=3
        )


def test_contract_rejects_naive_time_order_cutoff_count_and_extra_drift() -> None:
    for mutate in (
        lambda body: body.update(evaluatedAt=datetime(2026, 8, 24, 16, 0)),
        lambda body: body.update(slices=list(reversed(body["slices"]))),
        lambda body: body["slices"][0].update(dataCutoff="2026-08-24T16:01:00Z"),
        lambda body: body["page"].update(count=1),
        lambda body: body.update(contact="forbidden"),
    ):
        body = _body()
        mutate(body)
        with pytest.raises(ValidationError):
            WorkshopCreatorGrowthViewEnvelope.model_validate(body)


def test_contract_rejects_false_ready_and_cross_axis_ref() -> None:
    false_ready = _body()
    false_ready["slices"][0]["status"] = "ready"
    with pytest.raises(ValidationError):
        WorkshopCreatorGrowthViewEnvelope.model_validate(false_ready)

    cross_axis = _body()
    cross_axis["slices"][0]["authorityRefs"] = [{
        "resourceType": "CreatorContractRevision",
        "resourceId": "contract-1",
        "revision": 1,
        "contentHash": "sha256:" + "a" * 64,
        "receiptId": "receipt-1",
        "workflowPhase": "matching",
        "businessStage": "contract",
        "piiRefs": [],
    }]
    with pytest.raises(ValidationError):
        WorkshopCreatorGrowthViewEnvelope.model_validate(cross_axis)


def test_contract_rejects_duplicate_blocker_identity() -> None:
    body = _body()
    body["slices"][0]["blockers"].append(body["slices"][0]["blockers"][0])
    with pytest.raises(ValidationError):
        WorkshopCreatorGrowthViewEnvelope.model_validate(body)
