"""DICOM 医学影像 + Workshop 自动生成 + AIP Doc Intel 五步法引擎."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

_MAX_DICOM_METADATA = 200
_MAX_WORKSHOP_TEMPLATES = 200
_MAX_DOC_INTEL_JOBS = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


# ════════════════════ DicomEngine ════════════════════

class DicomEngineError(Exception):
    """DICOM 引擎错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DicomMetadata(BaseModel):
    dicom_id: str = ""
    media_ref_id: str
    patient_id: str = ""
    patient_name: str = ""
    study_id: str = ""
    study_date: str = ""
    series_id: str = ""
    modality: str = ""
    manufacturer: str = ""
    image_count: int = 0
    pixel_spacing: str = ""
    slice_thickness: str = ""
    window_center: str = ""
    window_width: str = ""
    created_at: datetime | None = None


class DicomEngine:
    """DICOM 医学影像支持引擎."""

    _instance: DicomEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._metadata: dict[str, DicomMetadata] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> DicomEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def extract_metadata(self, media_ref_id: str) -> DicomMetadata:
        if not media_ref_id or not media_ref_id.strip():
            raise DicomEngineError("MEDIA_REF_NOT_FOUND", "media_ref_id is required")

        now = _utcnow()
        dicom_id = f"dic-{uuid.uuid4().hex[:8]}"

        stored = DicomMetadata(
            dicom_id=dicom_id,
            media_ref_id=media_ref_id,
            patient_id=f"PT-{uuid.uuid4().hex[:6]}",
            patient_name="Anonymous",
            study_id=f"ST-{uuid.uuid4().hex[:6]}",
            study_date=now.strftime("%Y%m%d"),
            series_id=f"SR-{uuid.uuid4().hex[:6]}",
            modality="CT",
            manufacturer="Siemens",
            image_count=100,
            pixel_spacing="0.500x0.500",
            slice_thickness="1.0",
            window_center="40",
            window_width="400",
            created_at=now,
        )

        with self._lock:
            if len(self._metadata) >= _MAX_DICOM_METADATA:
                oldest = min(self._metadata.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._metadata[oldest.dicom_id]
            self._metadata[dicom_id] = stored

        return stored

    def get_metadata(self, dicom_id: str) -> DicomMetadata:
        with self._lock:
            metadata = self._metadata.get(dicom_id)
        if metadata is None:
            raise DicomEngineError("NOT_FOUND", f"DICOM metadata {dicom_id} not found")
        return metadata

    def list_metadata(self, media_set_id: str | None = None,
                      patient_id: str | None = None,
                      study_id: str | None = None) -> list[DicomMetadata]:
        with self._lock:
            results = list(self._metadata.values())
        if patient_id:
            results = [m for m in results if m.patient_id == patient_id]
        if study_id:
            results = [m for m in results if m.study_id == study_id]
        return sorted(results, key=lambda m: m.created_at or datetime.min, reverse=True)

    def render_image(self, dicom_id: str,
                     window_center: str | None = None,
                     window_width: str | None = None) -> dict[str, Any]:
        with self._lock:
            metadata = self._metadata.get(dicom_id)
        if metadata is None:
            raise DicomEngineError("NOT_FOUND", f"DICOM metadata {dicom_id} not found")

        return {
            "dicom_id": dicom_id,
            "window_center": window_center or metadata.window_center,
            "window_width": window_width or metadata.window_width,
            "pixel_spacing": metadata.pixel_spacing,
            "slice_thickness": metadata.slice_thickness,
            "modality": metadata.modality,
        }

    def delete_metadata(self, dicom_id: str) -> None:
        with self._lock:
            if dicom_id not in self._metadata:
                raise DicomEngineError("NOT_FOUND", f"DICOM metadata {dicom_id} not found")
            del self._metadata[dicom_id]


_dicom_engine: DicomEngine | None = None
_dicom_engine_lock = threading.Lock()


def get_dicom_engine() -> DicomEngine:
    global _dicom_engine
    if _dicom_engine is None:
        with _dicom_engine_lock:
            if _dicom_engine is None:
                _dicom_engine = DicomEngine.get_instance()
    return _dicom_engine


# ════════════════════ WorkshopAutoGenEngine ════════════════════

class WorkshopAutoGenEngineError(Exception):
    """Workshop 自动生成引擎错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_VALID_OBJECT_TYPES = {"data_connection", "ontology", "pipeline", "workspace"}


class WorkshopTemplate(BaseModel):
    template_id: str = ""
    object_type: str
    name: str = ""
    description: str = ""
    table_columns: list[dict[str, Any]] = []
    preview_config: dict[str, Any] = {}
    generated_at: datetime | None = None
    updated_at: datetime | None = None


class WorkshopAutoGenEngine:
    """Workshop 自动生成引擎."""

    _instance: WorkshopAutoGenEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._templates: dict[str, WorkshopTemplate] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> WorkshopAutoGenEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def generate_workshop(self, object_type: str) -> WorkshopTemplate:
        if object_type not in _VALID_OBJECT_TYPES:
            raise WorkshopAutoGenEngineError(
                "INVALID_OBJECT_TYPE",
                f"object_type must be one of {_VALID_OBJECT_TYPES}")

        now = _utcnow()
        template_id = f"wst-{uuid.uuid4().hex[:8]}"

        default_columns = []
        if object_type == "data_connection":
            default_columns = [
                {"name": "connection_name", "type": "string"},
                {"name": "connector_type", "type": "string"},
                {"name": "host", "type": "string"},
                {"name": "port", "type": "numeric"},
                {"name": "status", "type": "string"},
            ]
        elif object_type == "ontology":
            default_columns = [
                {"name": "entity_name", "type": "string"},
                {"name": "description", "type": "string"},
                {"name": "property_count", "type": "numeric"},
                {"name": "status", "type": "string"},
            ]
        elif object_type == "pipeline":
            default_columns = [
                {"name": "pipeline_name", "type": "string"},
                {"name": "step_count", "type": "numeric"},
                {"name": "status", "type": "string"},
                {"name": "last_run", "type": "timestamp"},
            ]
        elif object_type == "workspace":
            default_columns = [
                {"name": "workspace_name", "type": "string"},
                {"name": "owner", "type": "string"},
                {"name": "member_count", "type": "numeric"},
                {"name": "created_at", "type": "timestamp"},
            ]

        stored = WorkshopTemplate(
            template_id=template_id,
            object_type=object_type,
            name=f"{object_type}_workshop_template",
            description=f"Auto-generated workshop template for {object_type}",
            table_columns=default_columns,
            preview_config={"rows": 5, "show_header": True},
            generated_at=now,
            updated_at=now,
        )

        with self._lock:
            if len(self._templates) >= _MAX_WORKSHOP_TEMPLATES:
                oldest = min(self._templates.values(),
                             key=lambda x: x.generated_at or datetime.min)
                del self._templates[oldest.template_id]
            self._templates[template_id] = stored

        return stored

    def get_template(self, template_id: str) -> WorkshopTemplate:
        with self._lock:
            template = self._templates.get(template_id)
        if template is None:
            raise WorkshopAutoGenEngineError(
                "NOT_FOUND", f"template {template_id} not found")
        return template

    def list_templates(self, object_type: str | None = None) -> list[WorkshopTemplate]:
        with self._lock:
            results = list(self._templates.values())
        if object_type:
            results = [t for t in results if t.object_type == object_type]
        return sorted(results, key=lambda t: t.generated_at or datetime.min, reverse=True)

    def update_template(self, template_id: str, **kwargs: Any) -> WorkshopTemplate:
        with self._lock:
            template = self._templates.get(template_id)
            if template is None:
                raise WorkshopAutoGenEngineError(
                    "NOT_FOUND", f"template {template_id} not found")

            data = template.model_dump()
            data.update(kwargs)
            data["updated_at"] = _utcnow()
            updated = WorkshopTemplate(**data)
            self._templates[template_id] = updated

        return updated

    def delete_template(self, template_id: str) -> None:
        with self._lock:
            if template_id not in self._templates:
                raise WorkshopAutoGenEngineError(
                    "NOT_FOUND", f"template {template_id} not found")
            del self._templates[template_id]

    def preview_template(self, template_id: str) -> dict[str, Any]:
        with self._lock:
            template = self._templates.get(template_id)
        if template is None:
            raise WorkshopAutoGenEngineError(
                "NOT_FOUND", f"template {template_id} not found")

        sample_rows = []
        for _ in range(template.preview_config.get("rows", 5)):
            row = {}
            for col in template.table_columns:
                col_type = col.get("type", "string")
                if col_type == "string":
                    row[col["name"]] = f"sample_{col['name']}_{uuid.uuid4().hex[:4]}"
                elif col_type == "numeric":
                    row[col["name"]] = 0
                elif col_type == "timestamp":
                    row[col["name"]] = _utcnow().isoformat()
                else:
                    row[col["name"]] = ""
            sample_rows.append(row)

        return {
            "template_id": template_id,
            "columns": template.table_columns,
            "preview_data": sample_rows,
            "config": template.preview_config,
        }


_workshop_auto_gen_engine: WorkshopAutoGenEngine | None = None
_workshop_auto_gen_engine_lock = threading.Lock()


def get_workshop_auto_gen_engine() -> WorkshopAutoGenEngine:
    global _workshop_auto_gen_engine
    if _workshop_auto_gen_engine is None:
        with _workshop_auto_gen_engine_lock:
            if _workshop_auto_gen_engine is None:
                _workshop_auto_gen_engine = WorkshopAutoGenEngine.get_instance()
    return _workshop_auto_gen_engine


# ════════════════════ DocIntelEngine ════════════════════

class DocIntelEngineError(Exception):
    """Doc Intel 引擎错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_VALID_STATUSES = {
    "pending", "ocr", "md_conversion", "field_extraction",
    "validation", "linking", "completed", "failed",
}
_VALID_STEPS = ["ocr", "md_conversion", "field_extraction", "validation", "linking"]


class DocIntelJob(BaseModel):
    job_id: str = ""
    media_ref_id: str
    status: str = "pending"
    current_step: str = ""
    ocr_result: dict[str, Any] = {}
    md_content: str = ""
    extracted_fields: dict[str, Any] = {}
    validation_result: dict[str, Any] = {}
    linked_entities: list[dict[str, Any]] = []
    error_message: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocIntelEngine:
    """AIP Doc Intel 五步法引擎."""

    _instance: DocIntelEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._jobs: dict[str, DocIntelJob] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> DocIntelEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create_job(self, media_ref_id: str) -> DocIntelJob:
        if not media_ref_id or not media_ref_id.strip():
            raise DocIntelEngineError("MEDIA_REF_NOT_FOUND", "media_ref_id is required")

        now = _utcnow()
        job_id = f"di-{uuid.uuid4().hex[:8]}"

        stored = DocIntelJob(
            job_id=job_id,
            media_ref_id=media_ref_id,
            status="pending",
            current_step="",
            ocr_result={},
            md_content="",
            extracted_fields={},
            validation_result={},
            linked_entities=[],
            error_message="",
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            if len(self._jobs) >= _MAX_DOC_INTEL_JOBS:
                oldest = min(self._jobs.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._jobs[oldest.job_id]
            self._jobs[job_id] = stored

        return stored

    def get_job(self, job_id: str) -> DocIntelJob:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise DocIntelEngineError("NOT_FOUND", f"job {job_id} not found")
        return job

    def list_jobs(self, media_ref_id: str | None = None,
                  status: str | None = None) -> list[DocIntelJob]:
        with self._lock:
            results = list(self._jobs.values())
        if media_ref_id:
            results = [j for j in results if j.media_ref_id == media_ref_id]
        if status:
            results = [j for j in results if j.status == status]
        return sorted(results, key=lambda j: j.created_at or datetime.min, reverse=True)

    def run_step(self, job_id: str, step: str) -> DocIntelJob:
        if step not in _VALID_STEPS:
            raise DocIntelEngineError(
                "INVALID_STEP", f"step must be one of {_VALID_STEPS}")

        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise DocIntelEngineError("NOT_FOUND", f"job {job_id} not found")
            if job.status in ("completed", "failed"):
                raise DocIntelEngineError(
                    "INVALID_STEP", f"job {job_id} already in terminal state")

            now = _utcnow()
            updates: dict[str, Any] = {
                "status": step,
                "current_step": step,
                "updated_at": now,
            }

            if step == "ocr":
                updates["ocr_result"] = {
                    "pages": 1,
                    "text": "Sample OCR text content",
                    "confidence": 0.95,
                }
            elif step == "md_conversion":
                updates["md_content"] = "# Document Title\n\nSample markdown content.\n"
            elif step == "field_extraction":
                updates["extracted_fields"] = {
                    "title": "Document Title",
                    "author": "Unknown",
                    "date": now.strftime("%Y-%m-%d"),
                }
            elif step == "validation":
                updates["validation_result"] = {
                    "valid": True,
                    "errors": [],
                    "warnings": [],
                }
            elif step == "linking":
                updates["linked_entities"] = [
                    {"entity_id": "ent-123", "type": "person", "name": "John Doe"},
                ]
                updates["status"] = "completed"

            updated = job.model_copy(update=updates)
            self._jobs[job_id] = updated

        return updated

    def run_all_steps(self, job_id: str) -> DocIntelJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise DocIntelEngineError("NOT_FOUND", f"job {job_id} not found")
            if job.status in ("completed", "failed"):
                raise DocIntelEngineError(
                    "INVALID_STEP", f"job {job_id} already in terminal state")

            now = _utcnow()
            updated = job.model_copy(update={
                "status": "completed",
                "current_step": "linking",
                "ocr_result": {
                    "pages": 1,
                    "text": "Sample OCR text content",
                    "confidence": 0.95,
                },
                "md_content": "# Document Title\n\nSample markdown content.\n",
                "extracted_fields": {
                    "title": "Document Title",
                    "author": "Unknown",
                    "date": now.strftime("%Y-%m-%d"),
                },
                "validation_result": {
                    "valid": True,
                    "errors": [],
                    "warnings": [],
                },
                "linked_entities": [
                    {"entity_id": "ent-123", "type": "person", "name": "John Doe"},
                ],
                "updated_at": now,
            })
            self._jobs[job_id] = updated

        return updated

    def cancel_job(self, job_id: str) -> DocIntelJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise DocIntelEngineError("NOT_FOUND", f"job {job_id} not found")
            if job.status == "completed":
                raise DocIntelEngineError(
                    "INVALID_STEP", f"job {job_id} already completed")

            updated = job.model_copy(update={
                "status": "failed",
                "error_message": "Job cancelled",
                "updated_at": _utcnow(),
            })
            self._jobs[job_id] = updated

        return updated

    def get_extracted_fields(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise DocIntelEngineError("NOT_FOUND", f"job {job_id} not found")
        return job.extracted_fields


_doc_intel_engine: DocIntelEngine | None = None
_doc_intel_engine_lock = threading.Lock()


def get_doc_intel_engine() -> DocIntelEngine:
    global _doc_intel_engine
    if _doc_intel_engine is None:
        with _doc_intel_engine_lock:
            if _doc_intel_engine is None:
                _doc_intel_engine = DocIntelEngine.get_instance()
    return _doc_intel_engine