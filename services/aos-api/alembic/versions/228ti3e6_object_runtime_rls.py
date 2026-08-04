"""TI-3 E6 enforce tenant RLS for the Object Runtime family.

Revision ID: 228ti3e6rls
Revises: 228ti3e4validate
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti3e6rls"
down_revision: str | Sequence[str] | None = "228ti3e4validate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "aos_runtime"
SCOPED_TABLES = (
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

_SCOPE_MATCH = (
    "org_id = current_setting('aos.org_id', true) "
    "AND project_id = current_setting('aos.project_id', true)"
)


def upgrade() -> None:
    for table in SCOPED_TABLES:
        policy = f"tenant_scope_{table}_ti3"
        op.execute(
            f"CREATE POLICY {policy} ON {table} FOR ALL TO {RUNTIME_ROLE} "
            f"USING ({_SCOPE_MATCH}) WITH CHECK ({_SCOPE_MATCH})"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(SCOPED_TABLES):
        policy = f"tenant_scope_{table}_ti3"
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
