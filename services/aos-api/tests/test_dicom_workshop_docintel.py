"""DICOM 医学影像 + Workshop 自动生成 + AIP Doc Intel 三引擎测试."""
from __future__ import annotations

import pytest

from aos_api.dicom_workshop_docintel import (
    DicomEngine,
    DicomEngineError,
    DicomMetadata,
    DocIntelEngine,
    DocIntelEngineError,
    DocIntelJob,
    WorkshopAutoGenEngine,
    WorkshopAutoGenEngineError,
    WorkshopTemplate,
    _MAX_DICOM_METADATA,
    _MAX_DOC_INTEL_JOBS,
    _MAX_WORKSHOP_TEMPLATES,
    get_dicom_engine,
    get_doc_intel_engine,
    get_workshop_auto_gen_engine,
)


# ════════════════════════════════════════════════════════════════
# DicomEngine
# ════════════════════════════════════════════════════════════════


class TestDicomEngine:
    """DICOM 医学影像支持引擎测试."""

    def setup_method(self):
        self.eng = DicomEngine()
        self.eng._metadata = {}

    def test_singleton_instance(self):
        assert DicomEngine.get_instance() is DicomEngine.get_instance()

    def test_extract_metadata_success(self):
        result = self.eng.extract_metadata("media-123")
        assert result.dicom_id.startswith("dic-")
        assert result.media_ref_id == "media-123"
        assert result.patient_id.startswith("PT-")
        assert result.study_id.startswith("ST-")
        assert result.modality == "CT"
        assert result.created_at is not None

    def test_extract_metadata_not_found(self):
        with pytest.raises(DicomEngineError) as exc:
            self.eng.extract_metadata("")
        assert exc.value.code == "MEDIA_REF_NOT_FOUND"

    def test_get_metadata_success(self):
        metadata = self.eng.extract_metadata("media-123")
        got = self.eng.get_metadata(metadata.dicom_id)
        assert got.dicom_id == metadata.dicom_id
        assert got.media_ref_id == "media-123"

    def test_get_metadata_not_found(self):
        with pytest.raises(DicomEngineError) as exc:
            self.eng.get_metadata("dic-nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_list_metadata(self):
        self.eng.extract_metadata("media-1")
        self.eng.extract_metadata("media-2")
        results = self.eng.list_metadata()
        assert len(results) == 2

    def test_list_metadata_by_patient_id(self):
        m1 = self.eng.extract_metadata("media-1")
        m2 = self.eng.extract_metadata("media-2")
        results = self.eng.list_metadata(patient_id=m1.patient_id)
        assert len(results) == 1
        assert results[0].dicom_id == m1.dicom_id

    def test_list_metadata_by_study_id(self):
        m1 = self.eng.extract_metadata("media-1")
        m2 = self.eng.extract_metadata("media-2")
        results = self.eng.list_metadata(study_id=m1.study_id)
        assert len(results) == 1
        assert results[0].dicom_id == m1.dicom_id

    def test_render_image_success(self):
        metadata = self.eng.extract_metadata("media-123")
        result = self.eng.render_image(metadata.dicom_id)
        assert result["dicom_id"] == metadata.dicom_id
        assert result["window_center"] == metadata.window_center
        assert result["window_width"] == metadata.window_width
        assert result["modality"] == "CT"

    def test_render_image_not_found(self):
        with pytest.raises(DicomEngineError) as exc:
            self.eng.render_image("dic-nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_render_image_with_window_params(self):
        metadata = self.eng.extract_metadata("media-123")
        result = self.eng.render_image(metadata.dicom_id, window_center="50", window_width="500")
        assert result["window_center"] == "50"
        assert result["window_width"] == "500"

    def test_delete_metadata_success(self):
        metadata = self.eng.extract_metadata("media-123")
        self.eng.delete_metadata(metadata.dicom_id)
        with pytest.raises(DicomEngineError) as exc:
            self.eng.get_metadata(metadata.dicom_id)
        assert exc.value.code == "NOT_FOUND"

    def test_delete_metadata_not_found(self):
        with pytest.raises(DicomEngineError) as exc:
            self.eng.delete_metadata("dic-nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_fifo_eviction(self):
        for i in range(_MAX_DICOM_METADATA + 5):
            self.eng.extract_metadata(f"media-{i}")
        assert len(self.eng._metadata) == _MAX_DICOM_METADATA


# ════════════════════════════════════════════════════════════════
# WorkshopAutoGenEngine
# ════════════════════════════════════════════════════════════════


class TestWorkshopAutoGenEngine:
    """Workshop 自动生成引擎测试."""

    def setup_method(self):
        self.eng = WorkshopAutoGenEngine()
        self.eng._templates = {}

    def test_singleton_instance(self):
        assert WorkshopAutoGenEngine.get_instance() is WorkshopAutoGenEngine.get_instance()

    def test_generate_workshop_success(self):
        result = self.eng.generate_workshop("data_connection")
        assert result.template_id.startswith("wst-")
        assert result.object_type == "data_connection"
        assert result.generated_at is not None
        assert len(result.table_columns) > 0

    def test_generate_workshop_invalid_type(self):
        with pytest.raises(WorkshopAutoGenEngineError) as exc:
            self.eng.generate_workshop("invalid_type")
        assert exc.value.code == "INVALID_OBJECT_TYPE"

    def test_get_template_success(self):
        template = self.eng.generate_workshop("ontology")
        got = self.eng.get_template(template.template_id)
        assert got.template_id == template.template_id
        assert got.object_type == "ontology"

    def test_get_template_not_found(self):
        with pytest.raises(WorkshopAutoGenEngineError) as exc:
            self.eng.get_template("wst-nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_list_templates(self):
        self.eng.generate_workshop("data_connection")
        self.eng.generate_workshop("ontology")
        results = self.eng.list_templates()
        assert len(results) == 2

    def test_list_templates_by_type(self):
        self.eng.generate_workshop("data_connection")
        self.eng.generate_workshop("ontology")
        self.eng.generate_workshop("data_connection")
        results = self.eng.list_templates(object_type="data_connection")
        assert len(results) == 2
        assert all(t.object_type == "data_connection" for t in results)

    def test_update_template_success(self):
        template = self.eng.generate_workshop("pipeline")
        updated = self.eng.update_template(
            template.template_id,
            name="Custom Pipeline",
            description="Updated description",
        )
        assert updated.name == "Custom Pipeline"
        assert updated.description == "Updated description"
        assert updated.updated_at is not None

    def test_update_template_not_found(self):
        with pytest.raises(WorkshopAutoGenEngineError) as exc:
            self.eng.update_template("wst-nonexist", name="test")
        assert exc.value.code == "NOT_FOUND"

    def test_delete_template_success(self):
        template = self.eng.generate_workshop("workspace")
        self.eng.delete_template(template.template_id)
        with pytest.raises(WorkshopAutoGenEngineError) as exc:
            self.eng.get_template(template.template_id)
        assert exc.value.code == "NOT_FOUND"

    def test_delete_template_not_found(self):
        with pytest.raises(WorkshopAutoGenEngineError) as exc:
            self.eng.delete_template("wst-nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_preview_template(self):
        template = self.eng.generate_workshop("data_connection")
        preview = self.eng.preview_template(template.template_id)
        assert preview["template_id"] == template.template_id
        assert len(preview["columns"]) == len(template.table_columns)
        assert len(preview["preview_data"]) == 5

    def test_preview_template_not_found(self):
        with pytest.raises(WorkshopAutoGenEngineError) as exc:
            self.eng.preview_template("wst-nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_fifo_eviction(self):
        for i in range(_MAX_WORKSHOP_TEMPLATES + 5):
            self.eng.generate_workshop("data_connection")
        assert len(self.eng._templates) == _MAX_WORKSHOP_TEMPLATES


# ════════════════════════════════════════════════════════════════
# DocIntelEngine
# ════════════════════════════════════════════════════════════════


class TestDocIntelEngine:
    """AIP Doc Intel 五步法引擎测试."""

    def setup_method(self):
        self.eng = DocIntelEngine()
        self.eng._jobs = {}

    def test_singleton_instance(self):
        assert DocIntelEngine.get_instance() is DocIntelEngine.get_instance()

    def test_create_job_success(self):
        result = self.eng.create_job("media-123")
        assert result.job_id.startswith("di-")
        assert result.media_ref_id == "media-123"
        assert result.status == "pending"
        assert result.created_at is not None

    def test_create_job_not_found(self):
        with pytest.raises(DocIntelEngineError) as exc:
            self.eng.create_job("")
        assert exc.value.code == "MEDIA_REF_NOT_FOUND"

    def test_get_job_success(self):
        job = self.eng.create_job("media-123")
        got = self.eng.get_job(job.job_id)
        assert got.job_id == job.job_id
        assert got.media_ref_id == "media-123"

    def test_get_job_not_found(self):
        with pytest.raises(DocIntelEngineError) as exc:
            self.eng.get_job("di-nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_list_jobs(self):
        self.eng.create_job("media-1")
        self.eng.create_job("media-2")
        results = self.eng.list_jobs()
        assert len(results) == 2

    def test_list_jobs_by_status(self):
        job1 = self.eng.create_job("media-1")
        job2 = self.eng.create_job("media-2")
        self.eng.run_step(job1.job_id, "ocr")
        pending = self.eng.list_jobs(status="pending")
        ocr = self.eng.list_jobs(status="ocr")
        assert len(pending) == 1
        assert pending[0].job_id == job2.job_id
        assert len(ocr) == 1
        assert ocr[0].job_id == job1.job_id

    def test_run_step_success(self):
        job = self.eng.create_job("media-123")
        result = self.eng.run_step(job.job_id, "ocr")
        assert result.status == "ocr"
        assert result.current_step == "ocr"
        assert result.ocr_result is not None
        assert result.ocr_result.get("confidence") == 0.95

    def test_run_step_invalid_step(self):
        job = self.eng.create_job("media-123")
        with pytest.raises(DocIntelEngineError) as exc:
            self.eng.run_step(job.job_id, "invalid_step")
        assert exc.value.code == "INVALID_STEP"

    def test_run_step_not_found(self):
        with pytest.raises(DocIntelEngineError) as exc:
            self.eng.run_step("di-nonexist", "ocr")
        assert exc.value.code == "NOT_FOUND"

    def test_run_all_steps(self):
        job = self.eng.create_job("media-123")
        result = self.eng.run_all_steps(job.job_id)
        assert result.status == "completed"
        assert result.current_step == "linking"
        assert result.ocr_result is not None
        assert result.md_content is not None
        assert result.extracted_fields is not None
        assert result.validation_result is not None
        assert result.linked_entities is not None

    def test_cancel_job_success(self):
        job = self.eng.create_job("media-123")
        result = self.eng.cancel_job(job.job_id)
        assert result.status == "failed"
        assert result.error_message == "Job cancelled"

    def test_cancel_job_not_found(self):
        with pytest.raises(DocIntelEngineError) as exc:
            self.eng.cancel_job("di-nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_get_extracted_fields(self):
        job = self.eng.create_job("media-123")
        self.eng.run_step(job.job_id, "field_extraction")
        fields = self.eng.get_extracted_fields(job.job_id)
        assert "title" in fields
        assert "author" in fields
        assert "date" in fields

    def test_get_extracted_fields_not_found(self):
        with pytest.raises(DocIntelEngineError) as exc:
            self.eng.get_extracted_fields("di-nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_get_extracted_fields_pending(self):
        job = self.eng.create_job("media-123")
        fields = self.eng.get_extracted_fields(job.job_id)
        assert fields == {}

    def test_job_status_transitions(self):
        job = self.eng.create_job("media-123")
        assert job.status == "pending"

        job = self.eng.run_step(job.job_id, "ocr")
        assert job.status == "ocr"

        job = self.eng.run_step(job.job_id, "md_conversion")
        assert job.status == "md_conversion"

        job = self.eng.run_step(job.job_id, "field_extraction")
        assert job.status == "field_extraction"

        job = self.eng.run_step(job.job_id, "validation")
        assert job.status == "validation"

        job = self.eng.run_step(job.job_id, "linking")
        assert job.status == "completed"

    def test_fifo_eviction(self):
        for i in range(_MAX_DOC_INTEL_JOBS + 5):
            self.eng.create_job(f"media-{i}")
        assert len(self.eng._jobs) == _MAX_DOC_INTEL_JOBS


# ════════════════════════════════════════════════════════════════
# 单例工厂
# ════════════════════════════════════════════════════════════════


class TestSingletons:
    """三个引擎的单例工厂应返回同一实例。"""

    def test_dicom_engine_singleton(self):
        assert get_dicom_engine() is get_dicom_engine()

    def test_workshop_auto_gen_singleton(self):
        assert get_workshop_auto_gen_engine() is get_workshop_auto_gen_engine()

    def test_doc_intel_engine_singleton(self):
        assert get_doc_intel_engine() is get_doc_intel_engine()