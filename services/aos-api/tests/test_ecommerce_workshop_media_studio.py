"""W2-05A strict media-studio contract shell tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_media_studio import EcommerceWorkshopMediaStudio
from aos_api.ecommerce_workshop_media_studio_contracts import (
    MediaCountLedger,
    MediaExactRef,
    MediaReadinessAxis,
    MediaStudioSliceId,
)


def test_media_studio_shell_is_three_slice_target_only_and_count_safe() -> None:
    view = EcommerceWorkshopMediaStudio(
        clock=lambda: datetime(2026, 8, 24, tzinfo=UTC)
    ).read(org_id="org-org", project_id="dev-project")

    assert [item.slice_id for item in view.slices] == list(MediaStudioSliceId)
    assert all([item.axis for item in slice_.readiness_axes] == list(MediaReadinessAxis) for slice_ in view.slices)
    assert all(axis.status == "target" and axis.exact_ref is None for slice_ in view.slices for axis in slice_.readiness_axes)
    assert all(slice_.count_ledger.target == 6 and slice_.count_ledger.ready == 0 for slice_ in view.slices)
    assert view.page.count == 0


def test_target_state_cannot_be_promoted_to_ready() -> None:
    with pytest.raises(ValidationError):
        from aos_api.ecommerce_workshop_media_studio_contracts import MediaAxisReadiness

        MediaAxisReadiness(
            axis="provider",
            status="ready",
            targetContractRef="ADR-86#provider",
            gaps=["provider route missing"],
            blockers=[],
        )


def test_media_ledgers_and_exact_refs_fail_closed() -> None:
    with pytest.raises(ValidationError):
        MediaCountLedger(denominator=2, ready=1, target=0, blocked=0, unknown=0, conflict=0, notApplicable=0)
    with pytest.raises(ValidationError):
        MediaExactRef(resourceType="Artifact", resourceId="a1", revision=1, contentHash="sha256:bad", receiptId="r1")


def test_media_clock_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        EcommerceWorkshopMediaStudio(clock=lambda: datetime(2026, 8, 24)).read(
            org_id="org-org", project_id="dev-project"
        )
