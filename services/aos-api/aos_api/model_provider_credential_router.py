"""Model Provider Credential Router — 222plan Phase A.

供应商凭据管理 API 路由：
  - CRUD 凭据（加密存储）
  - 连接测试（向供应商 /v1/models 发 GET）
  - 轮换检查

对应 222 文档第 23 章 Tab 1 凭据管理。
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aos_api.logging_facade import get_logger
from aos_api.model_provider_credential import (
    ProviderCredential,
    get_credential_engine,
)

log = get_logger("aos-api.provider_credential_router")

router = APIRouter(prefix="/api/models/providers", tags=["model-provider-credentials"])

_engine = get_credential_engine()


# ── Request Models ────────────────────────────────────────────


class CreateCredentialRequest(BaseModel):
    api_key: str
    label: str = "默认"
    rotation_policy: str = "manual"  # manual / 30d / 90d


class UpdateCredentialRequest(BaseModel):
    api_key: str | None = None
    label: str | None = None
    rotation_policy: str | None = None


class TestConnectionRequest(BaseModel):
    base_url: str | None = None  # 可选，默认从插件配置获取


# ── Credential CRUD ───────────────────────────────────────────


@router.get("/{provider_id}/credentials")
def list_credentials(provider_id: str) -> list[dict[str, Any]]:
    """List all credentials for a provider (masked, no raw key)."""
    items = _engine.list_credentials(provider_id)
    return [_safe_dump(c) for c in items]


@router.post("/{provider_id}/credentials")
def create_credential(provider_id: str, req: CreateCredentialRequest) -> dict[str, Any]:
    """Create a new credential for a provider."""
    if not req.api_key.strip():
        raise HTTPException(400, "api_key 不能为空")
    cred = _engine.create_credential(
        provider_id=provider_id,
        api_key=req.api_key.strip(),
        label=req.label,
        rotation_policy=req.rotation_policy,
    )
    return _safe_dump(cred)


@router.put("/{provider_id}/credentials/{key_id}")
def update_credential(
    provider_id: str, key_id: str, req: UpdateCredentialRequest
) -> dict[str, Any]:
    """Update a credential (key rotation, label, policy)."""
    cred = _engine.update_credential(
        provider_id=provider_id,
        key_id=key_id,
        api_key=req.api_key,
        label=req.label,
        rotation_policy=req.rotation_policy,
    )
    if cred is None:
        raise HTTPException(404, f"凭据不存在 {key_id}")
    return _safe_dump(cred)


@router.delete("/{provider_id}/credentials/{key_id}")
def delete_credential(provider_id: str, key_id: str) -> dict[str, Any]:
    """Delete a credential."""
    if not _engine.delete_credential(provider_id, key_id):
        raise HTTPException(404, f"凭据不存在 {key_id}")
    return {"deleted": True, "key_id": key_id}


# ── Connection Test ───────────────────────────────────────────


@router.post("/{provider_id}/test-connection")
def test_connection(provider_id: str, req: TestConnectionRequest | None = None) -> dict[str, Any]:
    """Test connection to a provider by hitting its /v1/models endpoint.

    Tries to resolve base_url from:
    1. Request body
    2. llm_provider_registry plugin config
    3. Known provider defaults
    """
    from aos_api.llm_provider_registry import (
        find_plugin_for_model,
        plugin_base_url,
    )
    from aos_api.aip_kv_store import get_payload

    # 1. Resolve API key
    api_key = _engine.resolve_api_key(provider_id)
    if not api_key:
        # Try legacy secrets
        stored = get_payload("llm_provider_secrets") or {}
        by_id = (stored.get("byId") or {}) if isinstance(stored, dict) else {}
        api_key = str(by_id.get(provider_id, "")).strip()

    if not api_key:
        raise HTTPException(400, f"供应商 {provider_id} 没有可用的 API Key")

    # 2. Resolve base_url
    base_url = ""
    if req and req.base_url:
        base_url = req.base_url.rstrip("/")
    else:
        # Try plugin config
        configs = get_payload("llm_provider_configs") or {}
        cfg_by_id = (configs.get("byId") or {}) if isinstance(configs, dict) else {}
        cfg = cfg_by_id.get(provider_id, {})
        if isinstance(cfg, dict):
            base_url = str(cfg.get("baseUrl", "")).rstrip("/")

    if not base_url:
        # Known defaults
        defaults = {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "moonshot": "https://api.moonshot.cn/v1",
            "zhipu-glm": "https://open.bigmodel.cn/api/paas/v4",
            "qwen-dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        }
        base_url = defaults.get(provider_id, "")

    if not base_url:
        raise HTTPException(400, f"无法确定供应商 {provider_id} 的 base_url，请在请求体中指定")

    # 3. Send GET /v1/models
    url = f"{base_url}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    t0 = time.monotonic()
    try:
        resp = httpx.get(url, headers=headers, timeout=15.0)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        if resp.status_code == 200:
            body = {}
            try:
                body = resp.json()
            except Exception:
                pass
            model_count = 0
            if isinstance(body, dict):
                model_list = body.get("data") or body.get("models") or []
                if isinstance(model_list, list):
                    model_count = len(model_list)
            return {
                "ok": True,
                "status_code": resp.status_code,
                "latency_ms": elapsed_ms,
                "base_url": base_url,
                "model_count": model_count,
                "message": f"连接成功，发现 {model_count} 个模型",
            }
        else:
            return {
                "ok": False,
                "status_code": resp.status_code,
                "latency_ms": elapsed_ms,
                "base_url": base_url,
                "message": f"供应商返回 HTTP {resp.status_code}",
            }
    except httpx.TimeoutException:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {
            "ok": False,
            "status_code": 0,
            "latency_ms": elapsed_ms,
            "base_url": base_url,
            "message": "连接超时（15s）",
        }
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log.warning("test_connection_fail provider=%s err=%s", provider_id, exc)
        return {
            "ok": False,
            "status_code": 0,
            "latency_ms": elapsed_ms,
            "base_url": base_url,
            "message": f"连接失败：{exc}",
        }


# ── Helpers ───────────────────────────────────────────────────


def _safe_dump(c: ProviderCredential) -> dict[str, Any]:
    """Dump credential without exposing the encrypted key or raw key."""
    d = c.model_dump()
    # Don't return the encrypted_key to the client
    d.pop("encrypted_key", None)
    return d
