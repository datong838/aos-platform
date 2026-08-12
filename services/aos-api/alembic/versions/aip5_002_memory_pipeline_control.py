"""Add tenant-scoped AIP memory pipeline control authority.

Revision ID: aip5_002
Revises: aip5_001
Create Date: 2026-08-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip5_002"
down_revision: str | Sequence[str] | None = "aip5_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "aip_memory_pipeline_schedule",
    "aip_memory_pipeline_run",
    "aip_memory_pipeline_receipt",
    "aip_memory_pipeline_receipt_candidate",
    "aip_memory_pipeline_checkpoint_revision",
    "aip_memory_pipeline_alert",
)

_APPEND_ONLY_TABLES = (
    "aip_memory_pipeline_receipt",
    "aip_memory_pipeline_receipt_candidate",
    "aip_memory_pipeline_checkpoint_revision",
    "aip_memory_pipeline_alert",
)

_PIPELINE_KIND_CHECK = """CHECK (pipeline_kind IN (
  'seed_import','operational_learning','network_learning',
  'competitor_analysis','professional_database','customer_feedback',
  'human_experience'
))"""


def upgrade() -> None:
    op.execute(
        f"""CREATE TABLE aip_memory_pipeline_schedule (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          schedule_id TEXT NOT NULL, pipeline_kind TEXT NOT NULL,
          trigger TEXT NOT NULL, config_ref JSONB NOT NULL,
          schedule_spec TEXT, status TEXT NOT NULL,
          checkpoint_version BIGINT NOT NULL DEFAULT 0,
          next_run_at TIMESTAMPTZ, idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,schedule_id),
          UNIQUE (org_id,project_id,idempotency_key),
          {_PIPELINE_KIND_CHECK},
          CHECK (trigger IN ('manual','task_event','scheduled','version_event','domain_event')),
          CHECK (status IN ('active','paused','disabled')),
          CHECK (checkpoint_version >= 0), CHECK (version >= 1),
          CHECK (request_hash ~ '^[0-9a-f]{{64}}$'),
          CHECK ((trigger='scheduled') = (schedule_spec IS NOT NULL)),
          FOREIGN KEY (org_id,project_id)
            REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_memory_pipeline_run (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          pipeline_run_id TEXT NOT NULL, schedule_id TEXT NOT NULL,
          task_id TEXT NOT NULL, run_id TEXT NOT NULL,
          trigger TEXT NOT NULL, status TEXT NOT NULL,
          attempt BIGINT NOT NULL DEFAULT 1, retry_of_run_id TEXT,
          expected_checkpoint_version BIGINT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          version BIGINT NOT NULL DEFAULT 1, scheduled_for TIMESTAMPTZ NOT NULL,
          lease_owner TEXT, lease_expires_at TIMESTAMPTZ,
          started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,pipeline_run_id),
          UNIQUE (org_id,project_id,idempotency_key),
          CHECK (trigger IN ('manual','task_event','scheduled','version_event','domain_event')),
          CHECK (status IN ('queued','running','paused','succeeded','partial','failed','cancelled','unknown')),
          CHECK (attempt >= 1), CHECK (expected_checkpoint_version >= 0),
          CHECK (version >= 1), CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL)),
          CHECK (retry_of_run_id IS NULL OR retry_of_run_id<>pipeline_run_id),
          FOREIGN KEY (org_id,project_id,schedule_id)
            REFERENCES aip_memory_pipeline_schedule(org_id,project_id,schedule_id),
          FOREIGN KEY (org_id,project_id,task_id)
            REFERENCES aip_task(org_id,project_id,task_id),
          FOREIGN KEY (org_id,project_id,run_id)
            REFERENCES aip_task_run(org_id,project_id,run_id),
          FOREIGN KEY (org_id,project_id,retry_of_run_id)
            REFERENCES aip_memory_pipeline_run(org_id,project_id,pipeline_run_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_memory_pipeline_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          receipt_id TEXT NOT NULL, pipeline_run_id TEXT NOT NULL,
          status TEXT NOT NULL, input_hash TEXT NOT NULL, output_hash TEXT NOT NULL,
          checkpoint_before_version BIGINT NOT NULL,
          checkpoint_after_version BIGINT NOT NULL,
          produced_count BIGINT NOT NULL, failed_count BIGINT NOT NULL,
          error_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
          receipt_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,receipt_id),
          UNIQUE (org_id,project_id,pipeline_run_id),
          CHECK (status IN ('succeeded','partial','failed','cancelled','unknown')),
          CHECK (input_hash ~ '^[0-9a-f]{64}$'),
          CHECK (output_hash ~ '^[0-9a-f]{64}$'),
          CHECK (receipt_hash ~ '^[0-9a-f]{64}$'),
          CHECK (checkpoint_before_version >= 0),
          CHECK (checkpoint_after_version >= checkpoint_before_version),
          CHECK (produced_count >= 0 AND failed_count >= 0),
          CHECK (jsonb_typeof(error_codes)='array'),
          CHECK (status IN ('succeeded','partial') OR
                 checkpoint_after_version=checkpoint_before_version),
          FOREIGN KEY (org_id,project_id,pipeline_run_id)
            REFERENCES aip_memory_pipeline_run(org_id,project_id,pipeline_run_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_memory_pipeline_receipt_candidate (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          receipt_id TEXT NOT NULL, sequence BIGINT NOT NULL,
          candidate_id TEXT NOT NULL, candidate_revision BIGINT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,receipt_id,sequence),
          UNIQUE (org_id,project_id,receipt_id,candidate_id),
          CHECK (sequence >= 1), CHECK (candidate_revision >= 1),
          FOREIGN KEY (org_id,project_id,receipt_id)
            REFERENCES aip_memory_pipeline_receipt(org_id,project_id,receipt_id),
          FOREIGN KEY (org_id,project_id,candidate_id)
            REFERENCES aip_memory_candidate(org_id,project_id,candidate_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_memory_pipeline_checkpoint_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          schedule_id TEXT NOT NULL, revision BIGINT NOT NULL,
          pipeline_run_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          checkpoint_ref JSONB NOT NULL, checkpoint_hash TEXT NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,schedule_id,revision),
          UNIQUE (org_id,project_id,pipeline_run_id),
          CHECK (revision >= 1), CHECK (checkpoint_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY (org_id,project_id,schedule_id)
            REFERENCES aip_memory_pipeline_schedule(org_id,project_id,schedule_id),
          FOREIGN KEY (org_id,project_id,pipeline_run_id)
            REFERENCES aip_memory_pipeline_run(org_id,project_id,pipeline_run_id),
          FOREIGN KEY (org_id,project_id,receipt_id)
            REFERENCES aip_memory_pipeline_receipt(org_id,project_id,receipt_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_memory_pipeline_alert (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          alert_id TEXT NOT NULL, pipeline_run_id TEXT NOT NULL,
          code TEXT NOT NULL, severity TEXT NOT NULL,
          evidence_ref JSONB NOT NULL, alert_hash TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,alert_id),
          CHECK (severity IN ('warning','error','critical')),
          CHECK (alert_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY (org_id,project_id,pipeline_run_id)
            REFERENCES aip_memory_pipeline_run(org_id,project_id,pipeline_run_id)
        )"""
    )

    op.execute(
        """CREATE INDEX aip_memory_pipeline_schedule_due_idx
        ON aip_memory_pipeline_schedule
          (org_id,project_id,status,next_run_at,schedule_id)"""
    )
    op.execute(
        """CREATE INDEX aip_memory_pipeline_run_timeline_idx
        ON aip_memory_pipeline_run
          (org_id,project_id,schedule_id,scheduled_for,pipeline_run_id)"""
    )
    op.execute(
        """CREATE INDEX aip_memory_pipeline_alert_timeline_idx
        ON aip_memory_pipeline_alert
          (org_id,project_id,pipeline_run_id,created_at,alert_id)"""
    )

    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope_{table}_aip5 ON {table} TO aos_runtime
            USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
        )

    for table in _APPEND_ONLY_TABLES:
        op.execute(
            f"""CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_aip5_memory_append_only()"""
        )
        op.execute(
            f"""CREATE TRIGGER trg_{table}_truncate_guard
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION guard_aip5_memory_append_only()"""
        )
        op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")

    for table in ("aip_memory_pipeline_schedule", "aip_memory_pipeline_run"):
        op.execute(f"GRANT SELECT,INSERT,UPDATE ON {table} TO aos_runtime")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table}")
