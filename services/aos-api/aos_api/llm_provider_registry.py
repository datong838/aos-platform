"""LLM Provider plugin registry — scheme 83 · 对齐 20 §3.1."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from aos_api.aip_kv_store import get_payload, put_payload
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.llm_provider_registry")

KEY_INSTALLS = "llm_provider_installs"
KEY_CUSTOM = "llm_provider_custom"
KEY_READY = "llm_provider_ready"
KEY_CONFIGS = "llm_provider_configs"
KEY_SECRETS = "llm_provider_secrets"  # Dev 凭据槽：明文仅存 meta，不回显 API 列表

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


def plugins_root() -> Path:
    env = (os.environ.get("AOS_PLUGINS_ROOT") or "").strip()
    if env:
        return Path(env) / "llm-providers"
    return Path(__file__).resolve().parents[3] / "plugins" / "llm-providers"


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("manifest_read_fail path=%s err=%s", path, exc)
        return None
    if not isinstance(data, dict) or not data.get("id"):
        return None
    return data


def _scan_disk() -> list[dict[str, Any]]:
    root = plugins_root()
    if not root.is_dir():
        log.warning("llm_plugins_root_missing path=%s", root)
        return []
    items: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        man = _read_manifest(child / "manifest.json")
        if man:
            man = dict(man)
            man["source"] = "disk"
            items.append(man)
    return items


def _custom_items() -> list[dict[str, Any]]:
    stored = get_payload(KEY_CUSTOM) or {}
    raw = stored.get("items")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for it in raw:
        if isinstance(it, dict) and it.get("id"):
            row = dict(it)
            row["source"] = "custom"
            out.append(row)
    return out


def _installed_ids() -> set[str]:
    stored = get_payload(KEY_INSTALLS) or {}
    raw = stored.get("installed")
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw}


def _save_installed(ids: set[str]) -> list[str]:
    ordered = sorted(ids)
    put_payload(KEY_INSTALLS, {"installed": ordered})
    return ordered


def list_llm_provider_plugins() -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {}
    for man in _scan_disk() + _custom_items():
        by_id[str(man["id"])] = man
    installed = _installed_ids()
    ready = _ready_ids()
    cfgs = _configs()
    for auto in ("agnes-text", "agnes-image"):
        if auto in by_id:
            installed.add(auto)
            ready.add(auto)
    items: list[dict[str, Any]] = []
    for mid, man in sorted(by_id.items(), key=lambda x: x[0]):
        items.append(
            {
                "id": mid,
                "version": man.get("version") or "0.1.0",
                "name": man.get("name") or mid,
                "nameZh": man.get("nameZh") or man.get("name") or mid,
                "description": man.get("description") or "",
                "tier": man.get("tier") or "mid",
                "modalities": list(man.get("modalities") or ["text"]),
                "capabilities": list(man.get("capabilities") or ["llm"]),
                "formFamily": man.get("formFamily") or "openai_compatible",
                "defaultModels": list(man.get("defaultModels") or []),
                "litellmPrefix": man.get("litellmPrefix") or "",
                "author": man.get("author") or "aos",
                "configSchema": man.get("configSchema") or {},
                "source": man.get("source") or "disk",
                "installed": mid in installed,
                "ready": mid in ready,
                "config": dict(cfgs.get(mid) or {}),
                "enabledModels": list((cfgs.get(mid) or {}).get("models") or man.get("defaultModels") or []),
            }
        )
    return {
        "items": items,
        "totals": {
            "all": len(items),
            "installed": sum(1 for i in items if i["installed"]),
            "ready": sum(1 for i in items if i["ready"]),
            "catalog": sum(1 for i in items if not i["installed"]),
        },
        "pluginsRoot": str(plugins_root()),
    }


def install_plugin(plugin_id: str) -> dict[str, Any]:
    from aos_api.errors import ApiError

    catalog = {i["id"]: i for i in list_llm_provider_plugins()["items"]}
    if plugin_id not in catalog:
        raise ApiError(code="NOT_FOUND", message=f"plugin not found: {plugin_id}", status_code=404)
    ids = _installed_ids()
    ids.add(plugin_id)
    _save_installed(ids)
    log.info("llm_plugin_install id=%s", plugin_id)
    return {"id": plugin_id, "installed": True}


def uninstall_plugin(plugin_id: str) -> dict[str, Any]:
    ids = _installed_ids()
    ids.discard(plugin_id)
    _save_installed(ids)
    log.info("llm_plugin_uninstall id=%s", plugin_id)
    return {"id": plugin_id, "installed": False}


def publish_custom_plugin(body: dict[str, Any]) -> dict[str, Any]:
    from aos_api.errors import ApiError

    pid = str(body.get("id") or "").strip().lower()
    if not _ID_RE.match(pid):
        raise ApiError(
            code="VALIDATION",
            message="id must match ^[a-z][a-z0-9-]{1,63}$",
            status_code=400,
        )
    if pid in {m["id"] for m in _scan_disk()}:
        raise ApiError(
            code="CONFLICT",
            message="id collides with built-in plugin; choose another id",
            status_code=409,
        )
    modalities = body.get("modalities") or ["text"]
    if not isinstance(modalities, list) or not modalities:
        modalities = ["text"]
    man = {
        "id": pid,
        "version": str(body.get("version") or "0.1.0"),
        "name": str(body.get("name") or pid),
        "nameZh": str(body.get("nameZh") or body.get("name") or pid),
        "description": str(body.get("description") or ""),
        "tier": str(body.get("tier") or "mid"),
        "modalities": [str(x) for x in modalities],
        "capabilities": list(body.get("capabilities") or ["llm", "chat"]),
        "formFamily": str(body.get("formFamily") or "openai_compatible"),
        "defaultModels": list(body.get("defaultModels") or []),
        "litellmPrefix": str(body.get("litellmPrefix") or "openai/"),
        "author": str(body.get("author") or "custom"),
        "configSchema": body.get("configSchema")
        or {
            "type": "object",
            "properties": {
                "baseUrl": {"type": "string"},
                "apiKeyRef": {"type": "string"},
                "models": {"type": "array", "items": {"type": "string"}},
            },
        },
    }
    stored = get_payload(KEY_CUSTOM) or {"items": []}
    items = list(stored.get("items") or [])
    items = [it for it in items if not (isinstance(it, dict) and it.get("id") == pid)]
    items.append(man)
    put_payload(KEY_CUSTOM, {"items": items})
    ids = _installed_ids()
    ids.add(pid)
    _save_installed(ids)
    log.info("llm_plugin_publish id=%s", pid)
    return {"item": {**man, "source": "custom", "installed": True}}


def _ready_ids() -> set[str]:
    stored = get_payload(KEY_READY) or {}
    raw = stored.get("ready")
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw}


def _save_ready(ids: set[str]) -> list[str]:
    ordered = sorted(ids)
    put_payload(KEY_READY, {"ready": ordered})
    return ordered


def _configs() -> dict[str, dict[str, Any]]:
    stored = get_payload(KEY_CONFIGS) or {}
    raw = stored.get("byId")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            out[str(k)] = dict(v)
    return out


def _save_configs(by_id: dict[str, dict[str, Any]]) -> None:
    put_payload(KEY_CONFIGS, {"byId": by_id})


def get_plugin_config(plugin_id: str) -> dict[str, Any]:
    return dict(_configs().get(plugin_id) or {})


def put_plugin_config(plugin_id: str, body: dict[str, Any]) -> dict[str, Any]:
    from aos_api.errors import ApiError

    catalog = {i["id"]: i for i in list_llm_provider_plugins()["items"]}
    if plugin_id not in catalog:
        raise ApiError(code="NOT_FOUND", message=f"plugin not found: {plugin_id}", status_code=404)
    inst = _installed_ids()
    inst.add(plugin_id)
    _save_installed(inst)

    man = catalog[plugin_id]
    models = body.get("models")
    if not isinstance(models, list) or not models:
        models = list(man.get("defaultModels") or [])
        if not models:
            models = [plugin_id]
    models = [str(m) for m in models if str(m).strip()]
    cfg = {
        "displayName": str(body.get("displayName") or man.get("nameZh") or man.get("name") or plugin_id),
        "baseUrl": str(body.get("baseUrl") or ""),
        "secretRef": str(body.get("secretRef") or body.get("apiKeyRef") or ""),
        "models": models,
        "formFamily": man.get("formFamily") or "openai_compatible",
        "modalities": list(man.get("modalities") or ["text"]),
    }
    all_cfg = _configs()
    all_cfg[plugin_id] = cfg
    _save_configs(all_cfg)

    api_key = str(body.get("apiKey") or body.get("newSecret") or "").strip()
    if api_key:
        put_plugin_secret(plugin_id, api_key)

    make_ready = body.get("ready")
    if make_ready is None:
        make_ready = True
    ready = _ready_ids()
    if make_ready:
        ready.add(plugin_id)
    else:
        ready.discard(plugin_id)
    _save_ready(ready)
    log.info("llm_plugin_config id=%s ready=%s models=%s has_secret=%s", plugin_id, bool(make_ready), models, bool(api_key))
    return {
        "id": plugin_id,
        "installed": True,
        "ready": plugin_id in ready,
        "config": cfg,
        "hasSecret": has_plugin_secret(plugin_id),
    }


def enable_plugin(plugin_id: str) -> dict[str, Any]:
    return put_plugin_config(plugin_id, {"ready": True})


def disable_plugin(plugin_id: str) -> dict[str, Any]:
    ready = _ready_ids()
    ready.discard(plugin_id)
    _save_ready(ready)
    log.info("llm_plugin_disable id=%s", plugin_id)
    return {"id": plugin_id, "ready": False}


def routable_models_from_plugins() -> list[dict[str, Any]]:
    catalog = {i["id"]: i for i in list_llm_provider_plugins()["items"]}
    cfgs = _configs()
    items: list[dict[str, Any]] = []
    for pid in sorted(_ready_ids()):
        man = catalog.get(pid) or {}
        cfg = cfgs.get(pid) or {}
        models = list(cfg.get("models") or man.get("defaultModels") or [pid])
        mods = list(cfg.get("modalities") or man.get("modalities") or ["text"])
        kind = "text"
        if "text" not in mods and "image" in mods:
            kind = "image"
        elif "text" not in mods and "video" in mods:
            kind = "video"
        provider_name = str(cfg.get("displayName") or man.get("nameZh") or man.get("name") or pid)
        for mid in models:
            mid_s = str(mid).strip()
            if not mid_s:
                continue
            m_kind = "image" if "image" in mid_s.lower() else kind
            items.append(
                {
                    "id": mid_s,
                    "state": "ready",
                    "kind": m_kind,
                    "ready": True,
                    "provider": provider_name,
                    "pluginId": pid,
                    "source": "plugin",
                }
            )
    return items


def put_plugin_secret(plugin_id: str, api_key: str) -> None:
    stored = get_payload(KEY_SECRETS) or {"byId": {}}
    by_id = dict(stored.get("byId") or {})
    by_id[plugin_id] = api_key
    put_payload(KEY_SECRETS, {"byId": by_id})
    log.info("llm_plugin_secret_put id=%s", plugin_id)


def has_plugin_secret(plugin_id: str) -> bool:
    stored = get_payload(KEY_SECRETS) or {}
    by_id = stored.get("byId") or {}
    return bool(isinstance(by_id, dict) and by_id.get(plugin_id))


def resolve_plugin_api_key(plugin_id: str, secret_ref: str = "") -> str:
    """Resolve API key: Dev secrets 槽 → 环境变量。非 agnes 插件不得回落到 Agnes Key。"""
    from aos_api.env_load import load_dotenv

    load_dotenv()
    stored = get_payload(KEY_SECRETS) or {}
    by_id = stored.get("byId") or {}
    if isinstance(by_id, dict):
        got = str(by_id.get(plugin_id) or "").strip()
        if got:
            return got

    pid_env = plugin_id.upper().replace("-", "_")
    candidates = [
        f"AOS_LLM_KEY_{pid_env}",
        f"{pid_env}_API_KEY",
        f"AOS_{pid_env}_API_KEY",
    ]
    if plugin_id == "deepseek":
        candidates = ["AOS_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY", *candidates]
    if secret_ref and "#" in secret_ref:
        slot = secret_ref.rsplit("#", 1)[-1].strip()
        if slot and slot.lower() not in {"agnes", "default"}:
            candidates.insert(0, f"AOS_LLM_KEY_{slot.upper()}")
            candidates.insert(0, f"{slot.upper()}_API_KEY")

    for name in candidates:
        val = (os.environ.get(name) or "").strip()
        if val:
            return val

    if plugin_id.startswith("agnes"):
        from aos_api.llm_gateway import agnes_api_key

        return agnes_api_key()
    return ""


def find_plugin_for_model(model_id: str) -> dict[str, Any] | None:
    mid = str(model_id or "").strip()
    if not mid:
        return None
    for row in routable_models_from_plugins():
        if row.get("id") == mid:
            pid = str(row.get("pluginId") or "")
            man = next((i for i in list_llm_provider_plugins()["items"] if i["id"] == pid), None)
            cfg = get_plugin_config(pid)
            return {"pluginId": pid, "manifest": man or {}, "config": cfg, "model": mid}
    return None


def plugin_base_url(plugin_id: str, cfg: dict[str, Any] | None = None, man: dict[str, Any] | None = None) -> str:
    cfg = cfg or get_plugin_config(plugin_id)
    if cfg.get("baseUrl"):
        return str(cfg["baseUrl"]).rstrip("/")
    man = man or {}
    schema = man.get("configSchema") or {}
    props = schema.get("properties") if isinstance(schema, dict) else {}
    base_prop = (props or {}).get("baseUrl") if isinstance(props, dict) else {}
    if isinstance(base_prop, dict) and base_prop.get("default"):
        return str(base_prop["default"]).rstrip("/")
    if plugin_id == "deepseek":
        return "https://api.deepseek.com/v1"
    return ""
