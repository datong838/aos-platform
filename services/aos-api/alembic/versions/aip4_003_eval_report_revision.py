"""AIP-4 E1B immutable Eval report revisions.

Revision ID: aip4_003
Revises: aip4_002
Create Date: 2026-08-11
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip4_003"
down_revision: str | Sequence[str] | None = "aip4_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_eval_report_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          report_id TEXT NOT NULL, revision BIGINT NOT NULL,
          content_hash TEXT NOT NULL, run_id TEXT NOT NULL,
          suite_ref JSONB NOT NULL, target_ref JSONB NOT NULL,
          dataset_ref JSONB NOT NULL, judge_ref JSONB NOT NULL,
          results JSONB NOT NULL, passed BIGINT NOT NULL, failed BIGINT NOT NULL,
          total BIGINT NOT NULL, pass_rate DOUBLE PRECISION NOT NULL,
          gate_passed BOOLEAN NOT NULL, created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,report_id,revision),
          UNIQUE (org_id,project_id,run_id),
          UNIQUE (org_id,project_id,report_id,content_hash),
          CHECK (revision >= 1), CHECK (length(content_hash)=64),
          CHECK (jsonb_typeof(results)='array' AND jsonb_array_length(results)>0),
          CHECK (passed >= 0 AND failed >= 0 AND total > 0),
          CHECK (passed + failed = total),
          CHECK (pass_rate >= 0 AND pass_rate <= 1),
          FOREIGN KEY (org_id,project_id,run_id)
            REFERENCES aip_eval_run(org_id,project_id,run_id)
        )"""
    )
    op.execute("ALTER TABLE aip_eval_report_revision ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_eval_report_revision FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_aip_eval_report_revision_aip4
        ON aip_eval_report_revision TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_eval_report_revision_append_only
        BEFORE UPDATE OR DELETE ON aip_eval_report_revision
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_eval_report_revision_truncate_guard
        BEFORE TRUNCATE ON aip_eval_report_revision
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute("GRANT SELECT,INSERT ON aip_eval_report_revision TO aos_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_eval_report_revision CASCADE")
