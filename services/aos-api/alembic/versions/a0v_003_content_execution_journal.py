"""Immutable content execution input/result journal; budget owns invocation state."""
from alembic import op

revision = 'a0v_003'
down_revision = 'a0v_002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE ecommerce_content_execution_command (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, reservation_id UUID NOT NULL,
        budget_request_hash TEXT NOT NULL CHECK(budget_request_hash ~ '^[0-9a-f]{64}$'),
        command_hash TEXT NOT NULL CHECK(command_hash ~ '^[0-9a-f]{64}$'),
        command_payload JSONB NOT NULL CHECK(jsonb_typeof(command_payload)='object'),
        created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,reservation_id),
        FOREIGN KEY(org_id,project_id,reservation_id)
            REFERENCES aip_budget_reservation(org_id,project_id,reservation_id))''')
    op.execute('''CREATE TABLE ecommerce_content_execution_result (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, reservation_id UUID NOT NULL,
        provider_request_ref JSONB NOT NULL CHECK(jsonb_typeof(provider_request_ref)='object'),
        result_hash TEXT NOT NULL CHECK(result_hash ~ '^[0-9a-f]{64}$'),
        result_payload JSONB NOT NULL CHECK(jsonb_typeof(result_payload)='object'),
        recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,reservation_id),
        FOREIGN KEY(org_id,project_id,reservation_id)
            REFERENCES ecommerce_content_execution_command(org_id,project_id,reservation_id))''')
    op.execute('''CREATE FUNCTION guard_a0v_content_execution_journal() RETURNS trigger
        LANGUAGE plpgsql AS $$ DECLARE r RECORD; BEGIN
        IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'content execution journal is immutable'; END IF;
        EXECUTE format('SELECT state,operation_id,request_hash,provider_request_receipt_ref FROM %I.aip_budget_reservation WHERE org_id=$1 AND project_id=$2 AND reservation_id=$3 FOR UPDATE',TG_TABLE_SCHEMA)
            INTO r USING NEW.org_id,NEW.project_id,NEW.reservation_id;
        IF r.state IS NULL OR r.operation_id <> 'ecommerce_growth_content_generate' THEN
            RAISE EXCEPTION 'content reservation required'; END IF;
        IF TG_TABLE_NAME='ecommerce_content_execution_command' THEN
            IF r.state <> 'held' OR r.request_hash <> NEW.budget_request_hash THEN
                RAISE EXCEPTION 'held exact reservation required'; END IF;
        ELSE
            IF r.state NOT IN ('submitted','unknown') OR r.provider_request_receipt_ref IS NULL
                OR r.provider_request_receipt_ref IS DISTINCT FROM NEW.provider_request_ref THEN
                RAISE EXCEPTION 'submitted exact provider request required'; END IF;
        END IF;
        RETURN NEW; END $$''')
    for table in ('ecommerce_content_execution_command','ecommerce_content_execution_result'):
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'''CREATE POLICY tenant_scope_{table} ON {table} TO aos_runtime
            USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))''')
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC')
        op.execute(f'GRANT SELECT,INSERT ON {table} TO aos_runtime')
        op.execute(f'''CREATE TRIGGER immutable_{table} BEFORE INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_a0v_content_execution_journal()''')


def downgrade():
    op.execute('''DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM ecommerce_content_execution_command) THEN
            RAISE EXCEPTION 'content execution evidence prevents downgrade'; END IF;
        END $$''')
    op.execute('DROP TABLE ecommerce_content_execution_result')
    op.execute('DROP TABLE ecommerce_content_execution_command')
    op.execute('DROP FUNCTION guard_a0v_content_execution_journal()')
