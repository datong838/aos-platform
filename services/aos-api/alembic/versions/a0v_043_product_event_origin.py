"""Immutable original batch routing for product event occurrences."""
from alembic import op
revision='a0v_043'
down_revision='a0v_042'
branch_labels=depends_on=None


def upgrade():
    op.execute('''CREATE TABLE ecommerce_product_event_origin(
      org_id text NOT NULL,project_id text NOT NULL,occurrence_id uuid NOT NULL,
      source_event_id text NOT NULL CHECK(source_event_id ~ '^[0-9a-f]{64}$'),
      run_id text NOT NULL CHECK(length(run_id) BETWEEN 1 AND 200),
      actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240),
      content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,occurrence_id),
      FOREIGN KEY(org_id,project_id,occurrence_id)
        REFERENCES automation_occurrence(org_id,project_id,occurrence_id));
      ALTER TABLE ecommerce_product_event_origin ENABLE ROW LEVEL SECURITY;
      ALTER TABLE ecommerce_product_event_origin FORCE ROW LEVEL SECURITY;
      CREATE POLICY tenant_scope ON ecommerce_product_event_origin
        USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
        WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
      REVOKE ALL ON ecommerce_product_event_origin FROM PUBLIC,aos_runtime;
      GRANT SELECT,INSERT ON ecommerce_product_event_origin TO aos_runtime;
      CREATE FUNCTION guard_product_event_origin_a0v_043() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'original event origin immutable' USING ERRCODE='55000'; END $$;
      CREATE TRIGGER product_event_origin_immutable BEFORE UPDATE OR DELETE ON ecommerce_product_event_origin
        FOR EACH ROW EXECUTE FUNCTION guard_product_event_origin_a0v_043();
      CREATE TRIGGER product_event_origin_no_truncate BEFORE TRUNCATE ON ecommerce_product_event_origin
        FOR EACH STATEMENT EXECUTE FUNCTION guard_product_event_origin_a0v_043();''')


def downgrade():
    op.execute('''DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM ecommerce_product_event_origin) THEN
        RAISE EXCEPTION 'retain original event origins'; END IF;
      END $$''')
    op.execute('DROP TABLE ecommerce_product_event_origin')
    op.execute('DROP FUNCTION guard_product_event_origin_a0v_043()')
