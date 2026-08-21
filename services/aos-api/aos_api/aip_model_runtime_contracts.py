"""AIP-7 exact model-runtime contracts.

The DTOs in this module are authority-neutral. Importing them does not create
tables, register routes, resolve a provider, or permit an AgentRun to start.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import AipContractModel, TenantContext

SECRET_REF_PREFIXES = ("vault://", "secret://", "keychain://")


class ModelRuntimeLifecycle(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class ModelRuntimeReadiness(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ModelModality(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    EMBEDDING = "embedding"


class RouteStrategy(StrEnum):
    FAILOVER = "failover"
    WEIGHTED = "weighted"
    LOWEST_LATENCY = "lowest_latency"
    LOWEST_COST = "lowest_cost"


class ProviderEndpointProfile(AipContractModel):
    base_url: str = Field(min_length=1, max_length=1024)
    region: str = Field(min_length=1, max_length=120)
    timeout_ms: int = Field(ge=100, le=3_600_000)
    metadata: dict[str, str] = Field(default_factory=dict, max_length=32)

    @model_validator(mode="before")
    @classmethod
    def _forbid_secret_shaped_fields(cls, value: Any) -> Any:
        if isinstance(value, dict):
            forbidden = {
                "apiKey", "api_key", "token", "secret", "password",
                "authorization", "apiKeyMasked", "api_key_masked",
            }
            if forbidden & set(value):
                raise ValueError("endpoint profile must not contain credentials")
        return value


class ProviderInstanceRevision(AipContractModel):
    tenant: TenantContext
    provider_instance_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    plugin_ref: VersionedAssetRef
    endpoint_profile: ProviderEndpointProfile
    secret_ref: str = Field(min_length=1, max_length=512)
    secret_version: str = Field(min_length=1, max_length=120)
    egress_policy_ref: VersionedAssetRef
    data_classification_policy_ref: VersionedAssetRef
    lifecycle: ModelRuntimeLifecycle
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("secret_ref")
    @classmethod
    def _opaque_secret_ref(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith(SECRET_REF_PREFIXES):
            raise ValueError("secret_ref must be an opaque secret reference")
        return cleaned

    @model_validator(mode="after")
    def _exact_ref_kinds(self) -> ProviderInstanceRevision:
        if self.plugin_ref.asset_type != "ProviderPluginRevision":
            raise ValueError("plugin_ref must reference ProviderPluginRevision")
        if self.egress_policy_ref.asset_type != "EgressPolicyRevision":
            raise ValueError("egress_policy_ref must reference EgressPolicyRevision")
        if self.data_classification_policy_ref.asset_type != "DataClassificationPolicyRevision":
            raise ValueError(
                "data_classification_policy_ref must reference DataClassificationPolicyRevision"
            )
        return self


class ProviderHealthObservation(AipContractModel):
    tenant: TenantContext
    observation_id: str = Field(min_length=1, max_length=200)
    provider: VersionedAssetRef
    status: str = Field(pattern=r"^(healthy|degraded|unavailable|unknown)$")
    availability_pct: float | None = Field(default=None, ge=0, le=100)
    p50_latency_ms: int | None = Field(default=None, ge=0)
    observed_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _valid_observation(self) -> ProviderHealthObservation:
        if self.provider.asset_type != "ProviderInstanceRevision":
            raise ValueError("provider must reference ProviderInstanceRevision")
        if self.expires_at <= self.observed_at:
            raise ValueError("health observation expiry must follow observation time")
        return self


class RegisteredModelRevision(AipContractModel):
    tenant: TenantContext
    registered_model_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider: VersionedAssetRef
    provider_model_id: str = Field(min_length=1, max_length=240)
    input_modalities: list[ModelModality] = Field(min_length=1, max_length=8)
    output_modalities: list[ModelModality] = Field(min_length=1, max_length=8)
    capabilities: list[str] = Field(min_length=1, max_length=128)
    context_window: int = Field(ge=1)
    quota_policy_ref: VersionedAssetRef
    budget_policy_ref: VersionedAssetRef
    price_snapshot_ref: VersionedAssetRef
    eval_gate_ref: VersionedAssetRef
    lifecycle: ModelRuntimeLifecycle
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("input_modalities", "output_modalities")
    @classmethod
    def _unique_modalities(cls, values: list[ModelModality]) -> list[ModelModality]:
        if len(values) != len(set(values)):
            raise ValueError("model modalities must be unique")
        return values

    @field_validator("capabilities")
    @classmethod
    def _unique_capabilities(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("model capabilities must be unique and non-blank")
        return cleaned

    @model_validator(mode="after")
    def _exact_ref_kinds(self) -> RegisteredModelRevision:
        expected = {
            "provider": "ProviderInstanceRevision",
            "quota_policy_ref": "QuotaPolicyRevision",
            "budget_policy_ref": "BudgetPolicyRevision",
            "price_snapshot_ref": "ModelPriceSnapshotRevision",
            "eval_gate_ref": "EvalGateDecision",
        }
        for field_name, kind in expected.items():
            if getattr(self, field_name).asset_type != kind:
                raise ValueError(f"{field_name} must reference {kind}")
        return self


class ModelPriceSnapshotRevision(AipContractModel):
    tenant: TenantContext
    price_snapshot_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    input_token_price: float | None = Field(default=None, ge=0)
    output_token_price: float | None = Field(default=None, ge=0)
    cached_token_price: float | None = Field(default=None, ge=0)
    token_unit: int = Field(default=1000, ge=1)
    effective_from: datetime
    effective_until: datetime | None = None
    lifecycle: ModelRuntimeLifecycle
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @model_validator(mode="after")
    def _price_snapshot_is_usable(self) -> ModelPriceSnapshotRevision:
        if self.input_token_price is None and self.output_token_price is None:
            raise ValueError("price snapshot requires an input or output token price")
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise ValueError("price snapshot effective range is invalid")
        return self


class ModelRouteCandidate(AipContractModel):
    model: VersionedAssetRef
    weight: int = Field(default=100, ge=0, le=100)

    @model_validator(mode="after")
    def _model_kind(self) -> ModelRouteCandidate:
        if self.model.asset_type != "RegisteredModelRevision":
            raise ValueError("route candidate must reference RegisteredModelRevision")
        return self


class RuntimePolicyRevision(AipContractModel):
    tenant: TenantContext
    policy_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    network_policy_ref: VersionedAssetRef
    egress_policy_ref: VersionedAssetRef
    data_classification_policy_ref: VersionedAssetRef
    quota_policy_ref: VersionedAssetRef
    budget_policy_ref: VersionedAssetRef
    deadline_ms: int = Field(ge=100, le=3_600_000)
    max_attempts: int = Field(ge=1, le=20)
    allowed_fallback_reasons: list[str] = Field(default_factory=list, max_length=32)
    unknown_usage_behavior: str = Field(pattern=r"^(block|reconcile)$")
    unknown_price_behavior: str = Field(pattern=r"^(block|reconcile)$")
    kill_switch_enabled: bool
    lifecycle: ModelRuntimeLifecycle
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("allowed_fallback_reasons")
    @classmethod
    def _safe_fallback_reasons(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("fallback reasons must be unique and non-blank")
        forbidden = {"safety_rejected", "egress_denied", "pii_denied", "policy_denied"}
        if forbidden & set(cleaned):
            raise ValueError("safety and policy denials cannot be fallback reasons")
        return cleaned

    @model_validator(mode="after")
    def _exact_ref_kinds(self) -> RuntimePolicyRevision:
        expected = {
            "network_policy_ref": "NetworkPolicyRevision",
            "egress_policy_ref": "EgressPolicyRevision",
            "data_classification_policy_ref": "DataClassificationPolicyRevision",
            "quota_policy_ref": "QuotaPolicyRevision",
            "budget_policy_ref": "BudgetPolicyRevision",
        }
        for field_name, kind in expected.items():
            if getattr(self, field_name).asset_type != kind:
                raise ValueError(f"{field_name} must reference {kind}")
        return self


class ModelRouteRevision(AipContractModel):
    tenant: TenantContext
    route_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_types: list[str] = Field(min_length=1, max_length=64)
    required_input_modality: ModelModality
    required_output_modality: ModelModality
    required_capabilities: list[str] = Field(default_factory=list, max_length=128)
    candidates: list[ModelRouteCandidate] = Field(min_length=1, max_length=32)
    strategy: RouteStrategy
    runtime_policy_ref: VersionedAssetRef
    eval_gate_ref: VersionedAssetRef
    lifecycle: ModelRuntimeLifecycle
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("task_types", "required_capabilities")
    @classmethod
    def _unique_non_blank(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("route fields must be unique and non-blank")
        return cleaned

    @model_validator(mode="after")
    def _route_integrity(self) -> ModelRouteRevision:
        ids = [candidate.model.asset_id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("route candidates must be unique")
        if self.strategy is RouteStrategy.WEIGHTED:
            if sum(candidate.weight for candidate in self.candidates) != 100:
                raise ValueError("weighted route candidate weights must total 100")
        elif any(candidate.weight != 100 for candidate in self.candidates):
            raise ValueError("non-weighted route candidates must use weight 100")
        if self.runtime_policy_ref.asset_type != "RuntimePolicyRevision":
            raise ValueError("runtime_policy_ref must reference RuntimePolicyRevision")
        if self.eval_gate_ref.asset_type != "EvalGateDecision":
            raise ValueError("eval_gate_ref must reference EvalGateDecision")
        return self


class ModelRouteResolution(AipContractModel):
    tenant: TenantContext
    route: VersionedAssetRef
    policy: VersionedAssetRef
    readiness: ModelRuntimeReadiness
    selected_model: VersionedAssetRef | None = None
    selected_provider: VersionedAssetRef | None = None
    selected_price_snapshot: VersionedAssetRef | None = None
    blocker_codes: list[str] = Field(default_factory=list, max_length=64)
    resolved_at: datetime

    @field_validator("blocker_codes")
    @classmethod
    def _unique_blockers(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("blocker codes must be unique and non-blank")
        return cleaned

    @model_validator(mode="after")
    def _readiness_is_honest(self) -> ModelRouteResolution:
        if self.route.asset_type != "ModelRouteRevision":
            raise ValueError("route must reference ModelRouteRevision")
        if self.policy.asset_type != "RuntimePolicyRevision":
            raise ValueError("policy must reference RuntimePolicyRevision")
        selected = (
            self.selected_model is not None
            and self.selected_provider is not None
            and self.selected_price_snapshot is not None
        )
        if self.readiness is ModelRuntimeReadiness.READY:
            if not selected or self.blocker_codes:
                raise ValueError("ready resolution requires exact selections and no blockers")
        elif selected or not self.blocker_codes:
            raise ValueError("blocked/unknown resolution requires blockers and no selection")
        if self.selected_model and self.selected_model.asset_type != "RegisteredModelRevision":
            raise ValueError("selected_model must reference RegisteredModelRevision")
        if self.selected_provider and self.selected_provider.asset_type != "ProviderInstanceRevision":
            raise ValueError("selected_provider must reference ProviderInstanceRevision")
        if self.selected_price_snapshot and self.selected_price_snapshot.asset_type != "ModelPriceSnapshotRevision":
            raise ValueError("selected_price_snapshot must reference ModelPriceSnapshotRevision")
        return self


class ModelRuntimeAssetSummary(AipContractModel):
    """Secret-free current-head projection for the AIP-7 control plane."""

    ref: VersionedAssetRef
    lifecycle: ModelRuntimeLifecycle
    dependency_refs: list[VersionedAssetRef] = Field(default_factory=list, max_length=32)


class ModelRuntimeEvalGateSummary(AipContractModel):
    ref: VersionedAssetRef
    status: str = Field(pattern=r"^(passed|failed|blocked|unknown)$")


class ModelRuntimeCapacityPoolSummary(AipContractModel):
    pool_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    route_ref: VersionedAssetRef
    model_ref: VersionedAssetRef
    provider_ref: VersionedAssetRef
    max_concurrency: int = Field(ge=1)
    max_token_units: int = Field(ge=1)
    token_unit_per_reservation: int = Field(ge=1)
    lease_seconds: int = Field(ge=1, le=86_400)
    active_reservations: int = Field(ge=0)
    reserved_token_units: int = Field(ge=0)
    lifecycle: ModelRuntimeLifecycle


class ModelRuntimeOverview(AipContractModel):
    tenant: TenantContext
    providers: list[ModelRuntimeAssetSummary]
    models: list[ModelRuntimeAssetSummary]
    routes: list[ModelRuntimeAssetSummary]
    policies: list[ModelRuntimeAssetSummary]
    price_snapshots: list[ModelRuntimeAssetSummary]
    eval_gates: list[ModelRuntimeEvalGateSummary]
    capacity_pools: list[ModelRuntimeCapacityPoolSummary]
    health_observations: list[ProviderHealthObservation]
    resolutions: list[ModelRouteResolution]
    generated_at: datetime


class ModelPriceAuthoritySummary(AipContractModel):
    """Secret-free operational price interpretation for one exact model."""

    model_ref: VersionedAssetRef
    provider_model_id: str = Field(min_length=1, max_length=240)
    output_modalities: list[ModelModality] = Field(min_length=1, max_length=8)
    price_snapshot_ref: VersionedAssetRef | None = None
    status: str = Field(
        pattern=r"^(priced|approved_zero|unknown|inactive|out_of_window|unit_mismatch|drifted)$"
    )
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    input_token_price: float | None = Field(default=None, ge=0)
    output_token_price: float | None = Field(default=None, ge=0)
    cached_token_price: float | None = Field(default=None, ge=0)
    token_unit: int | None = Field(default=None, ge=1)
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    zero_price_approval_ref: str | None = None
    blocker_codes: list[str] = Field(default_factory=list, max_length=32)


class RuntimeBudgetAuthoritySummary(AipContractModel):
    budget_policy_ref: VersionedAssetRef
    budget_ref: VersionedAssetRef | None = None
    status: str = Field(pattern=r"^(active|inactive|out_of_window|drifted|unknown)$")
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    daily_limit_minor: int | None = Field(default=None, ge=0)
    monthly_limit_minor: int | None = Field(default=None, ge=0)
    hard_stop: bool | None = None
    unknown_usage_behavior: str | None = None
    unknown_price_behavior: str | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    blocker_codes: list[str] = Field(default_factory=list, max_length=32)


class RuntimeUsageAuthoritySummary(AipContractModel):
    state: str = Field(pattern=r"^(unobserved|measured|partial|unknown)$")
    receipt_count: int = Field(ge=0)
    measured_count: int = Field(ge=0)
    estimated_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    adjustment_count: int = Field(ge=0)
    cost_totals: dict[str, float] = Field(default_factory=dict, max_length=16)
    latest_observed_at: datetime | None = None
    truncated: bool = False

    @model_validator(mode="after")
    def _counts_are_consistent(self) -> ModelRuntimeUsageAuthoritySummary:
        if self.measured_count + self.estimated_count + self.unknown_count != self.receipt_count:
            raise ValueError("usage quality counts must total receipt_count")
        if self.state == "unobserved" and self.receipt_count != 0:
            raise ValueError("unobserved usage must not contain receipts")
        if self.state != "unobserved" and self.receipt_count == 0:
            raise ValueError("observed usage requires receipts")
        return self


class ModelRuntimeCostOverview(AipContractModel):
    tenant: TenantContext
    model_prices: list[ModelPriceAuthoritySummary]
    budgets: list[RuntimeBudgetAuthoritySummary]
    usage: RuntimeUsageAuthoritySummary
    generated_at: datetime
