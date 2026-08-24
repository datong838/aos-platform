"""Persist exact external-Action Preview and Proposal binding lineage.

Revision ID: w5_001
Revises: w4_003
Create Date: 2026-08-25
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w5_001"
down_revision: str | Sequence[str] | None = "w4_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """ALTER TABLE aip_impact_preview_revision
        ADD COLUMN external_action_binding JSONB,
        ADD CONSTRAINT ck_aip_impact_preview_external_binding_w5_001
        CHECK(external_action_binding IS NULL
          OR jsonb_typeof(external_action_binding)='object')"""
    )
    op.execute(
        """ALTER TABLE aip_action_proposal
        ADD COLUMN action_binding_hash TEXT,
        ADD CONSTRAINT ck_aip_action_proposal_binding_hash_w5_001
        CHECK(action_binding_hash IS NULL
          OR action_binding_hash ~ '^[0-9a-f]{64}$')"""
    )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN IF EXISTS (
          SELECT 1 FROM aip_impact_preview_revision
          WHERE external_action_binding IS NOT NULL LIMIT 1
        ) OR EXISTS (
          SELECT 1 FROM aip_action_proposal
          WHERE action_binding_hash IS NOT NULL LIMIT 1
        ) THEN RAISE EXCEPTION 'cannot downgrade w5_001 with Action binding facts'
          USING ERRCODE='55000'; END IF; END $$"""
    )
    op.execute(
        """ALTER TABLE aip_action_proposal
        DROP CONSTRAINT IF EXISTS ck_aip_action_proposal_binding_hash_w5_001,
        DROP COLUMN IF EXISTS action_binding_hash"""
    )
    op.execute(
        """ALTER TABLE aip_impact_preview_revision
        DROP CONSTRAINT IF EXISTS ck_aip_impact_preview_external_binding_w5_001,
        DROP COLUMN IF EXISTS external_action_binding"""
    )
