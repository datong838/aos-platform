"""Minimal OpenAI-compatible chat echo — Dev Provider behind LiteLLM only."""
from __future__ import annotations

import time
import uuid

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="aos-dev-llm-echo", version="0.1.0")


class Message(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    model: str = "aos-echo"
    messages: list[Message] = Field(default_factory=list)


@app.get("/health")
def health():
    return {"status": "ok", "role": "dev-provider-echo"}


@app.post("/v1/chat/completions")
def chat_completions(body: ChatIn):
    last = body.messages[-1].content if body.messages else ""
    content = f"[litellm-dev-echo] {last}"
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
