"""Close ReviewIssue rule, event payload and return impact lineage.

Revision ID: w4_003
Revises: w4_002
Create Date: 2026-08-25
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w4_003"
down_revision: str | Sequence[str] | None = "w4_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_review_rule_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, rule_id TEXT NOT NULL,
          revision BIGINT NOT NULL, spec JSONB NOT NULL, content_hash TEXT NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,rule_id,revision),
          CHECK(revision>=1), CHECK(jsonb_typeof(spec)='object'),
          CHECK(content_hash ~ '^[0-9a-f]{64}$'))"""
    )
    op.execute("ALTER TABLE aip_review_rule_revision ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_review_rule_revision FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY aip_review_rule_revision_tenant ON aip_review_rule_revision
        TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute("GRANT SELECT,INSERT ON aip_review_rule_revision TO aos_runtime")
    op.execute("REVOKE UPDATE,DELETE,TRUNCATE ON aip_review_rule_revision FROM aos_runtime")
    op.execute(
        """CREATE TRIGGER trg_aip_review_rule_revision_append_only_w4_003
        BEFORE UPDATE OR DELETE ON aip_review_rule_revision
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute("ALTER TABLE aip_review_issue_event ADD COLUMN payload JSONB")
    op.execute(
        """ALTER TABLE aip_review_issue_event ADD CONSTRAINT
        ck_aip_review_issue_event_payload_w4_003
        CHECK (payload IS NULL OR jsonb_typeof(payload)='object')"""
    )
    op.execute(
        """ALTER TABLE aip_return_decision ADD COLUMN impact_decisions JSONB
        NOT NULL DEFAULT '[]'::jsonb"""
    )
    op.execute(
        """ALTER TABLE aip_return_decision ADD CONSTRAINT
        ck_aip_return_decision_impact_w4_003
        CHECK (jsonb_typeof(impact_decisions)='array'
          AND jsonb_array_length(impact_decisions)>=1) NOT VALID"""
    )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN IF EXISTS (
          SELECT 1 FROM aip_review_rule_revision LIMIT 1
        ) OR EXISTS (
          SELECT 1 FROM aip_review_issue_event WHERE payload IS NOT NULL LIMIT 1
        ) OR EXISTS (
          SELECT 1 FROM aip_return_decision
          WHERE jsonb_array_length(impact_decisions)>0 LIMIT 1
        ) THEN RAISE EXCEPTION 'cannot downgrade w4_003 with review lineage facts'
          USING ERRCODE='55000'; END IF; END $$"""
    )
    op.execute("ALTER TABLE aip_return_decision DROP COLUMN impact_decisions")
    op.execute("ALTER TABLE aip_review_issue_event DROP COLUMN payload")
    op.execute("DROP TABLE aip_review_rule_revision")
