"""Price research, match, policy and side-effect-free batch authority (W6-05).

Revision ID: w6_005
Revises: w6_004
"""
from __future__ import annotations

from collections.abc import Sequence
from alembic import op

revision: str = "w6_005"
down_revision: str | Sequence[str] | None = "w6_004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    ("ecommerce_price_research_profile_revision", "profile_id"),
    ("ecommerce_price_observation_revision", "observation_id"),
    ("ecommerce_price_product_match_observation", "match_observation_id"),
    ("ecommerce_price_product_match_decision_revision", "decision_id"),
    ("ecommerce_price_monitoring_policy_revision", "policy_id"),
    ("ecommerce_price_research_batch_revision", "batch_id"),
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
