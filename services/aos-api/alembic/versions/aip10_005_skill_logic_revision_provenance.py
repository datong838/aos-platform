"""Bind governed published Skills to an exact published LogicRevision.

Revision ID: aip10_005
Revises: aip10_004
Create Date: 2026-08-17
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "aip10_005"
down_revision: str | Sequence[str] | None = "aip10_004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """ALTER TABLE aip_skill_template_revision
        ADD COLUMN logic_revision_ref JSONB,
        ADD CONSTRAINT aip_skill_logic_revision_provenance_chk CHECK (
          (lifecycle='published' AND logic_revision_ref IS NOT NULL)
          OR (lifecycle<>'published' AND logic_revision_ref IS NULL)) NOT VALID,
        ADD CONSTRAINT aip_skill_logic_revision_ref_chk CHECK (
          logic_revision_ref IS NULL OR (
            jsonb_typeof(logic_revision_ref)='object'
            AND logic_revision_ref->>'assetType'='LogicRevision'
            AND NULLIF(logic_revision_ref->>'assetId','') IS NOT NULL
            AND (logic_revision_ref->>'revision')::BIGINT >= 1
            AND logic_revision_ref->>'contentHash' ~ '^[0-9a-f]{64}$'))"""
    )


def downgrade() -> None:
    op.execute(
        """DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM aip_skill_template_revision
            WHERE logic_revision_ref IS NOT NULL
          ) THEN
            RAISE EXCEPTION 'AIP10_005_DOWNGRADE_REQUIRES_NO_LOGIC_BOUND_SKILLS'
              USING ERRCODE='55000';
          END IF;
        END $$"""
    )
    op.execute(
        """ALTER TABLE aip_skill_template_revision
        DROP CONSTRAINT aip_skill_logic_revision_ref_chk,
        DROP CONSTRAINT aip_skill_logic_revision_provenance_chk,
        DROP COLUMN logic_revision_ref"""
    )
