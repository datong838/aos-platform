"""Add HandoffDecisionRevision authority separate from Envelope transport (W-L12).

Revision ID: w2_007
Revises: w2_006
Create Date: 2026-08-20
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w2_007"
down_revision: str | Sequence[str] | None = "w2_006"
branch_labels = None
depends_on = None


def _tenant_table(name: str) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{name}_w2_007 ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"GRANT SELECT,INSERT,UPDATE ON {name} TO aos_runtime")


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_handoff_decision_head (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, handoff_id TEXT NOT NULL,
          current_revision BIGINT NOT NULL, version BIGINT NOT NULL DEFAULT 1,
          terminal_decision TEXT,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,handoff_id),
          CHECK(current_revision>=1), CHECK(version>=1),
          CHECK(terminal_decision IS NULL OR terminal_decision IN
            ('accepted','rejected','returned')),
          FOREIGN KEY(org_id,project_id,handoff_id)
            REFERENCES aip_handoff_envelope(org_id,project_id,handoff_id)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_handoff_decision_revision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, decision_id TEXT NOT NULL,
          handoff_id TEXT NOT NULL, revision BIGINT NOT NULL,
          envelope_ref JSONB NOT NULL, decision TEXT NOT NULL,
          reason_code TEXT, gap_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
          return_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
          correlation_ref JSONB, receiver_instance_ref JSONB NOT NULL,
          content_hash TEXT NOT NULL, actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,decision_id),
          UNIQUE(org_id,project_id,handoff_id,revision),
          CHECK(revision>=1),
          CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(decision IN ('accepted','rejected','request_more','returned')),
          CHECK(jsonb_typeof(envelope_ref)='object'),
          CHECK(jsonb_typeof(gap_codes)='array'),
          CHECK(jsonb_typeof(return_refs)='array'),
          CHECK(jsonb_typeof(receiver_instance_ref)='object'),
          FOREIGN KEY(org_id,project_id,handoff_id)
            REFERENCES aip_handoff_envelope(org_id,project_id,handoff_id)
        )"""
    )
    _tenant_table("aip_handoff_decision_head")
    op.execute(f"GRANT SELECT,INSERT ON aip_handoff_decision_revision TO aos_runtime")
    op.execute(f"ALTER TABLE aip_handoff_decision_revision ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE aip_handoff_decision_revision FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_aip_handoff_decision_revision_w2_007
        ON aip_handoff_decision_revision TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_handoff_decision_revision_append_only
        BEFORE UPDATE OR DELETE ON aip_handoff_decision_revision
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
    )
    op.execute(
        "CREATE INDEX aip_handoff_decision_handoff_idx ON aip_handoff_decision_revision"
        "(org_id,project_id,handoff_id,revision DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aip_handoff_decision_revision")
    op.execute("DROP TABLE IF EXISTS aip_handoff_decision_head")
