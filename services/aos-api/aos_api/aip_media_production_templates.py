"""Strict W7-01 media Stage/Responsibility template contracts.

These models validate immutable Bundle artifacts only. Lifecycle authority stays
with the signed Bundle registry and the tenant active installation.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_media_responsibility_capability_map import (
    LIVE_ADDON_CAPABILITY_ID,
    MEDIA_RESPONSIBILITY_CAPABILITY_MAP,
)


class MediaTemplateProfile(StrEnum):
    LITE = "LITE"
    STANDARD = "STANDARD"
    FULL = "FULL"


class MediaResponsibilitySlotTemplate(AipContractModel):
    slot_id: str = Field(pattern=r"^media[.][a-z0-9-]+$")
    responsibility_type: str = Field(min_length=1, max_length=160)
    required_capability_ids: list[str] = Field(min_length=1, max_length=16)
    required: bool
    protected: bool = False
    merge_allowed: bool = True
    return_stage: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def _protected_slot_cannot_merge(self) -> Self:
        if self.protected and self.merge_allowed:
            raise ValueError("protected media responsibility cannot merge")
        if len(self.required_capability_ids) != len(set(self.required_capability_ids)):
            raise ValueError("media responsibility capabilities must be unique")
        return self


class MediaResponsibilityTemplate(AipContractModel):
    schema_id: Literal["aos.ecommerce-media-responsibility-template/v1"] = Field(
        alias="schema"
    )
    template_id: str = Field(
        pattern=r"^ecommerce[.]media-studio[.](lite|standard|full)[.]responsibility$"
    )
    revision: int = Field(ge=1)
    profile: MediaTemplateProfile
    slots: list[MediaResponsibilitySlotTemplate] = Field(min_length=8, max_length=8)
    addon_capability_ids: list[str] = Field(default_factory=list, max_length=4)
    governance_responsibility_types: list[str] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def _canonical_media_mapping(self) -> Self:
        expected_suffix = f".{self.profile.value.lower()}.responsibility"
        if not self.template_id.endswith(expected_suffix):
            raise ValueError("media responsibility template ID/profile mismatch")
        by_id = {slot.slot_id: slot for slot in self.slots}
        if len(by_id) != len(self.slots) or set(by_id) != set(
            MEDIA_RESPONSIBILITY_CAPABILITY_MAP
        ):
            raise ValueError("media responsibility template must preserve all eight slots")
        for slot_id, capability_ids in MEDIA_RESPONSIBILITY_CAPABILITY_MAP.items():
            if tuple(by_id[slot_id].required_capability_ids) != capability_ids:
                raise ValueError(f"canonical capability mapping drifted for {slot_id}")
        review = by_id["media.review"]
        if not review.required or not review.protected or review.merge_allowed:
            raise ValueError("media review must remain required, protected, and unmerged")
        expected_addons = (
            [LIVE_ADDON_CAPABILITY_ID]
            if self.profile is MediaTemplateProfile.FULL
            else []
        )
        if self.addon_capability_ids != expected_addons:
            raise ValueError("live.orchestrate is allowed only by the FULL profile")
        required_governance = {
            "external_publication_approval",
            "receipt_reconciliation",
        }
        if len(self.governance_responsibility_types) != len(
            set(self.governance_responsibility_types)
        ) or not required_governance.issubset(self.governance_responsibility_types):
            raise ValueError("publication approval and receipt reconciliation stay separate")
        return self


class MediaStageTemplateItem(AipContractModel):
    stage_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    title: str = Field(min_length=1, max_length=160)
    depends_on: list[str] = Field(default_factory=list, max_length=16)
    responsibility_slot_ids: list[str] = Field(min_length=1, max_length=8)
    required_capability_ids: list[str] = Field(min_length=1, max_length=16)
    live_stage: bool = False

    @field_validator(
        "depends_on", "responsibility_slot_ids", "required_capability_ids"
    )
    @classmethod
    def _unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("media stage lists must be unique")
        return values


class MediaStageTemplate(AipContractModel):
    schema_id: Literal["aos.ecommerce-media-stage-template/v1"] = Field(alias="schema")
    template_id: str = Field(
        pattern=r"^ecommerce[.]media-studio[.](lite|standard|full)[.]stage$"
    )
    revision: int = Field(ge=1)
    profile: MediaTemplateProfile
    responsibility_template_id: str
    stages: list[MediaStageTemplateItem] = Field(min_length=1, max_length=32)
    required_capability_ids: list[str] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def _valid_stage_graph_and_capabilities(self) -> Self:
        profile_key = self.profile.value.lower()
        if self.template_id != f"ecommerce.media-studio.{profile_key}.stage":
            raise ValueError("media stage template ID/profile mismatch")
        if self.responsibility_template_id != (
            f"ecommerce.media-studio.{profile_key}.responsibility"
        ):
            raise ValueError("media stage/responsibility template pair mismatch")
        by_id = {stage.stage_id: stage for stage in self.stages}
        if len(by_id) != len(self.stages):
            raise ValueError("media stage IDs must be unique")
        known_slots = set(MEDIA_RESPONSIBILITY_CAPABILITY_MAP)
        canonical_capabilities = {
            capability
            for values in MEDIA_RESPONSIBILITY_CAPABILITY_MAP.values()
            for capability in values
        } | {LIVE_ADDON_CAPABILITY_ID}
        for stage in self.stages:
            if not set(stage.depends_on).issubset(by_id) or stage.stage_id in stage.depends_on:
                raise ValueError("media stage dependency is missing or self-referential")
            if not set(stage.responsibility_slot_ids).issubset(known_slots):
                raise ValueError("media stage references an unknown responsibility slot")
            if not set(stage.required_capability_ids).issubset(canonical_capabilities):
                raise ValueError("media stage references a non-canonical capability")
        self._assert_acyclic(by_id)
        live_stages = [stage for stage in self.stages if stage.live_stage]
        if self.profile is MediaTemplateProfile.FULL:
            if len(live_stages) != 1 or LIVE_ADDON_CAPABILITY_ID not in (
                live_stages[0].required_capability_ids
            ):
                raise ValueError("FULL profile requires one live.orchestrate stage")
        elif live_stages or any(
            LIVE_ADDON_CAPABILITY_ID in stage.required_capability_ids
            for stage in self.stages
        ):
            raise ValueError("live.orchestrate is forbidden outside FULL")
        stage_capabilities = {
            capability for stage in self.stages for capability in stage.required_capability_ids
        }
        if set(self.required_capability_ids) != stage_capabilities or len(
            self.required_capability_ids
        ) != len(set(self.required_capability_ids)):
            raise ValueError("template required capabilities must equal the stage union")
        return self

    @staticmethod
    def _assert_acyclic(by_id: dict[str, MediaStageTemplateItem]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(stage_id: str) -> None:
            if stage_id in visiting:
                raise ValueError("media stage dependencies must be acyclic")
            if stage_id in visited:
                return
            visiting.add(stage_id)
            for dependency in by_id[stage_id].depends_on:
                visit(dependency)
            visiting.remove(stage_id)
            visited.add(stage_id)

        for stage_id in by_id:
            visit(stage_id)


__all__ = [
    "MediaResponsibilityTemplate",
    "MediaStageTemplate",
    "MediaTemplateProfile",
]
