"""DICOM 医学影像 + Workshop 自动生成 + AIP Doc Intel 五步法路由."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.dicom_workshop_docintel import (
    DicomEngineError,
    DicomMetadata,
    DocIntelEngineError,
    DocIntelJob,
    WorkshopAutoGenEngineError,
    WorkshopTemplate,
    get_dicom_engine,
    get_doc_intel_engine,
    get_workshop_auto_gen_engine,
)

router = APIRouter(prefix="/dicom-workshop-docintel", tags=["dicom-workshop-docintel"])


# ════════════════════ Error Mapping ════════════════════

def _map_dicom_err(e: DicomEngineError) -> HTTPException:
    mapping = {
        "MEDIA_REF_NOT_FOUND": (400, "media_ref_id 不存在"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_workshop_err(e: WorkshopAutoGenEngineError) -> HTTPException:
    mapping = {
        "INVALID_OBJECT_TYPE": (400, "object_type 无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_docintel_err(e: DocIntelEngineError) -> HTTPException:
    mapping = {
        "MEDIA_REF_NOT_FOUND": (400, "media_ref_id 不存在"),
        "INVALID_STEP": (400, "步骤无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


# ════════════════════ DicomEngine Routes ════════════════════

class ExtractDicomBody(BaseModel):
    media_ref_id: str


@router.post("/dicom/metadata", response_model=DicomMetadata)
def extract_dicom_metadata(
    body: ExtractDicomBody,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_dicom_engine().extract_metadata(body.media_ref_id)
    except DicomEngineError as e:
        raise _map_dicom_err(e) from e


@router.get("/dicom/metadata", response_model=list[DicomMetadata])
def list_dicom_metadata(
    media_set_id: str | None = None,
    patient_id: str | None = None,
    study_id: str | None = None,
    principal: Principal = Depends(require_principal),
):
    return get_dicom_engine().list_metadata(
        media_set_id=media_set_id,
        patient_id=patient_id,
        study_id=study_id,
    )


@router.get("/dicom/metadata/{dicom_id}", response_model=DicomMetadata)
def get_dicom_metadata(
    dicom_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_dicom_engine().get_metadata(dicom_id)
    except DicomEngineError as e:
        raise _map_dicom_err(e) from e


@router.post("/dicom/metadata/{dicom_id}/render")
def render_dicom_image(
    dicom_id: str,
    window_center: str | None = None,
    window_width: str | None = None,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_dicom_engine().render_image(
            dicom_id, window_center, window_width)
    except DicomEngineError as e:
        raise _map_dicom_err(e) from e


@router.delete("/dicom/metadata/{dicom_id}")
def delete_dicom_metadata(
    dicom_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_dicom_engine().delete_metadata(dicom_id)
        return {"deleted": True}
    except DicomEngineError as e:
        raise _map_dicom_err(e) from e


# ════════════════════ WorkshopAutoGenEngine Routes ════════════════════

class GenerateWorkshopBody(BaseModel):
    object_type: str


@router.post("/workshop/templates", response_model=WorkshopTemplate)
def generate_workshop(
    body: GenerateWorkshopBody,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_workshop_auto_gen_engine().generate_workshop(body.object_type)
    except WorkshopAutoGenEngineError as e:
        raise _map_workshop_err(e) from e


@router.get("/workshop/templates", response_model=list[WorkshopTemplate])
def list_workshop_templates(
    object_type: str | None = None,
    principal: Principal = Depends(require_principal),
):
    return get_workshop_auto_gen_engine().list_templates(object_type=object_type)


@router.get("/workshop/templates/{template_id}", response_model=WorkshopTemplate)
def get_workshop_template(
    template_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_workshop_auto_gen_engine().get_template(template_id)
    except WorkshopAutoGenEngineError as e:
        raise _map_workshop_err(e) from e


@router.put("/workshop/templates/{template_id}", response_model=WorkshopTemplate)
def update_workshop_template(
    template_id: str,
    body: dict,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_workshop_auto_gen_engine().update_template(template_id, **body)
    except WorkshopAutoGenEngineError as e:
        raise _map_workshop_err(e) from e


@router.delete("/workshop/templates/{template_id}")
def delete_workshop_template(
    template_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        get_workshop_auto_gen_engine().delete_template(template_id)
        return {"deleted": True}
    except WorkshopAutoGenEngineError as e:
        raise _map_workshop_err(e) from e


@router.get("/workshop/templates/{template_id}/preview")
def preview_workshop_template(
    template_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_workshop_auto_gen_engine().preview_template(template_id)
    except WorkshopAutoGenEngineError as e:
        raise _map_workshop_err(e) from e


# ════════════════════ DocIntelEngine Routes ════════════════════

class CreateDocIntelJobBody(BaseModel):
    media_ref_id: str


@router.post("/docintel/jobs", response_model=DocIntelJob)
def create_doc_intel_job(
    body: CreateDocIntelJobBody,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_doc_intel_engine().create_job(body.media_ref_id)
    except DocIntelEngineError as e:
        raise _map_docintel_err(e) from e


@router.get("/docintel/jobs", response_model=list[DocIntelJob])
def list_doc_intel_jobs(
    media_ref_id: str | None = None,
    status: str | None = None,
    principal: Principal = Depends(require_principal),
):
    return get_doc_intel_engine().list_jobs(
        media_ref_id=media_ref_id,
        status=status,
    )


@router.get("/docintel/jobs/{job_id}", response_model=DocIntelJob)
def get_doc_intel_job(
    job_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_doc_intel_engine().get_job(job_id)
    except DocIntelEngineError as e:
        raise _map_docintel_err(e) from e


class RunStepBody(BaseModel):
    step: str


@router.post("/docintel/jobs/{job_id}/run-step", response_model=DocIntelJob)
def run_doc_intel_step(
    job_id: str,
    body: RunStepBody,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_doc_intel_engine().run_step(job_id, body.step)
    except DocIntelEngineError as e:
        raise _map_docintel_err(e) from e


@router.post("/docintel/jobs/{job_id}/run-all", response_model=DocIntelJob)
def run_all_doc_intel_steps(
    job_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_doc_intel_engine().run_all_steps(job_id)
    except DocIntelEngineError as e:
        raise _map_docintel_err(e) from e


@router.post("/docintel/jobs/{job_id}/cancel", response_model=DocIntelJob)
def cancel_doc_intel_job(
    job_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_doc_intel_engine().cancel_job(job_id)
    except DocIntelEngineError as e:
        raise _map_docintel_err(e) from e


@router.get("/docintel/jobs/{job_id}/extracted-fields")
def get_doc_intel_extracted_fields(
    job_id: str,
    principal: Principal = Depends(require_principal),
):
    try:
        return get_doc_intel_engine().get_extracted_fields(job_id)
    except DocIntelEngineError as e:
        raise _map_docintel_err(e) from e