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


def chat(query: str, *, with_tools: bool = False, tools: list[str] | None = None) -> dict[str, Any]:
    """Prefer Agnes (.env) → LiteLLM sidecar → mock fallback."""
    load_dotenv()
    tools_used = tools or ([] if not with_tools else ["query.objects"])
    tool_calls = [{"toolId": t, "ok": True} for t in tools_used]

    # 1) Agnes OpenAI-compatible (configured via .env)
    if agnes_configured():
        try:
            out = _openai_chat(
                base_url=agnes_base_url(),
                api_key=agnes_api_key(),
                model=agnes_text_model(),
                query=query,
            )
            log.info(
                "llm_chat via=agnes model=%s answer_len=%s",
                agnes_text_model(),
                len(out["answer"]),
            )
            return {
                "answer": out["answer"],
                "provider": agnes_text_model(),
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

    # 2) LiteLLM-shaped sidecar
    base = litellm_url()
    model = litellm_model()
    if base:
        try:
            out = _openai_chat(
                base_url=base,
                api_key=resolve_master_key(),
                model=model,
                query=query,
                timeout=30,
            )
            log.info("llm_chat via=litellm model=%s answer_len=%s", model, len(out["answer"]))
            return {
                "answer": out["answer"],
                "provider": model,
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

    if fallback_mode() == "off":
        raise RuntimeError("No LLM provider available (Agnes/.env or AOS_LITELLM_URL)")

    log.info("llm_chat via=fallback-mock query_len=%s", len(query))
    return {
        "answer": f"[mock-llm] {query}",
        "provider": "mock-llm",
        "warm": True,
        "route": "fallback-mock",
        "sidecar": "fallback-mock",
        "apiKeyRef": key_ref(),
        "toolCalls": tool_calls,
    }


def providers_payload() -> dict[str, Any]:
    load_dotenv()
    items: list[dict[str, Any]] = []
    if agnes_configured():
        items.append(
            {
                "id": agnes_text_model(),
                "name": "Agnes Text",
                "ready": True,
                "apiKeyRef": key_ref(),
                "kind": "text",
            }
        )
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
            "probe": {"ok": True, "sidecar": "agnes"},
        }

    probe = probe_sidecar()
    if probe.get("ok"):
        items = [
            {
                "id": litellm_model(),
                "name": "LiteLLM Dev Provider",
                "ready": True,
                "apiKeyRef": key_ref(),
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
            }
        ]
        sidecar = str(probe.get("sidecar") or "fallback-mock")
    return {
        "items": items,
        "sidecar": sidecar,
        "apiKeyRef": key_ref(),
        "probe": probe,
    }


def warmup_payload() -> dict[str, Any]:
    load_dotenv()
    if agnes_configured():
        models = [{"id": agnes_text_model(), "state": "ready"}]
        if agnes_image_model():
            models.append({"id": agnes_image_model(), "state": "ready"})
        return {
            "ready": True,
            "models": models,
            "sidecar": "agnes-openai-compatible",
            "apiKeyRef": key_ref(),
        }
    probe = probe_sidecar()
    ready = bool(probe.get("ok")) or fallback_mode() != "off"
    model_id = litellm_model() if probe.get("ok") else "mock-llm"
    return {
        "ready": ready,
        "models": [{"id": model_id, "state": "ready" if ready else "cold"}],
        "sidecar": "litellm" if probe.get("ok") else probe.get("sidecar"),
        "apiKeyRef": key_ref(),
    }


def models_payload() -> dict[str, Any]:
    """GET /v1/aip/models — routable model catalog (T-API)."""
    warm = warmup_payload()
    providers = providers_payload()
    by_id = {p["id"]: p for p in providers.get("items") or []}
    items = []
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
            }
        )
    return {
        "items": items,
        "defaultTextModel": next((i["id"] for i in items if i["kind"] == "text"), None),
        "sidecar": warm.get("sidecar"),
        "apiKeyRef": warm.get("apiKeyRef"),
    }
