"""TI-4 D1 expand TenantScope columns and workspace FKs for Data OS.

Revision ID: 228ti4d1expand
Revises: 228ti4c1expand
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti4d1expand"
down_revision: str | Sequence[str] | None = "228ti4c1expand"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DATA_OS_EXPAND_TABLES = (
    "meta_dataset",
    "meta_dataset_history",
    "meta_pipeline",
    "meta_sync",
    "phase5_pipeline_graph",
)

DATA_OS_TENANT_TABLES = (
    *DATA_OS_EXPAND_TABLES,
    "meta_schedule",
    "meta_source",
)

LEGACY_DATA_OS_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS meta_source (
      id TEXT PRIMARY KEY, type TEXT NOT NULL DEFAULT 'file',
      status TEXT NOT NULL DEFAULT 'registered', plugin_id TEXT,
      org_id TEXT NOT NULL DEFAULT 'dev-org',
      project_id TEXT NOT NULL DEFAULT 'dev-project',
      props JSONB NOT NULL DEFAULT '{}'::jsonb,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
    """CREATE TABLE IF NOT EXISTS meta_pipeline (
      id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
      target TEXT NOT NULL DEFAULT 'dataset', dataset_rid TEXT, name TEXT,
      object_type_hint TEXT, last_build JSONB NOT NULL DEFAULT '{}'::jsonb,
      props JSONB NOT NULL DEFAULT '{}'::jsonb,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
    """CREATE TABLE IF NOT EXISTS meta_dataset (
      rid TEXT PRIMARY KEY, name TEXT NOT NULL, display_name TEXT,
      pipeline_id TEXT, source_id TEXT, status TEXT NOT NULL DEFAULT 'READY',
      object_type_hint TEXT, created_at DOUBLE PRECISION,
      updated_at DOUBLE PRECISION, props JSONB NOT NULL DEFAULT '{}'::jsonb)""",
    """CREATE TABLE IF NOT EXISTS meta_sync (
      id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'SUCCEEDED',
      rows_synced INTEGER NOT NULL DEFAULT 0, started_at DOUBLE PRECISION,
      finished_at DOUBLE PRECISION, props JSONB NOT NULL DEFAULT '{}'::jsonb,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
    """CREATE TABLE IF NOT EXISTS meta_schedule (
      id TEXT PRIMARY KEY, cron TEXT NOT NULL DEFAULT '0 * * * *',
      pipeline_id TEXT, enabled BOOLEAN NOT NULL DEFAULT TRUE, name TEXT,
      ingest JSONB, last_run JSONB, org_id TEXT, project_id TEXT,
      props JSONB NOT NULL DEFAULT '{}'::jsonb,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
    """CREATE TABLE IF NOT EXISTS meta_dataset_history (
      id BIGSERIAL PRIMARY KEY, dataset_rid TEXT NOT NULL,
      payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
    """CREATE TABLE IF NOT EXISTS phase5_pipeline_graph (
      pipeline_id TEXT PRIMARY KEY, payload JSONB NOT NULL,
      revision BIGINT NOT NULL DEFAULT 1,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
)


def upgrade() -> None:
    # These tables predate Alembic. D1 adopts their non-destructive bootstrap so a
    # fresh database no longer depends on application runtime DDL.
    for statement in LEGACY_DATA_OS_SCHEMA:
        op.execute(statement)
    for table in DATA_OS_EXPAND_TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN org_id TEXT NULL")
        op.execute(f"ALTER TABLE {table} ADD COLUMN project_id TEXT NULL")
    for table in DATA_OS_TENANT_TABLES:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_workspace_ti4d1 "
            "FOREIGN KEY (org_id, project_id) "
            "REFERENCES twa_workspace(org_id, project_id) NOT VALID"
        )


def downgrade() -> None:
    for table in reversed(DATA_OS_TENANT_TABLES):
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT fk_{table}_workspace_ti4d1"
        )
    for table in reversed(DATA_OS_EXPAND_TABLES):
        op.execute(f"ALTER TABLE {table} DROP COLUMN project_id")
        op.execute(f"ALTER TABLE {table} DROP COLUMN org_id")
