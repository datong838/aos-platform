"""Draft renewal input for an existing policy, never approval or authority.

A producer must load current heads, references and membership from their Owners
in one scoped transaction. This pure envelope neither performs those reads nor
authorizes publication, runtime admission, spending or Provider calls.
"""
from typing import Annotated, Literal

from pydantic import Field, StrictInt, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_model_governance_policy_contracts import (
    BudgetPolicyRevision, BudgetPolicyRevisionCreate, ModelGovernancePolicyLifecycle,
)
from aos_api.aip_model_governance_policy_store import canonical_hash

PositiveInt = Annotated[StrictInt, Field(ge=1, le=9_007_199_254_740_991)]


class BudgetPolicyRenewalProposal(AipContractModel):
    schema_version: Literal[1]
    tenant: TenantContext
    source_policy: BudgetPolicyRevision
    target_policy: BudgetPolicyRevisionCreate
    expected_head_version: PositiveInt
    maker_subject: str = Field(min_length=1, max_length=200)
    checker_subject: str = Field(min_length=1, max_length=200)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _version(cls, value):
        if type(value) is not int:
            raise ValueError("integer schema version required")
        return value

    @field_validator("source_policy", "target_policy", mode="before")
    @classmethod
    def _policy(cls, value):
        if isinstance(value, (BudgetPolicyRevision, BudgetPolicyRevisionCreate)):
            value = value.model_dump(mode="python", by_alias=True)
        if not isinstance(value, dict):
            raise ValueError("exact policy payload required")
        revision = value.get("revision")
        if type(revision) is not int or not 1 <= revision <= 9_007_199_254_740_991:
            raise ValueError("exact integer policy revision required")
        return value

    @field_validator("maker_subject", "checker_subject")
    @classmethod
    def _subject(cls, value):
        if value != value.strip() or not value.isprintable():
            raise ValueError("canonical subject required")
        return value

    @model_validator(mode="after")
    def _scope(self):
        source, target = self.source_policy, self.target_policy
        if (self.tenant.org_id, self.tenant.project_id) != ("org-org", "dev-project"):
            raise ValueError("renewal tenant is not approved")
        if source.tenant != self.tenant:
            raise ValueError("source tenant mismatch")
        if self.maker_subject == self.checker_subject:
            raise ValueError("independent checker required")
        if (source.lifecycle is not ModelGovernancePolicyLifecycle.ACTIVE
                or target.lifecycle is not ModelGovernancePolicyLifecycle.DRAFT):
            raise ValueError("active historical source and draft target required")
        if (target.policy_id != source.policy_id
                or target.revision != source.revision + 1
                or target.owner != source.owner
                or target.budget_revision_ref != source.budget_revision_ref):
            raise ValueError("existing policy owner and exact budget must be preserved")
        if target.effective_from < source.effective_until:
            raise ValueError("renewal must follow the historical policy window")
        old, new = source.development_cost_authorization, target.development_cost_authorization
        if old is None or new is None:
            raise ValueError("development renewal requires explicit cost proposal scope")
        if (new.tenant != self.tenant or new.provider != old.provider
                or new.provider_model_id != old.provider_model_id):
            raise ValueError("existing cost tenant, Provider and model must be preserved")
        if target.approval_ref == source.approval_ref:
            raise ValueError("historical approval cannot authorize a renewal")
        if target.allow_zero_price or target.zero_price_approval_ref is not None:
            raise ValueError("renewal cannot introduce zero pricing")
        return self

    def canonical_payload(self) -> dict:
        # Reparse nested models too: model_copy/mutation must not yield a usable
        # envelope that bypasses any construction validation.
        checked = type(self).model_validate(self.model_dump(mode="python", by_alias=True))
        return checked.model_dump(mode="json", by_alias=True)

    @property
    def proposal_hash(self) -> str:
        return canonical_hash({
            "domain": "aos.budget-policy-renewal-proposal/v1",
            "proposal": self.canonical_payload(),
        })
