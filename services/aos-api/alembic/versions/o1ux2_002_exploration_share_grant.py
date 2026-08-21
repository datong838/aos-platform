"""O1-UX2 SavedExploration share grant authority (W-L16).

Revision ID: o1ux2_002
Revises: w2_007
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "o1ux2_002"
down_revision: str | Sequence[str] | None = "w2_007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE ontology_exploration_share_grant (
          org_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          grant_id TEXT NOT NULL,
          opaque_ref TEXT NOT NULL,
          asset_id TEXT NOT NULL,
          asset_revision INTEGER NOT NULL CHECK (asset_revision >= 1),
          asset_payload_hash CHAR(64) NOT NULL CHECK (asset_payload_hash ~ '^[0-9a-f]{64}$'),
          grantor_subject TEXT NOT NULL CHECK (BTRIM(grantor_subject) <> ''),
          grantee_scope TEXT NOT NULL CHECK (grantee_scope IN ('workspace','link')),
          purpose TEXT NOT NULL DEFAULT 'exploration_read'
            CHECK (BTRIM(purpose) <> ''),
          markings JSONB NOT NULL DEFAULT '[]'::jsonb,
          status TEXT NOT NULL CHECK (status IN ('active','expired','revoked')),
          issued_at TIMESTAMPTZ NOT NULL,
          expires_at TIMESTAMPTZ NOT NULL,
          revoked_at TIMESTAMPTZ,
          revoke_reason TEXT,
          version BIGINT NOT NULL DEFAULT 1 CHECK (version >= 1),
          PRIMARY KEY (org_id, workspace_id, grant_id),
          UNIQUE (org_id, workspace_id, opaque_ref),
          CHECK (expires_at > issued_at),
          CHECK (
            (status = 'revoked' AND revoked_at IS NOT NULL)
            OR (status <> 'revoked' AND revoked_at IS NULL)
          ),
          FOREIGN KEY (org_id, workspace_id)
            REFERENCES twa_workspace(org_id, project_id) ON DELETE RESTRICT,
          FOREIGN KEY (org_id, workspace_id, asset_id)
            REFERENCES ontology_exploration_asset_head(org_id, workspace_id, asset_id)
            ON DELETE RESTRICT
        )"""
    )
    op.execute(
        """CREATE TABLE ontology_exploration_share_grant_receipt (
          org_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          receipt_id TEXT NOT NULL,
          grant_id TEXT NOT NULL,
          command TEXT NOT NULL CHECK (command IN ('create','revoke')),
          idempotency_key TEXT NOT NULL,
          request_hash CHAR(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
          actor TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, workspace_id, receipt_id),
          UNIQUE (org_id, workspace_id, command, idempotency_key),
          FOREIGN KEY (org_id, workspace_id, grant_id)
            REFERENCES ontology_exploration_share_grant(org_id, workspace_id, grant_id)
            ON DELETE RESTRICT
        )"""
    )
    op.execute(
        """CREATE INDEX ontology_exploration_share_grant_asset_idx
           ON ontology_exploration_share_grant(org_id, workspace_id, asset_id, issued_at DESC)"""
    )
    op.execute(
        "ALTER TABLE ontology_exploration_share_grant ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ontology_exploration_share_grant FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """CREATE POLICY tenant_scope_ontology_exploration_share_grant
           ON ontology_exploration_share_grant TO aos_runtime
           USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND workspace_id=NULLIF(current_setting('aos.project_id',true),''))
           WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND workspace_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(
        "ALTER TABLE ontology_exploration_share_grant_receipt ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ontology_exploration_share_grant_receipt FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """CREATE POLICY tenant_scope_ontology_exploration_share_grant_receipt
           ON ontology_exploration_share_grant_receipt TO aos_runtime
           USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND workspace_id=NULLIF(current_setting('aos.project_id',true),''))
           WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND workspace_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(
        "GRANT SELECT,INSERT,UPDATE ON ontology_exploration_share_grant TO aos_runtime"
    )
    op.execute(
        "GRANT SELECT,INSERT ON ontology_exploration_share_grant_receipt TO aos_runtime"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ontology_exploration_share_grant_receipt CASCADE")
    op.execute("DROP TABLE IF EXISTS ontology_exploration_share_grant CASCADE")
