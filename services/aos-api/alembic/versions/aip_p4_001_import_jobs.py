"""Add governed AIP import job and reversible candidate authority.

Revision ID: aip_p4_001
Revises: aip_p3_002
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip_p4_001"
down_revision: str | Sequence[str] | None = "aip_p3_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _scope(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_aip_p4_001 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_import_job (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, job_id TEXT NOT NULL,
          preview_id TEXT NOT NULL, preview_content_hash TEXT NOT NULL,
          kind TEXT NOT NULL, target_id TEXT NOT NULL, display_name TEXT NOT NULL,
          request_payload JSONB NOT NULL, conflict_decisions JSONB NOT NULL,
          approval_evidence_ref JSONB, approval_reason TEXT, rollback_reason TEXT,
          created_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          compensated_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          status TEXT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          created_by TEXT NOT NULL, approved_by TEXT, applied_by TEXT,
          created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,job_id),
          UNIQUE (org_id,project_id,preview_id),
          CHECK (preview_content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (kind IN ('agent','capability')),
          CHECK (status IN ('awaiting_approval','approved','applied','rolled_back')),
          CHECK (version >= 1),
          CHECK (jsonb_typeof(request_payload)='object'),
          CHECK (jsonb_typeof(conflict_decisions)='object'),
          CHECK (jsonb_typeof(created_refs)='array'),
          CHECK (jsonb_typeof(compensated_refs)='array'),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_import_candidate (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
          job_id TEXT NOT NULL, kind TEXT NOT NULL, target_id TEXT NOT NULL,
          display_name TEXT NOT NULL, status TEXT NOT NULL, source_ref JSONB NOT NULL,
          payload JSONB NOT NULL, content_hash TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL, rolled_back_at TIMESTAMPTZ,
          PRIMARY KEY (org_id,project_id,candidate_id),
          UNIQUE (org_id,project_id,job_id),
          CHECK (kind IN ('agent','capability')),
          CHECK (status IN ('active','rolled_back')),
          CHECK (content_hash ~ '^[0-9a-f]{64}$'),
          CHECK (jsonb_typeof(source_ref)='object'),
          CHECK (jsonb_typeof(payload)='object'),
          FOREIGN KEY (org_id,project_id,job_id)
            REFERENCES aip_import_job(org_id,project_id,job_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_import_job_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          operation TEXT NOT NULL, idempotency_key TEXT NOT NULL,
          request_hash TEXT NOT NULL, job_id TEXT NOT NULL, status TEXT NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,receipt_id),
          UNIQUE (org_id,project_id,operation,idempotency_key),
          CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          FOREIGN KEY (org_id,project_id,job_id)
            REFERENCES aip_import_job(org_id,project_id,job_id)
        )"""
    )
    for table in ("aip_import_job", "aip_import_candidate", "aip_import_job_receipt"):
        _scope(table)
    op.execute("GRANT SELECT,INSERT,UPDATE ON aip_import_job TO aos_runtime")
    op.execute("GRANT SELECT,INSERT,UPDATE ON aip_import_candidate TO aos_runtime")
    op.execute("GRANT SELECT,INSERT ON aip_import_job_receipt TO aos_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_import_job_receipt")
    op.execute("DROP TABLE IF EXISTS aip_import_candidate")
    op.execute("DROP TABLE IF EXISTS aip_import_job")
