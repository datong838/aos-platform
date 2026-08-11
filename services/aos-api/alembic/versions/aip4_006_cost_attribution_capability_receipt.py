"""Add append-only usage attribution and capability receipts.

Revision ID: aip4_006
Revises: aip4_005
Create Date: 2026-08-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip4_006"
down_revision: str | Sequence[str] | None = "aip4_005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("aip_usage_attribution", "aip_capability_receipt")


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_usage_attribution (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          attribution_id TEXT NOT NULL, receipt_id TEXT NOT NULL,
          lineage_id TEXT NOT NULL, subject_type TEXT NOT NULL,
          subject_id TEXT NOT NULL, subject_revision TEXT NOT NULL,
          subject_authority TEXT NOT NULL, quality TEXT NOT NULL,
          weight DOUBLE PRECISION NOT NULL, source_hash TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,attribution_id),
          UNIQUE (org_id,project_id,receipt_id,subject_type,subject_id,subject_revision),
          CHECK (subject_type IN ('model','tool','capability','task','agent')),
          CHECK (quality IN ('measured','estimated','unknown')),
          CHECK (weight > 0 AND weight <= 1),
          CHECK (length(source_hash)=64),
          FOREIGN KEY (org_id,project_id,receipt_id)
            REFERENCES aip_usage_receipt(org_id,project_id,receipt_id)
        )"""
    )
    op.execute(
        """CREATE INDEX aip_usage_attribution_subject_idx
        ON aip_usage_attribution(
          org_id,project_id,subject_type,subject_id,subject_revision,created_at
        )"""
    )
    op.execute(
        """CREATE TABLE aip_capability_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          capability_receipt_id TEXT NOT NULL, provider TEXT NOT NULL,
          provider_receipt_id TEXT NOT NULL, lineage_id TEXT NOT NULL,
          task_run_id TEXT NOT NULL, step_key TEXT NOT NULL,
          capability_type TEXT NOT NULL, capability_id TEXT NOT NULL,
          capability_revision TEXT NOT NULL, capability_authority TEXT NOT NULL,
          status TEXT NOT NULL, quality TEXT NOT NULL,
          input_hash TEXT NOT NULL, output_hash TEXT,
          source_hash TEXT NOT NULL, observed_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,capability_receipt_id),
          UNIQUE (org_id,project_id,provider,provider_receipt_id),
          CHECK (capability_type='capability'),
          CHECK (status IN ('succeeded','failed','unknown','reconciled')),
          CHECK (quality IN ('measured','estimated','unknown')),
          CHECK (length(input_hash)=64),
          CHECK (output_hash IS NULL OR length(output_hash)=64),
          CHECK (length(source_hash)=64),
          CHECK (status NOT IN ('succeeded','reconciled') OR output_hash IS NOT NULL),
          CHECK (status<>'unknown' OR quality='unknown'),
          FOREIGN KEY (org_id,project_id,task_run_id)
            REFERENCES aip_task_run(org_id,project_id,run_id)
        )"""
    )
    op.execute(
        """CREATE INDEX aip_capability_receipt_lineage_idx
        ON aip_capability_receipt(org_id,project_id,lineage_id,observed_at,capability_receipt_id)"""
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
