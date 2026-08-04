"""Phase 6 · Documents 路由 (文档提取)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.phase6_datasource_engine import get_engine

router = APIRouter(
    prefix="/api/datasource",
    tags=["phase6-documents"],
    dependencies=[Depends(require_principal)],
)


class ExtractRequest(BaseModel):
    fields: list[str] | None = None
    template_id: str | None = None


class UpdateDocumentRequest(BaseModel):
    ocr_text: str | None = None
    extracted_fields: list[dict[str, Any]] | None = None


class ReviewRequest(BaseModel):
    action: str


class OntologyWriteRequest(BaseModel):
    object_type_id: str


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


@router.get("/documents/stats")
async def document_stats() -> dict[str, Any]:
    return get_engine().document_stats()


@router.post("/documents/upload")
async def upload_document(
    request: Request,
    name: str = Query(..., min_length=1),
) -> dict[str, Any]:
    """接收原始请求体字节；不接受只有文件名的伪上传。"""
    data = await request.body()
    try:
        d = get_engine().upload_document(
            name=name,
            data=data,
            content_type=request.headers.get("content-type", "application/octet-stream"),
        )
        return d.model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.put("/documents/{document_id}")
async def update_document(document_id: str, req: UpdateDocumentRequest) -> dict[str, Any]:
    try:
        d = get_engine().update_document(
            document_id,
            ocr_text=req.ocr_text,
            extracted_fields=req.extracted_fields,
        )
        return d.model_dump()
    except KeyError:
        raise HTTPException(404, f"Document {document_id} not found")


@router.post("/documents/{document_id}/extract")
async def extract_document(document_id: str, req: ExtractRequest | None = None) -> dict[str, Any]:
    eng = get_engine()
    try:
        if req and req.template_id:
            d = eng.process_document(document_id, req.template_id)
        else:
            fields = req.fields if req else None
            d = eng.extract_document(document_id, fields)
        return d.model_dump()
    except KeyError:
        raise HTTPException(404, f"Document {document_id} not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(document_id: str, req: ExtractRequest) -> dict[str, Any]:
    try:
        d = get_engine().process_document(document_id, req.template_id or "finance_report")
        return d.model_dump()
    except KeyError:
        raise HTTPException(404, f"Document {document_id} not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.post("/documents/{document_id}/review")
async def review_document(document_id: str, req: ReviewRequest) -> dict[str, Any]:
    try:
        return get_engine().review_document(document_id, req.action).model_dump()
    except KeyError:
        raise HTTPException(404, f"Document {document_id} not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/documents/{document_id}/ontology-write")
async def write_document_to_ontology(document_id: str, req: OntologyWriteRequest) -> dict[str, Any]:
    try:
        document, obj = get_engine().write_document_to_ontology(document_id, req.object_type_id)
        return {"document": document.model_dump(), "object": obj.model_dump()}
    except KeyError:
        raise HTTPException(404, f"Document {document_id} not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str) -> dict[str, Any]:
    if not get_engine().delete_document(document_id):
        raise HTTPException(404, f"Document {document_id} not found")
    return {"deleted": True, "document_id": document_id}


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
