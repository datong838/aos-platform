from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_exact_provider_invoker import (
    ExactProviderInvocationError,
    ExactProviderInvoker,
    ProviderTransportResponse,
)
from aos_api.aip_model_runtime_contracts import (
    ModelRouteResolution,
    ModelRuntimeLifecycle,
    ModelRuntimeReadiness,
)
from aos_api.aip_secret_backend import SecretBackendError


NOW = datetime(2026, 8, 17, tzinfo=UTC)
HASH = "a" * 64


def ref(kind: str, asset_id: str, content_hash: str = HASH) -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType=kind,
        assetId=asset_id,
        revision=1,
        contentHash=content_hash,
    )


class Store:
    def __init__(self, assets):
        self.assets = assets

    def get_route(self, _scope, _asset_id, _revision=None):
        return self.assets.route

    def get_policy(self, _scope, _asset_id, _revision=None):
        return self.assets.policy

    def get_model(self, _scope, _asset_id, _revision=None):
        return self.assets.model

    def get_provider(self, _scope, _asset_id, _revision=None):
        return self.assets.provider


class GuardStore:
    def __init__(self, assets):
        self.assets = assets
        self.calls = []

    def require_provider_dependencies(self, _scope, provider):
        self.calls.append(("provider", provider.provider_instance_id))

    def require_exact_active(self, _scope, policy_ref):
        self.calls.append(("policy", policy_ref.asset_type))
        if policy_ref.asset_type == "DataClassificationPolicyRevision":
            return self.assets.data_policy
        return self.assets.egress


class NetworkStore:
    def __init__(self, assets):
        self.assets = assets
        self.calls = 0

    def require_runtime_policy_dependency(self, _scope, _policy):
        self.calls += 1
        return self.assets.network


class GovernanceStore:
    def __init__(self):
        self.calls = []

    def require_model_dependencies(self, _scope, _model):
        self.calls.append("model")

    def require_runtime_policy_dependencies(self, _scope, _policy):
        self.calls.append("policy")


class PluginAuthority:
    def __init__(self, assets):
        self.assets = assets

    def validate_ref(self, _scope, _ref):
        return self.assets.plugin


class SecretResolver:
    def __init__(self, value="top-secret"):
        self.value = value
        self.calls = 0

    def resolve(self, _scope, _provider):
        self.calls += 1
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class Transport:
    def __init__(self, response=None):
        self.response = response or ProviderTransportResponse(
            status_code=200,
            payload={
                "model": "agnes-2.0-flash",
                "choices": [{"message": {"content": "真实回答"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 5, "total_tokens": 12},
            },
        )
        self.calls = []

    def post(self, *, url, headers, payload, timeout_ms):
        self.calls.append((url, headers, payload, timeout_ms))
        return self.response


def assembly(*, org_id="org-org", model_hash=HASH, region="cn-shanghai"):
    route_ref = ref("ModelRouteRevision", "route-1")
    policy_ref = ref("RuntimePolicyRevision", "policy-1")
    model_ref = ref("RegisteredModelRevision", "model-1", model_hash)
    provider_ref = ref("ProviderInstanceRevision", "provider-1")
    network_ref = ref("NetworkPolicyRevision", "network-1")
    egress_ref = ref("EgressPolicyRevision", "egress-1")
    data_ref = ref("DataClassificationPolicyRevision", "data-1")
    quota_ref = ref("QuotaPolicyRevision", "quota-1")
    budget_ref = ref("BudgetPolicyRevision", "budget-1")
    plugin_ref = ref("ProviderPluginRevision", "agnes-text")

    assets = SimpleNamespace(
        route=SimpleNamespace(
            route_id="route-1",
            revision=1,
            content_hash=HASH,
            lifecycle=ModelRuntimeLifecycle.ACTIVE,
            runtime_policy_ref=policy_ref,
            candidates=[SimpleNamespace(model=model_ref)],
        ),
        policy=SimpleNamespace(
            policy_id="policy-1",
            revision=1,
            content_hash=HASH,
            lifecycle=ModelRuntimeLifecycle.ACTIVE,
            kill_switch_enabled=False,
            deadline_ms=30_000,
            network_policy_ref=network_ref,
            egress_policy_ref=egress_ref,
            data_classification_policy_ref=data_ref,
            quota_policy_ref=quota_ref,
            budget_policy_ref=budget_ref,
        ),
        model=SimpleNamespace(
            registered_model_id="model-1",
            revision=1,
            content_hash=model_hash,
            lifecycle=ModelRuntimeLifecycle.ACTIVE,
            provider=provider_ref,
            provider_model_id="agnes-2.0-flash",
            input_modalities=["text"],
            output_modalities=["text"],
            capabilities=["llm", "chat"],
            quota_policy_ref=quota_ref,
            budget_policy_ref=budget_ref,
        ),
        provider=SimpleNamespace(
            tenant=SimpleNamespace(org_id="org-org", project_id="dev-project"),
            provider_instance_id="provider-1",
            revision=1,
            content_hash=HASH,
            lifecycle=ModelRuntimeLifecycle.ACTIVE,
            plugin_ref=plugin_ref,
            endpoint_profile=SimpleNamespace(
                base_url="https://apihub.agnes-ai.com/v1",
                region=region,
                timeout_ms=60_000,
            ),
            secret_ref=(
                "keychain://com.aos.llm/agnes-text/org-org/dev-project/"
                "provider-1#api-key"
            ),
            secret_version="v1",
            egress_policy_ref=egress_ref,
            data_classification_policy_ref=data_ref,
        ),
        plugin=SimpleNamespace(
            modalities=["text"],
            approved_capabilities=["llm", "chat"],
            default_models=["agnes-2.0-flash"],
        ),
        egress=SimpleNamespace(region="cn-shanghai"),
        network=SimpleNamespace(
            allowed_schemes=["https"],
            allowed_hosts=["apihub.agnes-ai.com"],
            allowed_ports=[443],
            tls_required=True,
            public_fallback_allowed=False,
        ),
        data_policy=SimpleNamespace(
            allowed_classifications=["approved_internal_knowledge"],
            prohibited_classifications=["direct_pii", "credential", "unknown"],
            deny_unknown=True,
        ),
    )
    resolution = ModelRouteResolution(
        tenant={"orgId": org_id, "projectId": "dev-project"},
        route=route_ref,
        policy=policy_ref,
        readiness=ModelRuntimeReadiness.READY,
        selectedModel=model_ref,
        selectedProvider=provider_ref,
        selectedPriceSnapshot=ref("ModelPriceSnapshotRevision", "price-1"),
        resolvedAt=NOW,
    )
    secret = SecretResolver()
    transport = Transport()
    invoker = ExactProviderInvoker(
        model_store=Store(assets),
        guard_store=GuardStore(assets),
        network_store=NetworkStore(assets),
        governance_store=GovernanceStore(),
        plugin_authority=PluginAuthority(assets),
        secret_resolver=secret,
        transport=transport,
    )
    return invoker, resolution, assets, secret, transport


def test_exact_invoker_composes_approved_request_and_returns_minimal_usage() -> None:
    invoker, resolution, _, secret, transport = assembly()

    result = invoker(
        resolution,
        "只处理批准的非敏感事实",
        "approved_internal_knowledge",
    )

    assert result == {
        "answer": "真实回答",
        "provider": "provider-1",
        "model": "model-1",
        "tokens": 12,
        "promptTokens": 7,
        "completionTokens": 5,
        "route": "route-1",
    }
    assert secret.calls == 1
    url, headers, payload, timeout_ms = transport.calls[0]
    assert url == "https://apihub.agnes-ai.com/v1/chat/completions"
    assert headers == {"Authorization": "Bearer top-secret", "Content-Type": "application/json"}
    assert payload == {
        "model": "agnes-2.0-flash",
        "messages": [{"role": "user", "content": "只处理批准的非敏感事实"}],
    }
    assert timeout_ms == 30_000
    assert "top-secret" not in repr(result)


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda resolution, assets: setattr(resolution.route, "content_hash", "b" * 64), "route_ref_drifted"),
        (lambda resolution, assets: setattr(assets.provider.endpoint_profile, "region", "unknown"), "provider_region_unconfirmed"),
        (lambda resolution, assets: setattr(assets.provider.endpoint_profile, "base_url", "http://apihub.agnes-ai.com/v1"), "provider_endpoint_blocked"),
        (lambda resolution, assets: setattr(assets.policy, "kill_switch_enabled", True), "runtime_policy_kill_switch"),
    ],
)
def test_composition_failure_happens_before_secret_or_transport(mutate, code) -> None:
    invoker, resolution, assets, secret, transport = assembly()
    mutate(resolution, assets)

    with pytest.raises(ExactProviderInvocationError, match=code):
        invoker(resolution, "prompt-must-not-leak", "approved_internal_knowledge")

    assert secret.calls == 0
    assert transport.calls == []


def test_negative_tenant_canary_is_rejected_before_side_effects() -> None:
    invoker, resolution, _, secret, transport = assembly(org_id="dev-org")

    with pytest.raises(ExactProviderInvocationError, match="provider_tenant_mismatch"):
        invoker(resolution, "prompt-must-not-leak", "approved_internal_knowledge")

    assert secret.calls == 0
    assert transport.calls == []


def test_secret_and_transport_failures_are_mapped_without_sensitive_values() -> None:
    invoker, resolution, _, secret, transport = assembly()
    secret.value = SecretBackendError("keychain_item_unavailable")

    with pytest.raises(ExactProviderInvocationError) as captured:
        invoker(resolution, "prompt-must-not-leak", "approved_internal_knowledge")
    assert str(captured.value) == "secret_keychain_item_unavailable"
    assert "prompt-must-not-leak" not in str(captured.value)
    assert transport.calls == []

    invoker, resolution, _, _, transport = assembly()
    transport.response = ProviderTransportResponse(
        status_code=502,
        payload={"error": {"message": "top-secret prompt-must-not-leak"}},
    )
    with pytest.raises(ExactProviderInvocationError) as captured:
        invoker(resolution, "prompt-must-not-leak", "approved_internal_knowledge")
    assert str(captured.value) == "provider_http_error"
    assert "top-secret" not in str(captured.value)
    assert "prompt-must-not-leak" not in str(captured.value)


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({}, "provider_response_model_missing"),
        ({"model": "other", "choices": [], "usage": {}}, "provider_response_model_drifted"),
        ({"model": "agnes-2.0-flash", "choices": [], "usage": {}}, "provider_response_answer_missing"),
        ({"model": "agnes-2.0-flash", "choices": [{"message": {"content": "ok"}}], "usage": {}}, "provider_response_usage_missing"),
    ],
)
def test_malformed_provider_response_fails_closed(payload, code) -> None:
    invoker, resolution, _, _, transport = assembly()
    transport.response = ProviderTransportResponse(status_code=200, payload=payload)

    with pytest.raises(ExactProviderInvocationError, match=code):
        invoker(resolution, "prompt", "approved_internal_knowledge")


@pytest.mark.parametrize("classification", ["", "unknown", "direct_pii"])
def test_unapproved_data_classification_fails_before_secret(classification) -> None:
    invoker, resolution, _, secret, transport = assembly()

    with pytest.raises(ExactProviderInvocationError, match="data_classification_blocked"):
        invoker(resolution, "prompt-must-not-leak", classification)

    assert secret.calls == 0
    assert transport.calls == []
