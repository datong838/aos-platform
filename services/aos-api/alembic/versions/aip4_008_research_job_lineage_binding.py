"""Bind every ResearchJob manifest to one exact immutable lineage event.

Revision ID: aip4_008
Revises: aip4_007
Create Date: 2026-08-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip4_008"
down_revision: str | Sequence[str] | None = "aip4_007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing jobs cannot be assigned a lineage event without inventing history.
    op.execute(
        """DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM aip_research_job_manifest) THEN
            RAISE EXCEPTION
              'aip4_008 requires an empty ResearchJob authority; exact lineage cannot be guessed';
          END IF;
        END $$"""
    )
    op.execute(
        """ALTER TABLE aip_lineage_event
        ADD CONSTRAINT uq_aip_lineage_event_exact
        UNIQUE (org_id,project_id,lineage_id,sequence,event_id)"""
    )
    op.execute(
        """ALTER TABLE aip_research_job_manifest
        ADD COLUMN lineage_id TEXT,
        ADD COLUMN lineage_sequence BIGINT,
        ADD COLUMN lineage_event_id TEXT"""
    )
    op.execute(
        """ALTER TABLE aip_research_job_manifest
        ALTER COLUMN lineage_id SET NOT NULL,
        ALTER COLUMN lineage_sequence SET NOT NULL,
        ALTER COLUMN lineage_event_id SET NOT NULL,
        ADD CONSTRAINT aip_research_job_lineage_sequence_check
          CHECK (lineage_sequence >= 1),
        ADD CONSTRAINT fk_aip_research_job_exact_lineage
          FOREIGN KEY (org_id,project_id,lineage_id,lineage_sequence,lineage_event_id)
          REFERENCES aip_lineage_event(org_id,project_id,lineage_id,sequence,event_id)"""
    )


def downgrade() -> None:
    op.execute(
        """ALTER TABLE aip_research_job_manifest
        DROP CONSTRAINT IF EXISTS fk_aip_research_job_exact_lineage,
        DROP CONSTRAINT IF EXISTS aip_research_job_lineage_sequence_check,
        DROP COLUMN IF EXISTS lineage_event_id,
        DROP COLUMN IF EXISTS lineage_sequence,
        DROP COLUMN IF EXISTS lineage_id"""
    )
    op.execute(
        """ALTER TABLE aip_lineage_event
        DROP CONSTRAINT IF EXISTS uq_aip_lineage_event_exact"""
    )
