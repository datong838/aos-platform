"""Add the append-only ResearchJob provider and receipt authority.

Revision ID: aip4_007
Revises: aip4_006
Create Date: 2026-08-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip4_007"
down_revision: str | Sequence[str] | None = "aip4_006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "aip_research_provider_revision",
    "aip_research_job_manifest",
    "aip_research_submission_receipt",
    "aip_research_event_receipt",
    "aip_research_callback_nonce",
    "aip_research_artifact_receipt",
    "aip_research_delivery_receipt",
)


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_research_provider_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          provider_id TEXT NOT NULL, revision BIGINT NOT NULL,
          adapter_kind TEXT NOT NULL, capability_type TEXT NOT NULL,
          capability_id TEXT NOT NULL, capability_revision TEXT NOT NULL,
          capability_authority TEXT NOT NULL, contract_hash TEXT NOT NULL,
          callback_secret_ref_hash TEXT NOT NULL, status TEXT NOT NULL,
          source_hash TEXT NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,provider_id,revision),
          CHECK (revision >= 1), CHECK (capability_type='capability'),
          CHECK (status IN ('enabled','disabled')),
          CHECK (length(contract_hash)=64),
          CHECK (length(callback_secret_ref_hash)=64),
          CHECK (length(source_hash)=64)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_research_job_manifest (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          job_id TEXT NOT NULL, run_id TEXT NOT NULL,
          plan_revision_id TEXT NOT NULL, step_key TEXT NOT NULL,
          provider_id TEXT NOT NULL, provider_revision BIGINT NOT NULL,
          capability_type TEXT NOT NULL, capability_id TEXT NOT NULL,
          capability_revision TEXT NOT NULL, capability_authority TEXT NOT NULL,
          manifest_hash TEXT NOT NULL, output_schema_hash TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          manifest JSONB NOT NULL, created_by TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,job_id),
          UNIQUE (org_id,project_id,run_id,step_key),
          UNIQUE (org_id,project_id,idempotency_key),
          CHECK (provider_revision >= 1), CHECK (capability_type='capability'),
          CHECK (length(manifest_hash)=64), CHECK (length(output_schema_hash)=64),
          CHECK (length(request_hash)=64),
          FOREIGN KEY (org_id,project_id,run_id)
            REFERENCES aip_task_run(org_id,project_id,run_id),
          FOREIGN KEY (org_id,project_id,provider_id,provider_revision)
            REFERENCES aip_research_provider_revision(org_id,project_id,provider_id,revision)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_research_submission_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          submission_receipt_id TEXT NOT NULL, job_id TEXT NOT NULL,
          provider_execution_id TEXT NOT NULL, provider_version TEXT NOT NULL,
          accepted_manifest_hash TEXT NOT NULL, source_hash TEXT NOT NULL,
          observed_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,submission_receipt_id),
          UNIQUE (org_id,project_id,job_id),
          UNIQUE (org_id,project_id,provider_execution_id),
          CHECK (length(accepted_manifest_hash)=64), CHECK (length(source_hash)=64),
          FOREIGN KEY (org_id,project_id,job_id)
            REFERENCES aip_research_job_manifest(org_id,project_id,job_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_research_event_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          event_receipt_id TEXT NOT NULL, job_id TEXT NOT NULL,
          provider_execution_id TEXT NOT NULL, sequence BIGINT NOT NULL,
          provider_event_id TEXT NOT NULL, status TEXT NOT NULL,
          payload_hash TEXT NOT NULL, observed_at TIMESTAMPTZ NOT NULL,
          created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,event_receipt_id),
          UNIQUE (org_id,project_id,provider_execution_id,sequence),
          UNIQUE (org_id,project_id,provider_execution_id,provider_event_id),
          CHECK (sequence >= 1),
          CHECK (status IN ('queued','running','succeeded','failed','cancelled','unknown')),
          CHECK (length(payload_hash)=64),
          FOREIGN KEY (org_id,project_id,job_id)
            REFERENCES aip_research_job_manifest(org_id,project_id,job_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_research_callback_nonce (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          callback_receipt_id TEXT NOT NULL, provider_id TEXT NOT NULL,
          provider_revision BIGINT NOT NULL, nonce_hash TEXT NOT NULL,
          body_hash TEXT NOT NULL, callback_timestamp BIGINT NOT NULL,
          observed_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,callback_receipt_id),
          UNIQUE (org_id,project_id,provider_id,nonce_hash),
          CHECK (length(nonce_hash)=64), CHECK (length(body_hash)=64),
          FOREIGN KEY (org_id,project_id,provider_id,provider_revision)
            REFERENCES aip_research_provider_revision(org_id,project_id,provider_id,revision)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_research_artifact_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          artifact_receipt_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
          job_id TEXT NOT NULL, provider_execution_id TEXT NOT NULL,
          content_ref TEXT NOT NULL, media_type TEXT NOT NULL,
          content_hash TEXT NOT NULL, source_hash TEXT NOT NULL,
          observed_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,artifact_receipt_id),
          UNIQUE (org_id,project_id,job_id,content_ref),
          UNIQUE (org_id,project_id,artifact_id),
          CHECK (length(content_hash)=64), CHECK (length(source_hash)=64),
          FOREIGN KEY (org_id,project_id,job_id)
            REFERENCES aip_research_job_manifest(org_id,project_id,job_id),
          FOREIGN KEY (org_id,project_id,artifact_id)
            REFERENCES aip_artifact(org_id,project_id,artifact_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_research_delivery_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          receipt_id TEXT NOT NULL, job_id TEXT NOT NULL,
          provider_execution_id TEXT NOT NULL, receipt_kind TEXT NOT NULL,
          status TEXT NOT NULL, artifact_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
          reason_code TEXT, source_hash TEXT NOT NULL,
          observed_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,receipt_id),
          CHECK (receipt_kind IN ('delivery','reconcile')),
          CHECK (status IN ('succeeded','failed','cancelled','unknown','reconciled')),
          CHECK (length(source_hash)=64),
          CHECK (receipt_kind<>'reconcile' OR reason_code IS NOT NULL),
          FOREIGN KEY (org_id,project_id,job_id)
            REFERENCES aip_research_job_manifest(org_id,project_id,job_id)
        )"""
    )
    op.execute(
        """CREATE INDEX aip_research_event_timeline_idx
        ON aip_research_event_receipt(org_id,project_id,job_id,sequence,provider_event_id)"""
    )
    op.execute(
        """CREATE INDEX aip_research_delivery_timeline_idx
        ON aip_research_delivery_receipt(org_id,project_id,job_id,created_at,receipt_id)"""
    )
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_scope_{table}_aip4 ON {table} TO aos_runtime
            USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
               AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
        )
        op.execute(
            f"""CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
        )
        op.execute(
            f"""CREATE TRIGGER trg_{table}_truncate_guard
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
        )
        op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table}")
