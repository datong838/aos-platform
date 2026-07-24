"""Platform default gateway — scheme 85."""
from __future__ import annotations

from typing import Any

from aos_api.aip_kv_store import get_payload, put_payload
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.gateway_default")

KEY = "gateway_default"


def _env_fallback_kind() -> dict[str, Any]:
    from aos_api.llm_gateway import agnes_configured, agnes_text_model, litellm_model, litellm_url

    if agnes_configured():
        return {
            "kind": "agnes",
            "pluginId": None,
            "defaultModel": agnes_text_model(),
            "source": "env-fallback",
        }
    if litellm_url():
        return {
            "kind": "litellm",
            "pluginId": None,
            "defaultModel": litellm_model(),
            "source": "env-fallback",
        }
    return {
        "kind": "mock",
        "pluginId": None,
        "defaultModel": "mock-llm",
        "source": "env-fallback",
    }


def get_gateway_default() -> dict[str, Any]:
    stored = get_payload(KEY) or {}
    kind = str(stored.get("kind") or "").strip()
    if not kind:
        return _env_fallback_kind()
    plugin_id = stored.get("pluginId")
    default_model = stored.get("defaultModel")
    out = {
        "kind": kind,
        "pluginId": str(plugin_id) if plugin_id else None,
        "defaultModel": str(default_model) if default_model else None,
        "source": "stored",
    }
    if not out["defaultModel"]:
        out["defaultModel"] = _resolve_model_for(out)
    return out


def _resolve_model_for(gd: dict[str, Any]) -> str | None:
    from aos_api.llm_gateway import agnes_text_model, litellm_model
    from aos_api.llm_provider_registry import get_plugin_config, list_llm_provider_plugins

    kind = gd.get("kind")
    if kind == "agnes":
        return agnes_text_model() or None
    if kind == "litellm":
        return litellm_model() or None
    if kind == "plugin":
        pid = str(gd.get("pluginId") or "")
        cfg = get_plugin_config(pid)
        models = list(cfg.get("models") or [])
        if models:
            return str(models[0])
        for it in list_llm_provider_plugins().get("items") or []:
            if it.get("id") == pid:
                dm = list(it.get("defaultModels") or it.get("enabledModels") or [])
                return str(dm[0]) if dm else pid
        return pid or None
    return "mock-llm"


def put_gateway_default(body: dict[str, Any]) -> dict[str, Any]:
    from aos_api.errors import ApiError
    from aos_api.llm_gateway import agnes_configured, litellm_url
    from aos_api.llm_provider_registry import list_llm_provider_plugins

    kind = str(body.get("kind") or "").strip()
    plugin_id = str(body.get("pluginId") or "").strip() or None
    default_model = str(body.get("defaultModel") or "").strip() or None

    if kind not in {"agnes", "plugin", "litellm", "mock"}:
        raise ApiError(code="VALIDATION", message="kind must be agnes|plugin|litellm|mock", status_code=400)
    if kind == "agnes" and not agnes_configured():
        raise ApiError(code="VALIDATION", message="Agnes 未配置（AGNES_*）", status_code=400)
    if kind == "litellm" and not litellm_url():
        raise ApiError(code="VALIDATION", message="LiteLLM 未配置（AOS_LITELLM_URL）", status_code=400)
    if kind == "plugin":
        if not plugin_id:
            raise ApiError(code="VALIDATION", message="plugin kind requires pluginId", status_code=400)
        plug = next(
            (i for i in list_llm_provider_plugins().get("items") or [] if i.get("id") == plugin_id),
            None,
        )
        if not plug:
            raise ApiError(code="NOT_FOUND", message=f"plugin not found: {plugin_id}", status_code=404)
        if not plug.get("ready"):
            raise ApiError(
                code="VALIDATION",
                message=f"插件 {plugin_id} 未就绪，请先「启用就绪」",
                status_code=400,
            )

    payload = {"kind": kind, "pluginId": plugin_id if kind == "plugin" else None, "defaultModel": default_model}
    if not payload["defaultModel"]:
        payload["defaultModel"] = _resolve_model_for(payload)
    put_payload(KEY, payload)
    log.info("gateway_default_put kind=%s pluginId=%s model=%s", kind, plugin_id, payload["defaultModel"])
    return {**payload, "source": "stored"}


def list_gateway_options() -> list[dict[str, Any]]:
    from aos_api.llm_gateway import agnes_configured, agnes_text_model, litellm_model, litellm_url
    from aos_api.llm_provider_registry import list_llm_provider_plugins

    opts: list[dict[str, Any]] = []
    if agnes_configured():
        opts.append(
            {
                "kind": "agnes",
                "pluginId": None,
                "label": f"Agnes（环境）· {agnes_text_model()}",
                "defaultModel": agnes_text_model(),
            }
        )
    for it in list_llm_provider_plugins().get("items") or []:
        if not it.get("ready"):
            continue
        pid = str(it["id"])
        models = list(it.get("enabledModels") or it.get("defaultModels") or [pid])
        opts.append(
            {
                "kind": "plugin",
                "pluginId": pid,
                "label": f"{it.get('nameZh') or it.get('name') or pid}（插件就绪）· {models[0]}",
                "defaultModel": str(models[0]),
            }
        )
    if litellm_url():
        opts.append(
            {
                "kind": "litellm",
                "pluginId": None,
                "label": f"LiteLLM 边车 · {litellm_model()}",
                "defaultModel": litellm_model(),
            }
        )
    return opts


def gateway_default_payload() -> dict[str, Any]:
    current = get_gateway_default()
    return {"current": current, "options": list_gateway_options()}
