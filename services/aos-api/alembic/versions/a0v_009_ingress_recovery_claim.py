"""Preserve the failed-run fact atomically with recovery claim."""
from alembic import op
revision='a0v_009'
down_revision='a0v_008'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('''CREATE TABLE ecommerce_ingress_recovery_claim(
        org_id TEXT NOT NULL,project_id TEXT NOT NULL,run_id TEXT NOT NULL,claim_id UUID NOT NULL,
        payload_hash TEXT NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
        payload JSONB NOT NULL CHECK(jsonb_typeof(payload)='object'),
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,run_id,claim_id),
        FOREIGN KEY(org_id,project_id,run_id) REFERENCES ecommerce_ingress_command(org_id,project_id,run_id))''')
    op.execute('''CREATE TRIGGER immutable_ingress_claim BEFORE UPDATE OR DELETE ON ecommerce_ingress_recovery_claim
        FOR EACH ROW EXECUTE FUNCTION guard_a0v_ingress_command()''')
    op.execute('''CREATE TRIGGER no_truncate_ingress_claim BEFORE TRUNCATE ON ecommerce_ingress_recovery_claim
        FOR EACH STATEMENT EXECUTE FUNCTION guard_a0v_ingress_command()''')
    op.execute('ALTER TABLE ecommerce_ingress_recovery_claim ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE ecommerce_ingress_recovery_claim FORCE ROW LEVEL SECURITY')
    op.execute('''CREATE POLICY ingress_claim_scope ON ecommerce_ingress_recovery_claim TO aos_runtime
        USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))''')
    op.execute('REVOKE ALL ON ecommerce_ingress_recovery_claim FROM PUBLIC')
    op.execute('GRANT SELECT,INSERT ON ecommerce_ingress_recovery_claim TO aos_runtime')


def downgrade():
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM ecommerce_ingress_recovery_claim) THEN RAISE EXCEPTION 'recovery evidence prevents downgrade'; END IF; END $$")
    op.execute('DROP TABLE ecommerce_ingress_recovery_claim')
