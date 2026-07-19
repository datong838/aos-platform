"""T3.9 Model Gateway → Agnes (OpenAI-compatible) and/or LiteLLM sidecar."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from aos_api.env_load import load_dotenv
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.llm_gateway")

DEFAULT_KEY_REF = "vault:secret/data/aos/llm#agnes"

# Ensure .env is visible for gateway calls
load_dotenv()


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def key_ref() -> str:
    return _env("AOS_LLM_API_KEY_REF", DEFAULT_KEY_REF)


def resolve_master_key() -> str:
    """Map vault ref → local Dev secret env. Never return this via API."""
    ref = key_ref()
    if ref.startswith("vault:"):
        return _env("AOS_LLM_MASTER_KEY", "aos_dev_litellm_master")
    return ref


def litellm_url() -> str:
    return _env("AOS_LITELLM_URL", "").rstrip("/")


def litellm_model() -> str:
    return _env("AOS_LITELLM_MODEL", "") or agnes_text_model() or "aos-dev"


def fallback_mode() -> str:
    """mock | off — pytest defaults to mock when URL empty or unreachable."""
    return _env("AOS_LITELLM_FALLBACK", "mock").lower()


def agnes_api_key() -> str:
    return _env("AGNES_API_KEY")


def agnes_base_url() -> str:
    return _env("AGNES_BASE_URL").rstrip("/")


def agnes_text_model() -> str:
    return _env("AGNES_TEXT_MODEL")


def agnes_image_model() -> str:
    return _env("AGNES_IMAGE_MODEL")


def agnes_configured() -> bool:
    return bool(agnes_base_url() and agnes_api_key() and agnes_text_model())


def _openai_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    query: str,
    timeout: float = 60,
) -> dict[str, Any]:
    """OpenAI-compatible chat completions (Agnes / LiteLLM / echo)."""
    root = base_url.rstrip("/")
    # Accept both https://host/v1 and https://host
    if root.endswith("/v1"):
        url = f"{root}/chat/completions"
    else:
        url = f"{root}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": query}],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    answer = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    return {"answer": answer or "", "raw": body}


def probe_sidecar(timeout: float = 1.5) -> dict[str, Any]:
    base = litellm_url()
    if not base:
        return {"ok": False, "sidecar": "unset", "detail": "AOS_LITELLM_URL empty"}
    for path in ("/health/liveliness", "/health", "/v1/models", "/"):
        try:
            req = urllib.request.Request(
                f"{base}{path}",
                headers={"Authorization": f"Bearer {resolve_master_key()}"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                _ = resp.read(64)
            return {"ok": True, "sidecar": "litellm", "probe": path}
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
            continue
    return {"ok": False, "sidecar": "litellm-down", "detail": last}


def chat(
    query: str,
    *,
    model: str | None = None,
    with_tools: bool = False,
    tools: list[str] | None = None,
) -> dict[str, Any]:
    """Honor explicit model when provided; else follow platform default gateway (85)."""
    load_dotenv()
    tools_used = tools or ([] if not with_tools else ["query.objects"])
    tool_calls = [{"toolId": t, "ok": True} for t in tools_used]
    requested = (model or "").strip() or None

    if requested:
        return _chat_for_model(requested, query=query, tool_calls=tool_calls)

    from aos_api.gateway_default import get_gateway_default

    gd = get_gateway_default()
    kind = str(gd.get("kind") or "")
    default_model = str(gd.get("defaultModel") or "").strip() or None

    if kind == "plugin" and default_model:
        return _chat_for_model(default_model, query=query, tool_calls=tool_calls)

    if kind == "litellm" or (kind in {"", "mock"} and not agnes_configured() and litellm_url()):
        base = litellm_url()
        litellm_m = default_model or litellm_model()
        if base:
            try:
                out = _openai_chat(
                    base_url=base,
                    api_key=resolve_master_key(),
                    model=litellm_m,
                    query=query,
                    timeout=30,
                )
                log.info("llm_chat via=litellm model=%s answer_len=%s", litellm_m, len(out["answer"]))
                return {
                    "answer": out["answer"],
                    "provider": litellm_m,
                    "model": litellm_m,
                    "warm": True,
                    "route": "litellm-sidecar",
                    "sidecar": "litellm",
                    "apiKeyRef": key_ref(),
                    "toolCalls": tool_calls,
                }
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                log.warning("llm_chat_sidecar_fail err=%s", exc)
                if fallback_mode() == "off":
                    raise

    if kind in {"agnes", ""} and agnes_configured():
        try:
            use_model = default_model or agnes_text_model()
            out = _openai_chat(
                base_url=agnes_base_url(),
                api_key=agnes_api_key(),
                model=use_model,
                query=query,
            )
            log.info("llm_chat via=agnes model=%s answer_len=%s", use_model, len(out["answer"]))
            return {
                "answer": out["answer"],
                "provider": use_model,
                "model": use_model,
                "warm": True,
                "route": "agnes",
                "sidecar": "agnes-openai-compatible",
                "apiKeyRef": key_ref(),
                "imageModel": agnes_image_model() or None,
                "toolCalls": tool_calls,
            }
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            log.warning("llm_chat_agnes_fail err=%s", exc)
            if fallback_mode() == "off":
                raise

    if fallback_mode() == "off":
        raise RuntimeError("No LLM provider available (默认网关 / Agnes / LiteLLM)")

    log.info("llm_chat via=fallback-mock query_len=%s", len(query))
    return {
        "answer": f"[mock-llm] {query}",
        "provider": "mock-llm",
        "model": "mock-llm",
        "warm": True,
        "route": "fallback-mock",
        "sidecar": "fallback-mock",
        "apiKeyRef": key_ref(),
        "toolCalls": tool_calls,
    }


def _chat_for_model(requested: str, *, query: str, tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    agnes_ids = {x for x in (agnes_text_model(), agnes_image_model()) if x}
    if requested in agnes_ids or (agnes_configured() and requested.startswith("agnes-")):
        if not agnes_configured():
            raise RuntimeError(f"模型 {requested} 需要 Agnes 网关，但未配置 AGNES_*")
        use_model = requested if requested != agnes_image_model() else agnes_text_model()
        out = _openai_chat(
            base_url=agnes_base_url(),
            api_key=agnes_api_key(),
            model=use_model,
            query=query,
        )
        return {
            "answer": out["answer"],
            "provider": requested,
            "model": requested,
            "warm": True,
            "route": "agnes",
            "sidecar": "agnes-openai-compatible",
            "apiKeyRef": key_ref(),
            "toolCalls": tool_calls,
        }

    from aos_api.llm_provider_registry import (
        find_plugin_for_model,
        plugin_base_url,
        resolve_plugin_api_key,
    )

    hit = find_plugin_for_model(requested)
    if hit:
        pid = str(hit["pluginId"])
        cfg = hit.get("config") or {}
        man = hit.get("manifest") or {}
        base = plugin_base_url(pid, cfg, man)
        if not base:
            raise RuntimeError(f"插件 {pid} 未配置 Base URL，请到供应商页保存配置")
        api_key = resolve_plugin_api_key(pid, str(cfg.get("secretRef") or ""))
        if not api_key:
            raise RuntimeError(
                f"模型 {requested}（插件 {pid}）未绑定可用密钥。"
                "请在「管理凭据」粘贴 API Key 并保存，或设置环境变量 "
                "AOS_DEEPSEEK_API_KEY / DEEPSEEK_API_KEY"
            )
        out = _openai_chat(base_url=base, api_key=api_key, model=requested, query=query)
        log.info("llm_chat via=plugin id=%s model=%s answer_len=%s", pid, requested, len(out["answer"]))
        return {
            "answer": out["answer"],
            "provider": requested,
            "model": requested,
            "warm": True,
            "route": f"plugin:{pid}",
            "sidecar": "plugin-openai-compatible",
            "pluginId": pid,
            "apiKeyRef": cfg.get("secretRef") or f"plugin:{pid}",
            "toolCalls": tool_calls,
        }

    base = litellm_url()
    if base:
        out = _openai_chat(
            base_url=base,
            api_key=resolve_master_key(),
            model=requested,
            query=query,
            timeout=30,
        )
        return {
            "answer": out["answer"],
            "provider": requested,
            "model": requested,
            "warm": True,
            "route": "litellm-sidecar",
            "sidecar": "litellm",
            "apiKeyRef": key_ref(),
            "toolCalls": tool_calls,
        }

    raise RuntimeError(
        f"无法路由模型 {requested}：未找到就绪插件，且 LiteLLM 未配置。"
        "请先在供应商页「启用就绪」并绑定密钥。"
    )


def _providers_from_agnes() -> dict[str, Any]:
    items: list[dict[str, Any]] = [
        {
            "id": agnes_text_model(),
            "name": "Agnes Text",
            "ready": True,
            "apiKeyRef": key_ref(),
            "kind": "text",
        }
    ]
    if agnes_image_model():
        items.append(
            {
                "id": agnes_image_model(),
                "name": "Agnes Image",
                "ready": True,
                "apiKeyRef": key_ref(),
                "kind": "image",
            }
        )
    return {
        "items": items,
        "sidecar": "agnes-openai-compatible",
        "apiKeyRef": key_ref(),
        "endpoint": agnes_base_url(),
        "defaultTextModel": agnes_text_model(),
        "probe": {"ok": True, "sidecar": "agnes"},
        "gatewayKind": "agnes",
    }


def _providers_from_plugin(plugin_id: str, default_model: str | None) -> dict[str, Any]:
    from aos_api.llm_provider_registry import (
        get_plugin_config,
        list_llm_provider_plugins,
        plugin_base_url,
    )

    plug = next(
        (i for i in list_llm_provider_plugins().get("items") or [] if i.get("id") == plugin_id),
        None,
    )
    if not plug or not plug.get("ready"):
        # Fall back so UI still loads
        if agnes_configured():
            return _providers_from_agnes()
        return {
            "items": [{"id": "mock-llm", "name": "Fallback Mock", "ready": True, "apiKeyRef": key_ref()}],
            "sidecar": "fallback-mock",
            "apiKeyRef": key_ref(),
            "probe": {"ok": False, "sidecar": "fallback-mock"},
            "gatewayKind": "mock",
        }

    cfg = get_plugin_config(plugin_id)
    models = list(cfg.get("models") or plug.get("enabledModels") or plug.get("defaultModels") or [plugin_id])
    label = str(plug.get("nameZh") or plug.get("name") or plugin_id)
    secret = str(cfg.get("secretRef") or f"vault:secret/data/aos/llm#{plugin_id}")
    items = []
    for mid in models:
        mid_s = str(mid)
        kind = "image" if "image" in mid_s.lower() else ("video" if "video" in mid_s.lower() else "text")
        items.append(
            {
                "id": mid_s,
                "name": f"{label} · {mid_s}",
                "ready": True,
                "apiKeyRef": secret,
                "kind": kind,
                "pluginId": plugin_id,
            }
        )
    endpoint = plugin_base_url(
        plugin_id,
        cfg,
        {"configSchema": plug.get("configSchema") or {}},
    ) or ""
    text_default = default_model or next((i["id"] for i in items if i["kind"] == "text"), items[0]["id"] if items else None)
    return {
        "items": items,
        "sidecar": f"plugin:{plugin_id}",
        "apiKeyRef": secret,
        "endpoint": endpoint,
        "defaultTextModel": text_default,
        "probe": {"ok": True, "sidecar": f"plugin:{plugin_id}"},
        "gatewayKind": "plugin",
        "pluginId": plugin_id,
    }


def _providers_from_litellm() -> dict[str, Any]:
    probe = probe_sidecar()
    if probe.get("ok"):
        items = [
            {
                "id": litellm_model(),
                "name": "LiteLLM Dev Provider",
                "ready": True,
                "apiKeyRef": key_ref(),
                "kind": "text",
            }
        ]
        sidecar = "litellm"
    else:
        items = [
            {
                "id": "mock-llm",
                "name": "Fallback Mock (no Agnes / sidecar)",
                "ready": True,
                "apiKeyRef": key_ref(),
                "kind": "text",
            }
        ]
        sidecar = str(probe.get("sidecar") or "fallback-mock")
    return {
        "items": items,
        "sidecar": sidecar,
        "apiKeyRef": key_ref(),
        "defaultTextModel": items[0]["id"] if items else None,
        "probe": probe,
        "gatewayKind": "litellm" if probe.get("ok") else "mock",
    }


def providers_payload() -> dict[str, Any]:
    """GET /v1/aip/providers — 运行态卡片跟随平台默认网关（85）。"""
    load_dotenv()
    from aos_api.gateway_default import get_gateway_default

    gd = get_gateway_default()
    kind = str(gd.get("kind") or "")
    if kind == "plugin" and gd.get("pluginId"):
        return _providers_from_plugin(str(gd["pluginId"]), gd.get("defaultModel"))
    if kind == "litellm":
        return _providers_from_litellm()
    if kind == "agnes" or (not kind and agnes_configured()):
        if agnes_configured():
            return _providers_from_agnes()
    if litellm_url():
        return _providers_from_litellm()
    return {
        "items": [
            {
                "id": "mock-llm",
                "name": "Fallback Mock (no Agnes / sidecar)",
                "ready": True,
                "apiKeyRef": key_ref(),
                "kind": "text",
            }
        ],
        "sidecar": "fallback-mock",
        "apiKeyRef": key_ref(),
        "defaultTextModel": "mock-llm",
        "probe": {"ok": False, "sidecar": "fallback-mock"},
        "gatewayKind": "mock",
    }


def warmup_payload() -> dict[str, Any]:
    load_dotenv()
    providers = providers_payload()
    models = [{"id": p["id"], "state": "ready" if p.get("ready") is not False else "cold"} for p in providers.get("items") or []]
    return {
        "ready": bool(models) and providers.get("probe", {}).get("ok", True) is not False,
        "models": models or [{"id": "mock-llm", "state": "cold"}],
        "sidecar": providers.get("sidecar"),
        "apiKeyRef": providers.get("apiKeyRef"),
    }


def models_payload() -> dict[str, Any]:
    """GET /v1/aip/models — routable model catalog (T-API) · 运行态 ∪ 已就绪插件模型。"""
    warm = warmup_payload()
    providers = providers_payload()
    by_id = {p["id"]: p for p in providers.get("items") or []}
    items = []
    seen: set[str] = set()
    for m in warm.get("models") or []:
        mid = m["id"]
        meta = by_id.get(mid) or {}
        items.append(
            {
                "id": mid,
                "state": m.get("state", "ready"),
                "kind": meta.get("kind") or ("image" if "image" in mid.lower() else "text"),
                "ready": m.get("state") == "ready",
                "provider": meta.get("name") or mid,
                "apiKeyRef": warm.get("apiKeyRef"),
                "source": "runtime",
            }
        )
        seen.add(mid)
    try:
        from aos_api.llm_provider_registry import routable_models_from_plugins

        for pm in routable_models_from_plugins():
            mid = str(pm.get("id") or "")
            if not mid or mid in seen:
                continue
            items.append(pm)
            seen.add(mid)
    except Exception as exc:  # noqa: BLE001
        log.warning("plugin_models_merge_skip err=%s", exc)

    from aos_api.gateway_default import get_gateway_default

    gd = get_gateway_default()
    default_text = gd.get("defaultModel") or providers.get("defaultTextModel")
    if not default_text:
        default_text = next((i["id"] for i in items if i.get("kind") == "text"), None)
    return {
        "items": items,
        "defaultTextModel": default_text,
        "sidecar": warm.get("sidecar"),
        "apiKeyRef": warm.get("apiKeyRef"),
        "gatewayKind": providers.get("gatewayKind"),
        "pluginId": providers.get("pluginId"),
    }
