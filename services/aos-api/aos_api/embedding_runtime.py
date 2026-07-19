"""Embedding / Rerank Host runtime — scheme 103 · 对齐 20 §3.1 / T07."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from aos_api.env_load import load_dotenv
from aos_api.errors import ApiError
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.embedding_runtime")

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def embed_base_url() -> str:
    return (_env("AOS_EMBED_BASE_URL") or _env("AGNES_BASE_URL")).rstrip("/")


def embed_api_key() -> str:
    return _env("AOS_EMBED_API_KEY") or _env("AGNES_API_KEY")


def embed_model(override: str | None = None) -> str:
    return (override or "").strip() or _env("AOS_EMBED_MODEL") or "text-embedding-3-small"


def embed_configured() -> bool:
    return bool(embed_base_url() and embed_api_key())


def assert_installed(plugin_id: str) -> str:
    from aos_api.embedding_registry import list_embedding_plugins

    pid = (plugin_id or "").strip()
    body = list_embedding_plugins()
    hit = next((i for i in body.get("items") or [] if i.get("id") == pid), None)
    if not hit:
        raise ApiError(code="UNKNOWN_EMBEDDING", message=f"unknown embedding plugin: {pid}", status_code=400)
    if not hit.get("installed"):
        raise ApiError(
            code="PLUGIN_NOT_INSTALLED",
            message=f"embedding plugin not installed: {pid}",
            status_code=400,
        )
    return pid


def _stub(plugin_id: str, op: str) -> None:
    raise ApiError(
        code="EMBEDDING_STUB",
        message=f"embedding plugin {plugin_id} has no live {op} (configure gateway or wait for provider)",
        status_code=501,
        details={"pluginId": plugin_id, "op": op},
    )


def _openai_embed_url(base: str) -> str:
    root = base.rstrip("/")
    if root.endswith("/v1"):
        return f"{root}/embeddings"
    return f"{root}/v1/embeddings"


def _call_openai_embeddings(*, texts: list[str], model: str) -> dict[str, Any]:
    base = embed_base_url()
    key = embed_api_key()
    if not base or not key:
        _stub("embed-openai-compatible", "embed")
    url = _openai_embed_url(base)
    payload = {"model": model, "input": texts}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ApiError(
            code="EMBEDDING_UPSTREAM",
            message=f"upstream embeddings HTTP {exc.code}",
            status_code=502,
            details={"status": exc.code, "body": detail},
        ) from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        raise ApiError(
            code="EMBEDDING_UPSTREAM",
            message=f"upstream embeddings failed: {exc}",
            status_code=502,
        ) from None

    rows = body.get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise ApiError(code="EMBEDDING_UPSTREAM", message="invalid embeddings response", status_code=502)
    ordered = sorted(rows, key=lambda r: int(r.get("index") or 0) if isinstance(r, dict) else 0)
    vectors: list[list[float]] = []
    for row in ordered:
        if not isinstance(row, dict):
            continue
        emb = row.get("embedding")
        if not isinstance(emb, list):
            raise ApiError(code="EMBEDDING_UPSTREAM", message="missing embedding vector", status_code=502)
        vectors.append([float(x) for x in emb])
    if len(vectors) != len(texts):
        raise ApiError(
            code="EMBEDDING_UPSTREAM",
            message=f"vector count {len(vectors)} != texts {len(texts)}",
            status_code=502,
        )
    return {
        "pluginId": "embed-openai-compatible",
        "model": body.get("model") or model,
        "sidecar": "openai-compatible",
        "vectors": vectors,
        "dimensions": len(vectors[0]) if vectors else 0,
    }


def _normalize_texts(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("texts")
    if raw is None and isinstance(payload.get("input"), list):
        raw = payload.get("input")
    if raw is None and isinstance(payload.get("text"), str):
        raw = [payload["text"]]
    if not isinstance(raw, list) or not raw:
        raise ApiError(code="VALIDATION", message="texts (non-empty list) required", status_code=400)
    out: list[str] = []
    for i, t in enumerate(raw):
        if not isinstance(t, str):
            raise ApiError(code="VALIDATION", message=f"texts[{i}] must be string", status_code=400)
        out.append(t)
    return out


def dispatch_embed(plugin_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    pid = assert_installed(plugin_id)
    body = payload or {}
    texts = _normalize_texts(body)
    model = embed_model(str(body.get("model") or "") or None)
    if pid == "embed-openai-compatible":
        if not embed_configured():
            _stub(pid, "embed")
        log.info("embedding_embed plugin=%s n=%s model=%s", pid, len(texts), model)
        return _call_openai_embeddings(texts=texts, model=model)
    _stub(pid, "embed")
    raise AssertionError("unreachable")  # pragma: no cover


def dispatch_rerank(plugin_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    pid = assert_installed(plugin_id)
    body = payload or {}
    query = str(body.get("query") or "").strip()
    docs = body.get("documents")
    if not query:
        raise ApiError(code="VALIDATION", message="query required", status_code=400)
    if not isinstance(docs, list) or not docs:
        raise ApiError(code="VALIDATION", message="documents (non-empty list) required", status_code=400)
    # Cohere / 其他 provider 未接 Key：诚实 501，不返回假分数
    _stub(pid, "rerank")
    raise AssertionError("unreachable")  # pragma: no cover


def embedding_health(plugin_id: str) -> dict[str, Any]:
    pid = assert_installed(plugin_id)
    if pid == "embed-openai-compatible":
        ok = embed_configured()
        return {
            "ok": ok,
            "pluginId": pid,
            "configured": ok,
            "mode": "openai-compatible" if ok else "stub",
            "model": embed_model() if ok else None,
            "capabilities": ["embed"],
        }
    if pid == "rerank-cohere":
        return {
            "ok": False,
            "pluginId": pid,
            "configured": False,
            "mode": "stub",
            "capabilities": ["rerank"],
        }
    return {"ok": False, "pluginId": pid, "mode": "stub"}
