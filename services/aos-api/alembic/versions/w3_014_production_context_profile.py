"""Retain exact ProductionProfile provenance on ProductionContext (W3-04).

Revision ID: w3_014
Revises: w4_001
Create Date: 2026-08-24
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w3_014"
down_revision: str | Sequence[str] | None = "w4_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """ALTER TABLE aip_production_context_revision
        ADD COLUMN production_profile_ref JSONB,
        ADD CONSTRAINT aip_production_context_profile_ref_object
        CHECK(production_profile_ref IS NULL OR jsonb_typeof(production_profile_ref)='object')"""
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE aip_production_context_revision DROP CONSTRAINT "
        "IF EXISTS aip_production_context_profile_ref_object"
    )
    op.execute(
        "ALTER TABLE aip_production_context_revision DROP COLUMN IF EXISTS production_profile_ref"
    )
