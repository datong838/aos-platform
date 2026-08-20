"""ToolBinding table + AssigneeResolutionReceipt (W-L20).

Revision ID: aip13_001
Revises: aip12_001
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip13_001"
down_revision: str | Sequence[str] | None = "aip12_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(name: str, grant: str) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{name}
           ON {name} TO aos_runtime
           USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))
           WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"GRANT {grant} ON {name} TO aos_runtime")


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_tool_binding (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          binding_id TEXT NOT NULL,
          tool_id TEXT NOT NULL,
          version BIGINT NOT NULL,
          agent_instance_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, binding_id),
          CHECK (version >= 1),
          CHECK (status IN ('active','disabled')),
          CHECK (length(agent_instance_id) > 0)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_assignee_resolution_receipt (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          receipt_id TEXT NOT NULL,
          subject_id TEXT NOT NULL,
          kind TEXT NOT NULL,
          resource_id TEXT NOT NULL,
          version BIGINT NOT NULL,
          status TEXT NOT NULL,
          resolved_ref TEXT,
          blocker_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
          actor TEXT NOT NULL,
          content_hash CHAR(64) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, receipt_id),
          CHECK (version >= 1),
          CHECK (status IN ('resolved','blocked')),
          CHECK (kind IN (
            'agent_instance','human_principal','tool_binding','provider_capability_binding'
          )),
          CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (jsonb_typeof(blocker_codes)='array')
        )"""
    )
    _rls("aip_tool_binding", "SELECT,INSERT,UPDATE")
    _rls("aip_assignee_resolution_receipt", "SELECT,INSERT")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_assignee_resolution_receipt CASCADE")
    op.execute("DROP TABLE IF EXISTS aip_tool_binding CASCADE")
