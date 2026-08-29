"""Repair tenant GUC names in model route draft RLS.

Revision ID: wcat_003
Revises: wcat_002
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "wcat_003"
down_revision: str | Sequence[str] | None = "wcat_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP POLICY tenant_scope_aip_model_route_draft_wcat_002 ON aip_model_route_draft")
    op.execute("""CREATE POLICY tenant_scope_aip_model_route_draft_wcat_003
      ON aip_model_route_draft TO aos_runtime
      USING (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))""")


def downgrade() -> None:
    op.execute("DROP POLICY tenant_scope_aip_model_route_draft_wcat_003 ON aip_model_route_draft")
    op.execute("""CREATE POLICY tenant_scope_aip_model_route_draft_wcat_002
      ON aip_model_route_draft TO aos_runtime
      USING (org_id=current_setting('app.org_id',true) AND project_id=current_setting('app.project_id',true))""")
