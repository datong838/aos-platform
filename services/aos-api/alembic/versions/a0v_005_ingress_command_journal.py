"""Persist immutable original canonical ingress commands for exact recovery."""
from alembic import op
revision = 'a0v_005'
down_revision = 'a0v_004'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE ecommerce_ingress_command(
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, run_id TEXT NOT NULL,
        pipeline_id TEXT NOT NULL, source_id TEXT NOT NULL, source_revision UUID NOT NULL,
        envelope_hash TEXT NOT NULL CHECK(envelope_hash ~ '^[0-9a-f]{64}$'),
        envelope JSONB NOT NULL CHECK(jsonb_typeof(envelope)='object'),
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,run_id),
        FOREIGN KEY(org_id,project_id,source_id,source_revision)
            REFERENCES data_source_configuration_revision(org_id,project_id,source_id,revision_id))''')
    op.execute('''CREATE FUNCTION guard_a0v_ingress_command() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        RAISE EXCEPTION 'ingress command is immutable'; END $$''')
    op.execute('''CREATE TRIGGER immutable_ingress_command BEFORE UPDATE OR DELETE ON ecommerce_ingress_command
        FOR EACH ROW EXECUTE FUNCTION guard_a0v_ingress_command()''')
    op.execute('''CREATE TRIGGER no_truncate_ingress_command BEFORE TRUNCATE ON ecommerce_ingress_command
        FOR EACH STATEMENT EXECUTE FUNCTION guard_a0v_ingress_command()''')
    op.execute('ALTER TABLE ecommerce_ingress_command ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE ecommerce_ingress_command FORCE ROW LEVEL SECURITY')
    op.execute('''CREATE POLICY ingress_scope ON ecommerce_ingress_command TO aos_runtime
        USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))''')
    op.execute('REVOKE ALL ON ecommerce_ingress_command FROM PUBLIC')
    op.execute('GRANT SELECT,INSERT ON ecommerce_ingress_command TO aos_runtime')


def downgrade():
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM ecommerce_ingress_command) THEN RAISE EXCEPTION 'ingress evidence prevents downgrade'; END IF; END $$")
    op.execute('DROP TABLE ecommerce_ingress_command')
    op.execute('DROP FUNCTION guard_a0v_ingress_command()')
