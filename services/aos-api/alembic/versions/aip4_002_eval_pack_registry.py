"""AIP-4 E1A immutable EvalPack suite revisions.

Revision ID: aip4_002
Revises: aip4_001
Create Date: 2026-08-11
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip4_002"
down_revision: str | Sequence[str] | None = "aip4_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_eval_suite_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          suite_id TEXT NOT NULL, revision BIGINT NOT NULL,
          content_hash TEXT NOT NULL, target_ref JSONB NOT NULL,
          dataset_ref JSONB NOT NULL, judge_ref JSONB NOT NULL,
          cases JSONB NOT NULL, gate_threshold DOUBLE PRECISION NOT NULL,
          actor TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id,project_id,suite_id,revision),
          UNIQUE (org_id,project_id,suite_id,content_hash),
          CHECK (revision >= 1), CHECK (length(content_hash)=64),
          CHECK (jsonb_typeof(cases)='array' AND jsonb_array_length(cases)>0),
          CHECK (gate_threshold >= 0 AND gate_threshold <= 1),
          FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
        )"""
    )
    op.execute("ALTER TABLE aip_eval_suite_revision ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_eval_suite_revision FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_aip_eval_suite_revision_aip4
        ON aip_eval_suite_revision TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_eval_suite_revision_append_only
        BEFORE UPDATE OR DELETE ON aip_eval_suite_revision
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_eval_suite_revision_truncate_guard
        BEFORE TRUNCATE ON aip_eval_suite_revision
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute("GRANT SELECT,INSERT ON aip_eval_suite_revision TO aos_runtime")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_eval_suite_revision CASCADE")
