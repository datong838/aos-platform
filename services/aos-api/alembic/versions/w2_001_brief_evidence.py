"""Add W2-A task brief and evidence bundle authority.

Revision ID: w2_001
Revises: aip6_004
Create Date: 2026-08-13
"""
from __future__ import annotations

from collections.abc import Sequence
from alembic import op

revision: str = "w2_001"
down_revision: str | Sequence[str] | None = "aip6_004"
branch_labels = None
depends_on = None

TABLES = ("aip_task_brief_revision", "aip_task_brief_head", "aip_evidence_bundle_revision", "aip_production_contract_receipt")


def _tenant_table(name: str) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""CREATE POLICY tenant_scope_{name}_w2 ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute(f"GRANT SELECT,INSERT,UPDATE ON {name} TO aos_runtime")


def upgrade() -> None:
    op.execute("""CREATE TABLE aip_task_brief_head (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, brief_id TEXT NOT NULL,
      task_id TEXT NOT NULL, current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,brief_id), CHECK(current_revision>=1), CHECK(version>=1),
      FOREIGN KEY(org_id,project_id,task_id) REFERENCES aip_task(org_id,project_id,task_id))""")
    op.execute("""CREATE TABLE aip_task_brief_revision (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, brief_id TEXT NOT NULL, revision BIGINT NOT NULL,
      task_id TEXT NOT NULL, brief_type TEXT NOT NULL, schema_ref JSONB NOT NULL, spec JSONB NOT NULL,
      content_hash TEXT NOT NULL, lifecycle TEXT NOT NULL, created_by TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,brief_id,revision),
      CHECK(revision>=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
      CHECK(lifecycle IN ('draft','frozen','withdrawn','superseded')),
      CHECK(jsonb_typeof(schema_ref)='object'), CHECK(jsonb_typeof(spec)='object'),
      FOREIGN KEY(org_id,project_id,task_id) REFERENCES aip_task(org_id,project_id,task_id),
      FOREIGN KEY(org_id,project_id,brief_id) REFERENCES aip_task_brief_head(org_id,project_id,brief_id)
        DEFERRABLE INITIALLY DEFERRED)""")
    op.execute("""CREATE TABLE aip_evidence_bundle_revision (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, bundle_id TEXT NOT NULL, revision BIGINT NOT NULL,
      brief_ref JSONB NOT NULL, subject_refs JSONB NOT NULL, cutoff_at TIMESTAMPTZ NOT NULL,
      item_refs JSONB NOT NULL, coverage TEXT NOT NULL, missing JSONB NOT NULL, conflicts JSONB NOT NULL,
      uncertainties JSONB NOT NULL, freshness TEXT NOT NULL, marking JSONB NOT NULL, license_summary JSONB NOT NULL,
      content_hash TEXT NOT NULL, lifecycle TEXT NOT NULL, created_by TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,bundle_id,revision), UNIQUE(org_id,project_id,bundle_id,content_hash),
      CHECK(revision>=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
      CHECK(coverage IN ('complete','partial','blocked','unknown')),
      CHECK(freshness IN ('fresh','stale','blocked','unknown')),
      CHECK(lifecycle IN ('frozen','withdrawn','superseded')),
      CHECK(jsonb_typeof(brief_ref)='object'), CHECK(jsonb_typeof(subject_refs)='array'),
      CHECK(jsonb_typeof(item_refs)='array'), CHECK(jsonb_typeof(missing)='array'),
      CHECK(jsonb_typeof(conflicts)='array'), CHECK(jsonb_typeof(uncertainties)='array'))""")
    op.execute("""CREATE TABLE aip_production_contract_receipt (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
      operation TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
      result_ref JSONB NOT NULL, created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,receipt_id), UNIQUE(org_id,project_id,operation,idempotency_key),
      CHECK(request_hash ~ '^[0-9a-f]{64}$'), CHECK(jsonb_typeof(result_ref)='object'))""")
    for table in TABLES:
        _tenant_table(table)
    op.execute("REVOKE UPDATE ON aip_task_brief_revision, aip_evidence_bundle_revision, aip_production_contract_receipt FROM aos_runtime")
    op.execute("CREATE INDEX aip_brief_task_idx ON aip_task_brief_head(org_id,project_id,task_id,updated_at DESC)")
    op.execute("CREATE INDEX aip_bundle_cutoff_idx ON aip_evidence_bundle_revision(org_id,project_id,cutoff_at DESC,bundle_id)")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
