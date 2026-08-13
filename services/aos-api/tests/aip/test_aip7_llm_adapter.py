from datetime import UTC, datetime

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import TenantContext
from aos_api.aip_llm_adapter import LLMAdapter, LLMRuntimeBlocked
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.tenant_scope import TenantScope

NOW=datetime(2026,8,14,tzinfo=UTC);SCOPE=TenantScope("org-org","dev-project");HASH="a"*64
def ref(kind,value):return VersionedAssetRef(assetType=kind,assetId=value,revision=1,contentHash=HASH)
def resolution(readiness=ModelRuntimeReadiness.READY):return ModelRouteResolution(tenant=TenantContext(orgId="org-org",projectId="dev-project"),route=ref("ModelRouteRevision","route-1"),policy=ref("RuntimePolicyRevision","policy-1"),readiness=readiness,selectedModel=ref("RegisteredModelRevision","model-1") if readiness is ModelRuntimeReadiness.READY else None,selectedProvider=ref("ProviderInstanceRevision","provider-1") if readiness is ModelRuntimeReadiness.READY else None,selectedPriceSnapshot=ref("ModelPriceSnapshotRevision","price-1") if readiness is ModelRuntimeReadiness.READY else None,blockerCodes=[] if readiness is ModelRuntimeReadiness.READY else ["provider_health_unavailable_or_stale"],resolvedAt=NOW)
class Resolver:
    def __init__(self,result):self.result=result
    def resolve(self,scope,route_id):return self.result
class Usage:
    def record(self,scope,lineage,resolved,response):return ["usage-1"]

def test_exact_adapter_returns_authority_refs_without_secret_or_mock():
    adapter=LLMAdapter(resolver=Resolver(resolution()),provider_invoker=lambda resolved,prompt:{"answer":"真实回答","provider":"provider-1","model":"model-1","tokens":12,"route":"exact"},usage_bridge=Usage())
    result=adapter.chat_exact(SCOPE,"route-1","问题",lineage_id="lineage-1")
    assert result["routeRef"]["assetId"]=="route-1" and result["providerRef"]["assetId"]=="provider-1"
    assert "secret" not in str(result).lower()

def test_legacy_and_blocked_calls_fail_closed():
    adapter=LLMAdapter(resolver=Resolver(resolution(ModelRuntimeReadiness.BLOCKED)))
    with pytest.raises(LLMRuntimeBlocked,match="exact_scope_and_model_route_required"):adapter.chat("问题")
    with pytest.raises(LLMRuntimeBlocked,match="provider_health_unavailable_or_stale"):adapter.chat_exact(SCOPE,"route-1","问题",lineage_id="lineage-1")

@pytest.mark.parametrize("response",[{"answer":"fallback","provider":"mock","model":"mock","tokens":10,"route":"mock-fallback"},{"answer":"真实回答","provider":"provider-1","model":"model-1","route":"exact"}])
def test_mock_or_unknown_usage_is_rejected(response):
    adapter=LLMAdapter(resolver=Resolver(resolution()),provider_invoker=lambda *_:response,usage_bridge=Usage())
    with pytest.raises(LLMRuntimeBlocked):adapter.chat_exact(SCOPE,"route-1","问题",lineage_id="lineage-1")
