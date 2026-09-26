"""N6 immutable internal content-task contracts."""

from __future__ import annotations

from dataclasses import dataclass

from .sdk_ports import ExactRef
from .sales_weapon_brief import SalesWeaponBriefDraft


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


def content_task_from_sales_weapon_brief(
    brief: SalesWeaponBriefDraft,
    *,
    artifact_refs: tuple[ExactRef, ...],
    channels: tuple[str, ...],
    time_window: str,
) -> ContentTaskSpec:
    """Map an already-validated draft into the existing internal Task shape.

    This does not publish the draft or prove current source/plan approval. The
    Host's exact review and Handoff Owner must still perform those checks.
    """
    if type(brief) is not SalesWeaponBriefDraft:
        raise ValueError("exact sales weapon brief draft required")
    constraints = (
        *("适合：" + item.text for item in brief.fit_for),
        *("不适合：" + item.text for item in brief.not_fit_for),
        *("待评审主张：" + item.text for item in brief.proposed_value_claims),
        *("未知：" + item for item in brief.unknown_facts),
        *("禁说：" + item for item in brief.prohibited_claims),
        "真人交接：" + brief.handoff_condition,
    )
    return ContentTaskSpec(
        title=brief.product_label + "内容说明",
        objective=("围绕" + brief.scenario.text + "，为" + brief.audience_hypothesis.text
                   + "制作有来源、待人工评审的产品说明"),
        channels=channels,
        audience=brief.audience_hypothesis.text,
        time_window=time_window,
        constraints=constraints,
        growth_plan_ref=brief.plan_ref,
        artifact_refs=artifact_refs,
    )


__all__ = ["ContentTaskSpec", "content_task_from_sales_weapon_brief"]
