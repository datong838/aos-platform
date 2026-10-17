"""Offline window feasibility; all authority checks remain outstanding."""
from typing import Literal

from aos_api.aip_budget_policy_window_contracts import BudgetPolicyWindow, BudgetPolicyWindowDraft
from aos_api.aip_contracts import AipContractModel


OwnerCheck = Literal[
    'parent_budget_current_exact_active', 'provider_current_exact_active',
    'cost_parent_approved_consumed_not_revoked', 'maker_checker_current_members',
    'explicit_new_policy_approval', 'paired_price_authorization',
    'model_owner_successor_and_eval', 'native_transaction_receipt',
]

PENDING_OWNER_CHECKS: tuple[OwnerCheck, ...] = (
    'parent_budget_current_exact_active', 'provider_current_exact_active',
    'cost_parent_approved_consumed_not_revoked', 'maker_checker_current_members',
    'explicit_new_policy_approval', 'paired_price_authorization',
    'model_owner_successor_and_eval', 'native_transaction_receipt',
)


class BudgetPolicyWindowPlan(AipContractModel):
    draft_hash: str
    source_verification: Literal['unverified_input'] = 'unverified_input'
    approval_verified: Literal[False] = False
    activation_eligible: Literal[False] = False
    native_write_allowed: Literal[False] = False
    claimed_follow_on_window: BudgetPolicyWindow
    pending_owner_checks: tuple[OwnerCheck, ...] = PENDING_OWNER_CHECKS


def plan_policy_window(value: BudgetPolicyWindowDraft | dict) -> BudgetPolicyWindowPlan:
    # Reparse even model input; no caller-provided verification flags survive.
    if isinstance(value, BudgetPolicyWindowDraft):
        value = value.canonical_payload()
    draft = BudgetPolicyWindowDraft.model_validate(value)
    return BudgetPolicyWindowPlan(
        draft_hash=draft.draft_hash,
        claimed_follow_on_window=BudgetPolicyWindow(
            effective_from=draft.requested_policy_window.effective_until,
            effective_until=draft.claimed_budget_window.effective_until,
        ),
    )
