"""Add W2-D impact preview and production start decision authority.

Revision ID: w2_004
Revises: w1e_001
Create Date: 2026-08-14
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w2_004"
down_revision: str | Sequence[str] | None = "w1e_001"
branch_labels = None
depends_on = None


def _tenant_table(name: str, *, mutable: bool) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{name}_w2d ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    privilege = "SELECT,INSERT,UPDATE" if mutable else "SELECT,INSERT"
    op.execute(f"GRANT {privilege} ON {name} TO aos_runtime")


def _append_only(name: str) -> None:
    op.execute(
        f"""CREATE TRIGGER trg_{name}_append_only
        BEFORE UPDATE OR DELETE ON {name}
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        f"""CREATE TRIGGER trg_{name}_truncate_guard
        BEFORE TRUNCATE ON {name}
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
    )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_impact_preview_head (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, preview_id TEXT NOT NULL,
          current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,preview_id),
          CHECK(current_revision>=1), CHECK(version>=1),
          FOREIGN KEY(org_id,project_id) REFERENCES twa_workspace(org_id,project_id))"""
    )
    op.execute(
        """CREATE TABLE aip_impact_preview_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, preview_id TEXT NOT NULL,
          revision BIGINT NOT NULL, task_id TEXT NOT NULL, plan_ref JSONB NOT NULL,
          brief_ref JSONB NOT NULL, evidence_bundle_ref JSONB NOT NULL,
          eval_contract_ref JSONB NOT NULL, responsibility_plan_ref JSONB NOT NULL,
          stage_template_ref JSONB NOT NULL, model_route_ref JSONB,
          runtime_policy_ref JSONB, binding_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          capability_ref JSONB, account_ref JSONB, impact JSONB NOT NULL,
          expires_at TIMESTAMPTZ NOT NULL, content_hash TEXT NOT NULL,
          dependency_snapshot_hash TEXT NOT NULL, dependency_snapshot JSONB NOT NULL,
          lifecycle TEXT NOT NULL, readiness TEXT NOT NULL, blockers JSONB NOT NULL,
          frozen_by TEXT, frozen_at TIMESTAMPTZ, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,preview_id,revision),
          CHECK(revision>=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(dependency_snapshot_hash ~ '^[0-9a-f]{64}$'),
          CHECK(lifecycle IN ('draft','frozen','withdrawn','superseded')),
          CHECK(readiness IN ('ready','blocked','stale','unknown')),
          CHECK(jsonb_typeof(plan_ref)='object'), CHECK(jsonb_typeof(brief_ref)='object'),
          CHECK(jsonb_typeof(evidence_bundle_ref)='object'),
          CHECK(jsonb_typeof(eval_contract_ref)='object'),
          CHECK(jsonb_typeof(responsibility_plan_ref)='object'),
          CHECK(jsonb_typeof(stage_template_ref)='object'),
          CHECK(jsonb_typeof(binding_refs)='array'), CHECK(jsonb_typeof(impact)='object'),
          CHECK(jsonb_typeof(dependency_snapshot)='array'), CHECK(jsonb_typeof(blockers)='array'),
          CHECK((lifecycle='frozen' AND frozen_by IS NOT NULL AND frozen_at IS NOT NULL)
             OR (lifecycle<>'frozen' AND frozen_by IS NULL AND frozen_at IS NULL)),
          FOREIGN KEY(org_id,project_id,preview_id)
            REFERENCES aip_impact_preview_head(org_id,project_id,preview_id)
            DEFERRABLE INITIALLY DEFERRED,
          FOREIGN KEY(org_id,project_id,task_id)
            REFERENCES aip_task(org_id,project_id,task_id))"""
    )
    op.execute(
        """CREATE TABLE aip_production_start_decision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, decision_id TEXT NOT NULL,
          status TEXT NOT NULL, task_id TEXT NOT NULL, plan_ref JSONB NOT NULL,
          preview_ref JSONB NOT NULL, action_proposal_ref JSONB NOT NULL,
          dependency_snapshot_hash TEXT NOT NULL, blockers JSONB NOT NULL,
          task_run_ref JSONB, idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,decision_id),
          UNIQUE(org_id,project_id,idempotency_key),
          CHECK(status IN ('started','blocked','stale','unknown')),
          CHECK(dependency_snapshot_hash ~ '^[0-9a-f]{64}$'),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(plan_ref)='object'), CHECK(jsonb_typeof(preview_ref)='object'),
          CHECK(jsonb_typeof(action_proposal_ref)='object'), CHECK(jsonb_typeof(blockers)='array'),
          CHECK((status='started' AND task_run_ref IS NOT NULL AND jsonb_array_length(blockers)=0)
             OR (status<>'started' AND task_run_ref IS NULL AND jsonb_array_length(blockers)>0)),
          FOREIGN KEY(org_id,project_id,task_id)
            REFERENCES aip_task(org_id,project_id,task_id))"""
    )
    op.execute(
        """ALTER TABLE aip_action_proposal
        ADD COLUMN impact_preview_id TEXT,
        ADD COLUMN impact_preview_revision BIGINT,
        ADD COLUMN impact_preview_hash TEXT,
        ADD CONSTRAINT aip_action_proposal_impact_preview_complete CHECK (
          (impact_preview_id IS NULL AND impact_preview_revision IS NULL AND impact_preview_hash IS NULL)
          OR (impact_preview_id IS NOT NULL AND impact_preview_revision>=1
              AND impact_preview_hash ~ '^[0-9a-f]{64}$')),
        ADD CONSTRAINT aip_action_proposal_impact_preview_fk
          FOREIGN KEY(org_id,project_id,impact_preview_id,impact_preview_revision)
          REFERENCES aip_impact_preview_revision(org_id,project_id,preview_id,revision)"""
    )
    _tenant_table("aip_impact_preview_head", mutable=True)
    _tenant_table("aip_impact_preview_revision", mutable=False)
    _tenant_table("aip_production_start_decision", mutable=False)
    _append_only("aip_impact_preview_revision")
    _append_only("aip_production_start_decision")
    op.execute(
        "CREATE INDEX aip_impact_preview_updated_idx ON "
        "aip_impact_preview_head(org_id,project_id,updated_at DESC,preview_id)"
    )
    op.execute(
        "CREATE INDEX aip_start_decision_created_idx ON "
        "aip_production_start_decision(org_id,project_id,created_at DESC,decision_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_production_start_decision CASCADE")
    op.execute("ALTER TABLE aip_action_proposal DROP CONSTRAINT IF EXISTS aip_action_proposal_impact_preview_fk")
    op.execute("ALTER TABLE aip_action_proposal DROP CONSTRAINT IF EXISTS aip_action_proposal_impact_preview_complete")
    op.execute("ALTER TABLE aip_action_proposal DROP COLUMN IF EXISTS impact_preview_hash")
    op.execute("ALTER TABLE aip_action_proposal DROP COLUMN IF EXISTS impact_preview_revision")
    op.execute("ALTER TABLE aip_action_proposal DROP COLUMN IF EXISTS impact_preview_id")
    op.execute("DROP TABLE IF EXISTS aip_impact_preview_revision CASCADE")
    op.execute("DROP TABLE IF EXISTS aip_impact_preview_head CASCADE")
