"""Add tenant-bound AIP feature activation authority. Revision ID: wcat_001."""

from collections.abc import Sequence

from alembic import op


revision: str = "wcat_001"
down_revision: str | Sequence[str] | None = "biw8_001"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE aip_feature_activation(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,feature_id TEXT NOT NULL,
      revision BIGINT NOT NULL,content_hash TEXT NOT NULL,status TEXT NOT NULL,
      activated_at TIMESTAMPTZ NOT NULL,expires_at TIMESTAMPTZ,
      authority_data JSONB NOT NULL,created_by TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,feature_id,revision),
      CHECK(feature_id ~ '^aip[.][a-z0-9]+([.-][a-z0-9]+)*$'),CHECK(revision>=1),
      CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(status IN('active','superseded','revoked')),
      CHECK(expires_at IS NULL OR expires_at>activated_at),
      CHECK(jsonb_typeof(authority_data)='object'))""")
    op.execute("""CREATE UNIQUE INDEX uq_aip_feature_activation_active
      ON aip_feature_activation(org_id,project_id,feature_id) WHERE status='active'""")
    op.execute("ALTER TABLE aip_feature_activation ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_feature_activation FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope_aip_feature_activation_wcat_001
      ON aip_feature_activation TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("GRANT SELECT ON aip_feature_activation TO aos_runtime")
    op.execute("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON aip_feature_activation FROM aos_runtime")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM aip_feature_activation LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade wcat_001 with AIP feature authority'
      USING ERRCODE='55000';END IF;END $$""")
    op.execute("DROP TABLE aip_feature_activation")
