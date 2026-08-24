"""Add tenant-safe canonical aftersales original events.

Revision ID: d0_after_001
Revises: w3_012
Create Date: 2026-08-24
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "d0_after_001"
down_revision: str | Sequence[str] | None = "w3_012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE ecommerce_aftersale_event (
        org_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        event_id TEXT NOT NULL,
        source_revision BIGINT NOT NULL,
        source_hash TEXT NOT NULL,
        event_type TEXT NOT NULL,
        status TEXT NOT NULL,
        occurred_at TIMESTAMPTZ NOT NULL,
        order_resource_id TEXT NOT NULL,
        order_revision BIGINT NOT NULL,
        order_content_hash TEXT NOT NULL,
        order_line_resource_id TEXT,
        order_line_revision BIGINT,
        order_line_content_hash TEXT,
        ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(org_id,project_id,event_id,source_revision),
        CHECK(source_revision>=1),
        CHECK(order_revision>=1),
        CHECK(source_hash ~ '^[0-9a-f]{64}$'),
        CHECK(order_content_hash ~ '^[0-9a-f]{64}$'),
        CHECK(event_type<>''),
        CHECK(status<>''),
        CHECK(
          (order_line_resource_id IS NULL AND order_line_revision IS NULL
            AND order_line_content_hash IS NULL)
          OR
          (order_line_resource_id IS NOT NULL AND order_line_revision>=1
            AND order_line_content_hash ~ '^[0-9a-f]{64}$')
        ))"""
    )
    op.execute("ALTER TABLE ecommerce_aftersale_event ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ecommerce_aftersale_event FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_ecommerce_aftersale_event_d0_after_001
        ON ecommerce_aftersale_event TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute("GRANT SELECT,INSERT ON ecommerce_aftersale_event TO aos_runtime")
    op.execute(
        "REVOKE UPDATE,DELETE,TRUNCATE ON ecommerce_aftersale_event FROM aos_runtime"
    )
    op.execute(
        """CREATE TRIGGER trg_ecommerce_aftersale_event_append_only
        BEFORE UPDATE OR DELETE ON ecommerce_aftersale_event
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        """CREATE TRIGGER trg_ecommerce_aftersale_event_truncate_guard
        BEFORE TRUNCATE ON ecommerce_aftersale_event
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        """CREATE INDEX ecommerce_aftersale_event_cutoff_idx
        ON ecommerce_aftersale_event(
          org_id,project_id,occurred_at DESC,event_id DESC,source_revision DESC
        )"""
    )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM ecommerce_aftersale_event LIMIT 1) THEN
          RAISE EXCEPTION 'cannot downgrade d0_after_001: canonical aftersales originals exist'
            USING ERRCODE = '55000';
        END IF;
        END $$"""
    )
    op.execute("DROP TABLE ecommerce_aftersale_event CASCADE")
