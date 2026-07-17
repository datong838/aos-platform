"""LiteLLM-shaped sidecar — prefers Agnes (.env) then echo upstream."""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="aos-dev-litellm-sidecar", version="0.2.0")


def _load_env_file() -> None:
    for p in (
        Path(__file__).resolve().parents[2] / ".env",  # aos-platform/.env
        Path(__file__).resolve().parents[1] / ".env",
    ):
        if not p.is_file():
            continue
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
        break


_load_env_file()

MASTER = os.environ.get("LITELLM_MASTER_KEY", "aos_dev_litellm_master")
AGNES_KEY = os.environ.get("AGNES_API_KEY", "").strip()
AGNES_BASE = os.environ.get("AGNES_BASE_URL", "").rstrip("/")
AGNES_TEXT = os.environ.get("AGNES_TEXT_MODEL", "").strip()
UPSTREAM_BASE = os.environ.get(
    "AOS_LLM_UPSTREAM_BASE",
    AGNES_BASE if AGNES_BASE else "http://aos-dev-llm-echo:8081/v1",
)
UPSTREAM_KEY = os.environ.get(
    "AOS_LLM_UPSTREAM_KEY",
    AGNES_KEY if AGNES_KEY else "aos_dev_upstream_only",
)
MODEL_ALIAS = os.environ.get("AOS_LITELLM_MODEL") or AGNES_TEXT or "aos-dev"


class Message(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    model: str = MODEL_ALIAS
    messages: list[Message] = Field(default_factory=list)


def _check_auth(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer")
    token = authorization.removeprefix("Bearer ").strip()
    if token != MASTER:
        raise HTTPException(status_code=401, detail="invalid master key")


@app.get("/health")
@app.get("/health/liveliness")
def health():
    mode = "agnes" if AGNES_BASE and AGNES_KEY else "echo"
    return {
        "status": "ok",
        "sidecar": "litellm-lib",
        "upstream": UPSTREAM_BASE,
        "mode": mode,
        "model": MODEL_ALIAS,
    }


@app.get("/v1/models")
def models(authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    return {
        "data": [{"id": MODEL_ALIAS, "object": "model", "owned_by": "aos-dev"}],
    }


@app.post("/v1/chat/completions")
def chat_completions(
    body: ChatIn,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _check_auth(authorization)
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    model = body.model or MODEL_ALIAS
    import urllib.request

    root = UPSTREAM_BASE.rstrip("/")
    url = f"{root}/chat/completions" if root.endswith("/v1") else f"{root}/v1/chat/completions"
    payload = json.dumps({"model": model, "messages": messages}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {UPSTREAM_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        # last-resort local echo so Dev UI never hard-breaks
        last = messages[-1]["content"] if messages else ""
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"[sidecar-fallback] {last} ({exc})",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
