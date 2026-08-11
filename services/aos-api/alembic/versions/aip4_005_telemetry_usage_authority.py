"""Persist tenant-scoped telemetry spans and honest usage quantities.

Revision ID: aip4_005
Revises: aip4_004
Create Date: 2026-08-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip4_005"
down_revision: str | Sequence[str] | None = "aip4_004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_telemetry_span (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          span_record_id TEXT NOT NULL, provider TEXT NOT NULL,
          provider_receipt_id TEXT NOT NULL, lineage_id TEXT NOT NULL,
          trace_id TEXT NOT NULL, span_id TEXT NOT NULL, parent_span_id TEXT,
          name TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL,
          producer_started_at TIMESTAMPTZ NOT NULL,
          producer_ended_at TIMESTAMPTZ, observed_at TIMESTAMPTZ NOT NULL,
          ingested_at TIMESTAMPTZ NOT NULL, attributes_hash TEXT NOT NULL,
          source_hash TEXT NOT NULL, quality TEXT NOT NULL,
          PRIMARY KEY (org_id,project_id,span_record_id),
          UNIQUE (org_id,project_id,provider,provider_receipt_id),
          CHECK (kind IN ('internal','server','client','producer','consumer','model','tool')),
          CHECK (status IN ('unset','ok','error')),
          CHECK (quality IN ('measured','estimated','unknown')),
          CHECK (length(attributes_hash)=64), CHECK (length(source_hash)=64),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE INDEX aip_telemetry_span_lineage_timeline_idx
        ON aip_telemetry_span(org_id,project_id,lineage_id,producer_started_at,span_record_id)"""
    )
    op.execute(
        """CREATE INDEX aip_telemetry_span_trace_timeline_idx
        ON aip_telemetry_span(org_id,project_id,trace_id,producer_started_at,span_record_id)"""
    )
    op.execute("ALTER TABLE aip_telemetry_span ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_telemetry_span FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_aip_telemetry_span_aip4
        ON aip_telemetry_span TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_telemetry_span_append_only
        BEFORE UPDATE OR DELETE ON aip_telemetry_span
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_telemetry_span_truncate_guard
        BEFORE TRUNCATE ON aip_telemetry_span
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute("GRANT SELECT,INSERT ON aip_telemetry_span TO aos_runtime")
    op.execute("ALTER TABLE aip_usage_receipt ALTER COLUMN quantity DROP NOT NULL")
    op.execute(
        "ALTER TABLE aip_usage_receipt DROP CONSTRAINT aip_usage_receipt_quantity_check"
    )
    op.execute(
        """ALTER TABLE aip_usage_receipt
        ADD CONSTRAINT aip_usage_receipt_quantity_quality_check CHECK (
          (quality='unknown' AND quantity IS NULL)
          OR (quality IN ('measured','estimated') AND quantity IS NOT NULL AND quantity>=0)
        )"""
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE aip_usage_receipt DROP CONSTRAINT IF EXISTS aip_usage_receipt_quantity_quality_check"
    )
    op.execute(
        "ALTER TABLE aip_usage_receipt ADD CONSTRAINT aip_usage_receipt_quantity_check CHECK (quantity>=0)"
    )
    op.execute("ALTER TABLE aip_usage_receipt ALTER COLUMN quantity SET NOT NULL")
    op.execute("DROP TABLE IF EXISTS aip_telemetry_span")
