"""Retain ProductionContext provenance across preview and start decision (W3-05).

Revision ID: w3_015
Revises: w3_014
Create Date: 2026-08-24
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w3_015"
down_revision: str | Sequence[str] | None = "w3_014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """ALTER TABLE aip_impact_preview_revision
        ADD COLUMN production_context_ref JSONB,
        ADD CONSTRAINT aip_impact_preview_context_ref_object
        CHECK(production_context_ref IS NULL OR jsonb_typeof(production_context_ref)='object')"""
    )
    op.execute(
        """ALTER TABLE aip_production_start_decision
        ADD COLUMN production_context_ref JSONB,
        ADD CONSTRAINT aip_start_decision_context_ref_object
        CHECK(production_context_ref IS NULL OR jsonb_typeof(production_context_ref)='object')"""
    )


def downgrade() -> None:
    op.execute(
        """ALTER TABLE aip_production_start_decision
        DROP CONSTRAINT IF EXISTS aip_start_decision_context_ref_object,
        DROP COLUMN IF EXISTS production_context_ref"""
    )
    op.execute(
        """ALTER TABLE aip_impact_preview_revision
        DROP CONSTRAINT IF EXISTS aip_impact_preview_context_ref_object,
        DROP COLUMN IF EXISTS production_context_ref"""
    )
