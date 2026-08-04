"""TI-3 E1 expand TenantScope columns for object runtime resources.

Revision ID: 228ti3e1expand
Revises: 228ti2e7contract
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti3e1expand"
down_revision: str | Sequence[str] | None = "228ti2e7contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EXPAND_TABLES = (
    "funnel_status",
    "graph_edge",
    "meta_branch",
    "obj_branch_overlay",
    "obj_instance",
)

_TENANT_TABLES = (
    *_EXPAND_TABLES,
    "object_lifecycle",
    "draft_dataset",
    "wiki_page",
    "wiki_page_version",
)


def upgrade() -> None:
    for table in _EXPAND_TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN org_id TEXT NULL")
        op.execute(f"ALTER TABLE {table} ADD COLUMN project_id TEXT NULL")
    for table in _TENANT_TABLES:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_workspace_ti3 "
            "FOREIGN KEY (org_id, project_id) "
            "REFERENCES twa_workspace(org_id, project_id) NOT VALID"
        )


def downgrade() -> None:
    for table in reversed(_TENANT_TABLES):
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT fk_{table}_workspace_ti3"
        )
    for table in reversed(_EXPAND_TABLES):
        op.execute(f"ALTER TABLE {table} DROP COLUMN project_id")
        op.execute(f"ALTER TABLE {table} DROP COLUMN org_id")
