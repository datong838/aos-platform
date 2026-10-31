"""Default-empty immutable Route Eval command/result journal; no worker enabled."""
from alembic import op


revision='a0v_168'
down_revision='a0v_167'
branch_labels=depends_on=None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_route_eval_journal') THEN
        CREATE ROLE aos_route_eval_journal NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
          NOCREATEROLE NOCREATEDB NOREPLICATION;
      END IF;
      IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_route_eval_journal'
        AND (rolcanlogin OR rolinherit OR rolsuper OR rolbypassrls OR rolcreaterole
          OR rolcreatedb OR rolreplication)) THEN
        RAISE EXCEPTION 'unsafe Route Eval journal role' USING ERRCODE='42501';
      END IF;
    END $$""")
    op.execute("""CREATE TABLE aip_route_eval_execution_command (
      org_id text NOT NULL,project_id text NOT NULL,reservation_id uuid NOT NULL,
      execution_id text NOT NULL,case_id text NOT NULL,purpose text NOT NULL,
      call_key text NOT NULL,command_hash text NOT NULL,command_payload jsonb NOT NULL,
      input_hash text NOT NULL,input_bytes bytea NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(org_id,project_id,reservation_id),
      UNIQUE(org_id,project_id,execution_id,call_key),
      UNIQUE(org_id,project_id,execution_id,case_id,purpose),
      FOREIGN KEY(org_id,project_id,reservation_id)
        REFERENCES aip_budget_reservation(org_id,project_id,reservation_id),
      CHECK(length(execution_id) BETWEEN 1 AND 200 AND execution_id=btrim(execution_id)),
      CHECK(length(case_id) BETWEEN 1 AND 200 AND case_id=btrim(case_id)),
      CHECK(purpose IN ('target','judge')),
      CHECK(length(call_key) BETWEEN 1 AND 200 AND call_key=btrim(call_key)),
      CHECK(command_hash ~ '^[0-9a-f]{64}$' AND input_hash ~ '^[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(command_payload)='object' AND command_payload<>'{}'::jsonb),
      CHECK(octet_length(input_bytes) BETWEEN 1 AND 1048576)
    )""")
    op.execute("""CREATE TABLE aip_route_eval_execution_result (
      org_id text NOT NULL,project_id text NOT NULL,reservation_id uuid NOT NULL,
      provider_request_ref jsonb NOT NULL,result_hash text NOT NULL,
      result_payload jsonb NOT NULL,output_hash text NOT NULL,output_bytes bytea NOT NULL,
      recorded_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(org_id,project_id,reservation_id),
      FOREIGN KEY(org_id,project_id,reservation_id)
        REFERENCES aip_route_eval_execution_command(org_id,project_id,reservation_id),
      CHECK(jsonb_typeof(provider_request_ref)='object' AND provider_request_ref<>'{}'::jsonb),
      CHECK(result_hash ~ '^[0-9a-f]{64}$' AND output_hash ~ '^[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(result_payload)='object' AND result_payload<>'{}'::jsonb),
      CHECK(octet_length(output_bytes) BETWEEN 0 AND 1048576)
    )""")
    scope="org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),'')"
    for table in ('aip_route_eval_execution_command','aip_route_eval_execution_result'):
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'''CREATE POLICY route_eval_journal_writer_{table} ON {table}
          TO aos_route_eval_journal USING({scope}) WITH CHECK({scope})''')
        op.execute(f'''CREATE POLICY route_eval_journal_reader_{table} ON {table}
          FOR SELECT TO aos_runtime USING({scope})''')
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC,aos_runtime,aos_route_eval_journal')
        op.execute(f'GRANT SELECT,INSERT ON {table} TO aos_route_eval_journal')
        op.execute(f'GRANT SELECT ON {table} TO aos_runtime')
        op.execute(f'''CREATE TRIGGER route_eval_journal_frozen_{table}
          BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW
          EXECUTE FUNCTION guard_aip4_append_only()''')
        op.execute(f'''CREATE TRIGGER route_eval_journal_no_truncate_{table}
          BEFORE TRUNCATE ON {table} FOR EACH STATEMENT
          EXECUTE FUNCTION guard_aip4_append_only()''')


def downgrade():
    raise RuntimeError('Route Eval journal removal requires explicit reconciliation')
