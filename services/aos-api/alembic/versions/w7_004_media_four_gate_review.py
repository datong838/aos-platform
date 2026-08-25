"""Bind media Eval subjects and close the immutable four-gate review set (W7-06).

Revision ID: w7_004
Revises: w7_003
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w7_004"
down_revision: str | Sequence[str] | None = "w7_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_table(table: str) -> str:
    return f"""
    ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope_{table}_w7_004 ON {table} TO aos_runtime
      USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''));
    GRANT SELECT,INSERT ON {table} TO aos_runtime;
    REVOKE UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime;
    CREATE TRIGGER trg_{table}_append_only_w7_004
      BEFORE UPDATE OR DELETE ON {table}
      FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only();
    CREATE TRIGGER trg_{table}_truncate_guard_w7_004
      BEFORE TRUNCATE ON {table}
      FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only();
    """


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE aip_eval_run
          ADD COLUMN subject_artifact_ref JSONB,
          ADD COLUMN stage_attempt_ref JSONB,
          ADD COLUMN gate_policy_ref JSONB,
          ADD COLUMN evidence_cutoff_at TIMESTAMPTZ,
          ADD CONSTRAINT ck_eval_run_media_subject_pair_w7_004 CHECK (
            (subject_artifact_ref IS NULL)=(stage_attempt_ref IS NULL)
            AND (subject_artifact_ref IS NULL)=(gate_policy_ref IS NULL)
            AND (subject_artifact_ref IS NULL)=(evidence_cutoff_at IS NULL)),
          ADD CONSTRAINT ck_eval_run_media_subject_w7_004 CHECK (
            subject_artifact_ref IS NULL OR (
              jsonb_typeof(subject_artifact_ref)='object'
              AND subject_artifact_ref->>'resourceType'='Artifact'
              AND char_length(COALESCE(subject_artifact_ref->>'resourceId','')) BETWEEN 1 AND 200
              AND (subject_artifact_ref->>'contentHash') ~ '^[0-9a-f]{64}$')),
          ADD CONSTRAINT ck_eval_run_stage_attempt_w7_004 CHECK (
            stage_attempt_ref IS NULL OR (
              jsonb_typeof(stage_attempt_ref)='object'
              AND stage_attempt_ref->>'resourceType'='StepRunAttempt'
              AND char_length(COALESCE(stage_attempt_ref->>'runId','')) BETWEEN 1 AND 200
              AND char_length(COALESCE(stage_attempt_ref->>'stepKey','')) BETWEEN 1 AND 160
              AND char_length(COALESCE(stage_attempt_ref->>'stepRunId','')) BETWEEN 1 AND 200
              AND (stage_attempt_ref->>'attempt') ~ '^[1-9][0-9]*$'
              AND (stage_attempt_ref->>'inputHash') ~ '^[0-9a-f]{64}$')),
          ADD CONSTRAINT ck_eval_run_gate_policy_w7_004 CHECK (
            gate_policy_ref IS NULL OR (
              jsonb_typeof(gate_policy_ref)='object'
              AND gate_policy_ref->>'resourceType'='MediaGatePolicyRevision'
              AND (gate_policy_ref->>'revision') ~ '^[1-9][0-9]*$'
              AND (gate_policy_ref->>'contentHash') ~ '^[0-9a-f]{64}$'));

        ALTER TABLE aip_eval_report_revision
          ADD COLUMN subject_artifact_ref JSONB,
          ADD COLUMN stage_attempt_ref JSONB,
          ADD COLUMN gate_policy_ref JSONB,
          ADD COLUMN evidence_cutoff_at TIMESTAMPTZ,
          ADD CONSTRAINT ck_eval_report_media_subject_pair_w7_004 CHECK (
            (subject_artifact_ref IS NULL)=(stage_attempt_ref IS NULL)
            AND (subject_artifact_ref IS NULL)=(gate_policy_ref IS NULL)
            AND (subject_artifact_ref IS NULL)=(evidence_cutoff_at IS NULL)),
          ADD CONSTRAINT ck_eval_report_media_subject_w7_004 CHECK (
            subject_artifact_ref IS NULL OR (
              jsonb_typeof(subject_artifact_ref)='object'
              AND subject_artifact_ref->>'resourceType'='Artifact'
              AND char_length(COALESCE(subject_artifact_ref->>'resourceId','')) BETWEEN 1 AND 200
              AND (subject_artifact_ref->>'contentHash') ~ '^[0-9a-f]{64}$')),
          ADD CONSTRAINT ck_eval_report_stage_attempt_w7_004 CHECK (
            stage_attempt_ref IS NULL OR (
              jsonb_typeof(stage_attempt_ref)='object'
              AND stage_attempt_ref->>'resourceType'='StepRunAttempt'
              AND char_length(COALESCE(stage_attempt_ref->>'runId','')) BETWEEN 1 AND 200
              AND char_length(COALESCE(stage_attempt_ref->>'stepKey','')) BETWEEN 1 AND 160
              AND char_length(COALESCE(stage_attempt_ref->>'stepRunId','')) BETWEEN 1 AND 200
              AND (stage_attempt_ref->>'attempt') ~ '^[1-9][0-9]*$'
              AND (stage_attempt_ref->>'inputHash') ~ '^[0-9a-f]{64}$')),
          ADD CONSTRAINT ck_eval_report_gate_policy_w7_004 CHECK (
            gate_policy_ref IS NULL OR (
              jsonb_typeof(gate_policy_ref)='object'
              AND gate_policy_ref->>'resourceType'='MediaGatePolicyRevision'
              AND (gate_policy_ref->>'revision') ~ '^[1-9][0-9]*$'
              AND (gate_policy_ref->>'contentHash') ~ '^[0-9a-f]{64}$'));

        CREATE TABLE aip_media_gate_profile_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, profile_id TEXT NOT NULL,
          revision BIGINT NOT NULL, source_bundle_ref JSONB NOT NULL,
          signature_ref JSONB NOT NULL, policy_ref JSONB NOT NULL,
          gates JSONB NOT NULL, content_hash CHAR(64) NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,profile_id,revision),
          CHECK(revision>=1), CHECK(jsonb_typeof(source_bundle_ref)='object'),
          CHECK(jsonb_typeof(signature_ref)='object'),
          CHECK(jsonb_typeof(policy_ref)='object'),
          CHECK(jsonb_typeof(gates)='array' AND jsonb_array_length(gates)=4),
          CHECK(content_hash ~ '^[0-9a-f]{64}$')
        );

        CREATE TABLE aip_contract_migration_decision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, decision_id TEXT NOT NULL,
          source_review_cycle_id TEXT NOT NULL, review_cycle_id TEXT NOT NULL,
          source_contract_ref JSONB NOT NULL,
          target_contract_ref JSONB NOT NULL, reason TEXT NOT NULL,
          decision_hash CHAR(64) NOT NULL, actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,decision_id),
          UNIQUE(org_id,project_id,review_cycle_id),
          CHECK(source_review_cycle_id<>review_cycle_id),
          CHECK(jsonb_typeof(source_contract_ref)='object'),
          CHECK(jsonb_typeof(target_contract_ref)='object'),
          CHECK(source_contract_ref<>target_contract_ref),
          CHECK(decision_hash ~ '^[0-9a-f]{64}$')
        );

        CREATE TABLE aip_media_gate_set_decision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, gate_set_id TEXT NOT NULL,
          review_cycle_id TEXT NOT NULL, artifact_ref JSONB NOT NULL,
          family_id TEXT NOT NULL, variant_profile TEXT NOT NULL,
          variant_platform TEXT NOT NULL, rendition_spec_hash CHAR(64) NOT NULL,
          eval_contract_ref JSONB NOT NULL, gate_profile_ref JSONB NOT NULL,
          policy_ref JSONB NOT NULL, cutoff_at TIMESTAMPTZ NOT NULL,
          stage_attempt_ref JSONB NOT NULL, gate_results JSONB NOT NULL,
          contract_migration_ref JSONB, readiness TEXT NOT NULL,
          eligible_for_approval BOOLEAN NOT NULL, blocker_codes JSONB NOT NULL,
          content_hash CHAR(64) NOT NULL, actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,gate_set_id),
          UNIQUE(org_id,project_id,review_cycle_id,artifact_ref,eval_contract_ref,stage_attempt_ref),
          CHECK(rendition_spec_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(artifact_ref)='object'),
          CHECK(jsonb_typeof(eval_contract_ref)='object'),
          CHECK(jsonb_typeof(gate_profile_ref)='object'),
          CHECK(jsonb_typeof(policy_ref)='object'),
          CHECK(jsonb_typeof(stage_attempt_ref)='object'),
          CHECK(jsonb_typeof(gate_results)='array' AND jsonb_array_length(gate_results)=4),
          CHECK(contract_migration_ref IS NULL OR jsonb_typeof(contract_migration_ref)='object'),
          CHECK(readiness IN ('ready','blocked','stale','conflict','unknown')),
          CHECK(jsonb_typeof(blocker_codes)='array'),
          CHECK((eligible_for_approval AND readiness='ready' AND jsonb_array_length(blocker_codes)=0)
             OR (NOT eligible_for_approval AND (readiness<>'ready' OR jsonb_array_length(blocker_codes)>0))),
          CHECK(content_hash ~ '^[0-9a-f]{64}$')
        );
        """
    )
    for table in (
        "aip_media_gate_profile_revision",
        "aip_contract_migration_decision",
        "aip_media_gate_set_decision",
    ):
        op.execute(_tenant_table(table))


def downgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM aip_media_gate_set_decision LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_contract_migration_decision LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_media_gate_profile_revision LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_eval_run WHERE subject_artifact_ref IS NOT NULL LIMIT 1)
             OR EXISTS (SELECT 1 FROM aip_eval_report_revision WHERE subject_artifact_ref IS NOT NULL LIMIT 1)
          THEN RAISE EXCEPTION 'cannot downgrade w7_004 with media review authority data'
            USING ERRCODE='55000'; END IF;
        END $$;
        DROP TABLE aip_media_gate_set_decision CASCADE;
        DROP TABLE aip_contract_migration_decision CASCADE;
        DROP TABLE aip_media_gate_profile_revision CASCADE;
        ALTER TABLE aip_eval_report_revision
          DROP CONSTRAINT ck_eval_report_gate_policy_w7_004,
          DROP CONSTRAINT ck_eval_report_stage_attempt_w7_004,
          DROP CONSTRAINT ck_eval_report_media_subject_w7_004,
          DROP CONSTRAINT ck_eval_report_media_subject_pair_w7_004,
          DROP COLUMN evidence_cutoff_at, DROP COLUMN gate_policy_ref,
          DROP COLUMN stage_attempt_ref, DROP COLUMN subject_artifact_ref;
        ALTER TABLE aip_eval_run
          DROP CONSTRAINT ck_eval_run_gate_policy_w7_004,
          DROP CONSTRAINT ck_eval_run_stage_attempt_w7_004,
          DROP CONSTRAINT ck_eval_run_media_subject_w7_004,
          DROP CONSTRAINT ck_eval_run_media_subject_pair_w7_004,
          DROP COLUMN evidence_cutoff_at, DROP COLUMN gate_policy_ref,
          DROP COLUMN stage_attempt_ref, DROP COLUMN subject_artifact_ref;
        """
    )
