"""Phase 6 · Documents 路由 (文档提取)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.phase6_datasource_engine import get_engine

router = APIRouter(prefix="/api/datasource", tags=["phase6-documents"])


class ExtractRequest(BaseModel):
    fields: list[str] | None = None


class ImportDocumentRequest(BaseModel):
    name: str
    source_id: str = ""
    template_id: str = ""
    file_type: str = "pdf"
    status: str = "pending"


@router.get("/documents")
async def list_documents(
    search: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    eng = get_engine()
    items, total = eng.list_documents(search=search, status=status, page=page, page_size=page_size)
    return {"items": [d.model_dump() for d in items], "total": total, "page": page, "page_size": page_size}


@router.post("/documents/{document_id}/extract")
async def extract_document(document_id: str, req: ExtractRequest | None = None) -> dict[str, Any]:
    eng = get_engine()
    try:
        fields = req.fields if req else None
        d = eng.extract_document(document_id, fields)
        return d.model_dump()
    except KeyError:
        raise HTTPException(404, f"Document {document_id} not found")


@router.post("/documents/import")
async def import_document(req: ImportDocumentRequest) -> dict[str, Any]:
    eng = get_engine()
    d = eng.import_document(**req.model_dump())
    return d.model_dump()


@router.get("/extraction-templates")
async def list_extraction_templates() -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_templates()
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.get("/projects")
async def list_projects() -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_projects()
    return {"items": [p.model_dump() for p in items], "count": len(items)}
