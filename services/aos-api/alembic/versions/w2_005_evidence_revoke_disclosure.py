"""Add EvidenceBundle revoke events and disclosure decision authority (W-L10).

Revision ID: w2_005
Revises: aip6_008
Create Date: 2026-08-20
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w2_005"
down_revision: str | Sequence[str] | None = "aip6_008"
branch_labels = None
depends_on = None

TABLES = (
    "aip_evidence_bundle_revoke_event",
    "aip_evidence_disclosure_decision",
)


def _tenant_table(name: str) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{name}_w2_005 ON {name} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"GRANT SELECT,INSERT ON {name} TO aos_runtime")


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_evidence_bundle_revoke_event (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
          bundle_id TEXT NOT NULL, revision BIGINT NOT NULL, content_hash TEXT NOT NULL,
          reason TEXT NOT NULL, actor TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,event_id),
          UNIQUE(org_id,project_id,bundle_id,revision,content_hash),
          CHECK(revision>=1), CHECK(content_hash ~ '^[0-9a-f]{64}$'),
          CHECK(char_length(reason) BETWEEN 1 AND 500)
        )"""
    )
    op.execute(
        """CREATE TABLE aip_evidence_disclosure_decision (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, decision_id TEXT NOT NULL,
          evidence_id TEXT NOT NULL, evidence_hash TEXT NOT NULL, purpose TEXT NOT NULL,
          requested_level TEXT NOT NULL, granted_level TEXT, status TEXT NOT NULL,
          reasons JSONB NOT NULL, citation JSONB NOT NULL, display_payload JSONB NOT NULL,
          redaction_receipt JSONB NOT NULL, decision_hash TEXT NOT NULL,
          expires_at TIMESTAMPTZ, actor TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,decision_id),
          CHECK(evidence_hash ~ '^[0-9a-f]{64}$'),
          CHECK(decision_hash ~ '^[0-9a-f]{64}$'),
          CHECK(requested_level IN ('l1','l2','l3')),
          CHECK(granted_level IS NULL OR granted_level IN ('l1','l2','l3')),
          CHECK(status IN ('allowed','blocked','stale','unknown')),
          CHECK(jsonb_typeof(reasons)='array'),
          CHECK(jsonb_typeof(citation)='object'),
          CHECK(jsonb_typeof(display_payload)='object'),
          CHECK(jsonb_typeof(redaction_receipt)='object')
        )"""
    )
    for table in TABLES:
        _tenant_table(table)
    op.execute(
        "CREATE INDEX aip_bundle_revoke_bundle_idx ON aip_evidence_bundle_revoke_event"
        "(org_id,project_id,bundle_id,revision,occurred_at DESC)"
    )
    op.execute(
        "CREATE INDEX aip_disclosure_evidence_idx ON aip_evidence_disclosure_decision"
        "(org_id,project_id,evidence_id,created_at DESC)"
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
