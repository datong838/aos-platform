"""Add durable AIP-6 registry command receipts.

Revision ID: aip6_002
Revises: aip6_001
Create Date: 2026-08-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip6_002"
down_revision: str | Sequence[str] | None = "aip6_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_agent_registry_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          receipt_id TEXT NOT NULL, operation TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          resource_ref JSONB NOT NULL, result_ref JSONB NOT NULL,
          status TEXT NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,receipt_id),
          UNIQUE (org_id,project_id,operation,idempotency_key),
          CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          CHECK (jsonb_typeof(resource_ref)='object'),
          CHECK (jsonb_typeof(result_ref)='object'),
          CHECK (status IN ('accepted','applied','rejected')),
          FOREIGN KEY (org_id,project_id)
            REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute("ALTER TABLE aip_agent_registry_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_agent_registry_receipt FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_aip_agent_registry_receipt_aip6
        ON aip_agent_registry_receipt TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_agent_registry_receipt_append_only
        BEFORE UPDATE OR DELETE ON aip_agent_registry_receipt
        FOR EACH ROW EXECUTE FUNCTION guard_aip6_registry_append_only()"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_agent_registry_receipt_truncate_guard
        BEFORE TRUNCATE ON aip_agent_registry_receipt
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip6_registry_append_only()"""
    )
    op.execute("GRANT SELECT,INSERT ON aip_agent_registry_receipt TO aos_runtime")
    op.execute("GRANT SELECT ON aip_agent_template_revision TO aos_runtime")
    op.execute("GRANT SELECT ON aip_skill_template_revision TO aos_runtime")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON aip_skill_template_revision FROM aos_runtime")
    op.execute("REVOKE SELECT ON aip_agent_template_revision FROM aos_runtime")
    op.execute("DROP TABLE IF EXISTS aip_agent_registry_receipt")
