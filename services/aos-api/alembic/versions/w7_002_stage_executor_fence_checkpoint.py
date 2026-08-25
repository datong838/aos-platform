"""Close canonical executor fence, checkpoint and resume contracts (W7-04).

Revision ID: w7_002
Revises: w7_001
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w7_002"
down_revision: str | Sequence[str] | None = "w7_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE aip_task_run
          DROP CONSTRAINT aip_task_run_status_check,
          ADD CONSTRAINT aip_task_run_status_check
            CHECK (status IN ('queued','running','pausing','paused','succeeded','failed','cancelled','unknown')),
          ADD COLUMN dependency_snapshot_hash CHAR(64),
          ADD COLUMN pause_requested_at TIMESTAMPTZ,
          ADD COLUMN pause_reason TEXT,
          ADD CONSTRAINT ck_task_run_dependency_snapshot_hash_w7_002
            CHECK (dependency_snapshot_hash IS NULL OR dependency_snapshot_hash ~ '^[0-9a-f]{64}$');

        ALTER TABLE aip_step_run
          ADD COLUMN fence BIGINT,
          ADD COLUMN assignment_lease_id TEXT,
          ADD COLUMN input_hash CHAR(64),
          ADD COLUMN provider_request_fingerprint CHAR(64),
          ADD COLUMN safe_point BOOLEAN NOT NULL DEFAULT FALSE,
          ADD COLUMN reconcile_required BOOLEAN NOT NULL DEFAULT FALSE,
          ADD CONSTRAINT ck_step_run_fence_w7_002 CHECK (fence IS NULL OR fence >= 1),
          ADD CONSTRAINT ck_step_run_input_hash_w7_002
            CHECK (input_hash IS NULL OR input_hash ~ '^[0-9a-f]{64}$'),
          ADD CONSTRAINT ck_step_run_provider_fingerprint_w7_002
            CHECK (provider_request_fingerprint IS NULL OR provider_request_fingerprint ~ '^[0-9a-f]{64}$');

        ALTER TABLE aip_checkpoint
          ADD COLUMN attempt INTEGER,
          ADD COLUMN plan_revision_id TEXT,
          ADD COLUMN input_hash CHAR(64),
          ADD COLUMN provider_request_fingerprint CHAR(64),
          ADD COLUMN dependency_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN dependency_snapshot_hash CHAR(64),
          ADD COLUMN checkpoint_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
          ADD COLUMN usage_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          ADD COLUMN receipt_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          ADD COLUMN lineage JSONB NOT NULL DEFAULT '{}'::jsonb,
          ADD CONSTRAINT ck_checkpoint_attempt_w7_002 CHECK (attempt IS NULL OR attempt >= 1),
          ADD CONSTRAINT ck_checkpoint_input_hash_w7_002
            CHECK (input_hash IS NULL OR input_hash ~ '^[0-9a-f]{64}$'),
          ADD CONSTRAINT ck_checkpoint_provider_fingerprint_w7_002
            CHECK (provider_request_fingerprint IS NULL OR provider_request_fingerprint ~ '^[0-9a-f]{64}$'),
          ADD CONSTRAINT ck_checkpoint_dependency_hash_w7_002
            CHECK (dependency_snapshot_hash IS NULL OR dependency_snapshot_hash ~ '^[0-9a-f]{64}$'),
          ADD CONSTRAINT ck_checkpoint_dependency_object_w7_002 CHECK (jsonb_typeof(dependency_snapshot)='object'),
          ADD CONSTRAINT ck_checkpoint_policy_object_w7_002 CHECK (jsonb_typeof(checkpoint_policy)='object'),
          ADD CONSTRAINT ck_checkpoint_usage_array_w7_002 CHECK (jsonb_typeof(usage_refs)='array'),
          ADD CONSTRAINT ck_checkpoint_receipt_array_w7_002 CHECK (jsonb_typeof(receipt_refs)='array'),
          ADD CONSTRAINT ck_checkpoint_lineage_object_w7_002 CHECK (jsonb_typeof(lineage)='object');

        CREATE TABLE aip_run_resume_decision_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, decision_id TEXT NOT NULL,
          run_id TEXT NOT NULL, revision BIGINT NOT NULL, checkpoint_id TEXT,
          decision TEXT NOT NULL, reason_codes JSONB NOT NULL,
          expected_dependency_snapshot_hash CHAR(64),
          observed_dependency_snapshot_hash CHAR(64) NOT NULL,
          expected_input_hash CHAR(64), observed_input_hash CHAR(64),
          actor TEXT NOT NULL, idempotency_key TEXT NOT NULL,
          request_hash CHAR(64) NOT NULL, content_hash CHAR(64) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,decision_id,revision),
          UNIQUE(org_id,project_id,run_id,idempotency_key),
          CHECK(revision>=1), CHECK(decision IN ('reuse','invalidated')),
          CHECK(jsonb_typeof(reason_codes)='array'),
          CHECK(expected_dependency_snapshot_hash IS NULL OR expected_dependency_snapshot_hash ~ '^[0-9a-f]{64}$'),
          CHECK(observed_dependency_snapshot_hash ~ '^[0-9a-f]{64}$'),
          CHECK(expected_input_hash IS NULL OR expected_input_hash ~ '^[0-9a-f]{64}$'),
          CHECK(observed_input_hash IS NULL OR observed_input_hash ~ '^[0-9a-f]{64}$'),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY(org_id,project_id,run_id) REFERENCES aip_task_run(org_id,project_id,run_id),
          FOREIGN KEY(org_id,project_id,checkpoint_id) REFERENCES aip_checkpoint(org_id,project_id,checkpoint_id)
        );
        ALTER TABLE aip_run_resume_decision_revision ENABLE ROW LEVEL SECURITY;
        ALTER TABLE aip_run_resume_decision_revision FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_scope_aip_run_resume_decision_w7_002
          ON aip_run_resume_decision_revision TO aos_runtime
          USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''));
        GRANT SELECT,INSERT ON aip_run_resume_decision_revision TO aos_runtime;
        REVOKE UPDATE,DELETE,TRUNCATE ON aip_run_resume_decision_revision FROM aos_runtime;
        CREATE TRIGGER trg_aip_run_resume_decision_append_only_w7_002
          BEFORE UPDATE OR DELETE ON aip_run_resume_decision_revision
          FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only();
        CREATE TRIGGER trg_aip_run_resume_decision_truncate_guard_w7_002
          BEFORE TRUNCATE ON aip_run_resume_decision_revision
          FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM aip_run_resume_decision_revision LIMIT 1) THEN
            RAISE EXCEPTION 'cannot downgrade w7_002 with resume decision authority data'
              USING ERRCODE='55000';
          END IF;
        END $$;
        DROP TABLE aip_run_resume_decision_revision CASCADE;
        ALTER TABLE aip_checkpoint
          DROP CONSTRAINT ck_checkpoint_lineage_object_w7_002,
          DROP CONSTRAINT ck_checkpoint_receipt_array_w7_002,
          DROP CONSTRAINT ck_checkpoint_usage_array_w7_002,
          DROP CONSTRAINT ck_checkpoint_policy_object_w7_002,
          DROP CONSTRAINT ck_checkpoint_dependency_object_w7_002,
          DROP CONSTRAINT ck_checkpoint_dependency_hash_w7_002,
          DROP CONSTRAINT ck_checkpoint_provider_fingerprint_w7_002,
          DROP CONSTRAINT ck_checkpoint_input_hash_w7_002,
          DROP CONSTRAINT ck_checkpoint_attempt_w7_002,
          DROP COLUMN lineage, DROP COLUMN receipt_refs, DROP COLUMN usage_refs,
          DROP COLUMN checkpoint_policy, DROP COLUMN dependency_snapshot_hash,
          DROP COLUMN dependency_snapshot, DROP COLUMN provider_request_fingerprint,
          DROP COLUMN input_hash, DROP COLUMN plan_revision_id, DROP COLUMN attempt;
        ALTER TABLE aip_step_run
          DROP CONSTRAINT ck_step_run_provider_fingerprint_w7_002,
          DROP CONSTRAINT ck_step_run_input_hash_w7_002,
          DROP CONSTRAINT ck_step_run_fence_w7_002,
          DROP COLUMN reconcile_required, DROP COLUMN safe_point,
          DROP COLUMN provider_request_fingerprint, DROP COLUMN input_hash,
          DROP COLUMN assignment_lease_id, DROP COLUMN fence;
        ALTER TABLE aip_task_run
          DROP CONSTRAINT ck_task_run_dependency_snapshot_hash_w7_002,
          DROP CONSTRAINT aip_task_run_status_check,
          ADD CONSTRAINT aip_task_run_status_check
            CHECK (status IN ('queued','running','succeeded','failed','cancelled','unknown')),
          DROP COLUMN pause_reason, DROP COLUMN pause_requested_at,
          DROP COLUMN dependency_snapshot_hash;
        """
    )
