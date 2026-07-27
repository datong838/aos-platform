"""Phase 6 · DataSource API — 单元测试 (≥25).

Tests for phase6_datasource_engine covering all 7 groups:
connectors, sources, schemas, syncs, agents, media-sets, documents.
"""
from __future__ import annotations

import pytest

from aos_api.phase6_datasource_engine import get_engine


@pytest.fixture(autouse=True)
def reset_engine():
    get_engine().reset()
    yield


# ═══════════════════════════════════════════
# Connectors tests (4)
# ═══════════════════════════════════════════


def test_create_and_get_connector() -> None:
    eng = get_engine()
    c = eng.create_connector(name="MySQL", connector_type="database", capabilities=["read", "write"])
    fetched = eng.get_connector(c.id)
    assert fetched is not None
    assert fetched.name == "MySQL"
    assert "read" in fetched.capabilities


def test_list_connectors_filter_by_type() -> None:
    eng = get_engine()
    eng.create_connector(name="MySQL", connector_type="database")
    eng.create_connector(name="Kafka", connector_type="stream")
    eng.create_connector(name="S3", connector_type="file")
    items, total = eng.list_connectors(connector_type="database")
    assert total == 1
    assert items[0].connector_type == "database"


def test_update_connector() -> None:
    eng = get_engine()
    c = eng.create_connector(name="MySQL", version="1.0.0")
    updated = eng.update_connector(c.id, version="2.0.0", description="updated desc")
    assert updated.version == "2.0.0"
    assert updated.description == "updated desc"


def test_connector_capabilities() -> None:
    eng = get_engine()
    c = eng.create_connector(name="PG", capabilities=["read", "write", "cdc"])
    caps = eng.get_connector_capabilities(c.id)
    assert "cdc" in caps
    assert len(caps) == 3


# ═══════════════════════════════════════════
# Sources tests (5)
# ═══════════════════════════════════════════


def test_create_and_get_source() -> None:
    eng = get_engine()
    s = eng.create_source(name="orders-db", source_type="database", host="mysql.local", port=3306)
    fetched = eng.get_source(s.id)
    assert fetched is not None
    assert fetched.name == "orders-db"
    assert fetched.host == "mysql.local"


def test_list_sources_search() -> None:
    eng = get_engine()
    eng.create_source(name="ecom-orders")
    eng.create_source(name="mfg-erp")
    items, total = eng.list_sources(search="ecom")
    assert total == 1
    assert items[0].name == "ecom-orders"


def test_list_sources_filter_type() -> None:
    eng = get_engine()
    eng.create_source(name="db1", source_type="database")
    eng.create_source(name="stream1", source_type="stream")
    items, total = eng.list_sources(source_type="stream")
    assert total == 1
    assert items[0].source_type == "stream"


def test_update_source() -> None:
    eng = get_engine()
    s = eng.create_source(name="src", status="active")
    updated = eng.update_source(s.id, status="inactive", host="new.host")
    assert updated.status == "inactive"
    assert updated.host == "new.host"


def test_delete_source() -> None:
    eng = get_engine()
    s = eng.create_source(name="to-delete")
    assert eng.delete_source(s.id) is True
    assert eng.get_source(s.id) is None
    assert eng.delete_source("nonexistent") is False


# ═══════════════════════════════════════════
# Schema exploration tests (4)
# ═══════════════════════════════════════════


def test_list_schemas() -> None:
    eng = get_engine()
    s = eng.create_source(name="db")
    eng.add_schema(s.id, "public")
    eng.add_schema(s.id, "sales")
    schemas = eng.list_schemas(s.id)
    assert len(schemas) == 2
    assert schemas[0].name == "public"


def test_list_tables_and_columns() -> None:
    eng = get_engine()
    s = eng.create_source(name="db")
    eng.add_table(s.id, "public", "orders", row_count=100)
    eng.add_column(s.id, "public", "orders", "id", datatype="int", primary_key=True)
    eng.add_column(s.id, "public", "orders", "amount", datatype="double")
    tables = eng.list_tables(s.id, "public")
    assert len(tables) == 1
    assert tables[0].name == "orders"
    cols = eng.list_columns(s.id, "public", "orders")
    assert len(cols) == 2
    assert cols[0].name == "id"
    assert cols[0].primary_key is True


def test_foreign_keys() -> None:
    eng = get_engine()
    s = eng.create_source(name="db")
    eng.add_foreign_key(s.id, "public", "orders", "customer_id", "public", "customers", "id")
    fks = eng.list_foreign_keys(s.id, "public", "orders")
    assert len(fks) == 1
    assert fks[0].column_name == "customer_id"
    assert fks[0].ref_table == "customers"


def test_preview_data() -> None:
    eng = get_engine()
    s = eng.create_source(name="db")
    eng.add_column(s.id, "public", "orders", "id", datatype="int")
    eng.add_column(s.id, "public", "orders", "name", datatype="string")
    result = eng.preview_data(s.id, schema_name="public", table_name="orders", limit=5)
    assert len(result["columns"]) == 2
    assert len(result["rows"]) == 5
    assert result["rows"][0]["id"] == 1


def test_source_capabilities() -> None:
    eng = get_engine()
    c = eng.create_connector(name="MySQL", capabilities=["read", "write", "cdc"])
    s = eng.create_source(name="src", connector_id=c.id)
    caps = eng.get_source_capabilities(s.id)
    assert "cdc" in caps


def test_source_capabilities_no_connector() -> None:
    eng = get_engine()
    s = eng.create_source(name="src")
    caps = eng.get_source_capabilities(s.id)
    assert "read" in caps


# ═══════════════════════════════════════════
# Sync tests (4)
# ═══════════════════════════════════════════


def test_create_and_get_sync() -> None:
    eng = get_engine()
    s = eng.create_source(name="db")
    st = eng.create_sync_task(name="Nightly Sync", source_id=s.id, mode="incremental")
    fetched = eng.get_sync_task(st.id)
    assert fetched is not None
    assert fetched.name == "Nightly Sync"
    assert fetched.mode == "incremental"


def test_list_syncs_filter() -> None:
    eng = get_engine()
    s = eng.create_source(name="db")
    eng.create_sync_task(name="A", source_id=s.id, status="active")
    eng.create_sync_task(name="B", source_id=s.id, status="paused")
    items, total = eng.list_sync_tasks(status="active")
    assert total == 1
    assert items[0].status == "active"


def test_update_sync() -> None:
    eng = get_engine()
    s = eng.create_source(name="db")
    st = eng.create_sync_task(name="sync", source_id=s.id)
    updated = eng.update_sync_task(st.id, mode="cdc", status="paused")
    assert updated.mode == "cdc"
    assert updated.status == "paused"


def test_run_sync_creates_run() -> None:
    eng = get_engine()
    s = eng.create_source(name="db")
    st = eng.create_sync_task(name="sync", source_id=s.id)
    run = eng.run_sync_task(st.id)
    assert run.status == "success"
    assert run.rows_synced > 0
    runs = eng.list_sync_runs(st.id)
    assert len(runs) == 1


# ═══════════════════════════════════════════
# Agents tests (4)
# ═══════════════════════════════════════════


def test_create_and_get_agent() -> None:
    eng = get_engine()
    a = eng.create_agent(name="edge-01", hostname="edge01.local", region="us-east-1", status="online")
    fetched = eng.get_agent(a.id)
    assert fetched is not None
    assert fetched.name == "edge-01"
    assert fetched.region == "us-east-1"


def test_list_agents_filter() -> None:
    eng = get_engine()
    eng.create_agent(name="a1", status="online", region="us-east-1")
    eng.create_agent(name="a2", status="offline", region="us-west-2")
    items, total = eng.list_agents(status="online")
    assert total == 1
    assert items[0].status == "online"


def test_agent_metrics() -> None:
    eng = get_engine()
    a = eng.create_agent(name="edge-01", status="online")
    m = eng.get_agent_metrics(a.id)
    assert m["agent_id"] == a.id
    assert m["cpu_usage"] >= 0
    assert m["active_connections"] >= 0


def test_agent_health() -> None:
    eng = get_engine()
    a = eng.create_agent(name="edge-01", status="online")
    h = eng.get_agent_health(a.id)
    assert h["healthy"] is True
    assert h["status"] == "online"


def test_agent_sources() -> None:
    eng = get_engine()
    s1 = eng.create_source(name="src1")
    s2 = eng.create_source(name="src2")
    a = eng.create_agent(name="edge-01", source_ids=[s1.id, s2.id])
    sources = eng.get_agent_sources(a.id)
    assert len(sources) == 2


def test_update_agent_config() -> None:
    eng = get_engine()
    a = eng.create_agent(name="edge-01", config={"key": "val"})
    updated = eng.update_agent_config(a.id, {"max_conn": 100})
    assert updated.config["max_conn"] == 100


# ═══════════════════════════════════════════
# Media Sets tests (3)
# ═══════════════════════════════════════════


def test_create_media_set_and_get() -> None:
    eng = get_engine()
    ms = eng.create_media_set(name="Photos", description="batch 1")
    fetched = eng.get_media_set(ms.id)
    assert fetched is not None
    assert fetched.name == "Photos"


def test_media_set_files() -> None:
    eng = get_engine()
    ms = eng.create_media_set(name="Photos")
    eng.add_media_file(ms.id, "img1.jpg", file_type="image", size_bytes=1024)
    eng.add_media_file(ms.id, "img2.jpg", file_type="image", size_bytes=2048)
    files = eng.list_media_set_files(ms.id)
    assert len(files) == 2
    assert files[0].filename == "img1.jpg"


def test_transform_media_files() -> None:
    eng = get_engine()
    ms = eng.create_media_set(name="Photos")
    eng.add_media_file(ms.id, "img1.jpg")
    eng.add_media_file(ms.id, "img2.jpg")
    result = eng.transform_media_files(ms.id, "resize", {"width": 800})
    assert result["files_transformed"] == 2
    assert result["operation"] == "resize"
    assert result["status"] == "completed"


# ═══════════════════════════════════════════
# Documents tests (4)
# ═══════════════════════════════════════════


def test_create_and_list_documents() -> None:
    eng = get_engine()
    eng.create_document(name="invoice-001.pdf", status="pending")
    eng.create_document(name="invoice-002.pdf", status="extracted")
    items, total = eng.list_documents()
    assert total == 2


def test_list_documents_filter() -> None:
    eng = get_engine()
    eng.create_document(name="doc1", status="pending")
    eng.create_document(name="doc2", status="extracted")
    items, total = eng.list_documents(status="extracted")
    assert total == 1
    assert items[0].status == "extracted"


def test_extract_document() -> None:
    eng = get_engine()
    d = eng.create_document(name="invoice.pdf", status="pending")
    extracted = eng.extract_document(d.id, fields=["vendor", "amount"])
    assert extracted.status == "extracted"
    assert "vendor" in extracted.extracted_fields
    assert "amount" in extracted.extracted_fields


def test_import_document() -> None:
    eng = get_engine()
    d = eng.import_document(name="imported.pdf", file_type="pdf", status="pending")
    assert d.name == "imported.pdf"
    assert d.file_type == "pdf"


def test_extraction_templates() -> None:
    eng = get_engine()
    eng.create_template(name="Invoice Template", doc_type="invoice", fields=[{"name": "amount"}])
    eng.create_template(name="Contract Template", doc_type="contract")
    templates = eng.list_templates()
    assert len(templates) == 2
    assert templates[0].doc_type == "invoice"


def test_data_projects() -> None:
    eng = get_engine()
    eng.create_project(name="Project A", status="active")
    eng.create_project(name="Project B", status="archived")
    projects = eng.list_projects()
    assert len(projects) == 2


# ═══════════════════════════════════════════
# Test connection test (1)
# ═══════════════════════════════════════════


def test_source_connection() -> None:
    eng = get_engine()
    s = eng.create_source(name="db", host="mysql.local", port=3306, database="test")
    result = eng.test_connection(s.id)
    assert result["status"] == "ok"
    assert result["latency_ms"] > 0
    assert result["details"]["host"] == "mysql.local"
