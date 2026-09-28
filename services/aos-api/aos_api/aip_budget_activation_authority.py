"""Necessary exact evidence checks for future BudgetRevision activation.

These values must be read from formal authorities in one scoped transaction. Passing
this pure check does not create an approval, consume it, or authorize publication.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aos_api.aip_budget_contracts import BudgetLifecycle, BudgetRevisionCreate
from aos_api.aip_budget_store import canonical_hash
from aos_api.tenant_scope import TenantScope


class BudgetActivationBlocked(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class BudgetActivationPreviewEvidence:
    scope: TenantScope
    budget_id: str
    revision: int
    target_hash: str
    head_version: int
    preview_hash: str
    lifecycle: str
    readiness: str
    usage_known: bool
    expires_at: datetime


@dataclass(frozen=True)
class BudgetActivationApprovalEvidence:
    scope: TenantScope
    budget_id: str
    revision: int
    target_hash: str
    head_version: int
    preview_hash: str
    maker: str
    checker: str
    checker_authorized: bool
    decision: str
    expires_at: datetime
    revoked: bool
    consumed: bool


def require_exact_budget_activation_evidence(
    *,
    scope: TenantScope,
    maker: str,
    target: BudgetRevisionCreate,
    expected_head_version: int,
    preview: BudgetActivationPreviewEvidence,
    approval: BudgetActivationApprovalEvidence,
    now: datetime,
) -> None:
    """Reject stale claims; a Store must independently load and consume authority."""
    if (type(scope) is not TenantScope or type(preview) is not BudgetActivationPreviewEvidence
            or type(approval) is not BudgetActivationApprovalEvidence):
        raise BudgetActivationBlocked("BUDGET_ACTIVATION_EVIDENCE_INVALID")
    if preview.scope != scope or approval.scope != scope:
        raise BudgetActivationBlocked("BUDGET_ACTIVATION_SCOPE_MISMATCH")
    if (type(target) is not BudgetRevisionCreate or target.lifecycle is not BudgetLifecycle.ACTIVE
            or not maker or not maker.strip() or now.tzinfo is None):
        raise BudgetActivationBlocked("BUDGET_ACTIVATION_EVIDENCE_INVALID")
    if (type(expected_head_version) is not int or expected_head_version < 0
            or preview.head_version != expected_head_version
            or approval.head_version != expected_head_version):
        raise BudgetActivationBlocked("BUDGET_ACTIVATION_HEAD_DRIFT")
    target_hash = canonical_hash(target.model_dump(mode="json", by_alias=True))
    if any((item.budget_id != target.budget_id or item.revision != target.revision
            or item.target_hash != target_hash) for item in (preview, approval)):
        raise BudgetActivationBlocked("BUDGET_ACTIVATION_TARGET_DRIFT")
    if (len(preview.preview_hash) != 64
            or any(character not in "0123456789abcdef" for character in preview.preview_hash)):
        raise BudgetActivationBlocked("BUDGET_ACTIVATION_PREVIEW_INVALID")
    if approval.preview_hash != preview.preview_hash:
        raise BudgetActivationBlocked("BUDGET_ACTIVATION_PREVIEW_DRIFT")
    if (approval.maker != maker or not approval.checker.strip() or approval.checker == maker
            or approval.checker_authorized is not True):
        raise BudgetActivationBlocked("BUDGET_ACTIVATION_CHECKER_INVALID")
    if (approval.decision != "approved" or approval.revoked is not False
            or approval.consumed is not False or approval.expires_at.tzinfo is None
            or approval.expires_at <= now):
        raise BudgetActivationBlocked("BUDGET_ACTIVATION_APPROVAL_INVALID")
    if (preview.lifecycle != "frozen" or preview.readiness != "ready"
            or preview.usage_known is not True or preview.expires_at.tzinfo is None
            or preview.expires_at <= now):
        raise BudgetActivationBlocked("BUDGET_ACTIVATION_PREVIEW_INVALID")
    if not (target.effective_from <= now < target.effective_until):
        raise BudgetActivationBlocked("BUDGET_ACTIVATION_TARGET_WINDOW_INVALID")
