"""W2-05A strict media-studio contract shell tests."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_workshop_media_studio import EcommerceWorkshopMediaStudio
from aos_api.ecommerce_workshop_media_studio_contracts import (
    MediaAxisReadiness,
    MediaBlocker,
    MediaCountLedger,
    MediaExactRef,
    MediaReadinessAxis,
    MediaStudioSliceId,
)
from aos_api.ecommerce_workshop_media_studio_reader import MediaStudioSliceObservation
from aos_api.tenant_scope import TenantScope
from aos_api.aip_media_provider_job_contracts import MediaJobStatus
from aos_api.aip_production_contracts import ExactRevisionRef


HASH = "sha256:" + "a" * 64


class FakeReader:
    def __init__(self, *, drift: str | None = None) -> None:
        self.drift = drift
        self.calls: list[tuple[str, TenantScope, datetime, int]] = []

    def _read(self, name: str, scope: TenantScope, cutoff: datetime, limit: int) -> MediaStudioSliceObservation:
        self.calls.append((name, scope, cutoff, limit))
        if self.drift == name:
            scope = TenantScope(org_id="dev-org", project_id="dev-project")
        ref = MediaExactRef(resourceType="CanonicalMediaFact", resourceId=f"{name}-1", revision=1, contentHash=HASH, receiptId=f"receipt-{name}-1")
        axes = tuple(
            MediaAxisReadiness(axis=axis, status="ready", exactRef=ref)
            for axis in MediaReadinessAxis
        )
        return MediaStudioSliceObservation(scope=scope, data_cutoff=cutoff, readiness_axes=axes, authority_refs=(ref,))

    def read_context(self, scope, *, cutoff, limit):
        return self._read("context", scope, cutoff, limit)

    def read_execution(self, scope, *, cutoff, limit):
        return self._read("execution", scope, cutoff, limit)

    def read_delivery(self, scope, *, cutoff, limit):
        return self._read("delivery", scope, cutoff, limit)


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


def test_bounded_reader_returns_exact_refs_and_trusted_ready_slices() -> None:
    reader = FakeReader()
    view = EcommerceWorkshopMediaStudio(reader=reader, clock=lambda: datetime(2026, 8, 24, tzinfo=UTC)).read(org_id="org-org", project_id="dev-project")

    assert [item.status for item in view.slices] == ["ready", "ready", "ready"]
    assert [item.count_ledger.ready for item in view.slices] == [6, 6, 6]
    assert view.page.count == 3
    assert [call[3] for call in reader.calls] == [100, 100, 100]


def test_one_reader_tenant_drift_blocks_only_its_slice() -> None:
    view = EcommerceWorkshopMediaStudio(reader=FakeReader(drift="execution"), clock=lambda: datetime(2026, 8, 24, tzinfo=UTC)).read(org_id="org-org", project_id="dev-project")

    assert [item.status for item in view.slices] == ["ready", "blocked", "ready"]
    assert view.slices[1].authority_refs == []
    assert view.slices[1].count_ledger.target == 6


def test_unknown_axis_stays_blocked_and_out_of_ready() -> None:
    blocker = MediaBlocker(code="PROVIDER_OUTCOME_UNKNOWN", dependency="provider-reconcile", requiredAction="reconcile original request fingerprint")
    axis = MediaAxisReadiness(axis="provider", status="unknown", blockers=[blocker])
    assert axis.status == "unknown"
    assert axis.exact_ref is None


def test_provider_job_projection_preserves_four_layer_contribution_chain() -> None:
    def ref(kind: str, name: str) -> ExactRevisionRef:
        return ExactRevisionRef(
            resourceType=kind, resourceId=name, revision=1, contentHash="b" * 64
        )

    job = SimpleNamespace(
        job_id="media-job-1",
        status=MediaJobStatus.UNKNOWN,
        sequence=3,
        task_run_ref=ref("TaskRun", "logic-run-1"),
        input_scan_refs=[ref("MediaScanObservation", "scan-1")],
        blocker_codes=["MEDIA_PROVIDER_RESULT_UNKNOWN_RECONCILE_REQUIRED"],
        binding=SimpleNamespace(
            capability_ref=ref("CapabilityRevision", "media-generate"),
            binding_ref=ref("CapabilityBindingRevision", "content-officer-binding"),
            model_ref=ref("RegisteredModelRevision", "image-model"),
            provider_ref=ref("ProviderInstanceRevision", "image-provider"),
            adapter_ref=ref("MediaProviderAdapterRevision", "image-adapter"),
        ),
    )

    class Store:
        def list_jobs(self, scope, *, limit):  # type: ignore[no-untyped-def]
            assert scope == TenantScope("org-org", "dev-project")
            assert limit == 100
            return SimpleNamespace(items=[job])

    view = EcommerceWorkshopMediaStudio(
        provider_job_store=Store(),  # type: ignore[arg-type]
        clock=lambda: datetime(2026, 8, 25, tzinfo=UTC),
    ).read(org_id="org-org", project_id="dev-project")

    assert view.schema_version.endswith("/v2")
    assert view.provider_jobs_status == "ready"
    assert view.provider_job_blockers == []
    contribution = view.provider_jobs[0]
    assert contribution.atomic_capability_ref.resource_id == "media-generate"
    assert contribution.logic_ref.resource_id == "logic-run-1"
    assert contribution.primary_colleague == "内容官"
    assert contribution.colleague_binding_ref.resource_id == "content-officer-binding"
    assert contribution.status == "unknown"
    assert contribution.external_effects_allowed is False
