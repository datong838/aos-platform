"""Grant tenant runtime access to Logic automation authority.

Revision ID: aip_p3_002
Revises: aip_p3_001
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip_p3_002"
down_revision: str | Sequence[str] | None = "aip_p3_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("aip_logic_automation_policy", "aip_logic_automation_run"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope_{table}_aip_p3_002
                  ON {table} TO aos_runtime
                  USING (
                    org_id=current_setting('aos.org_id',true)
                    AND project_id=current_setting('aos.project_id',true)
                  )
                  WITH CHECK (
                    org_id=current_setting('aos.org_id',true)
                    AND project_id=current_setting('aos.project_id',true)
                  )"""
        )
    op.execute(
        "GRANT SELECT,INSERT,UPDATE ON aip_logic_automation_policy TO aos_runtime"
    )
    op.execute(
        "GRANT SELECT,INSERT ON aip_logic_automation_run TO aos_runtime"
    )


def downgrade() -> None:
    for table in ("aip_logic_automation_run", "aip_logic_automation_policy"):
        op.execute(f"DROP POLICY IF EXISTS tenant_scope_{table}_aip_p3_002 ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
