"""TI-6 2B contract remaining Workshop and TWA scoped identities.

Revision ID: 228ti6bcontract
Revises: 228ti5b1models
Create Date: 2026-08-05
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti6bcontract"
down_revision: str | Sequence[str] | None = "228ti5b1models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKSHOP_TABLES = ("theme", "widget_catalog")
TWA_TABLES = ("twa_audit", "twa_invite", "twa_join_request")
ALL_TABLES = (*WORKSHOP_TABLES, *TWA_TABLES)
LEGACY_KEYS = {
    "theme": "id",
    "widget_catalog": "id",
    "twa_audit": "id",
    "twa_invite": "token",
    "twa_join_request": "id",
}


def upgrade() -> None:
    # Workshop catalog tables historically came from request-time ensure_schema.
    # Make the contract migration self-contained for a fresh database.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS theme (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          mode TEXT NOT NULL DEFAULT 'light',
          is_preset BOOLEAN NOT NULL DEFAULT FALSE,
          tokens JSONB NOT NULL DEFAULT '{}'::jsonb,
          description TEXT NOT NULL DEFAULT '',
          org_id TEXT NOT NULL DEFAULT 'dev-org',
          project_id TEXT NOT NULL DEFAULT 'dev-project',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS widget_catalog (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          name_zh TEXT NOT NULL DEFAULT '',
          type TEXT NOT NULL DEFAULT 'unknown',
          source TEXT NOT NULL DEFAULT 'builtin',
          category TEXT NOT NULL DEFAULT 'general',
          icon TEXT NOT NULL DEFAULT '',
          description TEXT NOT NULL DEFAULT '',
          config_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
          version TEXT NOT NULL DEFAULT '1.0.0',
          installed BOOLEAN NOT NULL DEFAULT TRUE,
          org_id TEXT NOT NULL DEFAULT 'dev-org',
          project_id TEXT NOT NULL DEFAULT 'dev-project',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    for table in ALL_TABLES:
        legacy_key = LEGACY_KEYS[table]
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey "
            f"PRIMARY KEY (org_id, project_id, {legacy_key})"
        )
        if table in TWA_TABLES:
            op.execute(
                f"ALTER TABLE {table} ADD CONSTRAINT uq_{table}_{legacy_key}_ti6 "
                f"UNIQUE ({legacy_key})"
            )
        parent = "meta_workspace" if table in WORKSHOP_TABLES else "twa_workspace"
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_workspace_ti6 "
            f"FOREIGN KEY (org_id, project_id) REFERENCES {parent}(org_id, project_id) "
            "NOT VALID"
        )
        op.execute(
            f"ALTER TABLE {table} VALIDATE CONSTRAINT fk_{table}_workspace_ti6"
        )

    predicate = (
        "org_id = current_setting('aos.org_id', true) AND "
        "project_id = current_setting('aos.project_id', true)"
    )
    for table in WORKSHOP_TABLES:
        op.execute(
            f"CREATE POLICY tenant_scope_{table}_ti6 ON {table} FOR ALL TO aos_runtime "
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(WORKSHOP_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_scope_{table}_ti6 ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    for table in reversed(ALL_TABLES):
        legacy_key = LEGACY_KEYS[table]
        op.execute(
            f"DO $guard$ BEGIN IF EXISTS (SELECT 1 FROM {table} "
            f"GROUP BY {legacy_key} HAVING COUNT(*) > 1) THEN "
            f"RAISE EXCEPTION 'TI-6 2B downgrade blocked by {table} legacy key collision' "
            "USING ERRCODE='23505'; END IF; END $guard$;"
        )
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT fk_{table}_workspace_ti6"
        )
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        if table in TWA_TABLES:
            op.execute(
                f"ALTER TABLE {table} DROP CONSTRAINT uq_{table}_{legacy_key}_ti6"
            )
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey PRIMARY KEY ({legacy_key})"
        )
