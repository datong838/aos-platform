from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_runtime_contracts import (
    ModelModality,
    ModelPriceSnapshotRevision,
    ModelRouteCandidate,
    ModelRouteResolution,
    ModelRouteRevision,
    ModelRuntimeLifecycle,
    ModelRuntimeReadiness,
    ProviderEndpointProfile,
    ProviderHealthObservation,
    ProviderInstanceRevision,
    RouteStrategy,
    RuntimePolicyRevision,
)

NOW = datetime(2026, 8, 13, tzinfo=UTC)
TENANT = TenantContext(org_id="org-org", project_id="dev-project")


def ref(kind: str, asset_id: str = "asset") -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=kind, asset_id=asset_id, revision=1, content_hash="a" * 64
    )


def policy() -> RuntimePolicyRevision:
    return RuntimePolicyRevision(
        tenant=TENANT,
        policy_id="policy-default",
        revision=1,
        content_hash="b" * 64,
        network_policy_ref=ref("NetworkPolicyRevision", "network"),
        egress_policy_ref=ref("EgressPolicyRevision", "egress"),
        data_classification_policy_ref=ref(
            "DataClassificationPolicyRevision", "classification"
        ),
        quota_policy_ref=ref("QuotaPolicyRevision", "quota"),
        budget_policy_ref=ref("BudgetPolicyRevision", "budget"),
        deadline_ms=30_000,
        max_attempts=2,
        allowed_fallback_reasons=["provider_unavailable", "deadline_exceeded"],
        unknown_usage_behavior="block",
        unknown_price_behavior="block",
        kill_switch_enabled=True,
        lifecycle=ModelRuntimeLifecycle.ACTIVE,
        created_by="reviewer",
        created_at=NOW,
    )


def route(*, strategy: RouteStrategy = RouteStrategy.FAILOVER) -> ModelRouteRevision:
    return ModelRouteRevision(
        tenant=TENANT,
        route_id="route-copy",
        revision=1,
        content_hash="c" * 64,
        task_types=["copy.generate"],
        required_input_modality=ModelModality.TEXT,
        required_output_modality=ModelModality.TEXT,
        required_capabilities=["structured_output"],
        candidates=[
            ModelRouteCandidate(model=ref("RegisteredModelRevision", "model-1"))
        ],
        strategy=strategy,
        runtime_policy_ref=ref("RuntimePolicyRevision", "policy-default"),
        eval_gate_ref=ref("EvalGateDecision", "eval-gate-1"),
        lifecycle=ModelRuntimeLifecycle.ACTIVE,
        created_by="reviewer",
        created_at=NOW,
    )


def test_provider_contract_is_secret_ref_only_and_exact() -> None:
    provider = ProviderInstanceRevision(
        tenant=TENANT,
        provider_instance_id="provider-1",
        revision=1,
        content_hash="d" * 64,
        plugin_ref=ref("ProviderPluginRevision", "plugin-1"),
        endpoint_profile=ProviderEndpointProfile(
            base_url="https://provider.invalid/v1",
            region="cn",
            timeout_ms=30_000,
        ),
        secret_ref="vault://aos/org-org/provider-1",
        secret_version="7",
        egress_policy_ref=ref("EgressPolicyRevision", "egress"),
        data_classification_policy_ref=ref(
            "DataClassificationPolicyRevision", "classification"
        ),
        lifecycle=ModelRuntimeLifecycle.VALIDATED,
        created_by="reviewer",
        created_at=NOW,
    )
    assert provider.secret_ref.startswith("vault://")
    with pytest.raises(ValidationError, match="credentials"):
        ProviderEndpointProfile(
            base_url="https://provider.invalid/v1",
            region="cn",
            timeout_ms=30_000,
            apiKeyMasked="abcd***wxyz",
        )
    with pytest.raises(ValidationError, match="opaque secret"):
        provider.model_copy(update={"secret_ref": "plaintext"}).model_validate(
            {**provider.model_dump(), "secret_ref": "plaintext"}
        )


def test_health_observation_has_exact_provider_and_freshness_window() -> None:
    observation = ProviderHealthObservation(
        tenant=TENANT,
        observation_id="health-1",
        provider=ref("ProviderInstanceRevision", "provider-1"),
        status="healthy",
        availability_pct=99.9,
        p50_latency_ms=100,
        observed_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    assert observation.status == "healthy"
    with pytest.raises(ValidationError, match="expiry"):
        ProviderHealthObservation(
            **{**observation.model_dump(), "expires_at": NOW - timedelta(seconds=1)}
        )


def test_runtime_policy_never_fallbacks_on_security_denials() -> None:
    assert policy().unknown_price_behavior == "block"
    with pytest.raises(ValidationError, match="cannot be fallback"):
        RuntimePolicyRevision(
            **{
                **policy().model_dump(),
                "allowed_fallback_reasons": ["safety_rejected"],
            }
        )


def test_route_requires_exact_unique_candidates_and_eval_policy_refs() -> None:
    assert route().runtime_policy_ref.asset_type == "RuntimePolicyRevision"
    duplicate = ModelRouteCandidate(
        model=ref("RegisteredModelRevision", "model-1")
    )
    with pytest.raises(ValidationError, match="unique"):
        ModelRouteRevision(
            **{**route().model_dump(), "candidates": [duplicate, duplicate]}
        )
    with pytest.raises(ValidationError, match="RuntimePolicyRevision"):
        ModelRouteRevision(
            **{
                **route().model_dump(),
                "runtime_policy_ref": ref("BudgetPolicyRevision", "budget"),
            }
        )


def test_weighted_route_must_total_one_hundred() -> None:
    with pytest.raises(ValidationError, match="total 100"):
        ModelRouteRevision(
            **{
                **route().model_dump(),
                "strategy": "weighted",
                "candidates": [
                    ModelRouteCandidate(
                        model=ref("RegisteredModelRevision", "model-1"), weight=60
                    ),
                    ModelRouteCandidate(
                        model=ref("RegisteredModelRevision", "model-2"), weight=30
                    ),
                ],
            }
        )


def test_resolution_cannot_claim_ready_without_exact_selection() -> None:
    blocked = ModelRouteResolution(
        tenant=TENANT,
        route=ref("ModelRouteRevision", "route-copy"),
        policy=ref("RuntimePolicyRevision", "policy-default"),
        readiness=ModelRuntimeReadiness.BLOCKED,
        blocker_codes=["provider_unavailable"],
        resolved_at=NOW,
    )
    assert blocked.selected_model is None
    with pytest.raises(ValidationError, match="exact selections"):
        ModelRouteResolution(
            tenant=TENANT,
            route=ref("ModelRouteRevision", "route-copy"),
            policy=ref("RuntimePolicyRevision", "policy-default"),
            readiness=ModelRuntimeReadiness.READY,
            resolved_at=NOW,
        )


def test_price_snapshot_requires_honest_currency_prices_and_effective_range() -> None:
    snapshot = ModelPriceSnapshotRevision(
        tenant=TENANT, priceSnapshotId="price-1", revision=1, contentHash="d" * 64,
        currency="CNY", inputTokenPrice=0.001, outputTokenPrice=0.002,
        tokenUnit=1000, effectiveFrom=NOW, lifecycle=ModelRuntimeLifecycle.ACTIVE,
        createdBy="reviewer", createdAt=NOW,
    )
    assert snapshot.currency == "CNY"
    with pytest.raises(ValidationError, match="requires an input or output"):
        ModelPriceSnapshotRevision(**{**snapshot.model_dump(), "input_token_price": None, "output_token_price": None})


def test_contracts_reject_tenant_payload_extensions() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        ModelRouteRevision(**route().model_dump(), org_id="dev-org")
