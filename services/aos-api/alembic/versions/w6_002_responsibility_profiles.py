"""Responsibility profile recommendation, confirmation and merge authority (W6-02).

Revision ID: w6_002
Revises: w6_001
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w6_002"
down_revision: str | Sequence[str] | None = "w6_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE aip_merge_policy_revision (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, policy_id TEXT NOT NULL,
      revision INTEGER NOT NULL CHECK (revision >= 1), minimum_profile TEXT NOT NULL CHECK (minimum_profile IN ('LITE','STANDARD','FULL')),
      maximum_risk_level INTEGER NOT NULL CHECK (maximum_risk_level BETWEEN 0 AND 3),
      allowed_merge_groups JSONB NOT NULL CHECK (jsonb_typeof(allowed_merge_groups)='array'),
      protected_responsibility_types JSONB NOT NULL CHECK (jsonb_typeof(protected_responsibility_types)='array'),
      expires_at TIMESTAMPTZ NOT NULL, content_hash CHAR(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
      created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (org_id,project_id,policy_id,revision),
      FOREIGN KEY (org_id,project_id) REFERENCES meta_workspace(org_id,project_id)
    );
    CREATE TABLE aip_profile_recommendation_revision (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, recommendation_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK (revision >= 1),
      subject_ref JSONB NOT NULL, recommended_profile TEXT NOT NULL CHECK (recommended_profile IN ('LITE','STANDARD','FULL')),
      candidate_template_refs JSONB NOT NULL CHECK (jsonb_typeof(candidate_template_refs)='object'), selected_template_ref JSONB NOT NULL,
      policy_ref JSONB NOT NULL, risk_level INTEGER NOT NULL CHECK (risk_level BETWEEN 0 AND 3), channel_count INTEGER NOT NULL CHECK (channel_count >= 1),
      reason_codes JSONB NOT NULL CHECK (jsonb_typeof(reason_codes)='array'), unknown_codes JSONB NOT NULL CHECK (jsonb_typeof(unknown_codes)='array'),
      snapshot_hash CHAR(64) NOT NULL CHECK (snapshot_hash ~ '^[0-9a-f]{64}$'), content_hash CHAR(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
      expires_at TIMESTAMPTZ NOT NULL, created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (org_id,project_id,recommendation_id,revision),
      FOREIGN KEY (org_id,project_id) REFERENCES meta_workspace(org_id,project_id)
    );
    CREATE TABLE aip_profile_confirmation_receipt (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, confirmation_id TEXT NOT NULL,
      recommendation_id TEXT NOT NULL, recommendation_revision INTEGER NOT NULL, recommendation_hash CHAR(64) NOT NULL,
      selected_profile TEXT NOT NULL CHECK (selected_profile IN ('LITE','STANDARD','FULL')), selected_template_ref JSONB NOT NULL, policy_ref JSONB NOT NULL,
      actor TEXT NOT NULL, reason TEXT NOT NULL, content_hash CHAR(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (org_id,project_id,confirmation_id),
      FOREIGN KEY (org_id,project_id,recommendation_id,recommendation_revision) REFERENCES aip_profile_recommendation_revision(org_id,project_id,recommendation_id,revision),
      FOREIGN KEY (org_id,project_id) REFERENCES meta_workspace(org_id,project_id)
    );
    CREATE TABLE aip_merge_decision_receipt (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL, plan_ref JSONB NOT NULL, policy_ref JSONB NOT NULL,
      confirmation_id TEXT NOT NULL, source_slot_ids JSONB NOT NULL CHECK (jsonb_typeof(source_slot_ids)='array'), target_slot_id TEXT NOT NULL,
      merged_responsibility_types JSONB NOT NULL CHECK (jsonb_typeof(merged_responsibility_types)='array'), capability_union JSONB NOT NULL CHECK (jsonb_typeof(capability_union)='array'),
      target_assignee_resolution_receipt_id TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL,
      content_hash CHAR(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'), created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (org_id,project_id,receipt_id),
      FOREIGN KEY (org_id,project_id,confirmation_id) REFERENCES aip_profile_confirmation_receipt(org_id,project_id,confirmation_id),
      FOREIGN KEY (org_id,project_id,target_assignee_resolution_receipt_id) REFERENCES aip_assignee_resolution_receipt(org_id,project_id,receipt_id),
      FOREIGN KEY (org_id,project_id) REFERENCES meta_workspace(org_id,project_id)
    );
    ALTER TABLE aip_responsibility_plan_revision
      ADD COLUMN profile_recommendation_ref JSONB,
      ADD COLUMN profile_confirmation_id TEXT,
      ADD COLUMN merge_policy_ref JSONB,
      ADD COLUMN merge_decision_receipt_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
      ADD CONSTRAINT ck_responsibility_merge_receipt_ids_array CHECK (jsonb_typeof(merge_decision_receipt_ids)='array');
    """)
    for table in (
        "aip_merge_policy_revision", "aip_profile_recommendation_revision",
        "aip_profile_confirmation_receipt", "aip_merge_decision_receipt",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_scope ON {table} USING (org_id=current_setting('app.current_org_id',true) AND project_id=current_setting('app.current_project_id',true)) WITH CHECK (org_id=current_setting('app.current_org_id',true) AND project_id=current_setting('app.current_project_id',true))")
        op.execute(f"GRANT SELECT, INSERT ON {table} TO aos_app")


def downgrade() -> None:
    op.execute("""ALTER TABLE aip_responsibility_plan_revision
      DROP CONSTRAINT IF EXISTS ck_responsibility_merge_receipt_ids_array,
      DROP COLUMN IF EXISTS merge_decision_receipt_ids,
      DROP COLUMN IF EXISTS merge_policy_ref,
      DROP COLUMN IF EXISTS profile_confirmation_id,
      DROP COLUMN IF EXISTS profile_recommendation_ref""")
    for table in (
        "aip_merge_decision_receipt", "aip_profile_confirmation_receipt",
        "aip_profile_recommendation_revision", "aip_merge_policy_revision",
    ):
        op.execute(f"DROP TABLE {table}")
