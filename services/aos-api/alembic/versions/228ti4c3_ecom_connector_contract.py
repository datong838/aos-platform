"""TI-4 C3 validate and enforce e-commerce Connector tenant boundaries.

Revision ID: 228ti4c3contract
Revises: 228ti4d7contract
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti4c3contract"
down_revision: str | Sequence[str] | None = "228ti4d7contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "aos_runtime"
SCOPED_TABLES = (
    "ecom_ingest_receipt",
    "ecom_link",
    "ecom_object",
    "ecom_sync_checkpoint",
    "oauth_token_store",
)
_SCOPE_MATCH = (
    "org_id = current_setting('aos.org_id', true) "
    "AND workspace_id = current_setting('aos.project_id', true)"
)


def upgrade() -> None:
    for table in SCOPED_TABLES:
        constraint = f"fk_{table}_workspace_ti4"
        op.execute(
            f"DO $check$ BEGIN IF EXISTS ("
            f"SELECT 1 FROM {table} child LEFT JOIN twa_workspace parent "
            "ON parent.org_id=child.org_id AND parent.project_id=child.workspace_id "
            "WHERE parent.org_id IS NULL) THEN "
            f"RAISE EXCEPTION 'TI-4 C3 workspace orphan in {table}'; "
            "END IF; END $check$;"
        )
        op.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {constraint}")
        policy = f"tenant_scope_{table}_ti4c3"
        op.execute(
            f"CREATE POLICY {policy} ON {table} FOR ALL TO {RUNTIME_ROLE} "
            f"USING ({_SCOPE_MATCH}) WITH CHECK ({_SCOPE_MATCH})"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(SCOPED_TABLES):
        policy = f"tenant_scope_{table}_ti4c3"
        constraint = f"fk_{table}_workspace_ti4"
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {constraint}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {constraint} "
            "FOREIGN KEY (org_id, workspace_id) "
            "REFERENCES twa_workspace(org_id, project_id) NOT VALID"
        )
