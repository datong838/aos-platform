"""Creator explicit start, partial and collaboration lifecycle (W6-04).

Revision ID: w6_004
Revises: w6_003
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w6_004"
down_revision: str | Sequence[str] | None = "w6_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = (
    ("ecommerce_creator_batch_start_decision_revision", "decision_id", "batch_id TEXT NOT NULL,"),
    ("ecommerce_creator_lane_observation", "observation_id", "decision_id TEXT NOT NULL,lane_id TEXT NOT NULL,"),
    ("ecommerce_creator_contract_revision", "collaboration_id", ""),
    ("ecommerce_creator_delivery_observation", "observation_id", ""),
    ("ecommerce_creator_relationship_revision", "relationship_id", ""),
)


def upgrade() -> None:
    for table, identity, extra in TABLES:
        op.execute(f"""
        CREATE TABLE {table} (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          {identity} TEXT NOT NULL,
          revision INTEGER NOT NULL CHECK (revision >= 1),
          {extra}
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
    op.execute("CREATE INDEX ecommerce_creator_start_batch_idx ON ecommerce_creator_batch_start_decision_revision(org_id,project_id,batch_id,revision DESC)")
    op.execute("CREATE INDEX ecommerce_creator_lane_decision_idx ON ecommerce_creator_lane_observation(org_id,project_id,decision_id,lane_id,created_at)")


def downgrade() -> None:
    for table, _identity, _extra in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
