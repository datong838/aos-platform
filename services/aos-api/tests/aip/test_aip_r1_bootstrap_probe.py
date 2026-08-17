from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_exact_provider_invoker import ProviderTransportResponse
from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle
from aos_api.aip_r1_bootstrap_probe import (
    AipR1BootstrapProbe,
    R1BootstrapProbeBlocked,
    R1BootstrapProbeRequest,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 17, tzinfo=UTC)
HASH = "a" * 64


def ref(kind: str, asset_id: str, digest: str = HASH) -> VersionedAssetRef:
    return VersionedAssetRef(assetType=kind, assetId=asset_id, revision=1, contentHash=digest)


class ModelStore:
    def __init__(self, provider):
        self.provider = provider

    def get_provider(self, _scope, _asset_id, _revision):
        return self.provider


class GuardStore:
    def __init__(self, assets):
        self.assets = assets

    def require_provider_dependencies(self, _scope, _provider):
        return None

    def require_exact_active(self, _scope, policy_ref):
        if policy_ref.asset_type == "DataClassificationPolicyRevision":
            return self.assets.data_policy
        return self.assets.egress


class NetworkStore:
    def __init__(self, assets):
        self.assets = assets

    def require_exact_active(self, _scope, _ref):
        return self.assets.network


class PluginAuthority:
    def __init__(self, plugin):
        self.plugin = plugin

    def validate_ref(self, _scope, _ref):
        return self.plugin


class SecretResolver:
    def __init__(self, value="top-secret"):
        self.value = value

    def resolve(self, _scope, _provider):
        return self.value


class Transport:
    def __init__(self, response=None):
        self.response = response or ProviderTransportResponse(
            status_code=200,
            payload={
                "model": "agnes-2.0-flash",
                "choices": [{"message": {"content": "pong"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            },
        )
        self.calls = []

    def post(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def assembly(*, scope=TenantScope("org-org", "dev-project"), region="Singapore (International)"):
    provider_ref = ref("ProviderInstanceRevision", "agnes-text-qyh-dev")
    egress_ref = ref("EgressPolicyRevision", "agnes-text-qyh-dev-egress")
    data_ref = ref("DataClassificationPolicyRevision", "agnes-text-qyh-dev-data-classification")
    network_ref = ref("NetworkPolicyRevision", "network-qyh-text-dev")
    provider = SimpleNamespace(
        tenant=SimpleNamespace(org_id=scope.org_id, project_id=scope.project_id),
        provider_instance_id=provider_ref.asset_id,
        revision=1,
        content_hash=provider_ref.content_hash,
        lifecycle=ModelRuntimeLifecycle.VALIDATED,
        plugin_ref=ref("ProviderPluginRevision", "agnes-text"),
        endpoint_profile=SimpleNamespace(
            base_url="https://apihub.agnes-ai.com/v1", region=region, timeout_ms=10_000
        ),
        egress_policy_ref=egress_ref,
        data_classification_policy_ref=data_ref,
    )
    assets = SimpleNamespace(
        provider=provider,
        egress=SimpleNamespace(region=region),
        data_policy=SimpleNamespace(
            allowed_classifications=["approved_development_sample"],
            prohibited_classifications=["direct_pii", "unknown"],
        ),
        network=SimpleNamespace(
            allowed_schemes=["https"], allowed_hosts=["apihub.agnes-ai.com"],
            allowed_ports=[443], tls_required=True, public_fallback_allowed=False,
            egress_policy_ref=egress_ref, effective_from=NOW - timedelta(days=1),
            effective_until=NOW + timedelta(days=1),
        ),
        plugin=SimpleNamespace(
            modalities=["text"], approved_capabilities=["llm", "chat"],
            default_models=["agnes-2.0-flash"],
        ),
    )
    request = R1BootstrapProbeRequest(
        provider=provider_ref,
        networkPolicy=network_ref,
        providerModelId="agnes-2.0-flash",
        dataClassification="approved_development_sample",
        prompt="只回复 pong。",
        approvalRef="35-R1-C",
    )
    return assets, request


def probe(assets, *, transport=None, secret=None):
    return AipR1BootstrapProbe(
        model_store=ModelStore(assets.provider),
        guard_store=GuardStore(assets),
        network_store=NetworkStore(assets),
        plugin_authority=PluginAuthority(assets.plugin),
        secret_resolver=secret or SecretResolver(),
        transport=transport or Transport(),
        clock=lambda: NOW,
    )


def test_probe_validates_exact_authority_and_returns_metadata_only():
    assets, request = assembly()
    transport = Transport()
    result = probe(assets, transport=transport).run(
        TenantScope("org-org", "dev-project"), request
    )

    assert result.status == "healthy"
    assert result.response_model == "agnes-2.0-flash"
    assert result.total_tokens == 3
    assert result.answer_present is True
    assert "top-secret" not in repr(result)
    assert "pong" not in repr(result)
    assert transport.calls[0]["url"] == "https://apihub.agnes-ai.com/v1/chat/completions"


def test_probe_fails_closed_when_expected_response_contract_is_missing():
    assets, request = assembly()
    request = request.model_copy(
        update={"expected_response_behavior": "refusal"}
    )
    with pytest.raises(
        R1BootstrapProbeBlocked, match="provider_response_contract_failed"
    ):
        probe(assets).run(TenantScope("org-org", "dev-project"), request)


def test_probe_fails_closed_for_cross_tenant_and_unapproved_classification():
    assets, request = assembly()
    with pytest.raises(R1BootstrapProbeBlocked, match="provider_tenant_mismatch"):
        probe(assets).run(TenantScope("dev-org", "dev-project"), request)

    bad = request.model_copy(update={"data_classification": "direct_pii"})
    with pytest.raises(R1BootstrapProbeBlocked, match="data_classification_blocked"):
        probe(assets).run(TenantScope("org-org", "dev-project"), bad)


def test_probe_fails_closed_for_model_drift_and_invalid_usage():
    assets, request = assembly()
    with pytest.raises(R1BootstrapProbeBlocked, match="provider_model_blocked"):
        probe(assets).run(
            TenantScope("org-org", "dev-project"),
            request.model_copy(update={"provider_model_id": "other-model"}),
        )

    transport = Transport(ProviderTransportResponse(
        status_code=200,
        payload={
            "model": "agnes-2.0-flash",
            "choices": [{"message": {"content": "pong"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 4},
        },
    ))
    with pytest.raises(R1BootstrapProbeBlocked, match="provider_response_usage_invalid"):
        probe(assets, transport=transport).run(TenantScope("org-org", "dev-project"), request)
