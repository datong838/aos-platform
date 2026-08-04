"""TI-3 E4 validate Object runtime workspace foreign keys.

Revision ID: 228ti3e4validate
Revises: 228ti3e1expand
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti3e4validate"
down_revision: str | Sequence[str] | None = "228ti3e1expand"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "funnel_status",
    "graph_edge",
    "meta_branch",
    "obj_branch_overlay",
    "obj_instance",
    "object_lifecycle",
    "draft_dataset",
    "wiki_page",
    "wiki_page_version",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT fk_{table}_workspace_ti3")


def downgrade() -> None:
    for table in reversed(_TABLES):
        constraint = f"fk_{table}_workspace_ti3"
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {constraint}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {constraint} "
            "FOREIGN KEY (org_id, project_id) "
            "REFERENCES twa_workspace(org_id, project_id) NOT VALID"
        )
