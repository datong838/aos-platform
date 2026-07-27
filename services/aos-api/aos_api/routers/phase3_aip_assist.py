"""Phase 3 · AIP Assist 路由.

GET  /v1/aip/assist/welcome        — 欢迎语 + 权限标签
GET  /v1/aip/assist/suggestions     — 建议问题列表
GET  /v1/aip/assist/conversations   — 对话历史
POST /v1/aip/assist/chat            — SSE 流式对话
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from aos_api.aip_assist_engine import get_engine

router = APIRouter(prefix="/v1/aip", tags=["aip-assist"])


class ChatRequest(BaseModel):
    message: str = ""
    conversation_id: str | None = None
    role: str = "viewer"


@router.get("/assist/welcome")
async def get_welcome(role: str = Query("viewer")) -> dict[str, Any]:
    eng = get_engine()
    return eng.get_welcome(role=role)


@router.get("/assist/suggestions")
async def list_suggestions(category: str | None = Query(None)) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_suggestions(category=category)
    return {"items": items, "count": len(items)}


@router.get("/assist/conversations")
async def list_conversations(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    eng = get_engine()
    convs = eng.list_conversations(limit=limit)
    return {
        "items": [
            {
                "id": c.id,
                "title": c.title,
                "message_count": len(c.messages),
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
            for c in convs
        ],
        "count": len(convs),
    }


@router.post("/assist/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    eng = get_engine()
    # 获取或创建 conversation
    conv_id = req.conversation_id
    if conv_id:
        conv = eng.get_conversation(conv_id)
        if conv is None:
            raise HTTPException(404, f"Conversation {conv_id} not found")
    else:
        conv = eng.create_conversation(title=req.message[:30] if req.message else "New Chat")
        conv_id = conv.id

    # 记录用户消息
    eng.add_message(conv_id, "user", req.message)

    # 生成回复 tokens
    tokens = eng.generate_reply_tokens(req.message)

    async def stream():
        # 1. start
        yield f"data: {json.dumps({'type': 'start', 'conversation_id': conv_id})}\n\n"
        await asyncio.sleep(0.02)
        # 2. tokens
        full_reply = ""
        for chunk in tokens:
            full_reply += chunk
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
            await asyncio.sleep(0.05)
        # 3. 记录 assistant 消息
        eng.add_message(conv_id, "assistant", full_reply)
        # 4. suggestions
        sugs = eng.list_suggestions()[:3]
        yield f"data: {json.dumps({'type': 'suggestions', 'items': sugs})}\n\n"
        # 5. done
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
