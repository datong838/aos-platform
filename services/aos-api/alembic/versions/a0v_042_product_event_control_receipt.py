"""Immutable event-control receipts; no new executable state or enable function."""
from alembic import op
revision='a0v_042'
down_revision='a0v_041'
branch_labels=depends_on=None


def upgrade():
    op.execute('''CREATE TABLE ecommerce_product_event_control_receipt(
      org_id text NOT NULL,project_id text NOT NULL,
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 200),
      receipt_id uuid NOT NULL,request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      policy_id text NOT NULL,policy_revision bigint NOT NULL CHECK(policy_revision>0),
      binding_revision bigint NOT NULL CHECK(binding_revision>0),actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240),
      command jsonb NOT NULL CHECK(jsonb_typeof(command)='object'),
      authority jsonb NOT NULL CHECK(jsonb_typeof(authority)='object'),
      content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,idempotency_key),UNIQUE(org_id,project_id,receipt_id),
      FOREIGN KEY(org_id,project_id,policy_id,policy_revision)
        REFERENCES automation_schedule_binding(org_id,project_id,policy_id,policy_revision));
      ALTER TABLE ecommerce_product_event_control_receipt ENABLE ROW LEVEL SECURITY;
      ALTER TABLE ecommerce_product_event_control_receipt FORCE ROW LEVEL SECURITY;
      CREATE POLICY tenant_scope ON ecommerce_product_event_control_receipt
        USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
        WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
      REVOKE ALL ON ecommerce_product_event_control_receipt FROM PUBLIC,aos_runtime;
      GRANT SELECT,INSERT ON ecommerce_product_event_control_receipt TO aos_runtime;
      CREATE FUNCTION guard_product_event_control_receipt_a0v_042() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'event control receipt immutable' USING ERRCODE='55000'; END $$;
      CREATE TRIGGER event_control_receipt_immutable BEFORE UPDATE OR DELETE ON ecommerce_product_event_control_receipt
        FOR EACH ROW EXECUTE FUNCTION guard_product_event_control_receipt_a0v_042();''')


def downgrade():
    op.execute('''DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM ecommerce_product_event_control_receipt) THEN
        RAISE EXCEPTION 'retain event control receipts'; END IF;
      END $$''')
    op.execute('DROP TABLE ecommerce_product_event_control_receipt')
    op.execute('DROP FUNCTION guard_product_event_control_receipt_a0v_042()')
