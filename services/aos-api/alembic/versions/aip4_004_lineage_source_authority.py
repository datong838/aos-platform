"""Bind AIP lineage facts to immutable authority source events.

Revision ID: aip4_004
Revises: aip4_003
Create Date: 2026-08-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip4_004"
down_revision: str | Sequence[str] | None = "aip4_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE aip_lineage_event ADD COLUMN source_kind TEXT")
    op.execute("ALTER TABLE aip_lineage_event ADD COLUMN source_id TEXT")
    op.execute("ALTER TABLE aip_lineage_event ADD COLUMN source_hash TEXT")
    op.execute(
        """ALTER TABLE aip_lineage_event ADD CONSTRAINT aip_lineage_event_source_kind_check
        CHECK (source_kind IS NULL OR source_kind IN (
          'task_run','step_run','checkpoint','artifact','evidence',
          'action_event','action_receipt','eval_run','eval_run_event',
          'eval_report','publication_event'
        ))"""
    )
    op.execute(
        """ALTER TABLE aip_lineage_event ADD CONSTRAINT aip_lineage_event_source_hash_check
        CHECK (source_hash IS NULL OR length(source_hash)=64)"""
    )
    op.execute(
        """ALTER TABLE aip_lineage_event ADD CONSTRAINT aip_lineage_event_source_tuple_check
        CHECK ((source_kind IS NULL AND source_id IS NULL AND source_hash IS NULL)
            OR (source_kind IS NOT NULL AND source_id IS NOT NULL AND source_hash IS NOT NULL))"""
    )
    op.execute(
        """CREATE UNIQUE INDEX aip_lineage_event_source_uq
        ON aip_lineage_event(org_id,project_id,source_kind,source_id)
        WHERE source_kind IS NOT NULL"""
    )
    op.execute(
        """CREATE INDEX aip_lineage_event_root_timeline_idx
        ON aip_lineage_event(org_id,project_id,root_type,root_id,sequence,event_id)"""
    )
    op.execute(
        "ALTER TABLE aip_lineage_event DROP CONSTRAINT IF EXISTS aip_lineage_event_root_type_check"
    )
    op.execute(
        """ALTER TABLE aip_lineage_event ADD CONSTRAINT aip_lineage_event_root_type_check
        CHECK (root_type IN (
          'task_run','action','eval_run','publication','research_job',
          'legacy_decision_lineage'
        ))"""
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS aip_lineage_event_root_timeline_idx")
    op.execute("DROP INDEX IF EXISTS aip_lineage_event_source_uq")
    op.execute(
        "ALTER TABLE aip_lineage_event DROP CONSTRAINT IF EXISTS aip_lineage_event_source_tuple_check"
    )
    op.execute(
        "ALTER TABLE aip_lineage_event DROP CONSTRAINT IF EXISTS aip_lineage_event_source_hash_check"
    )
    op.execute(
        "ALTER TABLE aip_lineage_event DROP CONSTRAINT IF EXISTS aip_lineage_event_source_kind_check"
    )
    op.execute(
        "ALTER TABLE aip_lineage_event DROP CONSTRAINT IF EXISTS aip_lineage_event_root_type_check"
    )
    op.execute(
        """ALTER TABLE aip_lineage_event ADD CONSTRAINT aip_lineage_event_root_type_check
        CHECK (root_type IN (
          'task_run','action','research_job','legacy_decision_lineage'
        ))"""
    )
    op.execute("ALTER TABLE aip_lineage_event DROP COLUMN IF EXISTS source_hash")
    op.execute("ALTER TABLE aip_lineage_event DROP COLUMN IF EXISTS source_id")
    op.execute("ALTER TABLE aip_lineage_event DROP COLUMN IF EXISTS source_kind")
