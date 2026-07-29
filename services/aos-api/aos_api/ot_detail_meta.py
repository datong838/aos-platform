"""W3-C2 · Object Type 详情元数据派生（不改表结构）。"""
from __future__ import annotations

from typing import Any


def _prop_name(p: Any) -> str:
    if isinstance(p, dict):
        return str(p.get("name") or "").strip()
    return str(p or "").strip()


def _prop_names(properties: Any) -> list[str]:
    if not isinstance(properties, list):
        return []
    return [n for n in (_prop_name(p) for p in properties) if n]


def build_ot_detail_meta(
    *,
    type_id: str,
    name: str,
    description: str = "",
    published: bool = False,
    properties: Any = None,
    required_markings: Any = None,
    created_at: Any = None,
) -> dict[str, Any]:
    """从既有 OT 行派生视觉稿向齐的元数据字段。"""
    props = properties if isinstance(properties, list) else []
    names = _prop_names(props)
    primary_key = names[0] if names else "id"
    title_candidates = [n for n in names if n.lower() in ("title", "name", "display_name", "label")]
    title_key = title_candidates[0] if title_candidates else (names[1] if len(names) > 1 else primary_key)
    display = (name or type_id).strip() or type_id
    plural = f"{display}s" if display and not display.endswith("s") else (display or f"{type_id}s")
    markings = required_markings if isinstance(required_markings, list) else []
    visibility = ", ".join(str(m) for m in markings) if markings else "org"

    return {
        "id": type_id,
        "name": name,
        "description": description or "",
        "published": bool(published),
        "properties": props,
        "rid": f"ri.ontology.main.object-type.{type_id.lower()}",
        "apiName": type_id,
        "primaryKey": primary_key,
        "titleKey": title_key,
        "displayName": display,
        "pluralName": plural,
        "backingDataset": f"ds/{type_id.lower()}",
        "syncStrategy": "incremental",
        "storageType": "object_storage",
        "createdBy": "system",
        "createdAt": str(created_at) if created_at else None,
        "visibility": visibility,
        "requiredMarkings": markings,
    }
