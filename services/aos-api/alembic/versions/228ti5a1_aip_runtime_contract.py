"""TI-5 A1 contract tenant-scoped AIP runtime tables.

Revision ID: 228ti5a1aip
Revises: 228ti4a1apollo
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti5a1aip"
down_revision: str | Sequence[str] | None = "228ti4a1apollo"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AIP_TABLES = (
    "aip_logic_graph",
    "aip_logic_graph_revision",
    "aip_logic_graph_runs",
    "aip_logic_graph_run_nodes",
    "aip_eval_suite",
    "aip_eval_report",
    "aip_logic_publication",
)


def upgrade() -> None:
    for table in AIP_TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM {table} child
                LEFT JOIN twa_workspace parent
                  ON parent.org_id=child.org_id
                 AND parent.project_id=child.project_id
                WHERE parent.org_id IS NULL
              ) THEN
                RAISE EXCEPTION '{table} contains workspace orphans';
              END IF;
            END $$
            """
        )
        op.execute(
            f"""
            ALTER TABLE {table}
              ADD CONSTRAINT fk_{table}_workspace_ti5a1
              FOREIGN KEY (org_id,project_id)
              REFERENCES twa_workspace(org_id,project_id)
              NOT VALID
            """
        )
        op.execute(
            f"ALTER TABLE {table} VALIDATE CONSTRAINT fk_{table}_workspace_ti5a1"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_scope_{table}_ti5a1 ON {table}
              TO PUBLIC
              USING (
                org_id = NULLIF(current_setting('aos.org_id', TRUE), '')
                AND project_id = NULLIF(current_setting('aos.project_id', TRUE), '')
              )
              WITH CHECK (
                org_id = NULLIF(current_setting('aos.org_id', TRUE), '')
                AND project_id = NULLIF(current_setting('aos.project_id', TRUE), '')
              )
            """
        )
        op.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON {table} TO aos_runtime")


def downgrade() -> None:
    for table in reversed(AIP_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_scope_{table}_ti5a1 ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk_{table}_workspace_ti5a1"
        )
