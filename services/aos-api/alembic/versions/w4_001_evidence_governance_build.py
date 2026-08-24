"""Make base Evidence append-only and add exact revoke authority.

Revision ID: w4_001
Revises: w3_013
Create Date: 2026-08-24
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "w4_001"
down_revision: str | Sequence[str] | None = "w3_013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("REVOKE UPDATE,DELETE,TRUNCATE ON aip_evidence FROM aos_runtime")
    op.execute(
        """CREATE TRIGGER trg_aip_evidence_append_only_w4_001
        BEFORE UPDATE OR DELETE ON aip_evidence
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        """CREATE TABLE aip_evidence_revoke_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
          evidence_id TEXT NOT NULL, revision BIGINT NOT NULL DEFAULT 1,
          content_hash TEXT NOT NULL, reason TEXT NOT NULL, actor TEXT NOT NULL,
          occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,event_id),
          UNIQUE(org_id,project_id,evidence_id,revision,content_hash),
          FOREIGN KEY(org_id,project_id,evidence_id)
            REFERENCES aip_evidence(org_id,project_id,evidence_id),
          CHECK(revision=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(char_length(reason) BETWEEN 1 AND 500)
        )"""
    )
    op.execute("ALTER TABLE aip_evidence_revoke_event ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_evidence_revoke_event FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_aip_evidence_revoke_event_w4_001
        ON aip_evidence_revoke_event TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute("GRANT SELECT,INSERT ON aip_evidence_revoke_event TO aos_runtime")
    op.execute("REVOKE UPDATE,DELETE,TRUNCATE ON aip_evidence_revoke_event FROM aos_runtime")
    op.execute(
        """CREATE TRIGGER trg_aip_evidence_revoke_event_append_only_w4_001
        BEFORE UPDATE OR DELETE ON aip_evidence_revoke_event
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        "CREATE INDEX aip_evidence_revoke_lookup_w4_001 ON "
        "aip_evidence_revoke_event(org_id,project_id,evidence_id,revision,occurred_at DESC)"
    )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM aip_evidence_revoke_event LIMIT 1) THEN
          RAISE EXCEPTION 'cannot downgrade w4_001 with canonical Evidence revocations'
            USING ERRCODE = '55000';
        END IF;
        END $$"""
    )
    op.execute("DROP TABLE aip_evidence_revoke_event CASCADE")
    op.execute("DROP TRIGGER trg_aip_evidence_append_only_w4_001 ON aip_evidence")
    op.execute("GRANT UPDATE,DELETE ON aip_evidence TO aos_runtime")
