"""Add ProductionContextRevision four-contract freeze authority (W-L11).

Revision ID: w2_006
Revises: w2_005
Create Date: 2026-08-20
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w2_006"
down_revision: str | Sequence[str] | None = "w2_005"
branch_labels = None
depends_on = None


def _tenant_table(name: str) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{name}_w2_006 ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"GRANT SELECT,INSERT ON {name} TO aos_runtime")
    op.execute(
        f"""CREATE TRIGGER trg_{name}_append_only
        BEFORE UPDATE OR DELETE ON {name}
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_production_context_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, context_id TEXT NOT NULL,
          revision BIGINT NOT NULL, task_id TEXT NOT NULL,
          brief_ref JSONB NOT NULL, evidence_bundle_ref JSONB NOT NULL,
          eval_contract_ref JSONB NOT NULL, responsibility_plan_ref JSONB NOT NULL,
          preparation_ref JSONB, profile TEXT NOT NULL DEFAULT 'default',
          dependency_snapshot JSONB NOT NULL, dependency_snapshot_hash TEXT NOT NULL,
          content_hash TEXT NOT NULL, lifecycle TEXT NOT NULL, readiness TEXT NOT NULL,
          blockers JSONB NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,context_id,revision),
          CHECK(revision>=1),
          CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(dependency_snapshot_hash ~ '^[0-9a-f]{64}$'),
          CHECK(lifecycle IN ('frozen')),
          CHECK(readiness IN ('ready','blocked','stale','unknown')),
          CHECK(jsonb_typeof(brief_ref)='object'),
          CHECK(jsonb_typeof(evidence_bundle_ref)='object'),
          CHECK(jsonb_typeof(eval_contract_ref)='object'),
          CHECK(jsonb_typeof(responsibility_plan_ref)='object'),
          CHECK(jsonb_typeof(dependency_snapshot)='array'),
          CHECK(jsonb_typeof(blockers)='array')
        )"""
    )
    _tenant_table("aip_production_context_revision")
    op.execute(
        "CREATE INDEX aip_production_context_task_idx ON aip_production_context_revision"
        "(org_id,project_id,task_id,created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_production_context_revision")
