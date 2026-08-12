"""Add immutable schedule events for AIP memory pipelines.

Revision ID: aip5_003
Revises: aip5_002
Create Date: 2026-08-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "aip5_003"
down_revision: str | Sequence[str] | None = "aip5_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_memory_pipeline_schedule_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          event_id TEXT NOT NULL, schedule_id TEXT NOT NULL,
          sequence BIGINT NOT NULL, event_type TEXT NOT NULL,
          from_status TEXT, to_status TEXT NOT NULL,
          schedule_version BIGINT NOT NULL, reason_code TEXT NOT NULL,
          dependency_review_ref JSONB, event_hash TEXT NOT NULL,
          actor TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,event_id),
          UNIQUE (org_id,project_id,schedule_id,sequence),
          CHECK (sequence >= 1), CHECK (schedule_version >= 1),
          CHECK (from_status IS NULL OR from_status IN ('active','paused','disabled')),
          CHECK (to_status IN ('active','paused','disabled')),
          CHECK (event_type IN ('created','transitioned')),
          CHECK (event_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY (org_id,project_id,schedule_id)
            REFERENCES aip_memory_pipeline_schedule(org_id,project_id,schedule_id)
        )"""
    )
    op.execute(
        """CREATE INDEX aip_memory_pipeline_schedule_event_timeline_idx
        ON aip_memory_pipeline_schedule_event
          (org_id,project_id,schedule_id,sequence,event_id)"""
    )
    op.execute(
        """ALTER TABLE aip_memory_pipeline_schedule_event
        ENABLE ROW LEVEL SECURITY"""
    )
    op.execute(
        """ALTER TABLE aip_memory_pipeline_schedule_event
        FORCE ROW LEVEL SECURITY"""
    )
    op.execute(
        """CREATE POLICY tenant_scope_aip_memory_pipeline_schedule_event_aip5
        ON aip_memory_pipeline_schedule_event TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_memory_pipeline_schedule_event_append_only
        BEFORE UPDATE OR DELETE ON aip_memory_pipeline_schedule_event
        FOR EACH ROW EXECUTE FUNCTION guard_aip5_memory_append_only()"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_memory_pipeline_schedule_event_truncate_guard
        BEFORE TRUNCATE ON aip_memory_pipeline_schedule_event
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip5_memory_append_only()"""
    )
    op.execute(
        "GRANT SELECT,INSERT ON aip_memory_pipeline_schedule_event TO aos_runtime"
    )
    op.execute(
        """CREATE TABLE aip_memory_pipeline_run_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          event_id TEXT NOT NULL, pipeline_run_id TEXT NOT NULL,
          sequence BIGINT NOT NULL, event_type TEXT NOT NULL,
          from_status TEXT, to_status TEXT NOT NULL,
          run_version BIGINT NOT NULL, reason_code TEXT NOT NULL,
          lease_owner TEXT, event_hash TEXT NOT NULL,
          actor TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,event_id),
          UNIQUE (org_id,project_id,pipeline_run_id,sequence),
          CHECK (sequence >= 1), CHECK (run_version >= 1),
          CHECK (from_status IS NULL OR from_status IN
            ('queued','running','paused','succeeded','partial','failed','cancelled','unknown')),
          CHECK (to_status IN
            ('queued','running','paused','succeeded','partial','failed','cancelled','unknown')),
          CHECK (event_type IN
            ('enqueued','claimed','paused','resumed','completed','lease_expired')),
          CHECK (event_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY (org_id,project_id,pipeline_run_id)
            REFERENCES aip_memory_pipeline_run(org_id,project_id,pipeline_run_id)
        )"""
    )
    op.execute(
        """CREATE INDEX aip_memory_pipeline_run_event_timeline_idx
        ON aip_memory_pipeline_run_event
          (org_id,project_id,pipeline_run_id,sequence,event_id)"""
    )
    op.execute(
        "ALTER TABLE aip_memory_pipeline_run_event ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE aip_memory_pipeline_run_event FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """CREATE POLICY tenant_scope_aip_memory_pipeline_run_event_aip5
        ON aip_memory_pipeline_run_event TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_memory_pipeline_run_event_append_only
        BEFORE UPDATE OR DELETE ON aip_memory_pipeline_run_event
        FOR EACH ROW EXECUTE FUNCTION guard_aip5_memory_append_only()"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_memory_pipeline_run_event_truncate_guard
        BEFORE TRUNCATE ON aip_memory_pipeline_run_event
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip5_memory_append_only()"""
    )
    op.execute("GRANT SELECT,INSERT ON aip_memory_pipeline_run_event TO aos_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_memory_pipeline_run_event")
    op.execute("DROP TABLE IF EXISTS aip_memory_pipeline_schedule_event")
