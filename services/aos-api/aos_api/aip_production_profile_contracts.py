"""Strict, side-effect-free contracts for installed production profiles."""
from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel


class BriefMode(StrEnum):
    OWNED = "owned"
    REFERENCE_ONLY = "reference_only"


class BriefProfile(AipContractModel):
    mode: BriefMode
    brief_type: str = Field(min_length=1, max_length=120)
    required_fields: list[str] = Field(min_length=1, max_length=64)
    source_responsibility_preserved: bool = True

    @field_validator("required_fields")
    @classmethod
    def _unique_required_fields(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not item.strip() for item in values):
            raise ValueError("brief required fields must be unique and non-blank")
        return values


class EvidenceSelectionProfile(AipContractModel):
    required_facts: list[str] = Field(min_length=1, max_length=128)
    require_provenance: bool = True
    require_freshness: bool = True
    require_negative_evidence: bool = True

    @field_validator("required_facts")
    @classmethod
    def _unique_required_facts(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not item.strip() for item in values):
            raise ValueError("required facts must be unique and non-blank")
        return values


class EvalProfile(AipContractModel):
    gates: list[str] = Field(min_length=1, max_length=64)
    fail_closed: Literal[True] = True
    same_revision_required: Literal[True] = True

    @field_validator("gates")
    @classmethod
    def _unique_gates(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)) or any(not item.strip() for item in values):
            raise ValueError("eval gates must be unique and non-blank")
        return values


class ResponsibilitySlotProfile(AipContractModel):
    slot_id: str = Field(min_length=1, max_length=160)
    responsibility_type: str = Field(min_length=1, max_length=160)
    atomic_skill_ids: list[str] = Field(min_length=1, max_length=32)
    protected: bool = False
    merge_allowed: bool = True
    return_stage: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def _protected_slot_cannot_merge(self) -> Self:
        if self.protected and self.merge_allowed:
            raise ValueError("protected responsibility slot cannot be merged")
        if len(self.atomic_skill_ids) != len(set(self.atomic_skill_ids)):
            raise ValueError("atomic skill ids must be unique")
        return self


class ResponsibilityProfile(AipContractModel):
    slots: list[ResponsibilitySlotProfile] = Field(min_length=1, max_length=32)
    handoff_required: bool = True
    reassignment_requires_canonical_decision: Literal[True] = True

    @model_validator(mode="after")
    def _unique_slots_and_independent_review(self) -> Self:
        slot_ids = [item.slot_id for item in self.slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("responsibility slot ids must be unique")
        if not any(
            item.responsibility_type == "independent_review" and item.protected
            for item in self.slots
        ):
            raise ValueError("production profile requires protected independent review")
        return self


class ContributionProjection(AipContractModel):
    show_atomic_skill_attribution: Literal[True] = True
    show_logic_revision: Literal[True] = True
    show_coworker_binding: Literal[True] = True
    show_blockers: Literal[True] = True


class ProductionProfile(AipContractModel):
    schema_id: Literal["aos.ecommerce-production-profile/v1"] = Field(alias="schema")
    module_id: str = Field(pattern=r"^ecommerce[.][a-z0-9-]+$")
    profile_revision: int = Field(ge=1)
    brief: BriefProfile
    evidence_selection: EvidenceSelectionProfile
    eval: EvalProfile
    responsibility: ResponsibilityProfile
    contribution_projection: ContributionProjection

    @model_validator(mode="after")
    def _task_cockpit_is_reference_only(self) -> Self:
        if self.module_id == "ecommerce.task-cockpit":
            if self.brief.mode is not BriefMode.REFERENCE_ONLY:
                raise ValueError("task cockpit brief must remain reference-only")
            if not self.brief.source_responsibility_preserved:
                raise ValueError("task cockpit must preserve source responsibility")
        elif self.brief.mode is not BriefMode.OWNED:
            raise ValueError("domain module brief must be owned")
        return self
