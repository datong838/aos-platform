"""TI-4 A1 contract Apollo Spoke tenant instances.

Revision ID: 228ti4a1apollo
Revises: 228ti4c3contract
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti4a1apollo"
down_revision: str | Sequence[str] | None = "228ti4c3contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POLICY = "tenant_scope_apollo_spoke_ti4a1"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS apollo_channel (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'open',
          rank INT NOT NULL DEFAULT 0,
          promoted_from TEXT,
          promoted_at TIMESTAMPTZ,
          recalled_from TEXT,
          recalled_at TIMESTAMPTZ,
          meta JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS apollo_spoke (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          kind TEXT NOT NULL DEFAULT 'lite',
          channel_id TEXT NOT NULL REFERENCES apollo_channel(id),
          version TEXT NOT NULL DEFAULT '0.3.0-dev',
          status TEXT NOT NULL DEFAULT 'online',
          heartbeat_ok BOOLEAN NOT NULL DEFAULT TRUE,
          hub TEXT NOT NULL DEFAULT 'dev-hub',
          runtime TEXT NOT NULL DEFAULT 'compose',
          org_id TEXT NOT NULL DEFAULT 'dev-org',
          meta JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    op.execute("ALTER TABLE apollo_spoke ADD COLUMN IF NOT EXISTS project_id TEXT")
    op.execute(
        "UPDATE apollo_spoke SET org_id='dev-org',project_id='dev-project' "
        "WHERE id IN ('spoke-local-dev','spoke-full-stub')"
    )
    op.execute(
        """
        DO $check$ BEGIN
          IF EXISTS (SELECT 1 FROM apollo_spoke WHERE project_id IS NULL) THEN
            RAISE EXCEPTION 'TI-4 A1 unknown Apollo Spoke ownership';
          END IF;
        END $check$
        """
    )
    op.execute("ALTER TABLE apollo_spoke ALTER COLUMN project_id SET NOT NULL")
    op.execute("ALTER TABLE apollo_spoke DROP CONSTRAINT apollo_spoke_pkey")
    op.execute(
        "ALTER TABLE apollo_spoke ADD CONSTRAINT apollo_spoke_pkey "
        "PRIMARY KEY (org_id,project_id,id)"
    )
    op.execute(
        "ALTER TABLE apollo_spoke ADD CONSTRAINT fk_apollo_spoke_workspace_ti4a1 "
        "FOREIGN KEY (org_id,project_id) "
        "REFERENCES twa_workspace(org_id,project_id)"
    )
    op.execute(
        f"CREATE POLICY {POLICY} ON apollo_spoke FOR ALL TO PUBLIC "
        "USING (org_id=current_setting('aos.org_id',true) "
        "AND project_id=current_setting('aos.project_id',true)) "
        "WITH CHECK (org_id=current_setting('aos.org_id',true) "
        "AND project_id=current_setting('aos.project_id',true))"
    )
    op.execute("ALTER TABLE apollo_spoke ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE apollo_spoke FORCE ROW LEVEL SECURITY")
    op.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON apollo_spoke TO aos_runtime")
    op.execute("GRANT SELECT,UPDATE ON apollo_channel TO aos_runtime")


def downgrade() -> None:
    op.execute(
        """
        DO $check$ BEGIN
          IF EXISTS (
            SELECT id FROM apollo_spoke GROUP BY id HAVING COUNT(*) > 1
          ) THEN
            RAISE EXCEPTION 'TI-4 A1 downgrade blocked by scoped id collision';
          END IF;
        END $check$
        """
    )
    op.execute(f"DROP POLICY IF EXISTS {POLICY} ON apollo_spoke")
    op.execute("ALTER TABLE apollo_spoke NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE apollo_spoke DISABLE ROW LEVEL SECURITY")
    op.execute(
        "ALTER TABLE apollo_spoke DROP CONSTRAINT fk_apollo_spoke_workspace_ti4a1"
    )
    op.execute("ALTER TABLE apollo_spoke DROP CONSTRAINT apollo_spoke_pkey")
    op.execute(
        "ALTER TABLE apollo_spoke ADD CONSTRAINT apollo_spoke_pkey PRIMARY KEY (id)"
    )
    op.execute("ALTER TABLE apollo_spoke DROP COLUMN project_id")
