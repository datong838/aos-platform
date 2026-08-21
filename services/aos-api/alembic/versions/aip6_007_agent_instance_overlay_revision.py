"""Add versioned AgentInstance prompt/tools overlay authority.

Revision ID: aip6_007
Revises: aip10_006
Create Date: 2026-08-19
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "aip6_007"
down_revision: str | Sequence[str] | None = "aip10_006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_agent_instance_overlay_revision (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          instance_id TEXT NOT NULL,
          revision INTEGER NOT NULL,
          prompt TEXT NOT NULL DEFAULT '',
          tools_json JSONB NOT NULL DEFAULT '[]'::jsonb,
          content_hash TEXT NOT NULL,
          created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, instance_id, revision),
          CHECK (revision >= 1),
          CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (jsonb_typeof(tools_json) = 'array'),
          FOREIGN KEY (org_id, project_id, instance_id)
            REFERENCES aip_agent_instance(org_id, project_id, instance_id)
        )"""
    )
    op.execute(
        """CREATE INDEX idx_aip_agent_overlay_latest
        ON aip_agent_instance_overlay_revision
          (org_id, project_id, instance_id, revision DESC)"""
    )
    op.execute("ALTER TABLE aip_agent_instance_overlay_revision ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_agent_instance_overlay_revision FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_aip_agent_instance_overlay_revision
        ON aip_agent_instance_overlay_revision TO aos_runtime
        USING (org_id = NULLIF(current_setting('aos.org_id', true), '')
          AND project_id = NULLIF(current_setting('aos.project_id', true), ''))
        WITH CHECK (org_id = NULLIF(current_setting('aos.org_id', true), '')
          AND project_id = NULLIF(current_setting('aos.project_id', true), ''))"""
    )
    op.execute(
        "GRANT SELECT, INSERT ON aip_agent_instance_overlay_revision TO aos_runtime"
    )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM aip_agent_instance_overlay_revision) THEN
            RAISE EXCEPTION 'AIP6_007_DOWNGRADE_REQUIRES_EMPTY_OVERLAY_AUTHORITY'
              USING ERRCODE='55000';
          END IF;
        END $$"""
    )
    op.execute("DROP TABLE aip_agent_instance_overlay_revision")
