"""TI-4 D4 validate Data OS workspace foreign keys.

Revision ID: 228ti4d4validate
Revises: 228ti4d1expand
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti4d4validate"
down_revision: str | Sequence[str] | None = "228ti4d1expand"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DATA_OS_TENANT_TABLES = (
    "meta_dataset",
    "meta_dataset_history",
    "meta_pipeline",
    "meta_sync",
    "phase5_pipeline_graph",
    "meta_schedule",
    "meta_source",
)


def upgrade() -> None:
    for table in DATA_OS_TENANT_TABLES:
        op.execute(
            f"ALTER TABLE {table} "
            f"VALIDATE CONSTRAINT fk_{table}_workspace_ti4d1"
        )


def downgrade() -> None:
    for table in reversed(DATA_OS_TENANT_TABLES):
        constraint = f"fk_{table}_workspace_ti4d1"
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {constraint}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {constraint} "
            "FOREIGN KEY (org_id, project_id) "
            "REFERENCES twa_workspace(org_id, project_id) NOT VALID"
        )
