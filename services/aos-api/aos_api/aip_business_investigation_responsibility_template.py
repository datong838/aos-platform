"""Strict content contract for a future signed BI responsibility template."""
from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel


BI_TEMPLATE_SCHEMA = "aos.ecommerce-business-investigation-responsibility-template/v1"
BI_TEMPLATE_ID = "ecommerce.business-investigation.readonly"

# Slot facts are product content; instance assignees and approvals are separate
# current tenant authorities and must never be embedded in the signed template.
BI_ROLE_BLUEPRINTS = (
    ("investigation-owner", "investigation_owner", "ecommerce.data_advisor.default", ("strategy.plan",), "portrait"),
    ("data-steward", "data_steward", "ecommerce.customer_service.default", ("material.collect",), "portrait"),
    ("content-research", "content_research", "ecommerce.content_officer.default", ("content.review",), "diagnosis"),
    ("customer-research", "customer_research", "ecommerce.private_domain_manager.default", ("material.collect",), "diagnosis"),
    ("channel-research", "channel_research", "ecommerce.campaign_planner.default", ("strategy.plan",), "solution-design"),
    ("business-reviewer", "business_review", "ecommerce.shopping_advisor.default", ("strategy.plan",), "solution-design"),
)


class BIResponsibilitySlot(AipContractModel):
    slot_id: str = Field(min_length=1, max_length=160)
    responsibility_type: str = Field(min_length=1, max_length=160)
    required_capability_ids: list[str] = Field(min_length=1, max_length=16)
    return_stage: str = Field(min_length=1, max_length=160)


class BIResponsibilityTemplate(AipContractModel):
    schema_id: Literal[BI_TEMPLATE_SCHEMA] = Field(alias="schema")
    template_id: Literal[BI_TEMPLATE_ID]
    revision: int = Field(ge=1)
    profile: Literal[BI_TEMPLATE_ID]
    safety_mode: Literal["read-only"]
    slots: list[BIResponsibilitySlot] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def _canonical_roles(self) -> Self:
        observed = tuple(
            (slot.slot_id, slot.responsibility_type,
             tuple(slot.required_capability_ids), slot.return_stage)
            for slot in self.slots
        )
        expected = tuple(
            (slot_id, role, capabilities, stage)
            for slot_id, role, _instance_id, capabilities, stage in BI_ROLE_BLUEPRINTS
        )
        if observed != expected:
            raise ValueError("BI responsibility slots differ from canonical product roles")
        return self
