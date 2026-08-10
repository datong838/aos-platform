"""AIP 三层运行记忆管理 — FastAPI 路由。

遵循 06-228-AIP方案 §1 冻结口径：三层运行记忆 (Working / Episodic / Semantic)。
Procedural 不作为运行记忆层；Shared 是受治理投影，不是第四种存储。

保留原有 CRUD 端点（向后兼容），新增：
  - GET /api/aip/long-memory/meta/layers — 三层统计
  - GET /api/aip/long-memory/meta/by-layer/{layer} — 按层筛选
  - GET /api/aip/long-memory/meta/search?q=xxx — 关键词检索

注意：FastAPI 按注册顺序匹配路由。meta/* 路径必须在 /{item_id} 之前注册，
否则 "meta" 会被当作 item_id 参数。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .aip_long_memory import MemoryLayer, get_engine

router = APIRouter(prefix="/api/aip/long-memory", tags=["aip-long_memory"])
_engine = get_engine()


class CreateRequest(BaseModel):
    name: str
    config: dict = {}
    layer: str | None = None       # working / episodic / semantic
    content: str | None = None     # 记忆正文
    object_type: str | None = None # 关联本体对象
    tags: list[str] | None = None  # 标签


class UpdateRequest(BaseModel):
    name: str | None = None
    config: dict | None = None
    status: str | None = None
    layer: str | None = None
    content: str | None = None
    object_type: str | None = None
    tags: list[str] | None = None


# ── 元数据 / 分层端点（必须在 /{item_id} 之前注册）──


@router.get("/meta/layers")
def layer_stats():
    """返回三层运行记忆的统计信息。"""
    return _engine.layer_stats()


@router.get("/meta/by-layer/{layer}")
def list_by_layer(layer: str):
    """按记忆层筛选条目。"""
    try:
        MemoryLayer(layer)  # 校验
    except ValueError:
        raise HTTPException(400, f"无效的记忆层: {layer}")
    return [item.model_dump() for item in _engine.list_by_layer(layer)]


@router.get("/meta/search")
def search_items(q: str = Query(..., min_length=1), layer: str | None = Query(None)):
    """关键词检索记忆（可选限定层）。"""
    return [item.model_dump() for item in _engine.search(q, layer)]


# ── 原有 CRUD（向后兼容）──


@router.get("")
def list_items():
    return [item.model_dump() for item in _engine.list()]


@router.post("")
def create_item(req: CreateRequest):
    try:
        kwargs: dict = {}
        if req.layer:
            kwargs["layer"] = req.layer
        if req.content:
            kwargs["content"] = req.content
        if req.object_type:
            kwargs["object_type"] = req.object_type
        if req.tags:
            kwargs["tags"] = req.tags
        return _engine.create(req.name, req.config, **kwargs).model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/{item_id}")
def get_item(item_id: str):
    item = _engine.get(item_id)
    if item is None:
        raise HTTPException(404, f"不存在 {item_id}")
    return item.model_dump()


@router.put("/{item_id}")
def update_item(item_id: str, req: UpdateRequest):
    try:
        return _engine.update(item_id, **req.model_dump(exclude_none=True)).model_dump()
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/{item_id}")
def delete_item(item_id: str):
    if not _engine.delete(item_id):
        raise HTTPException(404, f"不存在 {item_id}")
    return {"deleted": True}
