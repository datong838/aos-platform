"""Add tenant-scoped encrypted OAuth token store.

Revision ID: 228ec02oauth
Revises: 6cd2ca0eff8f
"""
from alembic import op

revision = "228ec02oauth"
down_revision = "6cd2ca0eff8f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE oauth_token_store (
          org_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          platform TEXT NOT NULL,
          external_account_id TEXT NOT NULL,
          payload JSONB NOT NULL,
          version BIGINT NOT NULL DEFAULT 1,
          expires_at TIMESTAMPTZ,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, workspace_id, platform, external_account_id)
        )
    """)
    op.execute("CREATE INDEX idx_oauth_token_due ON oauth_token_store (expires_at) WHERE expires_at IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS oauth_token_store")
