from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.ontology_engine import get_engine as get_ontology_engine
from aos_api.phase6_datasource_engine import get_engine as get_datasource_engine
from aos_api.routers.phase6_documents import router as documents_router


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

    processed = doc_client.post(
        f"/api/datasource/documents/{document['id']}/reprocess",
        json={"template_id": "invoice"},
    )
    assert processed.status_code == 200, processed.text
    assert processed.json()["ocr_text"] == raw.decode()
    assert processed.json()["extracted_fields"]
    fields = list(processed.json()["extracted_fields"].values())
    fields[0]["value"] = "人工修正值"
    updated = doc_client.put(
        f"/api/datasource/documents/{document['id']}",
        json={"extracted_fields": fields, "ocr_text": "人工 OCR"},
    )
    assert updated.status_code == 200
    assert updated.json()["ocr_text"] == "人工 OCR"
    assert list(updated.json()["extracted_fields"].values())[0]["value"] == "人工修正值"

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
    assert get_ontology_engine().get_object(object_id) is not None
    assert written.json()["document"]["ontology_object_id"] == object_id
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
