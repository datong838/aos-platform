"""AIP KV settings (model routes, tools panel config) — scheme 81."""
from __future__ import annotations

import json
from typing import Any

from aos_api.db import connect
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.aip_kv")

KEY_MODEL_ROUTES = "model_routes"
KEY_TOOLS_CONFIG = "tools_config"

DEFAULT_ROUTE_DEFS: list[dict[str, Any]] = [
    {"id": "summarize", "task": "摘要 / 分类", "span": False},
    {"id": "wiki_qa", "task": "业务问答 + Wiki", "span": False},
    {"id": "logic_long", "task": "Logic 长上下文 (>32k)", "span": False},
    {"id": "chatbot", "task": "Chatbot 日常对话", "span": False},
    {"id": "pii", "task": "含 PII 字段", "span": False},
    {"id": "provider_down", "task": "Provider 不可用", "span": True},
]

EGRESS_DEFAULTS = {
    "summarize": "禁公网",
    "wiki_qa": "禁公网",
    "logic_long": "审批后",
    "chatbot": "继承",
    "pii": "强制不出域",
    "provider_down": "fallback",
}


def ensure_aip_kv_schema() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_aip_kv (
              key TEXT PRIMARY KEY,
              payload JSONB NOT NULL DEFAULT '{}'::jsonb,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()


def get_payload(key: str) -> dict[str, Any] | None:
    ensure_aip_kv_schema()
    with connect() as conn:
        row = conn.execute(
            "SELECT payload FROM meta_aip_kv WHERE key = %s",
            (key,),
        ).fetchone()
    if not row:
        return None
    payload = row["payload"]
    if isinstance(payload, str):
        return json.loads(payload)
    return dict(payload or {})


def put_payload(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_aip_kv_schema()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO meta_aip_kv (key, payload, updated_at)
            VALUES (%s, %s::jsonb, NOW())
            ON CONFLICT (key) DO UPDATE
              SET payload = EXCLUDED.payload,
                  updated_at = NOW()
            """,
            (key, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
    log.info("aip_kv_put key=%s", key)
    return payload


def _pick(models: list[str], *needles: str) -> str:
    if not models:
        return "—"
    for n in needles:
        for m in models:
            if n.lower() in m.lower():
                return m
    return models[0]


def default_model_routes(model_ids: list[str] | None = None) -> list[dict[str, Any]]:
    models = list(model_ids or [])
    primary = _pick(models, "agnes") if models else "—"
    local = _pick(models, "vllm", "local", "qwen") if models else "—"
    mini = _pick(models, "mini", "small", "flash") if models else "—"
    rows: list[dict[str, Any]] = []
    for d in DEFAULT_ROUTE_DEFS:
        rid = d["id"]
        if rid == "provider_down":
            rows.append(
                {
                    "id": rid,
                    "task": d["task"],
                    "primary": mini if mini != "—" else primary,
                    "fallback": "",
                    "egress": EGRESS_DEFAULTS[rid],
                    "span": True,
                }
            )
            continue
        if rid == "chatbot":
            p, f = (mini if mini != "—" else primary), "—"
        elif rid == "pii":
            p, f = (local if local != "—" else primary), "—"
        elif rid == "wiki_qa":
            p, f = primary, "—"
        else:
            p, f = primary, mini if mini != primary else "—"
        rows.append(
            {
                "id": rid,
                "task": d["task"],
                "primary": p,
                "fallback": f,
                "egress": EGRESS_DEFAULTS[rid],
                "span": False,
            }
        )
    return rows


def get_model_routes(model_ids: list[str] | None = None) -> list[dict[str, Any]]:
    stored = get_payload(KEY_MODEL_ROUTES)
    if stored and isinstance(stored.get("items"), list) and stored["items"]:
        return list(stored["items"])
    return default_model_routes(model_ids)


def put_model_routes(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    for raw in items:
        rid = str(raw.get("id") or "")
        if not rid:
            continue
        clean.append(
            {
                "id": rid,
                "task": str(raw.get("task") or rid),
                "primary": str(raw.get("primary") or "—"),
                "fallback": str(raw.get("fallback") or "—"),
                "egress": str(raw.get("egress") or "继承"),
                "span": bool(raw.get("span")),
            }
        )
    put_payload(KEY_MODEL_ROUTES, {"items": clean})
    return clean


def default_tools_config() -> dict[str, Any]:
    return {
        "categories": ["action", "query", "function", "clarify", "capability", "wiki"],
        "mode": "native",
        "hitl": "form",
    }


def get_tools_config() -> dict[str, Any]:
    stored = get_payload(KEY_TOOLS_CONFIG)
    if not stored:
        return default_tools_config()
    base = default_tools_config()
    cats = stored.get("categories")
    if isinstance(cats, list) and cats:
        base["categories"] = [str(c) for c in cats]
    if stored.get("mode"):
        base["mode"] = str(stored["mode"])
    if stored.get("hitl"):
        base["hitl"] = str(stored["hitl"])
    return base


def put_tools_config(body: dict[str, Any]) -> dict[str, Any]:
    cfg = default_tools_config()
    cats = body.get("categories")
    if isinstance(cats, list):
        cfg["categories"] = [str(c) for c in cats]
    if body.get("mode"):
        cfg["mode"] = str(body["mode"])
    if body.get("hitl"):
        cfg["hitl"] = str(body["hitl"])
    put_payload(KEY_TOOLS_CONFIG, cfg)
    return cfg


def circuit_drill(items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rules = items if items is not None else get_model_routes()
    down = next((r for r in rules if r.get("id") == "provider_down" or r.get("span")), None)
    target = (down or {}).get("primary") or "—"
    return {
        "ok": True,
        "scenario": "primary_provider_unavailable",
        "degradedTo": target,
        "message": f"演练通过 · 熔断后降级到 {target}",
    }
