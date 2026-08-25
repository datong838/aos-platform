"""Customer consent, segment, journey, dialogue and zero-send batch authority (W6-07).

Revision ID: w6_007
Revises: w6_006
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w6_007"
down_revision: str | Sequence[str] | None = "w6_006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    ("ecommerce_customer_consent_policy_revision", "policy_id"),
    ("ecommerce_customer_segment_revision", "segment_id"),
    ("ecommerce_customer_journey_revision", "journey_id"),
    ("ecommerce_customer_dialogue_strategy_revision", "dialogue_id"),
    ("ecommerce_customer_dialogue_batch_revision", "batch_id"),
)


def upgrade() -> None:
    for table, identity in TABLES:
        op.execute(f"""
        CREATE TABLE {table} (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, {identity} TEXT NOT NULL,
          revision INTEGER NOT NULL CHECK (revision >= 1),
          content_hash CHAR(64) NOT NULL CHECK (content_hash ~ '^[0-9a-f]{{64}}$'),
          authority_data JSONB NOT NULL CHECK (jsonb_typeof(authority_data)='object'),
          created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (org_id,project_id,{identity},revision),
          FOREIGN KEY (org_id,project_id) REFERENCES meta_workspace(org_id,project_id)
        );
        ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_scope ON {table}
          USING (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
        GRANT SELECT, INSERT ON {table} TO aos_runtime;
        """)


def downgrade() -> None:
    for table, _identity in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
