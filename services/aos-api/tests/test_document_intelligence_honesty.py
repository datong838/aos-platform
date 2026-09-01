from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from aos_api.ontology_engine import get_engine as get_ontology_engine
from aos_api.phase6_datasource_engine import get_engine as get_datasource_engine
from aos_api.routers.phase6_documents import router as documents_router
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_docintel_engines():
    datasource = get_datasource_engine()
    ontology = get_ontology_engine()
    datasource.reset()
    ontology.reset()
    yield
    datasource.reset()
    ontology.reset()


@pytest.fixture()
def doc_client():
    app = FastAPI()
    app.include_router(documents_router)
    with TestClient(app) as test_client:
        test_client.headers.update({
            "Authorization": "Bearer dev",
            "X-Org-Id": "dev-org",
            "X-Project-Id": "dev-project",
        })
        yield test_client


def test_engine_upload_keeps_real_bytes_and_reprocesses_them() -> None:
    raw = "公司名称: AOS\n总收入: 123".encode()
    engine = get_datasource_engine()

    document = engine.upload_document("report.txt", raw, "text/plain")

    assert document.size_bytes == len(raw)
    assert document.content_sha256 == hashlib.sha256(raw).hexdigest()
    processed = engine.process_document(document.id, "finance_report")
    assert processed.ocr_text == raw.decode()
    assert processed.parser == "parser-text"
    assert processed.extracted_fields


def test_engine_reprocess_without_uploaded_bytes_fails_closed() -> None:
    document = get_datasource_engine().create_document(name="legacy.pdf", status="pending")

    with pytest.raises(ValueError, match="服务端文件字节"):
        get_datasource_engine().process_document(document.id, "invoice")

    assert document.status == "pending"
    assert document.extracted_fields == {}


def test_ontology_write_is_atomic_under_concurrent_retries() -> None:
    datasource = get_datasource_engine()
    ontology = get_ontology_engine()
    ontology.create_object_type(id="Invoice", name="Invoice")
    document = datasource.upload_document("invoice.txt", b"amount: 10", "text/plain")
    datasource.update_document(
        document.id,
        extracted_fields=[
            {"id": "amount", "name": "amount", "value": "10", "confidence": 0.99},
        ],
    )
    workers = 8
    barrier = Barrier(workers)

    def write_once() -> str:
        barrier.wait()
        _, obj = datasource.write_document_to_ontology(document.id, "Invoice")
        return obj.id

    with ThreadPoolExecutor(max_workers=workers) as executor:
        object_ids = list(executor.map(lambda _: write_once(), range(workers)))

    objects, total = ontology.list_objects(object_type_id="Invoice", page_size=100)
    assert len(set(object_ids)) == 1
    assert total == 1
    assert [obj.id for obj in objects] == [object_ids[0]]
    assert sum("已写入本体 Object" in item["note"] for item in document.history) == 1


def test_document_api_real_upload_reprocess_ontology_write_and_delete(doc_client) -> None:
    raw = "发票号码: INV-1\n金额(含税): 88.00".encode()
    uploaded = doc_client.post(
        "/api/datasource/documents/upload?name=invoice.txt",
        content=raw,
        headers={"Content-Type": "text/plain"},
    )
    assert uploaded.status_code == 200, uploaded.text
    document = uploaded.json()
    assert document["size_bytes"] == len(raw)
    assert document["content_sha256"] == hashlib.sha256(raw).hexdigest()
    assert document["org_id"] == "dev-org"
    assert document["project_id"] == "dev-project"
    assert document["receipt_ref"].startswith("document-upload:")
    assert document["lineage_ref"].endswith(":upload")

    processed = doc_client.post(
        f"/api/datasource/documents/{document['id']}/reprocess",
        json={"template_id": "invoice"},
    )
    assert processed.status_code == 200, processed.text
    assert processed.json()["ocr_text"] == raw.decode()
    assert processed.json()["extracted_fields"]
    assert processed.json()["template_revision"] == "v1"
    assert processed.json()["processing_progress"] == 100
    assert processed.json()["run_evidence_ref"].startswith("document-run:")
    assert processed.json()["receipt_ref"].startswith("document-extract:")
    assert processed.json()["processing_attempts"] == 1
    assert len(processed.json()["receipt_refs"]) == 2
    first_receipt = processed.json()["receipt_ref"]
    retried = doc_client.post(
        f"/api/datasource/documents/{document['id']}/reprocess",
        json={"template_id": "invoice"},
    )
    assert retried.status_code == 200
    assert retried.json()["processing_attempts"] == 2
    assert retried.json()["receipt_ref"] != first_receipt
    processed = retried
    fields = list(processed.json()["extracted_fields"].values())
    fields[0]["value"] = "人工修正值"
    updated = doc_client.put(
        f"/api/datasource/documents/{document['id']}",
        json={"extracted_fields": fields, "ocr_text": "人工 OCR"},
    )
    assert updated.status_code == 200
    assert updated.json()["ocr_text"] == "人工 OCR"
    first_updated_field = next(iter(updated.json()["extracted_fields"].values()))
    assert first_updated_field["value"] == "人工修正值"

    missing_type = doc_client.post(
        f"/api/datasource/documents/{document['id']}/ontology-write",
        json={"object_type_id": "missing"},
    )
    assert missing_type.status_code == 409
    assert get_datasource_engine().get_document(document["id"]).ontology_object_id == ""

    get_ontology_engine().create_object_type(id="Invoice", name="Invoice")
    written = doc_client.post(
        f"/api/datasource/documents/{document['id']}/ontology-write",
        json={"object_type_id": "Invoice"},
    )
    assert written.status_code == 200, written.text
    object_id = written.json()["object"]["id"]
    ontology_object = get_ontology_engine().get_object(object_id)
    assert ontology_object is not None
    assert ontology_object.properties["source_org_id"] == "dev-org"
    assert ontology_object.properties["source_project_id"] == "dev-project"
    assert written.json()["document"]["ontology_object_id"] == object_id
    assert written.json()["document"]["review_status"] == "approved"
    assert written.json()["document"]["reviewed_by"] == "user:dev"
    assert written.json()["document"]["downstream_ref"].startswith("ontology-object:")
    assert written.json()["document"]["receipt_ref"].startswith("document-ontology-write:")
    repeated = doc_client.post(
        f"/api/datasource/documents/{document['id']}/ontology-write",
        json={"object_type_id": "Invoice"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["object"]["id"] == object_id

    stats = doc_client.get("/api/datasource/documents/stats")
    assert stats.status_code == 200
    assert stats.json()["total"] == 1
    assert stats.json()["average_confidence"] is not None

    deleted = doc_client.delete(f"/api/datasource/documents/{document['id']}")
    assert deleted.status_code == 200
    assert get_datasource_engine().get_document(document["id"]) is None


def test_document_api_rejects_empty_upload(doc_client) -> None:
    response = doc_client.post(
        "/api/datasource/documents/upload?name=empty.pdf",
        content=b"",
        headers={"Content-Type": "application/pdf"},
    )

    assert response.status_code == 400
    assert "为空" in response.json()["detail"]
    assert get_datasource_engine().document_stats()["total"] == 0


def test_document_api_records_governance_metadata_and_hides_cross_tenant_documents(doc_client) -> None:
    uploaded = doc_client.post(
        "/api/datasource/documents/upload",
        params={
            "name": "qyh-contract.txt",
            "source_label": "栖月汇合同归档",
            "document_kind": "supplier_contract",
            "sensitivity": "restricted",
            "retention_policy": "180_days",
        },
        content=b"contract bytes",
        headers={"Content-Type": "text/plain"},
    )
    assert uploaded.status_code == 200, uploaded.text
    document = uploaded.json()
    assert document["source_label"] == "栖月汇合同归档"
    assert document["document_kind"] == "supplier_contract"
    assert document["sensitivity"] == "restricted"
    assert document["retention_policy"] == "180_days"

    isolated = doc_client.get(
        "/api/datasource/documents?page=1&page_size=100",
        headers={"X-Org-Id": "org-org", "X-Project-Id": "dev-project"},
    )
    assert isolated.status_code == 200, isolated.text
    assert isolated.json()["total"] == 0
    forbidden_read = doc_client.post(
        f"/api/datasource/documents/{document['id']}/reprocess",
        json={"template_id": "contract"},
        headers={"X-Org-Id": "org-org", "X-Project-Id": "dev-project"},
    )
    assert forbidden_read.status_code == 404


def test_extraction_template_versions_are_tenant_scoped_and_cas_guarded(doc_client) -> None:
    created = doc_client.post(
        "/api/datasource/extraction-templates",
        json={
            "name": "供应商合同字段模板",
            "description": "提取合同主体、金额与期限",
            "doc_type": "supplier_contract",
            "fields": [{"name": "甲方", "label": "甲方"}, {"name": "合同金额", "label": "合同金额"}],
            "validation_rules": [{"field": "合同金额", "rule": "required"}],
            "model_route": "deterministic_document_parser",
            "estimated_cost_units": 2,
            "approval_gate": "manual_review",
        },
    )
    assert created.status_code == 200
    template = created.json()
    assert template["revision"] == 1

    updated = doc_client.put(
        f"/api/datasource/extraction-templates/{template['id']}",
        json={"expected_revision": 1, "description": "合同主体、金额、期限与续签日", "change_note": "增加续签说明"},
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2

    stale = doc_client.put(
        f"/api/datasource/extraction-templates/{template['id']}",
        json={"expected_revision": 1, "description": "过期覆盖"},
    )
    assert stale.status_code == 409

    versions = doc_client.get(f"/api/datasource/extraction-templates/{template['id']}/versions")
    assert versions.status_code == 200
    assert [item["revision"] for item in versions.json()["items"]] == [1, 2]

    rolled_back = doc_client.post(
        f"/api/datasource/extraction-templates/{template['id']}/rollback",
        json={"expected_revision": 2, "target_revision": 1},
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["revision"] == 3
    assert rolled_back.json()["description"] == "提取合同主体、金额与期限"
    assert rolled_back.json()["change_note"] == "回滚到 v1"

    uploaded = doc_client.post(
        "/api/datasource/documents/upload?name=supplier-contract.txt",
        content="甲方: 栖月汇商贸有限公司\n合同金额: 100000".encode(),
        headers={"Content-Type": "text/plain"},
    )
    assert uploaded.status_code == 200, uploaded.text
    processed = doc_client.post(
        f"/api/datasource/documents/{uploaded.json()['id']}/reprocess",
        json={"template_id": template["id"]},
    )
    assert processed.status_code == 200, processed.text
    payload = processed.json()
    assert payload["template_id"] == template["id"]
    assert payload["template_revision"] == "v3"
    assert [field["name"] for field in payload["extracted_fields"].values()] == ["甲方", "合同金额"]
    assert [field["value"] for field in payload["extracted_fields"].values()] == [
        "栖月汇商贸有限公司",
        "100000",
    ]

    isolated = doc_client.get(
        "/api/datasource/extraction-templates",
        headers={"X-Org-Id": "org-org", "X-Project-Id": "dev-project"},
    )
    assert isolated.status_code == 200
    assert isolated.json()["count"] == 0
