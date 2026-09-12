"""N6 immutable internal content-task contracts."""

from __future__ import annotations

from dataclasses import dataclass

from .sdk_ports import ExactRef


@dataclass(frozen=True, slots=True)
class ContentTaskSpec:
    title: str
    objective: str
    channels: tuple[str, ...]
    audience: str
    time_window: str
    constraints: tuple[str, ...]
    growth_plan_ref: ExactRef
    artifact_refs: tuple[ExactRef, ...]

    def __post_init__(self) -> None:
        text_limits = (
            (self.title, 120),
            (self.objective, 500),
            (self.audience, 300),
            (self.time_window, 200),
        )
        if any(type(value) is not str or not 1 <= len(value.strip()) <= limit for value, limit in text_limits):
            raise ValueError("content task text fields are required and bounded")
        if self.growth_plan_ref.resource_type != "GrowthPlanRevision":
            raise ValueError("content task requires an exact GrowthPlanRevision")
        if type(self.channels) is not tuple or not 1 <= len(self.channels) <= 12:
            raise ValueError("content channels must be an immutable non-empty tuple")
        if type(self.constraints) is not tuple or len(self.constraints) > 30:
            raise ValueError("content constraints must be an immutable bounded tuple")
        values = (*self.channels, *self.constraints)
        if any(
            type(value) is not str or not 1 <= len(value.strip()) <= 200
            for value in values
        ):
            raise ValueError("content business values must be non-blank strings")
        if len(values) != len(set(values)):
            raise ValueError("content business values must be unique")
        if (
            type(self.artifact_refs) is not tuple
            or len(self.artifact_refs) != 4
            or len(set(self.artifact_refs)) != 4
            or any(ref.resource_type != "ArtifactRevision" for ref in self.artifact_refs)
        ):
            raise ValueError("content task requires four unique Artifact revisions")

    def business_text_values(self) -> tuple[str, ...]:
        return (
            self.title,
            self.objective,
            *self.channels,
            self.audience,
            self.time_window,
            *self.constraints,
        )


__all__ = ["ContentTaskSpec"]
