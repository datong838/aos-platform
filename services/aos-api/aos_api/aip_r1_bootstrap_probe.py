"""Restricted R1-C Provider preflight; never a business or Agent tool entrypoint."""
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any, Callable, Literal
from urllib.parse import urlsplit

from pydantic import Field

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import AipContractModel
from aos_api.aip_exact_provider_invoker import (
    ExactProviderInvocationError,
    HttpxProviderTransport,
    ProviderTransport,
    ProviderTransportResponse,
)
from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeStoreError
from aos_api.aip_network_policy_store import AipNetworkPolicyStore, NetworkPolicyStoreError
from aos_api.aip_provider_plugin_authority import (
    ProviderPluginAuthority,
    ProviderPluginAuthorityError,
)
from aos_api.aip_runtime_guard_policy_store import (
    AipRuntimeGuardPolicyStore,
    GuardPolicyStoreError,
)
from aos_api.aip_secret_backend import ExactSecretResolver, SecretBackendError
from aos_api.tenant_scope import TenantScope


class R1BootstrapProbeBlocked(RuntimeError):
    """Stable blocker that never contains prompt, answer, endpoint payload or secret."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class R1BootstrapProbeRequest(AipContractModel):
    provider: VersionedAssetRef
    network_policy: VersionedAssetRef
    provider_model_id: str = Field(min_length=1, max_length=240)
    data_classification: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=4000, repr=False)
    expected_response_behavior: Literal["non_empty", "refusal"] | None = None
    approval_ref: str = Field(min_length=1, max_length=240)


class R1BootstrapProbeResult(AipContractModel):
    status: str = Field(pattern=r"^healthy$")
    response_model: str = Field(min_length=1, max_length=240)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    answer_present: bool
    response_contract_passed: bool | None = None
    observed_at: datetime


class AipR1BootstrapProbe:
    """Exact Provider preflight used only before model-route readiness exists.

    The class is deliberately not registered in any router, adapter registry or
    Agent tool catalog.  It accepts only the R1-C approval marker and the
    approved development classification.
    """

    def __init__(
        self,
        *,
        model_store: Any | None = None,
        guard_store: Any | None = None,
        network_store: Any | None = None,
        plugin_authority: Any | None = None,
        secret_resolver: Any | None = None,
        transport: ProviderTransport | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._model_store = model_store or AipModelRuntimeStore()
        self._guard_store = guard_store or AipRuntimeGuardPolicyStore()
        self._network_store = network_store or AipNetworkPolicyStore()
        self._plugin_authority = plugin_authority or ProviderPluginAuthority()
        self._secret_resolver = secret_resolver or ExactSecretResolver()
        self._transport = transport or HttpxProviderTransport()
        self._clock = clock or (lambda: datetime.now(UTC))

    def run(
        self,
        scope: TenantScope,
        request: R1BootstrapProbeRequest,
    ) -> R1BootstrapProbeResult:
        if scope.key != ("org-org", "dev-project"):
            raise R1BootstrapProbeBlocked("provider_tenant_mismatch")
        if request.approval_ref != "35-R1-C":
            raise R1BootstrapProbeBlocked("r1_probe_approval_blocked")
        if request.provider.asset_type != "ProviderInstanceRevision":
            raise R1BootstrapProbeBlocked("provider_ref_invalid")
        if request.network_policy.asset_type != "NetworkPolicyRevision":
            raise R1BootstrapProbeBlocked("network_policy_ref_invalid")

        provider = self._provider(scope, request.provider)
        plugin = self._plugin(scope, provider)
        egress, data_policy = self._guard_dependencies(scope, provider)
        network = self._network(scope, request.network_policy)
        self._validate_request(
            request, provider, plugin, egress, data_policy, network
        )
        try:
            secret = self._secret_resolver.resolve(scope, provider)
        except SecretBackendError as exc:
            raise R1BootstrapProbeBlocked(f"secret_{exc.code}") from None

        endpoint = urlsplit(str(provider.endpoint_profile.base_url))
        host = endpoint.hostname or ""
        started = time.perf_counter()
        try:
            response = self._transport.post(
                url=f"https://{host}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {secret}",
                    "Content-Type": "application/json",
                },
                payload={
                    "model": request.provider_model_id,
                    "messages": [{"role": "user", "content": request.prompt}],
                },
                timeout_ms=min(60_000, int(provider.endpoint_profile.timeout_ms)),
            )
        except ExactProviderInvocationError as exc:
            raise R1BootstrapProbeBlocked(exc.code) from None
        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        return self._result(request, response, latency_ms)

    def _provider(self, scope: TenantScope, ref: VersionedAssetRef):
        try:
            provider = self._model_store.get_provider(
                scope, ref.asset_id, ref.revision
            )
        except ModelRuntimeStoreError:
            raise R1BootstrapProbeBlocked("provider_authority_unavailable") from None
        if (
            provider.provider_instance_id != ref.asset_id
            or provider.revision != ref.revision
            or provider.content_hash != ref.content_hash
        ):
            raise R1BootstrapProbeBlocked("provider_ref_drifted")
        if (provider.tenant.org_id, provider.tenant.project_id) != scope.key:
            raise R1BootstrapProbeBlocked("provider_tenant_mismatch")
        if provider.lifecycle not in {
            ModelRuntimeLifecycle.VALIDATED,
            ModelRuntimeLifecycle.ACTIVE,
        }:
            raise R1BootstrapProbeBlocked("provider_lifecycle_blocked")
        return provider

    def _plugin(self, scope: TenantScope, provider):
        try:
            return self._plugin_authority.validate_ref(scope, provider.plugin_ref)
        except ProviderPluginAuthorityError:
            raise R1BootstrapProbeBlocked("provider_plugin_authority_blocked") from None

    def _guard_dependencies(self, scope: TenantScope, provider):
        try:
            self._guard_store.require_provider_dependencies(scope, provider)
            egress = self._guard_store.require_exact_active(
                scope, provider.egress_policy_ref
            )
            data = self._guard_store.require_exact_active(
                scope, provider.data_classification_policy_ref
            )
        except GuardPolicyStoreError:
            raise R1BootstrapProbeBlocked("runtime_guard_policy_blocked") from None
        return egress, data

    def _network(self, scope: TenantScope, ref: VersionedAssetRef):
        try:
            return self._network_store.require_exact_active(scope, ref)
        except NetworkPolicyStoreError:
            raise R1BootstrapProbeBlocked("network_policy_blocked") from None

    @staticmethod
    def _validate_request(request, provider, plugin, egress, data_policy, network) -> None:
        if (
            request.provider_model_id not in plugin.default_models
            or "text" not in plugin.modalities
            or not {"llm", "chat"}.issubset(set(plugin.approved_capabilities))
        ):
            raise R1BootstrapProbeBlocked("provider_model_blocked")
        if (
            request.data_classification not in data_policy.allowed_classifications
            or request.data_classification in data_policy.prohibited_classifications
        ):
            raise R1BootstrapProbeBlocked("data_classification_blocked")
        from aos_api.aip_runtime_guard_policy_contracts import APPROVED_AGNES_HOSTS

        endpoint = urlsplit(str(provider.endpoint_profile.base_url))
        host = endpoint.hostname
        if (
            endpoint.scheme != "https"
            or host not in APPROVED_AGNES_HOSTS
            or (endpoint.port or 443) != 443
            or endpoint.path.rstrip("/") != "/v1"
            or endpoint.username is not None
            or endpoint.password is not None
            or endpoint.query
            or endpoint.fragment
        ):
            raise R1BootstrapProbeBlocked("provider_endpoint_blocked")
        if (
            provider.endpoint_profile.region != egress.region
            or network.egress_policy_ref != provider.egress_policy_ref
            or network.allowed_schemes != ["https"]
            or network.allowed_hosts != [host]
            or network.allowed_ports != [443]
            or not network.tls_required
            or network.public_fallback_allowed
        ):
            raise R1BootstrapProbeBlocked("provider_network_boundary_blocked")

    def _result(
        self,
        request: R1BootstrapProbeRequest,
        response: ProviderTransportResponse,
        latency_ms: int,
    ) -> R1BootstrapProbeResult:
        if not 200 <= response.status_code < 300:
            raise R1BootstrapProbeBlocked("provider_http_error")
        body = response.payload
        if not isinstance(body, dict):
            raise R1BootstrapProbeBlocked("provider_response_invalid")
        if body.get("model") != request.provider_model_id:
            raise R1BootstrapProbeBlocked("provider_response_model_drifted")
        choices = body.get("choices")
        message = choices[0].get("message") if isinstance(choices, list) and choices else None
        answer = message.get("content") if isinstance(message, dict) else None
        if not isinstance(answer, str) or not answer:
            raise R1BootstrapProbeBlocked("provider_response_answer_missing")
        contract_passed = None
        if request.expected_response_behavior is not None:
            normalized = answer.casefold()
            refusal_markers = (
                "refuse",
                "cannot",
                "can't",
                "unable",
                "fail_closed",
                "抱歉",
                "不能",
                "无法",
                "拒绝",
            )
            contract_passed = (
                bool(answer.strip())
                if request.expected_response_behavior == "non_empty"
                else any(marker in normalized for marker in refusal_markers)
            )
            if not contract_passed:
                raise R1BootstrapProbeBlocked("provider_response_contract_failed")
        usage = body.get("usage")
        values = (
            usage.get("prompt_tokens") if isinstance(usage, dict) else None,
            usage.get("completion_tokens") if isinstance(usage, dict) else None,
            usage.get("total_tokens") if isinstance(usage, dict) else None,
        )
        if (
            not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in values)
            or values[2] != values[0] + values[1]
        ):
            raise R1BootstrapProbeBlocked("provider_response_usage_invalid")
        return R1BootstrapProbeResult(
            status="healthy",
            responseModel=request.provider_model_id,
            promptTokens=values[0],
            completionTokens=values[1],
            totalTokens=values[2],
            latencyMs=latency_ms,
            answerPresent=True,
            responseContractPassed=contract_passed,
            observedAt=self._clock(),
        )
