"""Phase 5 seed · Pipeline core — 10 pipelines + 20 nodes + 15 edges + 10 proposals + 15 schedules + 10 runs + 10 datasets + 5 builds (≈95)."""
from __future__ import annotations

from aos_api.phase5_pipeline_engine import get_engine
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_phase5_pipeline")

# ── Pipeline specs (10) ──
_PIPELINES: list[dict] = [
    {"name": "Customer 360 ETL", "description": "Extract customer data from CRM and load to warehouse", "pipeline_type": "ETL", "status": "active", "owner": "data-team", "tags": ["customer", "crm"]},
    {"name": "Orders ELT Pipeline", "description": "Load raw orders then transform in warehouse", "pipeline_type": "ELT", "status": "active", "owner": "data-team", "tags": ["orders"]},
    {"name": "Real-time Events Stream", "description": "Stream user click events through Kafka", "pipeline_type": "Streaming", "status": "scheduled", "owner": "platform", "tags": ["events", "kafka"]},
    {"name": "Nightly Batch Rollup", "description": "Batch daily sales rollup", "pipeline_type": "Batch", "status": "scheduled", "owner": "analytics", "tags": ["sales", "batch"]},
    {"name": "Product Catalog Sync", "description": "Sync product catalog from PIM", "pipeline_type": "ETL", "status": "active", "owner": "catalog-team", "tags": ["product"]},
    {"name": "LLM Sentiment Enrichment", "description": "Enrich customer feedback with LLM sentiment", "pipeline_type": "ETL", "status": "active", "owner": "ai-team", "tags": ["llm", "sentiment"]},
    {"name": "Invoice Batch Processor", "description": "Process invoices in nightly batch", "pipeline_type": "Batch", "status": "failed", "owner": "finance", "tags": ["invoice"]},
    {"name": "User Activity Streaming", "description": "Stream user activity logs", "pipeline_type": "Streaming", "status": "draft", "owner": "platform", "tags": ["activity"]},
    {"name": "Inventory ETL", "description": "Extract inventory levels from ERP", "pipeline_type": "ETL", "status": "active", "owner": "ops", "tags": ["inventory"]},
    {"name": "Marketing ELT", "description": "Load marketing campaign data", "pipeline_type": "ELT", "status": "draft", "owner": "marketing", "tags": ["campaign"]},
]

# ── Node specs per pipeline: (name, node_type, x, y) ──
_NODE_SPECS: list[tuple[str, str, float, float]] = [
    ("source_crm", "source", 100, 100),
    ("transform_clean", "transform", 300, 100),
    ("sink_warehouse", "sink", 500, 100),
]


def seed_phase5_pipeline() -> int:
    """Seed Phase 5 pipeline data (~95 records). Returns total record count."""
    eng = get_engine()
    count = 0

    pipeline_ids: list[str] = []
    for spec in _PIPELINES:
        pl = eng.create_pipeline(**spec)
        pipeline_ids.append(pl.id)
        count += 1

    # ── Nodes: 20 (each of 10 pipelines gets 2 nodes) ──
    node_ids_per_pipeline: dict[str, list[str]] = {}
    for idx, pl_id in enumerate(pipeline_ids):
        # Each pipeline gets 2 nodes
        node_specs = [
            ("source_node", "source", 100.0, 100.0 + idx * 50),
            ("sink_node", "sink", 400.0, 100.0 + idx * 50),
        ]
        nids: list[str] = []
        for nm, nt, x, y in node_specs:
            node = eng.add_node(pl_id, nm, node_type=nt, position_x=x, position_y=y,
                                config={"batch_size": 1000} if nt == "source" else {"target": "warehouse"})
            nids.append(node.id)
            count += 1
        node_ids_per_pipeline[pl_id] = nids

    # ── Edges: 15 (connect source->sink for first 8 pipelines, + extra for first 7) ──
    for idx, pl_id in enumerate(pipeline_ids[:8]):
        nids = node_ids_per_pipeline[pl_id]
        if len(nids) >= 2:
            extra = f"Edge-{idx}" if idx < 7 else ""
            eng.add_edge(pl_id, nids[0], nids[1], label=extra)
            count += 1
    # Add 7 more edges for variety (source->transform on first 7)
    for idx, pl_id in enumerate(pipeline_ids[:7]):
        nids = node_ids_per_pipeline[pl_id]
        if len(nids) >= 2:
            eng.add_edge(pl_id, nids[0], nids[1], label="secondary")
            count += 1

    # ── Proposals: 10 ──
    proposal_statuses = ["pending", "approved", "rejected", "discarded", "pending",
                         "approved", "rejected", "pending", "approved", "pending"]
    for idx, pl_id in enumerate(pipeline_ids):
        pp = eng.create_proposal(
            pl_id,
            title=f"Proposal-{idx} optimize flow",
            description=f"Optimization proposal for pipeline {idx}",
            proposed_by="analyst",
            status=proposal_statuses[idx],
            diff_summary=f"+10 -3 lines changed",
        )
        count += 1

    # ── Schedules: 15 ──
    schedule_specs = [
        ("Daily Customer ETL", "cron", "0 2 * * *", "active"),
        ("Hourly Orders ELT", "cron", "0 * * * *", "active"),
        ("Events Stream", "event", "", "active"),
        ("Nightly Rollup", "cron", "0 3 * * *", "active"),
        ("Catalog Sync Hourly", "cron", "30 * * * *", "active"),
        ("Sentiment Enrichment", "cron", "0 4 * * *", "active"),
        ("Invoice Batch", "cron", "0 5 * * *", "error"),
        ("Manual Activity Trigger", "manual", "", "paused"),
        ("Inventory Sync", "cron", "0 6 * * *", "active"),
        ("Marketing Load", "cron", "0 7 * * *", "active"),
        ("Weekly Rollup", "cron", "0 2 * * 1", "active"),
        ("Monthly Audit", "cron", "0 2 1 * *", "paused"),
        ("Event-Driven Catalog", "event", "", "active"),
        ("Real-time Fraud Detect", "event", "", "active"),
        ("Quarterly Archive", "cron", "0 2 1 1,4,7,10 *", "active"),
    ]
    schedule_ids: list[str] = []
    for idx, (nm, tt, cron, st) in enumerate(schedule_specs):
        pl_id = pipeline_ids[idx % len(pipeline_ids)]
        sc = eng.create_schedule(nm, pipeline_id=pl_id, trigger_type=tt, cron_expr=cron, status=st, owner="ops")
        schedule_ids.append(sc.id)
        count += 1

    # ── Schedule runs: 10 ──
    run_statuses = ["success", "success", "failed", "success", "success",
                    "success", "failed", "success", "success", "running"]
    for idx, sc_id in enumerate(schedule_ids[:10]):
        import time as _t
        run = eng._schedule_runs  # access dict
        from aos_api.phase5_pipeline_engine import ScheduleRun
        r = ScheduleRun(
            schedule_id=sc_id,
            status=run_statuses[idx],
            started_at=_t.time() - 60,
            finished_at=_t.time() if run_statuses[idx] != "running" else 0.0,
            duration_ms=60000 if run_statuses[idx] != "running" else 0,
            rows_processed=500 + idx * 100,
            error="" if run_statuses[idx] != "failed" else "Connection timeout",
        )
        eng._schedule_runs[r.id] = r
        count += 1

    # ── Datasets: 10 ──
    dataset_specs = [
        {"name": "customers", "description": "Customer master data", "source_type": "database", "source_uri": "postgres://dw/customers", "schema": [{"name": "customer_id", "datatype": "string"}, {"name": "name", "datatype": "string"}, {"name": "email", "datatype": "string"}, {"name": "revenue", "datatype": "double"}], "row_count": 50000, "size_bytes": 5242880},
        {"name": "orders", "description": "Sales orders", "source_type": "database", "source_uri": "postgres://dw/orders", "schema": [{"name": "order_id", "datatype": "string"}, {"name": "amount", "datatype": "double"}, {"name": "ts", "datatype": "datetime"}], "row_count": 120000, "size_bytes": 10485760},
        {"name": "events", "description": "Click stream events", "source_type": "stream", "source_uri": "kafka://events-topic", "schema": [{"name": "event_id", "datatype": "string"}, {"name": "user_id", "datatype": "string"}, {"name": "event_type", "datatype": "string"}], "row_count": 1000000, "size_bytes": 52428800},
        {"name": "products", "description": "Product catalog", "source_type": "database", "source_uri": "postgres://dw/products", "schema": [{"name": "sku", "datatype": "string"}, {"name": "price", "datatype": "double"}, {"name": "in_stock", "datatype": "boolean"}], "row_count": 8000, "size_bytes": 1048576},
        {"name": "invoices", "description": "Invoice records", "source_type": "file", "source_uri": "s3://bucket/invoices", "schema": [{"name": "invoice_id", "datatype": "string"}, {"name": "amount", "datatype": "double"}], "row_count": 30000, "size_bytes": 3145728},
        {"name": "inventory", "description": "Inventory snapshot", "source_type": "database", "source_uri": "postgres://erp/inventory", "schema": [{"name": "sku", "datatype": "string"}, {"name": "qty", "datatype": "int"}, {"name": "warehouse", "datatype": "string"}], "row_count": 15000, "size_bytes": 1572864},
        {"name": "campaigns", "description": "Marketing campaign metrics", "source_type": "api", "source_uri": "https://api.ads/campaigns", "schema": [{"name": "campaign_id", "datatype": "string"}, {"name": "clicks", "datatype": "int"}, {"name": "spend", "datatype": "double"}], "row_count": 2000, "size_bytes": 262144},
        {"name": "users", "description": "User profiles", "source_type": "database", "source_uri": "postgres://dw/users", "schema": [{"name": "user_id", "datatype": "string"}, {"name": "name", "datatype": "string"}, {"name": "active", "datatype": "boolean"}], "row_count": 75000, "size_bytes": 7864320},
        {"name": "feedback", "description": "Customer feedback text", "source_type": "file", "source_uri": "s3://bucket/feedback", "schema": [{"name": "feedback_id", "datatype": "string"}, {"name": "text", "datatype": "string"}, {"name": "sentiment", "datatype": "string"}], "row_count": 9000, "size_bytes": 4525856},
        {"name": "shipments", "description": "Shipment tracking", "source_type": "database", "source_uri": "postgres://log/shipments", "schema": [{"name": "shipment_id", "datatype": "string"}, {"name": "status", "datatype": "string"}, {"name": "cost", "datatype": "double"}], "row_count": 45000, "size_bytes": 4194304},
    ]
    dataset_ids: list[str] = []
    for spec in dataset_specs:
        ds = eng.create_dataset(**spec)
        dataset_ids.append(ds.id)
        count += 1

    # ── Builds: 5 ──
    import time as _t2
    build_statuses = ["success", "success", "failed", "success", "running"]
    for idx in range(5):
        ds_id = dataset_ids[idx]
        from aos_api.phase5_pipeline_engine import DatasetBuild
        b = DatasetBuild(
            dataset_id=ds_id,
            status=build_statuses[idx],
            started_at=_t2.time() - 300,
            finished_at=_t2.time() if build_statuses[idx] != "running" else 0.0,
            rows_written=10000 + idx * 5000 if build_statuses[idx] == "success" else 0,
            error="" if build_statuses[idx] != "failed" else "Schema mismatch",
        )
        eng._builds[b.id] = b
        count += 1

    log.info("seed_phase5_pipeline_done records=%s", count)
    return count
