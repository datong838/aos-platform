"""Internal input only: current installed owners must establish its authority."""
from datetime import datetime
from typing import Self

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.source_readiness_contracts import (
    CANONICAL_QYH_SOURCES, ExactResourceRef, LatestRunObservation,
    PolicyObservation, SourceCounts,
)

SNAPSHOT_REF_TYPES = {
    "source_config_ref": "DataSourceConfigurationRevision",
    "mapping_ref": "Mapping",
    "schema_ref": "SchemaFingerprint",
    "masking_policy_ref": "MaskingPolicy",
    "freshness_policy_ref": "SnapshotReadinessPolicy",
    "quality_policy_ref": "SnapshotFactQualityPolicy",
    "reconciliation_policy_ref": "SnapshotReadinessPolicy",
    "query_capability_ref": "CapabilityBinding",
}


def _aware(value: datetime | None) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("snapshot times require a timezone")


class InstalledSnapshotReadinessSource(AipContractModel):
    tenant: TenantContext
    source_id: str = Field(min_length=1, pattern=r"^\S+$")
    pipeline_id: str
    object_type: str
    observed_at: datetime | None = None
    source_event_at: datetime | None = None
    projected_at: datetime | None = None
    freshness_expires_at: datetime | None = None
    source_config_ref: ExactResourceRef | None = None
    mapping_ref: ExactResourceRef | None = None
    schema_ref: ExactResourceRef | None = None
    masking_policy_ref: ExactResourceRef | None = None
    freshness_policy_ref: ExactResourceRef | None = None
    quality_policy_ref: ExactResourceRef | None = None
    reconciliation_policy_ref: ExactResourceRef | None = None
    query_capability_ref: ExactResourceRef | None = None
    latest_run: LatestRunObservation
    counts: SourceCounts
    quality: PolicyObservation

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for key, expected in SNAPSHOT_REF_TYPES.items():
            ref = getattr(self, key)
            if ref is not None and ref.resource_type != expected:
                raise ValueError(f"{key} requires {expected}")
        binding = self.query_capability_ref
        if binding is not None and (not binding.revision.isascii()
                or not binding.revision.isdigit() or int(binding.revision) < 1
                or str(int(binding.revision)) != binding.revision):
            raise ValueError("binding revision must be a canonical positive integer")
        if self.quality.rule_ref != self.quality_policy_ref:
            raise ValueError("quality observation must reference the exact quality policy")
        if self.quality_policy_ref is None and self.quality.status != "unknown":
            raise ValueError("quality without policy must remain unknown")
        for value in (self.observed_at, self.source_event_at, self.projected_at,
                self.freshness_expires_at, self.latest_run.scheduled_for,
                self.latest_run.started_at, self.latest_run.finished_at):
            _aware(value)
        run = self.latest_run
        if run.status == "succeeded" and (not run.run_id or run.finished_at is None
                or self.observed_at is None):
            raise ValueError("succeeded snapshot requires observed time and finished run identity")
        if run.started_at and run.finished_at and run.started_at > run.finished_at:
            raise ValueError("run finished before it started")
        counts = self.counts
        if all(v is not None for v in (counts.source_total, counts.source_active, counts.source_deleted)):
            if counts.source_active + counts.source_deleted != counts.source_total:
                raise ValueError("active and deleted counts must sum to source total")
        return self


class InstalledSnapshotReadinessInput(AipContractModel):
    tenant: TenantContext
    checked_at: datetime
    cutoff_at: datetime
    sources: list[InstalledSnapshotReadinessSource]

    @model_validator(mode="after")
    def _canonical_current_input(self) -> Self:
        _aware(self.checked_at)
        _aware(self.cutoff_at)
        if self.cutoff_at > self.checked_at:
            raise ValueError("snapshot cutoff exceeds check time")
        expected = [(s.pipeline_id, s.object_type) for s in CANONICAL_QYH_SOURCES]
        if [(s.pipeline_id, s.object_type) for s in self.sources] != expected:
            raise ValueError("snapshot requires ordered canonical P01-P12 identities")
        for source in self.sources:
            if source.tenant != self.tenant:
                raise ValueError("snapshot source tenant mismatch")
            for value in (source.observed_at, source.source_event_at):
                if value is not None and value > self.cutoff_at:
                    raise ValueError("source observation exceeds cutoff")
            for value in (source.projected_at, source.latest_run.started_at,
                          source.latest_run.finished_at):
                if value is not None and value > self.checked_at:
                    raise ValueError("snapshot includes future run or projection")
        return self
