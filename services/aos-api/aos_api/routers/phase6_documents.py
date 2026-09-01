"""Phase 6 · Documents 路由 (文档提取)."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
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


class ExtractionTemplateCreateRequest(BaseModel):
    name: str
    description: str = ""
    fields: list[dict[str, Any]] = Field(default_factory=list)
    doc_type: str = "custom"
    validation_rules: list[dict[str, Any]] = Field(default_factory=list)
    model_route: str = "deterministic_document_parser"
    estimated_cost_units: int = 0
    approval_gate: str = "manual_review"
    change_note: str = "首次创建"


class ExtractionTemplateUpdateRequest(BaseModel):
    expected_revision: int
    name: str | None = None
    description: str | None = None
    fields: list[dict[str, Any]] | None = None
    doc_type: str | None = None
    validation_rules: list[dict[str, Any]] | None = None
    model_route: str | None = None
    estimated_cost_units: int | None = None
    approval_gate: str | None = None
    active: bool | None = None
    change_note: str | None = None


class ExtractionTemplateRollbackRequest(BaseModel):
    expected_revision: int
    target_revision: int


@router.get("/documents")
async def list_documents(
    search: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    eng = get_engine()
    items, total = eng.list_documents(
        search=search,
        status=status,
        page=page,
        page_size=page_size,
        org_id=principal.org_id,
        project_id=principal.project_id,
    )
    return {"items": [d.model_dump() for d in items], "total": total, "page": page, "page_size": page_size}


@router.get("/documents/stats")
async def document_stats(principal: Principal = Depends(require_principal)) -> dict[str, Any]:
    return get_engine().document_stats(principal.org_id, principal.project_id)


@router.post("/documents/upload")
async def upload_document(
    request: Request,
    name: str = Query(..., min_length=1),
    source_label: str = Query("manual_upload", min_length=1, max_length=120),
    document_kind: str = Query("business_document", min_length=1, max_length=80),
    sensitivity: Literal["public", "internal", "restricted"] = Query("internal"),
    retention_policy: Literal["project_default", "30_days", "180_days", "permanent"] = Query("project_default"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    """接收原始请求体字节；不接受只有文件名的伪上传。"""
    data = await request.body()
    try:
        d = get_engine().upload_document(
            name=name,
            data=data,
            content_type=request.headers.get("content-type", "application/octet-stream"),
            org_id=principal.org_id,
            project_id=principal.project_id,
            source_label=source_label,
            document_kind=document_kind,
            sensitivity=sensitivity,
            retention_policy=retention_policy,
        )
        return d.model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.put("/documents/{document_id}")
async def update_document(
    document_id: str,
    req: UpdateDocumentRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    try:
        d = get_engine().update_document(
            document_id,
            ocr_text=req.ocr_text,
            extracted_fields=req.extracted_fields,
            org_id=principal.org_id,
            project_id=principal.project_id,
        )
        return d.model_dump()
    except KeyError:
        raise HTTPException(404, f"Document {document_id} not found")


@router.post("/documents/{document_id}/extract")
async def extract_document(
    document_id: str,
    req: ExtractRequest | None = None,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    eng = get_engine()
    try:
        if req and req.template_id:
            d = eng.process_document(document_id, req.template_id, principal.org_id, principal.project_id)
        else:
            fields = req.fields if req else None
            d = eng.extract_document(document_id, fields, principal.org_id, principal.project_id)
        return d.model_dump()
    except KeyError:
        raise HTTPException(404, f"Document {document_id} not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    req: ExtractRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    try:
        d = get_engine().process_document(
            document_id,
            req.template_id or "finance_report",
            principal.org_id,
            principal.project_id,
        )
        return d.model_dump()
    except KeyError:
        raise HTTPException(404, f"Document {document_id} not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.post("/documents/{document_id}/review")
async def review_document(
    document_id: str,
    req: ReviewRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    try:
        return get_engine().review_document(
            document_id, req.action, principal.org_id, principal.project_id, principal.subject,
        ).model_dump()
    except KeyError:
        raise HTTPException(404, f"Document {document_id} not found")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/documents/{document_id}/ontology-write")
async def write_document_to_ontology(
    document_id: str,
    req: OntologyWriteRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    try:
        document, obj = get_engine().write_document_to_ontology(
            document_id,
            req.object_type_id,
            principal.org_id,
            principal.project_id,
            principal.subject,
        )
        return {"document": document.model_dump(), "object": obj.model_dump()}
    except KeyError:
        raise HTTPException(404, f"Document {document_id} not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if not get_engine().delete_document(document_id, principal.org_id, principal.project_id):
        raise HTTPException(404, f"Document {document_id} not found")
    return {"deleted": True, "document_id": document_id}


@router.post("/documents/import")
async def import_document(
    req: ImportDocumentRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    eng = get_engine()
    d = eng.import_document(
        **req.model_dump(),
        org_id=principal.org_id,
        project_id=principal.project_id,
        source_label="registered_source",
    )
    return d.model_dump()


@router.get("/extraction-templates")
async def list_extraction_templates(
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_templates(principal.org_id, principal.project_id)
    return {"items": [t.model_dump() for t in items], "count": len(items)}


@router.post("/extraction-templates")
async def create_extraction_template(
    req: ExtractionTemplateCreateRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    template = get_engine().create_template(
        **req.model_dump(), org_id=principal.org_id, project_id=principal.project_id,
    )
    return template.model_dump()


@router.put("/extraction-templates/{template_id}")
async def update_extraction_template(
    template_id: str,
    req: ExtractionTemplateUpdateRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    payload = req.model_dump(exclude={"expected_revision"}, exclude_none=True)
    try:
        template = get_engine().update_template(
            template_id, req.expected_revision, principal.org_id, principal.project_id, **payload,
        )
        return template.model_dump()
    except KeyError:
        raise HTTPException(404, f"ExtractionTemplate {template_id} not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.get("/extraction-templates/{template_id}/versions")
async def list_extraction_template_versions(
    template_id: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    try:
        items = get_engine().list_template_versions(
            template_id, principal.org_id, principal.project_id,
        )
        return {"items": [item.model_dump() for item in items], "count": len(items)}
    except KeyError:
        raise HTTPException(404, f"ExtractionTemplate {template_id} not found")


@router.post("/extraction-templates/{template_id}/rollback")
async def rollback_extraction_template(
    template_id: str,
    req: ExtractionTemplateRollbackRequest,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    try:
        template = get_engine().rollback_template(
            template_id,
            req.target_revision,
            req.expected_revision,
            principal.org_id,
            principal.project_id,
        )
        return template.model_dump()
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.get("/projects")
async def list_projects() -> dict[str, Any]:
    eng = get_engine()
    items = eng.list_projects()
    return {"items": [p.model_dump() for p in items], "count": len(items)}
