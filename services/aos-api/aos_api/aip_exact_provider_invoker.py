"""Exact fail-closed OpenAI-compatible Provider invocation for AIP-7.

The invoker consumes only an already READY model-route resolution, then
re-reads every exact authority before resolving a secret or touching a
transport.  It deliberately has no environment-variable, redirect, proxy or
provider fallback path.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from aos_api.aip_model_governance_policy_store import (
    AipModelGovernancePolicyStore,
    ModelGovernancePolicyStoreError,
)
from aos_api.aip_model_runtime_contracts import (
    ModelRouteResolution,
    ModelRuntimeLifecycle,
    ModelRuntimeReadiness,
)
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeStoreError
from aos_api.aip_network_policy_store import (
    AipNetworkPolicyStore,
    NetworkPolicyStoreError,
)
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


class ExactProviderInvocationError(RuntimeError):
    """Stable invocation blocker that never includes prompt or secret data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ProviderTransportResponse:
    status_code: int
    payload: dict[str, Any] | None


class ProviderTransport(Protocol):
    def post(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_ms: int,
    ) -> ProviderTransportResponse: ...


class HttpxProviderTransport:
    """Transport with redirects, environment proxies and implicit retries off."""

    def post(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_ms: int,
    ) -> ProviderTransportResponse:
        try:
            with httpx.Client(
                trust_env=False,
                follow_redirects=False,
                timeout=timeout_ms / 1000,
            ) as client:
                response = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException:
            raise ExactProviderInvocationError("provider_timeout") from None
        except httpx.HTTPError:
            raise ExactProviderInvocationError("provider_transport_error") from None
        try:
            body = response.json()
        except ValueError:
            body = None
        return ProviderTransportResponse(
            status_code=response.status_code,
            payload=body if isinstance(body, dict) else None,
        )


class ExactProviderInvoker:
    """Compose exact runtime authority and perform one bounded text request."""

    def __init__(
        self,
        *,
        model_store: Any | None = None,
        guard_store: Any | None = None,
        network_store: Any | None = None,
        governance_store: Any | None = None,
        plugin_authority: Any | None = None,
        secret_resolver: Any | None = None,
        transport: ProviderTransport | None = None,
    ) -> None:
        self._model_store = model_store or AipModelRuntimeStore()
        self._guard_store = guard_store or AipRuntimeGuardPolicyStore()
        self._network_store = network_store or AipNetworkPolicyStore()
        self._governance_store = governance_store or AipModelGovernancePolicyStore()
        self._plugin_authority = plugin_authority or ProviderPluginAuthority()
        self._secret_resolver = secret_resolver or ExactSecretResolver()
        self._transport = transport or HttpxProviderTransport()

    def __call__(
        self,
        resolution: ModelRouteResolution,
        prompt: str,
        data_classification: str,
    ) -> dict[str, Any]:
        scope = TenantScope(
            resolution.tenant.org_id,
            resolution.tenant.project_id,
        )
        if resolution.readiness is not ModelRuntimeReadiness.READY:
            raise ExactProviderInvocationError("model_runtime_not_ready")
        if not prompt:
            raise ExactProviderInvocationError("provider_prompt_empty")

        route, policy, model, provider = self._load_exact(scope, resolution)
        modality = self._validate_composition(
            scope, resolution, route, policy, model, provider
        )
        self._validate_runtime_dependencies(
            scope,
            policy,
            model,
            provider,
            data_classification,
        )
        url = self._validated_url(policy, provider, modality=modality)

        try:
            secret = self._secret_resolver.resolve(scope, provider)
        except SecretBackendError as exc:
            raise ExactProviderInvocationError(f"secret_{exc.code}") from None

        timeout_ms = min(
            int(policy.deadline_ms),
            int(provider.endpoint_profile.timeout_ms),
        )
        response = self._transport.post(
            url=url,
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/json",
            },
            payload=self._request_payload(modality, model, prompt),
            timeout_ms=timeout_ms,
        )
        return self._validated_response(
            response, route, model, provider, modality=modality
        )

    def _load_exact(self, scope: TenantScope, resolution: ModelRouteResolution):
        try:
            route = self._model_store.get_route(
                scope, resolution.route.asset_id, resolution.route.revision
            )
            policy = self._model_store.get_policy(
                scope, resolution.policy.asset_id, resolution.policy.revision
            )
            model = self._model_store.get_model(
                scope,
                resolution.selected_model.asset_id,
                resolution.selected_model.revision,
            )
            provider = self._model_store.get_provider(
                scope,
                resolution.selected_provider.asset_id,
                resolution.selected_provider.revision,
            )
        except ModelRuntimeStoreError:
            raise ExactProviderInvocationError("model_runtime_authority_unavailable") from None
        return route, policy, model, provider

    def _validate_composition(
        self,
        scope: TenantScope,
        resolution: ModelRouteResolution,
        route: Any,
        policy: Any,
        model: Any,
        provider: Any,
    ) -> None:
        self._require_exact(resolution.route, route, "route_id", "route_ref_drifted")
        self._require_exact(
            resolution.policy, policy, "policy_id", "runtime_policy_ref_drifted"
        )
        self._require_exact(
            resolution.selected_model,
            model,
            "registered_model_id",
            "model_ref_drifted",
        )
        self._require_exact(
            resolution.selected_provider,
            provider,
            "provider_instance_id",
            "provider_ref_drifted",
        )
        provider_scope = (
            provider.tenant.org_id,
            provider.tenant.project_id,
        )
        if provider_scope != scope.key:
            raise ExactProviderInvocationError("provider_tenant_mismatch")
        if any(
            item.lifecycle is not ModelRuntimeLifecycle.ACTIVE
            for item in (route, policy, model, provider)
        ):
            raise ExactProviderInvocationError("model_runtime_lifecycle_blocked")
        if policy.kill_switch_enabled:
            raise ExactProviderInvocationError("runtime_policy_kill_switch")
        if route.runtime_policy_ref != resolution.policy:
            raise ExactProviderInvocationError("route_policy_ref_drifted")
        if not any(candidate.model == resolution.selected_model for candidate in route.candidates):
            raise ExactProviderInvocationError("route_model_ref_drifted")
        if model.provider != resolution.selected_provider:
            raise ExactProviderInvocationError("model_provider_ref_drifted")
        if model.quota_policy_ref != policy.quota_policy_ref:
            raise ExactProviderInvocationError("quota_policy_ref_drifted")
        if model.budget_policy_ref != policy.budget_policy_ref:
            raise ExactProviderInvocationError("budget_policy_ref_drifted")
        if provider.egress_policy_ref != policy.egress_policy_ref:
            raise ExactProviderInvocationError("egress_policy_ref_drifted")
        if provider.data_classification_policy_ref != policy.data_classification_policy_ref:
            raise ExactProviderInvocationError("data_policy_ref_drifted")

        try:
            plugin = self._plugin_authority.validate_ref(scope, provider.plugin_ref)
        except ProviderPluginAuthorityError:
            raise ExactProviderInvocationError("provider_plugin_authority_blocked") from None
        return self._resolve_invocation_modality(plugin, model)

    @staticmethod
    def _resolve_invocation_modality(plugin: Any, model: Any) -> str:
        caps = set(plugin.approved_capabilities)
        modalities = set(plugin.modalities)
        model_caps = set(model.capabilities)
        model_in = {str(value) for value in model.input_modalities}
        model_out = {str(value) for value in model.output_modalities}
        if model.provider_model_id not in plugin.default_models:
            raise ExactProviderInvocationError("provider_plugin_capability_blocked")
        if not model_caps.issubset(caps):
            raise ExactProviderInvocationError("provider_plugin_capability_blocked")
        if (
            "image" in modalities
            and "image" in caps
            and "image" in model_out
            and "image" in model_caps
        ):
            return "image"
        if (
            "video" in modalities
            and "video" in caps
            and "video" in model_out
            and "video" in model_caps
        ):
            return "video"
        if (
            "text" in modalities
            and {"llm", "chat"}.issubset(caps)
            and "text" in model_in
            and "text" in model_out
        ):
            return "text"
        raise ExactProviderInvocationError("provider_plugin_capability_blocked")

    def _validate_runtime_dependencies(
        self,
        scope: TenantScope,
        policy: Any,
        model: Any,
        provider: Any,
        data_classification: str,
    ) -> None:
        try:
            self._guard_store.require_provider_dependencies(scope, provider)
            egress = self._guard_store.require_exact_active(
                scope, provider.egress_policy_ref
            )
            data_policy = self._guard_store.require_exact_active(
                scope, provider.data_classification_policy_ref
            )
        except GuardPolicyStoreError:
            raise ExactProviderInvocationError("runtime_guard_policy_blocked") from None
        if (
            not data_classification
            or data_classification not in data_policy.allowed_classifications
            or data_classification in data_policy.prohibited_classifications
        ):
            raise ExactProviderInvocationError("data_classification_blocked")
        if (
            not egress.region
            or provider.endpoint_profile.region != egress.region
        ):
            raise ExactProviderInvocationError("provider_region_unconfirmed")
        try:
            self._network_store.require_runtime_policy_dependency(scope, policy)
        except NetworkPolicyStoreError:
            raise ExactProviderInvocationError("network_policy_blocked") from None
        try:
            self._governance_store.require_model_dependencies(scope, model)
            self._governance_store.require_runtime_policy_dependencies(scope, policy)
        except ModelGovernancePolicyStoreError:
            raise ExactProviderInvocationError("model_governance_policy_blocked") from None

    def _validated_url(self, policy: Any, provider: Any, *, modality: str) -> str:
        from aos_api.aip_runtime_guard_policy_contracts import APPROVED_AGNES_HOSTS

        try:
            endpoint = urlsplit(str(provider.endpoint_profile.base_url))
            port = endpoint.port or 443
        except ValueError:
            raise ExactProviderInvocationError("provider_endpoint_blocked") from None
        host = endpoint.hostname
        if (
            endpoint.scheme != "https"
            or host not in APPROVED_AGNES_HOSTS
            or port != 443
            or endpoint.username is not None
            or endpoint.password is not None
            or endpoint.query
            or endpoint.fragment
            or endpoint.path.rstrip("/") != "/v1"
        ):
            raise ExactProviderInvocationError("provider_endpoint_blocked")
        if policy.deadline_ms <= 0 or provider.endpoint_profile.timeout_ms <= 0:
            raise ExactProviderInvocationError("provider_timeout_policy_blocked")
        if modality == "image":
            return f"https://{host}/v1/images/generations"
        if modality == "video":
            return f"https://{host}/v1/video/generations"
        return f"https://{host}/v1/chat/completions"

    @staticmethod
    def _request_payload(modality: str, model: Any, prompt: str) -> dict[str, Any]:
        if modality == "image":
            return {
                "model": model.provider_model_id,
                "prompt": prompt,
                "n": 1,
                "size": "256x256",
            }
        if modality == "video":
            return {
                "model": model.provider_model_id,
                "prompt": prompt,
                "n": 1,
            }
        return {
            "model": model.provider_model_id,
            "messages": [{"role": "user", "content": prompt}],
        }

    @staticmethod
    def _require_exact(ref: Any, item: Any, id_field: str, code: str) -> None:
        if (
            ref.asset_id != getattr(item, id_field)
            or ref.revision != item.revision
            or ref.content_hash != item.content_hash
        ):
            raise ExactProviderInvocationError(code)

    @staticmethod
    def _validated_response(
        response: ProviderTransportResponse,
        route: Any,
        model: Any,
        provider: Any,
        *,
        modality: str = "text",
    ) -> dict[str, Any]:
        if not 200 <= response.status_code < 300:
            raise ExactProviderInvocationError("provider_http_error")
        body = response.payload
        if not isinstance(body, dict):
            raise ExactProviderInvocationError("provider_response_invalid")
        response_model = body.get("model")
        if modality in {"image", "video"}:
            if response_model is not None:
                if not isinstance(response_model, str) or not response_model:
                    raise ExactProviderInvocationError("provider_response_model_missing")
                if response_model != model.provider_model_id:
                    raise ExactProviderInvocationError("provider_response_model_drifted")
            else:
                response_model = model.provider_model_id

        if modality == "image":
            data = body.get("data")
            if not isinstance(data, list) or not data or not isinstance(data[0], dict):
                raise ExactProviderInvocationError("provider_response_answer_missing")
            item = data[0]
            if not (item.get("url") or item.get("b64_json")):
                raise ExactProviderInvocationError("provider_response_answer_missing")
            provider_receipt_id = body.get("id")
            if not isinstance(provider_receipt_id, str) or not provider_receipt_id.strip():
                provider_receipt_id = (
                    "img-"
                    + hashlib.sha256(
                        f"{model.provider_model_id}:{route.route_id}:image".encode()
                    ).hexdigest()[:32]
                )
            answer = "image_generation_succeeded"
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
        elif modality == "video":
            has_video = False
            data = body.get("data")
            if isinstance(data, list) and data and isinstance(data[0], dict):
                item = data[0]
                has_video = bool(
                    item.get("url")
                    or item.get("b64_json")
                    or item.get("id")
                    or item.get("video_url")
                )
            if not has_video:
                has_video = any(
                    isinstance(body.get(key), str) and body.get(key)
                    for key in ("id", "video_id", "task_id")
                )
            if not has_video:
                raise ExactProviderInvocationError("provider_response_answer_missing")
            provider_receipt_id = body.get("id") or body.get("task_id") or body.get(
                "video_id"
            )
            if not isinstance(provider_receipt_id, str) or not provider_receipt_id.strip():
                provider_receipt_id = (
                    "vid-"
                    + hashlib.sha256(
                        f"{model.provider_model_id}:{route.route_id}:video".encode()
                    ).hexdigest()[:32]
                )
            answer = "video_generation_accepted"
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
        else:
            provider_receipt_id = body.get("id")
            if not isinstance(provider_receipt_id, str) or not provider_receipt_id.strip():
                raise ExactProviderInvocationError("provider_response_receipt_missing")
            if not isinstance(response_model, str) or not response_model:
                raise ExactProviderInvocationError("provider_response_model_missing")
            if response_model != model.provider_model_id:
                raise ExactProviderInvocationError("provider_response_model_drifted")
            choices = body.get("choices")
            message = (
                choices[0].get("message")
                if isinstance(choices, list) and choices
                else None
            )
            answer = message.get("content") if isinstance(message, dict) else None
            if not isinstance(answer, str) or not answer:
                raise ExactProviderInvocationError("provider_response_answer_missing")
            usage = body.get("usage")
            if not isinstance(usage, dict):
                raise ExactProviderInvocationError("provider_response_usage_missing")
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            if (
                not all(
                    isinstance(value, int)
                    and not isinstance(value, bool)
                    and value >= 0
                    for value in (prompt_tokens, completion_tokens, total_tokens)
                )
                or total_tokens != prompt_tokens + completion_tokens
            ):
                raise ExactProviderInvocationError("provider_response_usage_missing")

        observed_at = datetime.now(UTC)

        def usage_receipt(kind: str, quantity: int) -> dict[str, Any]:
            source = {
                "providerReceiptId": provider_receipt_id,
                "providerModelId": response_model,
                "usageKind": kind,
                "quantity": quantity,
                "unit": "token",
            }
            source_hash = hashlib.sha256(
                json.dumps(source, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest()
            return {
                "usageKind": kind,
                "quantity": quantity,
                "unit": "token",
                "quality": "measured",
                "sourceHash": source_hash,
                "observedAt": observed_at,
            }

        return {
            "answer": answer,
            "provider": provider.provider_instance_id,
            "model": model.registered_model_id,
            "tokens": total_tokens,
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "route": route.route_id,
            "providerReceiptId": provider_receipt_id,
            "usageReceipts": [
                usage_receipt("input_token", prompt_tokens),
                usage_receipt("output_token", completion_tokens),
            ],
            "modality": modality,
        }
