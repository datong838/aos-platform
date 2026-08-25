"""Customer contact governance without contact resolution or dispatch (W6-08).

Revision ID: w6_008
Revises: w6_007
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w6_008"
down_revision: str | Sequence[str] | None = "w6_007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = (
    ("ecommerce_customer_frequency_policy_revision", "policy_id", ""),
    ("ecommerce_customer_frequency_reservation_revision", "reservation_id", "customer_id TEXT NOT NULL,policy_id TEXT NOT NULL,sequence BIGINT NOT NULL CHECK(sequence>=1),status TEXT NOT NULL CHECK(status='held'),"),
    ("ecommerce_customer_consent_withdrawal_observation", "observation_id", "customer_id TEXT NOT NULL,consent_policy_id TEXT NOT NULL,sequence BIGINT NOT NULL CHECK(sequence>=1),"),
    ("ecommerce_customer_batch_start_decision_revision", "decision_id", "batch_id TEXT NOT NULL,"),
    ("ecommerce_customer_dispatch_observation", "observation_id", "decision_id TEXT NOT NULL,item_key TEXT NOT NULL,"),
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
    op.execute("CREATE INDEX ecommerce_customer_withdrawal_sequence_idx ON ecommerce_customer_consent_withdrawal_observation(org_id,project_id,customer_id,consent_policy_id,sequence DESC)")
    op.execute("CREATE INDEX ecommerce_customer_frequency_reservation_window_idx ON ecommerce_customer_frequency_reservation_revision(org_id,project_id,customer_id,policy_id,status,created_at DESC)")
    op.execute("CREATE INDEX ecommerce_customer_start_batch_idx ON ecommerce_customer_batch_start_decision_revision(org_id,project_id,batch_id,revision DESC)")
    op.execute("CREATE INDEX ecommerce_customer_dispatch_decision_idx ON ecommerce_customer_dispatch_observation(org_id,project_id,decision_id,item_key,created_at)")


def downgrade() -> None:
    for table, _identity, _extra in reversed(TABLES):
        op.execute(f"DROP TABLE {table}")
