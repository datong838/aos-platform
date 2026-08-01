"""Phase 4 · Ontology Wikis 路由 (wikis + versions + diff)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.ontology_wiki_engine import get_wiki_engine

router = APIRouter(prefix="/v1/ontology", tags=["ontology-wikis"])


class UpdateWikiRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    author: str | None = None
    widgets: list[dict[str, Any]] | None = None
    variables: dict[str, Any] | None = None
    expected_version: int | None = None
    message: str = ""


@router.get("/wikis")
async def list_wikis(
    search: str | None = Query(None),
    tag: str | None = Query(None),
) -> dict[str, Any]:
    eng = get_wiki_engine()
    items = eng.list_wikis(search=search, tag=tag)
    return {"items": [w.model_dump() for w in items], "count": len(items)}


@router.get("/wikis/{wiki_id}")
async def get_wiki(wiki_id: str) -> dict[str, Any]:
    eng = get_wiki_engine()
    w = eng.get_wiki(wiki_id)
    if w is None:
        raise HTTPException(404, f"Wiki {wiki_id} not found")
    return w.model_dump()


@router.put("/wikis/{wiki_id}")
async def update_wiki(wiki_id: str, req: UpdateWikiRequest) -> dict[str, Any]:
    eng = get_wiki_engine()
    try:
        data = {k: v for k, v in req.model_dump().items() if v is not None}
        expected_version = data.pop("expected_version", None)
        w = eng.update_wiki(wiki_id, expected_version=expected_version, **data)
        return w.model_dump()
    except KeyError:
        raise HTTPException(404, f"Wiki {wiki_id} not found")
    except ValueError:
        raise HTTPException(409, f"Wiki {wiki_id} version conflict")


@router.get("/wikis/{wiki_id}/versions")
async def list_versions(wiki_id: str) -> dict[str, Any]:
    eng = get_wiki_engine()
    if eng.get_wiki(wiki_id) is None:
        raise HTTPException(404, f"Wiki {wiki_id} not found")
    items = eng.list_versions(wiki_id)
    return {"items": [v.model_dump() for v in items], "count": len(items)}


@router.get("/wikis/{wiki_id}/diff")
async def diff_wiki(
    wiki_id: str,
    from_version: int = Query(...),
    to_version: int = Query(...),
) -> dict[str, Any]:
    eng = get_wiki_engine()
    try:
        return eng.diff(wiki_id, from_version, to_version)
    except KeyError:
        raise HTTPException(404, f"Wiki or version not found for {wiki_id}")
