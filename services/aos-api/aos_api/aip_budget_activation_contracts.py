"""HTTP contracts for first BudgetRevision activation review, without activation."""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_contracts import AipContractModel


class CreateBudgetActivationPreviewRequest(AipContractModel):
    target: BudgetRevisionCreate
    checker_subject: str = Field(min_length=1, max_length=200)

    @field_validator("checker_subject")
    @classmethod
    def _checker(cls, value: str) -> str:
        if value != value.strip() or not value.isprintable():
            raise ValueError("checkerSubject must be a canonical subject")
        return value


class BudgetActivationPreviewView(AipContractModel):
    preview_id: str
    preview_hash: str
    budget_id: str
    target_revision: int
    target_hash: str
    expected_head_version: int
    maker_subject: str
    checker_subject: str
    external_usage_proven: Literal[False]
    activation_eligible: Literal[False] = False
    target: BudgetRevisionCreate
    internal_ledger_checked_at: datetime
    expires_at: datetime


class BudgetPreviewInquiryPending(AipContractModel):
    status: Literal['unresolved', 'conflict']


class BudgetPreviewInquiryObserved(AipContractModel):
    status: Literal['observed']
    preview_id: str = Field(min_length=1, max_length=160)
    preview_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    activation_eligible: Literal[False] = False


class DecideBudgetActivationRequest(AipContractModel):
    decision: Literal["approved", "rejected"]


class BudgetActivationDecisionView(AipContractModel):
    decision_id: str
    preview_id: str
    preview_hash: str
    target_hash: str
    checker_subject: str
    decision: Literal["approved", "rejected"]
    activation_eligible: Literal[False] = False
    expires_at: datetime


class RevokeBudgetActivationDecisionRequest(AipContractModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        if value != value.strip() or not value.isprintable():
            raise ValueError("reason must be canonical printable text")
        return value


class BudgetActivationRevocationView(AipContractModel):
    revocation_id: str
    decision_id: str
    actor_subject: str
    reason: str
    created_at: datetime
