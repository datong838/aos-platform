"""Read-only Owner snapshot for review; never an approval or runtime permit."""
from contextlib import contextmanager
from datetime import datetime
from typing import Literal

from psycopg import DatabaseError, IsolationLevel
from pydantic import AwareDatetime, ValidationError, field_validator, model_validator

from aos_api.aip_budget_contracts import BudgetRevision
from aos_api.aip_budget_policy_renewal_contracts import ExactVersion, PolicyIdentifier
from aos_api.aip_budget_policy_renewal_identity import _HUMAN
from aos_api.aip_budget_store import AipBudgetAuthorityStore, BudgetNotFound, BudgetStoreError
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevision
from aos_api.aip_model_governance_policy_store import (
    AipModelGovernancePolicyStore, ModelGovernancePolicyNotFound,
    ModelGovernancePolicyStoreError,
)
from aos_api.aip_model_runtime_contracts import ProviderInstanceRevision
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore, ModelRuntimeNotFound, ModelRuntimeStoreError,
)
from aos_api.db import connect_read_only
from aos_api.tenant_scope import TenantScope


Window = Literal["expired", "effective", "not-yet-effective"]
APPROVED_SCOPE = ("org-org", "dev-project")


class BudgetPolicyRenewalReviewUnavailable(RuntimeError):
    """A complete, isolated Owner snapshot could not be established."""


class BudgetPolicyRenewalCheckerDenied(ValueError):
    """The original current member cannot be observed as owner or admin."""


class BudgetPolicyRenewalCheckerView(AipContractModel):
    """Current-member read observation; never approval or execution permission."""
    schema_version: Literal["aos.budget-policy-renewal.review-checker/v1"]
    tenant: TenantContext
    subject: Literal["6f31cfdc-a26c-4f1f-ad6b-95a8559cc657"]
    token_kind: Literal["oidc"]
    role: Literal["owner", "admin"]
    evaluated_at: AwareDatetime
    approval_verified: Literal[False] = False
    activation_eligible: Literal[False] = False

    @field_validator("approval_verified", "activation_eligible", mode="before")
    @classmethod
    def _observation_only(cls, value):
        if value is not False:
            raise ValueError("member observation cannot grant permission")
        return value

    @model_validator(mode="after")
    def _approved_tenant(self):
        if (self.tenant.org_id, self.tenant.project_id) != APPROVED_SCOPE:
            raise ValueError("checker observation crosses tenant boundary")
        return self


def _window(item, now: datetime) -> Window:
    if now < item.effective_from:
        return "not-yet-effective"
    return "effective" if now < item.effective_until else "expired"


def _same_ref(item, ref) -> bool:
    return item is not None and (
        item.revision == ref.revision and item.content_hash == ref.content_hash
    )


class BudgetPolicyRenewalReviewSource(AipContractModel):
    schema_version: Literal["aos.budget-policy-renewal.review-source/v1"]
    tenant: TenantContext
    evaluated_at: AwareDatetime
    source_policy: BudgetPolicyRevision
    source_head_version: ExactVersion
    source_budget: BudgetRevision | None
    current_budget: BudgetRevision | None
    source_provider: ProviderInstanceRevision | None
    current_provider: ProviderInstanceRevision | None
    source_window: Window
    budget_window: Window | Literal["unknown"]
    state: Literal["ready", "blocked"]
    blockers: list[str]
    approval_verified: Literal[False] = False
    activation_eligible: Literal[False] = False

    @field_validator("approval_verified", "activation_eligible", mode="before")
    @classmethod
    def _observation_only(cls, value):
        if value is not False:
            raise ValueError("read observation cannot grant approval or activation")
        return value

    def observation_blockers(self) -> list[str]:
        reasons = []
        policy = self.source_policy
        if policy.lifecycle != "active":
            reasons.append("RENEWAL_SOURCE_POLICY_NOT_ACTIVE")
        # Historical policy expiry is expected during renewal. It is reported
        # separately and must not be confused with the Budget's current window.
        ref = policy.budget_revision_ref
        if self.source_budget is None:
            reasons.append("RENEWAL_SOURCE_BUDGET_MISSING")
        elif self.source_budget.budget_id != ref.asset_id or not _same_ref(self.source_budget, ref):
            reasons.append("RENEWAL_SOURCE_BUDGET_REF_MISMATCH")
        if self.current_budget is None:
            reasons.append("RENEWAL_CURRENT_BUDGET_MISSING")
        elif self.current_budget.budget_id != ref.asset_id or not _same_ref(self.current_budget, ref):
            reasons.append("RENEWAL_CURRENT_BUDGET_CHANGED")
        if self.source_budget is not None:
            if self.source_budget.lifecycle != "active":
                reasons.append("RENEWAL_SOURCE_BUDGET_NOT_ACTIVE")
            if _window(self.source_budget, self.evaluated_at) != "effective":
                reasons.append("RENEWAL_SOURCE_BUDGET_WINDOW_UNAVAILABLE")
        authorization = policy.development_cost_authorization
        if authorization is None:
            reasons.append("RENEWAL_SOURCE_COST_AUTHORIZATION_MISSING")
        else:
            provider_ref = authorization.provider
            if self.source_provider is None:
                reasons.append("RENEWAL_SOURCE_PROVIDER_MISSING")
            elif (self.source_provider.provider_instance_id != provider_ref.asset_id
                  or not _same_ref(self.source_provider, provider_ref)):
                reasons.append("RENEWAL_SOURCE_PROVIDER_REF_MISMATCH")
            if self.current_provider is None:
                reasons.append("RENEWAL_CURRENT_PROVIDER_MISSING")
            elif (self.current_provider.provider_instance_id != provider_ref.asset_id
                  or not _same_ref(self.current_provider, provider_ref)):
                reasons.append("RENEWAL_CURRENT_PROVIDER_CHANGED")
            if self.source_provider is not None and self.source_provider.lifecycle != "active":
                reasons.append("RENEWAL_SOURCE_PROVIDER_NOT_ACTIVE")
        return reasons

    @model_validator(mode="after")
    def _consistent_snapshot(self):
        if (self.tenant.org_id, self.tenant.project_id) != APPROVED_SCOPE:
            raise ValueError("renewal review tenant is not approved")
        for item in (self.source_policy, self.source_budget, self.current_budget,
                     self.source_provider, self.current_provider):
            if item is not None and item.tenant != self.tenant:
                raise ValueError("renewal review snapshot crosses tenant boundary")
        if self.source_policy.development_cost_authorization is None and (
            self.source_provider is not None or self.current_provider is not None
        ):
            raise ValueError("provider cannot be inferred without an exact source reference")
        if self.source_window != _window(self.source_policy, self.evaluated_at):
            raise ValueError("source policy window observation is inconsistent")
        expected_budget_window = (
            _window(self.source_budget, self.evaluated_at) if self.source_budget else "unknown"
        )
        if self.budget_window != expected_budget_window:
            raise ValueError("source Budget window observation is inconsistent")
        reasons = self.observation_blockers()
        if self.blockers != reasons or self.state != ("blocked" if reasons else "ready"):
            raise ValueError("review state must match the complete metadata observations")
        return self


class BudgetPolicyRenewalReviewReader:
    def __init__(self, connect_factory=None):
        self._connect_factory = connect_factory or connect_read_only

    def read_checker(self, scope: TenantScope, subject: str) -> BudgetPolicyRenewalCheckerView:
        if scope.key != APPROVED_SCOPE or subject != _HUMAN:
            raise BudgetPolicyRenewalCheckerDenied("original member required")
        try:
            with self._connect_factory(scope) as connection:
                if (connection.read_only is not True
                        or connection.isolation_level != IsolationLevel.REPEATABLE_READ):
                    raise BudgetPolicyRenewalReviewUnavailable("read-only snapshot required")
                row = connection.execute(
                    "SELECT lower(role) AS role, clock_timestamp() AS evaluated_at "
                    "FROM public.meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",
                    (*scope.key, subject),
                ).fetchone()
                if not row or row["role"] not in {"owner", "admin"}:
                    raise BudgetPolicyRenewalCheckerDenied("original current member required")
                return BudgetPolicyRenewalCheckerView(
                    schema_version="aos.budget-policy-renewal.review-checker/v1",
                    tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
                    subject=subject, token_kind="oidc", role=row["role"], evaluated_at=row["evaluated_at"],
                )
        except (DatabaseError, ValidationError) as exc:
            raise BudgetPolicyRenewalReviewUnavailable("current member observation unavailable") from exc

    def read(self, scope: TenantScope, policy_id: PolicyIdentifier) -> BudgetPolicyRenewalReviewSource:
        if scope.key != APPROVED_SCOPE:
            raise ValueError("renewal review tenant is not approved")
        try:
            with self._connect_factory(scope) as connection:
                # Refuse an injected writable factory before the first read.
                if (connection.read_only is not True
                        or connection.isolation_level != IsolationLevel.REPEATABLE_READ):
                    raise BudgetPolicyRenewalReviewUnavailable("read-only snapshot required")

                @contextmanager
                def borrow(request_scope):
                    if request_scope != scope:
                        raise BudgetPolicyRenewalReviewUnavailable("snapshot scope changed")
                    yield connection

                policies = AipModelGovernancePolicyStore(connect_factory=borrow)
                budgets = AipBudgetAuthorityStore(connect_factory=borrow)
                providers = AipModelRuntimeStore(connect_factory=borrow)
                policy, version = policies.get_budget_head(scope, policy_id)
                now = connection.execute("SELECT clock_timestamp() AS now").fetchone()["now"]

                def optional(get, missing, *args):
                    try:
                        return get(*args)
                    except missing:
                        return None

                ref = policy.budget_revision_ref
                budget = optional(budgets.get, BudgetNotFound, scope, ref.asset_id, ref.revision)
                current_budget = optional(budgets.get, BudgetNotFound, scope, ref.asset_id)
                provider = current_provider = None
                authorization = policy.development_cost_authorization
                if authorization is not None:
                    ref = authorization.provider
                    provider = optional(providers.get_provider, ModelRuntimeNotFound,
                                        scope, ref.asset_id, ref.revision)
                    current_provider = optional(providers.get_provider, ModelRuntimeNotFound,
                                                scope, ref.asset_id)
                fields = dict(
                    schema_version="aos.budget-policy-renewal.review-source/v1",
                    tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
                    evaluated_at=now, source_policy=policy, source_head_version=version,
                    source_budget=budget, current_budget=current_budget,
                    source_provider=provider, current_provider=current_provider,
                    source_window=_window(policy, now),
                    budget_window=_window(budget, now) if budget else "unknown",
                )
                # Calculate observations from typed Owner facts; validate the
                # entire response afterwards, including every tenant and flag.
                observation = BudgetPolicyRenewalReviewSource.model_construct(**fields)
                reasons = observation.observation_blockers()
                return BudgetPolicyRenewalReviewSource(
                    **fields, state="blocked" if reasons else "ready", blockers=reasons,
                )
        except ModelGovernancePolicyNotFound:
            raise
        except (DatabaseError, ValidationError, BudgetStoreError,
                ModelGovernancePolicyStoreError, ModelRuntimeStoreError) as exc:
            raise BudgetPolicyRenewalReviewUnavailable("Owner snapshot unavailable") from exc
