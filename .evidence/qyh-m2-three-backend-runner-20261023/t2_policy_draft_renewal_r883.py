"""Build revision-2 T2 policy drafts only; no Store or runtime action."""

from datetime import UTC, datetime, timedelta

from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevisionCreate
from aos_api.aip_runtime_guard_policy_contracts import (
    DataClassificationPolicyRevisionCreate,
    EgressPolicyRevisionCreate,
)


AUTHORIZED_UNTIL = datetime(2027, 3, 31, 4, 0, tzinfo=UTC)
ACTOR = "synthetic-m2-three-t2-source-author"
CHECKER = "synthetic-m2-three-t2-source-checker"
APPROVAL_REF = "fixture-draft-only:m2-three-t2"
STEPS = ("budget", "egress", "data", "quota")
TYPES = (
    BudgetRevisionCreate,
    EgressPolicyRevisionCreate,
    DataClassificationPolicyRevisionCreate,
    QuotaPolicyRevisionCreate,
)
IDENTITIES = (
    "m2-three-t2-budget",
    "m2-three-t2-egress",
    "m2-three-t2-data",
    "m2-three-t2-quota",
)
OPERATIONS = (
    "budget_revision.publish",
    "runtime_guard_policy.egress.publish",
    "runtime_guard_policy.data_classification.publish",
    "model_governance_policy.quota.publish",
)


def _resource_id(item):
    return item.budget_id if type(item) is BudgetRevisionCreate else item.policy_id


def _validate_originals(requests, effective_from):
    if (type(requests) is not tuple or len(requests) != 4
            or type(effective_from) is not datetime or effective_from.tzinfo is None
            or effective_from.utcoffset() != timedelta(0)):
        raise ValueError("original draft authority differs")
    old_until = None
    for item, expected_type, identity in zip(requests, TYPES, IDENTITIES, strict=True):
        if (type(item) is not expected_type or _resource_id(item) != identity
                or item.revision != 1 or getattr(item.lifecycle, "value", None) != "draft"
                or item.owner != ACTOR):
            raise ValueError("original draft authority differs")
        if type(item) is BudgetRevisionCreate:
            if item.over_budget_approver != CHECKER:
                raise ValueError("original draft authority differs")
        elif item.approval_ref != APPROVAL_REF:
            raise ValueError("original draft authority differs")
        if old_until is None:
            old_until = item.effective_until
        elif item.effective_until != old_until:
            raise ValueError("original draft authority differs")
    if not (old_until < effective_from < AUTHORIZED_UNTIL):
        raise ValueError("renewal window differs")


def build_policy_draft_renewals(requests, *, effective_from):
    _validate_originals(requests, effective_from)
    renewed = []
    for item in requests:
        value = item.model_dump(mode="python", by_alias=False)
        value.update(
            revision=2,
            effective_from=effective_from,
            effective_until=AUTHORIZED_UNTIL,
            lifecycle="draft",
        )
        candidate = type(item).model_validate(value)
        before = item.model_dump(mode="json", by_alias=True)
        after = candidate.model_dump(mode="json", by_alias=True)
        changed = {key for key in before if before[key] != after[key]}
        if changed != {"revision", "effectiveFrom", "effectiveUntil"}:
            raise ValueError("renewal changed policy semantics")
        renewed.append(candidate)
    return tuple(renewed)


def _validate_renewals(requests):
    if type(requests) is not tuple or len(requests) != 4:
        raise ValueError("exact renewal requests required")
    effective_from = None
    for item, expected_type, identity in zip(requests, TYPES, IDENTITIES, strict=True):
        if (type(item) is not expected_type or _resource_id(item) != identity
                or item.revision != 2 or getattr(item.lifecycle, "value", None) != "draft"
                or item.owner != ACTOR or item.effective_until != AUTHORIZED_UNTIL
                or item.effective_from.tzinfo is None
                or item.effective_from.utcoffset() != timedelta(0)):
            raise ValueError("exact renewal requests required")
        if type(item) is BudgetRevisionCreate:
            if item.over_budget_approver != CHECKER:
                raise ValueError("exact renewal requests required")
        elif item.approval_ref != APPROVAL_REF:
            raise ValueError("exact renewal requests required")
        if effective_from is None:
            effective_from = item.effective_from
        elif item.effective_from != effective_from:
            raise ValueError("exact renewal requests required")


def build_renewal_descriptors(requests):
    _validate_renewals(requests)
    values = []
    for step, operation, item in zip(STEPS, OPERATIONS, requests, strict=True):
        body = item.model_dump(mode="json", by_alias=True)
        values.append({
            "step": step,
            "operation": operation,
            "resourceId": _resource_id(item),
            "expectedVersion": 1,
            "idempotencyKey": f"m2-three-t2-renewal-20270331-{step}",
            "requestHash": canonical_hash({"expectedVersion": 1, "revision": body}),
        })
    return tuple(values)
