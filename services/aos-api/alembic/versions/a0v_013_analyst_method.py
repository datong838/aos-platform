"""Scoped immutable descriptive analysis method revisions."""
from alembic import op

revision = "a0v_013"
down_revision = "a0v_012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE ecommerce_analyst_method_head (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, method_id TEXT NOT NULL,
        current_revision BIGINT NOT NULL CHECK(current_revision>=1),
        version BIGINT NOT NULL DEFAULT 1 CHECK(version=current_revision),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY(org_id,project_id,method_id))""")
    op.execute("""CREATE TABLE ecommerce_analyst_method_revision (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, method_id TEXT NOT NULL,
        revision BIGINT NOT NULL CHECK(revision>=1), parent_revision BIGINT,
        content_hash CHAR(64) NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
        receipt_id TEXT NOT NULL, payload JSONB NOT NULL CHECK(jsonb_typeof(payload)='object'),
        created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY(org_id,project_id,method_id,revision), UNIQUE(org_id,project_id,receipt_id),
        FOREIGN KEY(org_id,project_id,method_id) REFERENCES ecommerce_analyst_method_head(org_id,project_id,method_id),
        FOREIGN KEY(org_id,project_id,receipt_id) REFERENCES ecommerce_analyst_authority_receipt(org_id,project_id,receipt_id) DEFERRABLE INITIALLY DEFERRED,
        CHECK((revision=1 AND parent_revision IS NULL) OR (revision>1 AND parent_revision=revision-1)))""")
    for suffix in ("head", "revision"):
        table = "ecommerce_analyst_method_" + suffix
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY method_scope ON {table} TO aos_runtime
            USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
        op.execute(f"REVOKE ALL ON {table} FROM aos_runtime")
        op.execute(f"GRANT SELECT,INSERT ON {table} TO aos_runtime")
    op.execute("GRANT UPDATE ON ecommerce_analyst_method_head TO aos_runtime")
    op.execute("""CREATE TRIGGER method_revision_immutable BEFORE UPDATE OR DELETE ON ecommerce_analyst_method_revision
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute("""CREATE TRIGGER method_revision_no_truncate BEFORE TRUNCATE ON ecommerce_analyst_method_revision
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()""")


def downgrade():
    raise RuntimeError("Forward-only method authority; preserve historical analysis provenance")
