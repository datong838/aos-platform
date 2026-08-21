"""Add guardrails_json to AgentInstance overlay revision authority.

Revision ID: aip6_008
Revises: aip6_007
Create Date: 2026-08-19
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "aip6_008"
down_revision: str | Sequence[str] | None = "aip6_007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """ALTER TABLE aip_agent_instance_overlay_revision
           ADD COLUMN IF NOT EXISTS guardrails_json JSONB NOT NULL DEFAULT '[]'::jsonb"""
    )
    op.execute(
        """ALTER TABLE aip_agent_instance_overlay_revision
           DROP CONSTRAINT IF EXISTS aip_agent_overlay_guardrails_array_chk"""
    )
    op.execute(
        """ALTER TABLE aip_agent_instance_overlay_revision
           ADD CONSTRAINT aip_agent_overlay_guardrails_array_chk
           CHECK (jsonb_typeof(guardrails_json) = 'array')"""
    )


def downgrade() -> None:
    op.execute(
        """ALTER TABLE aip_agent_instance_overlay_revision
           DROP CONSTRAINT IF EXISTS aip_agent_overlay_guardrails_array_chk"""
    )
    op.execute(
        """ALTER TABLE aip_agent_instance_overlay_revision
           DROP COLUMN IF EXISTS guardrails_json"""
    )
