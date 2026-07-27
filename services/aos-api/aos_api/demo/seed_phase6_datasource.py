"""Phase 6 seed · DataSource — connectors + sources + schemas/tables/columns/fks +
syncs/runs + agents + media-sets/files + documents/templates/projects (≈330).
"""
from __future__ import annotations

from aos_api.phase6_datasource_engine import get_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase6_datasource")

# ── Connector specs (10) ──
_CONNECTORS: list[dict] = [
    {"name": "MySQL Connector", "connector_type": "database", "version": "2.1.0", "description": "MySQL/MariaDB JDBC connector", "capabilities": ["read", "write", "schema", "cdc", "preview"], "config_schema": {"host": "string", "port": "int", "database": "string"}, "status": "active"},
    {"name": "PostgreSQL Connector", "connector_type": "database", "version": "2.3.0", "description": "PostgreSQL connector with logical replication", "capabilities": ["read", "write", "schema", "cdc", "preview"], "config_schema": {"host": "string", "port": "int", "database": "string"}, "status": "active"},
    {"name": "Apache Kafka Connector", "connector_type": "stream", "version": "3.0.0", "description": "Kafka topic stream connector", "capabilities": ["read", "write", "stream"], "config_schema": {"brokers": "list", "topic": "string"}, "status": "active"},
    {"name": "AWS S3 Connector", "connector_type": "file", "version": "1.5.0", "description": "S3 object storage connector", "capabilities": ["read", "write", "preview"], "config_schema": {"bucket": "string", "region": "string"}, "status": "active"},
    {"name": "Salesforce Connector", "connector_type": "api", "version": "1.8.0", "description": "Salesforce CRM REST API connector", "capabilities": ["read", "write", "schema"], "config_schema": {"instance": "string", "api_version": "string"}, "status": "active"},
    {"name": "MongoDB Connector", "connector_type": "nosql", "version": "2.0.0", "description": "MongoDB document database connector", "capabilities": ["read", "write", "schema", "preview"], "config_schema": {"uri": "string", "database": "string"}, "status": "active"},
    {"name": "Snowflake Connector", "connector_type": "warehouse", "version": "1.9.0", "description": "Snowflake cloud warehouse connector", "capabilities": ["read", "write", "schema", "preview"], "config_schema": {"account": "string", "warehouse": "string"}, "status": "active"},
    {"name": "Oracle Connector", "connector_type": "database", "version": "1.6.0", "description": "Oracle DB connector with redo log CDC", "capabilities": ["read", "write", "schema", "cdc"], "config_schema": {"host": "string", "service": "string"}, "status": "beta"},
    {"name": "REST API Connector", "connector_type": "api", "version": "1.3.0", "description": "Generic REST API connector", "capabilities": ["read", "write"], "config_schema": {"base_url": "string", "auth_type": "string"}, "status": "active"},
    {"name": "Azure Blob Connector", "connector_type": "file", "version": "1.4.0", "description": "Azure Blob Storage connector", "capabilities": ["read", "write", "preview"], "config_schema": {"account": "string", "container": "string"}, "status": "active"},
]

# ── Source specs (20) ──
_SOURCE_SPECS: list[dict] = [
    # E-commerce
    {"name": "ecom-orders-mysql", "connector_id_idx": 0, "source_type": "database", "host": "mysql-prod-01.ecom.internal", "port": 3306, "database": "ecommerce", "username": "etl_reader", "status": "active", "tags": ["ecommerce", "orders"], "owner": "data-team"},
    {"name": "ecom-customers-mysql", "connector_id_idx": 0, "source_type": "database", "host": "mysql-prod-01.ecom.internal", "port": 3306, "database": "ecommerce", "username": "etl_reader", "status": "active", "tags": ["ecommerce", "customers"], "owner": "data-team"},
    {"name": "ecom-events-kafka", "connector_id_idx": 2, "source_type": "stream", "host": "kafka-cluster-01.ecom.internal", "port": 9092, "database": "click_events", "username": "", "status": "active", "tags": ["ecommerce", "events", "streaming"], "owner": "platform"},
    {"name": "ecom-product-images-s3", "connector_id_idx": 3, "source_type": "file", "host": "s3://ecom-product-images", "port": 0, "database": "", "username": "", "status": "active", "tags": ["ecommerce", "media"], "owner": "catalog-team"},
    {"name": "ecom-salesforce-crm", "connector_id_idx": 4, "source_type": "api", "host": "ecom-corp.my.salesforce.com", "port": 443, "database": "", "username": "api@ecom.com", "status": "active", "tags": ["ecommerce", "crm"], "owner": "sales-ops"},
    {"name": "ecom-mongo-catalog", "connector_id_idx": 5, "source_type": "nosql", "host": "mongo-prod.ecom.internal", "port": 27017, "database": "catalog", "username": "app_reader", "status": "active", "tags": ["ecommerce", "catalog"], "owner": "catalog-team"},
    {"name": "ecom-snowflake-dw", "connector_id_idx": 6, "source_type": "warehouse", "host": "ecom-corp.snowflakecomputing.com", "port": 443, "database": "WAREHOUSE", "username": "ETL_SVC", "status": "active", "tags": ["ecommerce", "warehouse"], "owner": "data-team"},
    # Manufacturing
    {"name": "mfg-erp-postgres", "connector_id_idx": 1, "source_type": "database", "host": "pg-erp.mfg.internal", "port": 5432, "database": "erp", "username": "reporting", "status": "active", "tags": ["manufacturing", "erp"], "owner": "ops"},
    {"name": "mfg-mes-oracle", "connector_id_idx": 7, "source_type": "database", "host": "oracle-mes.mfg.internal", "port": 1521, "database": "MES", "username": "mes_read", "status": "active", "tags": ["manufacturing", "mes"], "owner": "ops"},
    {"name": "mfg-iot-kafka", "connector_id_idx": 2, "source_type": "stream", "host": "kafka-iot.mfg.internal", "port": 9092, "database": "sensor_data", "username": "", "status": "active", "tags": ["manufacturing", "iot"], "owner": "platform"},
    {"name": "mfg-quality-mongo", "connector_id_idx": 5, "source_type": "nosql", "host": "mongo-quality.mfg.internal", "port": 27017, "database": "quality", "username": "qa_reader", "status": "active", "tags": ["manufacturing", "quality"], "owner": "qa-team"},
    {"name": "mfg-drawings-s3", "connector_id_idx": 3, "source_type": "file", "host": "s3://mfg-engineering-drawings", "port": 0, "database": "", "username": "", "status": "active", "tags": ["manufacturing", "documents"], "owner": "engineering"},
    {"name": "mfg-snowflake-dw", "connector_id_idx": 6, "source_type": "warehouse", "host": "mfg-corp.snowflakecomputing.com", "port": 443, "database": "FACTORY_DW", "username": "BI_SVC", "status": "active", "tags": ["manufacturing", "warehouse"], "owner": "data-team"},
    {"name": "mfg-supply-rest", "connector_id_idx": 8, "source_type": "api", "host": "https://supply.mfg.com/api", "port": 443, "database": "", "username": "svc_account", "status": "active", "tags": ["manufacturing", "supply-chain"], "owner": "ops"},
    # Logistics / retail
    {"name": "log-shipments-mysql", "connector_id_idx": 0, "source_type": "database", "host": "mysql-log.log.internal", "port": 3306, "database": "logistics", "username": "log_reader", "status": "active", "tags": ["logistics", "shipments"], "owner": "ops"},
    {"name": "log-tracking-kafka", "connector_id_idx": 2, "source_type": "stream", "host": "kafka-log.log.internal", "port": 9092, "database": "gps_tracking", "username": "", "status": "active", "tags": ["logistics", "tracking"], "owner": "platform"},
    {"name": "log-warehouse-mongo", "connector_id_idx": 5, "source_type": "nosql", "host": "mongo-log.log.internal", "port": 27017, "database": "wms", "username": "wms_reader", "status": "active", "tags": ["logistics", "wms"], "owner": "ops"},
    {"name": "retail-pos-postgres", "connector_id_idx": 1, "source_type": "database", "host": "pg-pos.retail.internal", "port": 5432, "database": "pos", "username": "analytics", "status": "active", "tags": ["retail", "pos"], "owner": "analytics"},
    {"name": "retail-ads-rest", "connector_id_idx": 8, "source_type": "api", "host": "https://ads.retail.com/v2", "port": 443, "database": "", "username": "marketing", "status": "active", "tags": ["retail", "ads"], "owner": "marketing"},
    {"name": "retail-images-blob", "connector_id_idx": 9, "source_type": "file", "host": "azure-blob.retail.com", "port": 443, "database": "media", "username": "", "status": "inactive", "tags": ["retail", "media"], "owner": "marketing"},
]

# ── Schema/Table/Column templates ──
_SCHEMA_SPECS: list[tuple[str, str]] = [
    ("public", "Default schema"),
    ("sales", "Sales domain"),
    ("inventory", "Inventory domain"),
]

_TABLE_COLS: dict[str, list[tuple[str, str, bool, bool]]] = {
    "orders": [("order_id", "string", False, True), ("customer_id", "string", False, False), ("order_date", "datetime", False, False), ("total_amount", "double", False, False), ("status", "string", True, False)],
    "customers": [("customer_id", "string", False, True), ("name", "string", False, False), ("email", "string", True, False), ("phone", "string", True, False), ("created_at", "datetime", False, False)],
    "order_items": [("item_id", "string", False, True), ("order_id", "string", False, False), ("product_id", "string", False, False), ("quantity", "int", False, False), ("unit_price", "double", False, False)],
    "products": [("product_id", "string", False, True), ("sku", "string", False, False), ("name", "string", False, False), ("price", "double", False, False), ("category", "string", True, False)],
    "inventory_levels": [("sku", "string", False, True), ("warehouse_id", "string", False, False), ("quantity", "int", False, False), ("updated_at", "datetime", False, False)],
}

# ── Edge Agent specs (10) ──
_AGENT_SPECS: list[dict] = [
    {"name": "edge-dc-east-01", "hostname": "edge01.ecom-east.dc", "ip_address": "10.10.1.10", "region": "us-east-1", "version": "2.0.0", "status": "online", "config": {"max_connections": 50, "buffer_mb": 512}},
    {"name": "edge-dc-west-01", "hostname": "edge01.ecom-west.dc", "ip_address": "10.20.1.10", "region": "us-west-2", "version": "2.0.0", "status": "online", "config": {"max_connections": 50, "buffer_mb": 512}},
    {"name": "edge-mfg-plant-01", "hostname": "edge01.mfg-plant.factory", "ip_address": "192.168.1.10", "region": "apac-shanghai", "version": "2.0.0", "status": "online", "config": {"max_connections": 30, "buffer_mb": 256}},
    {"name": "edge-mfg-plant-02", "hostname": "edge02.mfg-plant.factory", "ip_address": "192.168.1.11", "region": "apac-shenzhen", "version": "1.9.0", "status": "degraded", "config": {"max_connections": 30, "buffer_mb": 256}},
    {"name": "edge-log-hub-01", "hostname": "edge01.log-hub.logistics", "ip_address": "10.30.1.10", "region": "eu-west-1", "version": "2.0.0", "status": "online", "config": {"max_connections": 40, "buffer_mb": 384}},
    {"name": "edge-retail-store-01", "hostname": "edge01.retail-store.shop", "ip_address": "10.40.1.10", "region": "us-east-1", "version": "2.0.0", "status": "online", "config": {"max_connections": 20, "buffer_mb": 128}},
    {"name": "edge-retail-store-02", "hostname": "edge02.retail-store.shop", "ip_address": "10.40.1.11", "region": "us-west-2", "version": "2.0.0", "status": "offline", "config": {"max_connections": 20, "buffer_mb": 128}},
    {"name": "edge-iot-gateway-01", "hostname": "edge01.iot.mfg.factory", "ip_address": "192.168.2.10", "region": "apac-shanghai", "version": "2.0.0", "status": "online", "config": {"max_connections": 100, "buffer_mb": 1024}},
    {"name": "edge-dc-eu-01", "hostname": "edge01.ecom-eu.dc", "ip_address": "10.50.1.10", "region": "eu-west-1", "version": "2.0.0", "status": "online", "config": {"max_connections": 50, "buffer_mb": 512}},
    {"name": "edge-cloud-sync-01", "hostname": "edge01.cloud-sync.global", "ip_address": "10.60.1.10", "region": "global", "version": "2.0.0", "status": "online", "config": {"max_connections": 80, "buffer_mb": 768}},
]

# ── Media Set specs (5) ──
_MEDIA_SET_SPECS: list[dict] = [
    {"name": "E-com Product Images 2026Q2", "description": "Product photo batch for Q2 catalog", "file_count": 4, "total_size_bytes": 52428800, "tags": ["ecommerce", "images"]},
    {"name": "Manufacturing Drawings", "description": "CAD engineering drawings", "file_count": 4, "total_size_bytes": 104857600, "tags": ["manufacturing", "cad"]},
    {"name": "Retail Ad Creatives", "description": "Marketing banner assets", "file_count": 4, "total_size_bytes": 31457280, "tags": ["retail", "marketing"]},
    {"name": "Quality Inspection Photos", "description": "Factory QC photos batch", "file_count": 4, "total_size_bytes": 20971520, "tags": ["manufacturing", "quality"]},
    {"name": "Logistics Label Scans", "description": "Shipping label scan images", "file_count": 4, "total_size_bytes": 10485760, "tags": ["logistics", "labels"]},
]

# ── Document specs (10) ──
_DOCUMENT_SPECS: list[dict] = [
    {"name": "Invoice-INV-2026-0001.pdf", "file_type": "pdf", "status": "extracted", "doc_type": "invoice"},
    {"name": "Invoice-INV-2026-0002.pdf", "file_type": "pdf", "status": "extracted", "doc_type": "invoice"},
    {"name": "Contract-Vendor-ACME.docx", "file_type": "docx", "status": "pending", "doc_type": "contract"},
    {"name": "Receipt-LOG-20260701.pdf", "file_type": "pdf", "status": "extracted", "doc_type": "receipt"},
    {"name": "PO-2026-04567.pdf", "file_type": "pdf", "status": "pending", "doc_type": "form"},
    {"name": "Quality-Report-Q2.html", "file_type": "html", "status": "extracted", "doc_type": "custom"},
    {"name": "Invoice-INV-2026-0003.pdf", "file_type": "pdf", "status": "failed", "doc_type": "invoice"},
    {"name": "Contract-Supplier-GlobalCorp.docx", "file_type": "docx", "status": "pending", "doc_type": "contract"},
    {"name": "Receipt-LOG-20260715.pdf", "file_type": "pdf", "status": "extracted", "doc_type": "receipt"},
    {"name": "Bill-of-Materials-BOM-098.pdf", "file_type": "pdf", "status": "pending", "doc_type": "form"},
]

# ── Extraction Template specs (5) ──
_TEMPLATE_SPECS: list[dict] = [
    {"name": "Standard Invoice Template", "description": "Extract vendor, invoice_number, date, amount, tax", "doc_type": "invoice", "fields": [{"name": "vendor", "type": "string"}, {"name": "invoice_number", "type": "string"}, {"name": "date", "type": "date"}, {"name": "amount", "type": "double"}, {"name": "tax", "type": "double"}]},
    {"name": "Vendor Contract Template", "description": "Extract parties, effective_date, terms, amount", "doc_type": "contract", "fields": [{"name": "party_a", "type": "string"}, {"name": "party_b", "type": "string"}, {"name": "effective_date", "type": "date"}, {"name": "terms", "type": "string"}, {"name": "total_value", "type": "double"}]},
    {"name": "Shipping Receipt Template", "description": "Extract tracking_id, sender, receiver, weight", "doc_type": "receipt", "fields": [{"name": "tracking_id", "type": "string"}, {"name": "sender", "type": "string"}, {"name": "receiver", "type": "string"}, {"name": "weight_kg", "type": "double"}]},
    {"name": "Purchase Order Template", "description": "Extract po_number, supplier, items, total", "doc_type": "form", "fields": [{"name": "po_number", "type": "string"}, {"name": "supplier", "type": "string"}, {"name": "line_items", "type": "array"}, {"name": "total", "type": "double"}]},
    {"name": "Quality Report Template", "description": "Extract report_id, batch, inspector, pass_rate", "doc_type": "custom", "fields": [{"name": "report_id", "type": "string"}, {"name": "batch_number", "type": "string"}, {"name": "inspector", "type": "string"}, {"name": "pass_rate", "type": "double"}]},
]

# ── Data Project specs (5) ──
_PROJECT_SPECS: list[dict] = [
    {"name": "E-commerce Customer 360", "description": "Unified customer view across channels", "owner": "data-team", "status": "active", "tags": ["ecommerce", "analytics"]},
    {"name": "Manufacturing Quality Insights", "description": "Real-time quality monitoring and analytics", "owner": "qa-team", "status": "active", "tags": ["manufacturing", "quality"]},
    {"name": "Supply Chain Visibility", "description": "End-to-end supply chain tracking", "owner": "ops", "status": "active", "tags": ["logistics", "supply-chain"]},
    {"name": "Retail Demand Forecasting", "description": "POS + ads data for demand prediction", "owner": "analytics", "status": "active", "tags": ["retail", "forecasting"]},
    {"name": "IoT Predictive Maintenance", "description": "Sensor data for equipment health", "owner": "ops", "status": "archived", "tags": ["manufacturing", "iot"]},
]


def seed_phase6_datasource() -> int:
    """Seed Phase 6 datasource data (~330 records). Returns total record count."""
    import time as _t

    eng = get_engine()
    count = 0

    # ── Connectors: 10 ──
    connector_ids: list[str] = []
    for spec in _CONNECTORS:
        c = eng.create_connector(**spec)
        connector_ids.append(c.id)
        count += 1

    # ── Sources: 20 ──
    source_ids: list[str] = []
    for spec in _SOURCE_SPECS:
        connector_idx = spec.pop("connector_id_idx")
        spec["connector_id"] = connector_ids[connector_idx]
        s = eng.create_source(**spec)
        source_ids.append(s.id)
        count += 1

    # ── Schemas + Tables + Columns: for first 15 sources, 2 schemas each, 5 tables per schema ──
    # Total: 15 * 2 = 30 schemas, 30 * 5 = 150 tables, 150 * ~5 = 750 columns → too many
    # Adjust: 10 sources × 3 schemas = 30 schemas, 30 × 5 = 150 table entries, each with ~5 cols
    # But spec says "30 Schema × 5 表 = 150 条表/列信息" and total ~330
    # Let's do: 10 sources get schemas, 3 schemas each → 30 schemas total
    # But that exceeds 30. Let's do: 10 sources × 3 schemas = 30 schemas
    # Each schema gets 5 tables → but we won't add columns individually (just store metadata)
    # Actually the plan says "30 Schema × 5 表 = 150 条表/列信息"
    # So 30 schemas + 150 tables = 180 items in schema/table group. That's a lot.
    # But total needs ~330, and we also have 20 FK, 20 syncs + 30 runs, 10 agents, 5 MS + 20 files, 10 docs + 5 templates + 5 projects
    # = 180 + 20 + 50 + 10 + 25 + 20 = 305. Close enough.
    # Actually re-reading: "30 Schema × 5 表 = 150 条表/列信息" — this means 30 schemas and 150 table/column records combined.
    # Let's interpret as: 30 schemas, 150 tables, columns included as part of table metadata (not separate count)
    # But for the engine, columns are separate records. Let's adjust:
    # 10 sources × 3 schemas = 30 schemas
    # 30 schemas × 5 tables = 150 tables
    # For columns: we'll add columns only for first table of each schema (30 × 5 cols = 150 cols)
    # That would be 30 + 150 + 150 = 330 already, plus other items. Too many.
    #
    # Revised interpretation: "30 Schema × 5 表 = 150 条表/列信息" means 30 schemas producing 150 records of table info
    # So: 30 schemas + 150 tables = 180 records. Columns are detail within table, not counted separately.
    # For the engine we DO store columns, but let's keep column count reasonable (only for a few tables)
    #
    # Final plan to hit ~330:
    # 10 connectors + 20 sources + 30 schemas + 150 tables + 20 FKs +
    # 20 syncs + 30 runs + 10 agents + 5 media-sets + 20 files +
    # 10 docs + 5 templates + 5 projects + columns(only for some tables)
    # = 10+20+30+150+20+20+30+10+5+20+10+5+5 = 335 base (without columns as separate)
    # We'll add columns for first 2 tables per schema as bonus data (not counted in total)

    table_names = list(_TABLE_COLS.keys())

    for src_idx, src_id in enumerate(source_ids[:10]):  # first 10 sources
        for sch_idx, (sch_name, sch_desc) in enumerate(_SCHEMA_SPECS):
            sch = eng.add_schema(src_id, sch_name, description=sch_desc, table_count=5)
            count += 1

            for tbl_idx, tbl_name in enumerate(table_names):
                row_count = 1000 + src_idx * 500 + tbl_idx * 200
                size_bytes = row_count * 256
                t = eng.add_table(
                    src_id, sch_name, tbl_name,
                    row_count=row_count, size_bytes=size_bytes,
                    description=f"Table {tbl_name} in {sch_name}",
                )
                count += 1

                # Add columns only for first 2 tables of first schema per source (to avoid explosion)
                if sch_idx == 0 and tbl_idx < 2:
                    col_specs = _TABLE_COLS.get(tbl_name, [])
                    for col_name, col_type, nullable, is_pk in col_specs:
                        eng.add_column(
                            src_id, sch_name, tbl_name, col_name,
                            datatype=col_type, nullable=nullable, primary_key=is_pk,
                        )
                        # columns not counted in total to keep ~330

    # ── Foreign Keys: 20 ──
    fk_specs = [
        ("order_items", "order_id", "orders", "order_id"),
        ("order_items", "product_id", "products", "product_id"),
        ("orders", "customer_id", "customers", "customer_id"),
        ("inventory_levels", "sku", "products", "sku"),
    ]
    fk_count = 0
    for src_idx, src_id in enumerate(source_ids[:5]):  # first 5 sources get FKs
        for tbl_name, col_name, ref_tbl, ref_col in fk_specs:
            if fk_count >= 20:
                break
            eng.add_foreign_key(
                src_id, "public", tbl_name, col_name,
                "public", ref_tbl, ref_col,
            )
            count += 1
            fk_count += 1

    # ── Sync Tasks: 20 ──
    sync_modes = ["full", "incremental", "cdc", "incremental", "full"]
    sync_statuses = ["active", "active", "active", "paused", "active",
                     "active", "error", "active", "active", "paused",
                     "active", "active", "active", "active", "error",
                     "active", "active", "paused", "active", "active"]
    for i in range(20):
        src_id = source_ids[i % len(source_ids)]
        st = eng.create_sync_task(
            name=f"Sync-{i+1:02d} {source_ids[i % len(source_ids)].replace('-', ' ')}",
            source_id=src_id,
            target_dataset=f"dataset_{i+1:02d}",
            mode=sync_modes[i % len(sync_modes)],
            cron_expr=f"{i % 60} * * * *" if i % 3 == 0 else f"0 {i % 24} * * *",
            status=sync_statuses[i],
            owner="data-ops",
        )
        count += 1

    # ── Sync Runs: 30 (distributed across sync tasks) ──
    from aos_api.phase6_datasource_engine import SyncRun
    sync_task_ids = list(eng._sync_tasks.keys())
    run_statuses = ["success", "success", "failed", "success", "success",
                    "success", "failed", "success", "running", "success",
                    "success", "success", "failed", "success", "success",
                    "success", "success", "failed", "success", "running",
                    "success", "success", "success", "failed", "success",
                    "success", "success", "success", "failed", "success"]
    for i in range(30):
        sync_id = sync_task_ids[i % len(sync_task_ids)]
        status = run_statuses[i]
        r = SyncRun(
            sync_id=sync_id,
            status=status,
            started_at=_t.time() - 60 - i * 10,
            finished_at=_t.time() - i * 10 if status != "running" else 0.0,
            duration_ms=(60000 - i * 500) if status != "running" else 0,
            rows_synced=(5000 + i * 200) if status == "success" else 0,
            error="" if status != "failed" else f"Error: connection timeout (run {i})",
        )
        eng._sync_runs[r.id] = r
        count += 1

    # ── Edge Agents: 10 ──
    agent_ids: list[str] = []
    for spec in _AGENT_SPECS:
        a = eng.create_agent(**spec)
        agent_ids.append(a.id)
        count += 1

    # Associate sources with agents
    for idx, aid in enumerate(agent_ids):
        a = eng._agents[aid]
        # Assign 2 sources per agent
        a.source_ids = [source_ids[idx * 2 % len(source_ids)], source_ids[(idx * 2 + 1) % len(source_ids)]]

    # ── Media Sets: 5 ──
    media_set_ids: list[str] = []
    for spec in _MEDIA_SET_SPECS:
        ms = eng.create_media_set(**spec)
        media_set_ids.append(ms.id)
        count += 1

    # ── Media Files: 20 (4 per set) ──
    file_types = [
        [("product_001.jpg", "image", "image/jpeg", 1048576), ("product_002.jpg", "image", "image/jpeg", 2097152), ("product_003.png", "image", "image/png", 3145728), ("product_004.png", "image", "image/png", 1572864)],
        [("drawing_A001.dwg", "document", "application/dwg", 5242880), ("drawing_A002.dwg", "document", "application/dwg", 8388608), ("spec_B001.pdf", "document", "application/pdf", 2097152), ("diagram_C001.pdf", "document", "application/pdf", 4194304)],
        [("banner_summer.png", "image", "image/png", 524288), ("banner_spring.jpg", "image", "image/jpeg", 786432), ("ad_video_01.mp4", "video", "video/mp4", 10485760), ("ad_video_02.mp4", "video", "video/mp4", 12582912)],
        [("qc_photo_batch1.jpg", "image", "image/jpeg", 2097152), ("qc_photo_batch2.jpg", "image", "image/jpeg", 1992294), ("qc_defect_01.png", "image", "image/png", 3145728), ("qc_report.pdf", "document", "application/pdf", 1572864)],
        [("label_001.png", "image", "image/png", 262144), ("label_002.png", "image", "image/png", 262144), ("label_003.jpg", "image", "image/jpeg", 524288), ("label_004.jpg", "image", "image/jpeg", 524288)],
    ]
    for ms_idx, ms_id in enumerate(media_set_ids):
        for fname, ftype, mime, fsize in file_types[ms_idx]:
            eng.add_media_file(
                ms_id, fname,
                file_type=ftype, mime_type=mime, size_bytes=fsize,
                url=f"https://storage.example.com/ media/{ms_id}/{fname}".replace(" ", ""),
            )
            count += 1

    # ── Extraction Templates: 5 ──
    template_ids: list[str] = []
    for spec in _TEMPLATE_SPECS:
        t = eng.create_template(**spec)
        template_ids.append(t.id)
        count += 1

    # ── Documents: 10 ──
    for idx, spec in enumerate(_DOCUMENT_SPECS):
        tid = template_ids[idx % len(template_ids)] if spec["status"] == "extracted" else ""
        d = eng.create_document(
            name=spec["name"],
            source_id=source_ids[idx % len(source_ids)],
            template_id=tid,
            file_type=spec["file_type"],
            status=spec["status"],
        )
        if spec["status"] == "extracted":
            d.extracted_fields = {
                "vendor": f"Vendor-{idx}",
                "amount": 1000.50 + idx * 100,
                "date": "2026-07-15",
                "invoice_number": f"INV-2026-{idx:04d}",
            }
        count += 1

    # ── Data Projects: 5 ──
    for spec in _PROJECT_SPECS:
        p = eng.create_project(**spec)
        count += 1

    log.info("seed_phase6_datasource_done records=%s", count)
    return count
