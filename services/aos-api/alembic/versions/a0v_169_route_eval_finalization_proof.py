"""Default-empty immutable Route finalization sidecars; no finalizer enabled."""
from alembic import op


revision='a0v_169'
down_revision='a0v_168'
branch_labels=depends_on=None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_route_eval_finalizer') THEN
        CREATE ROLE aos_route_eval_finalizer NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
          NOCREATEROLE NOCREATEDB NOREPLICATION;
      END IF;
      IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_route_eval_finalizer'
        AND (rolcanlogin OR rolinherit OR rolsuper OR rolbypassrls OR rolcreaterole
          OR rolcreatedb OR rolreplication)) THEN
        RAISE EXCEPTION 'unsafe Route Eval finalizer role' USING ERRCODE='42501';
      END IF;
    END $$""")
    op.execute("""CREATE TABLE aip_route_eval_finalization_proof (
      org_id text NOT NULL,project_id text NOT NULL,execution_id text NOT NULL,
      proof_hash text NOT NULL,proof_payload jsonb NOT NULL,
      manifest_hash text NOT NULL,context_binding_hash text NOT NULL,
      admission_hash text NOT NULL,run_id text NOT NULL,report_id text NOT NULL,
      report_revision bigint NOT NULL,report_hash text NOT NULL,
      finalized_at timestamptz NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(org_id,project_id,execution_id),
      UNIQUE(org_id,project_id,report_id,report_revision),
      FOREIGN KEY(org_id,project_id,run_id)
        REFERENCES aip_eval_run(org_id,project_id,run_id),
      FOREIGN KEY(org_id,project_id,report_id,report_revision)
        REFERENCES aip_eval_report_revision(org_id,project_id,report_id,revision),
      CHECK(length(execution_id) BETWEEN 1 AND 200 AND execution_id=btrim(execution_id)),
      CHECK(proof_hash ~ '^[0-9a-f]{64}$' AND manifest_hash ~ '^[0-9a-f]{64}$'
        AND context_binding_hash ~ '^[0-9a-f]{64}$' AND admission_hash ~ '^[0-9a-f]{64}$'
        AND report_hash ~ '^[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(proof_payload)='object' AND proof_payload<>'{}'::jsonb),
      CHECK(report_revision>=1)
    )""")
    op.execute("""CREATE TABLE aip_route_eval_finalized_call_proof (
      org_id text NOT NULL,project_id text NOT NULL,execution_id text NOT NULL,
      case_id text NOT NULL,purpose text NOT NULL,reservation_id uuid NOT NULL,
      call_key text NOT NULL,call_proof_hash text NOT NULL,call_proof_payload jsonb NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(org_id,project_id,execution_id,case_id,purpose),
      UNIQUE(org_id,project_id,reservation_id),
      FOREIGN KEY(org_id,project_id,execution_id)
        REFERENCES aip_route_eval_finalization_proof(org_id,project_id,execution_id),
      FOREIGN KEY(org_id,project_id,reservation_id)
        REFERENCES aip_route_eval_execution_result(org_id,project_id,reservation_id),
      CHECK(length(case_id) BETWEEN 1 AND 200 AND case_id=btrim(case_id)),
      CHECK(purpose IN ('target','judge')),
      CHECK(length(call_key) BETWEEN 1 AND 200 AND call_key=btrim(call_key)),
      CHECK(call_proof_hash ~ '^[0-9a-f]{64}$'),
      CHECK(jsonb_typeof(call_proof_payload)='object' AND call_proof_payload<>'{}'::jsonb)
    )""")
    scope="org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),'')"
    for table in ('aip_route_eval_finalization_proof','aip_route_eval_finalized_call_proof'):
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'''CREATE POLICY route_eval_finalizer_{table} ON {table}
          TO aos_route_eval_finalizer USING({scope}) WITH CHECK({scope})''')
        op.execute(f'''CREATE POLICY route_eval_finalization_reader_{table} ON {table}
          FOR SELECT TO aos_runtime USING({scope})''')
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC,aos_runtime,aos_route_eval_finalizer')
        op.execute(f'GRANT SELECT,INSERT ON {table} TO aos_route_eval_finalizer')
        op.execute(f'GRANT SELECT ON {table} TO aos_runtime')
        op.execute(f'''CREATE TRIGGER route_eval_finalization_frozen_{table}
          BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW
          EXECUTE FUNCTION guard_aip4_append_only()''')
        op.execute(f'''CREATE TRIGGER route_eval_finalization_no_truncate_{table}
          BEFORE TRUNCATE ON {table} FOR EACH STATEMENT
          EXECUTE FUNCTION guard_aip4_append_only()''')
    op.execute("""GRANT SELECT ON aip_route_eval_execution_command,
      aip_route_eval_execution_result,aip_budget_reservation,aip_eval_run,
      aip_eval_report_revision TO aos_route_eval_finalizer""")
    for table in ('aip_route_eval_execution_command','aip_route_eval_execution_result',
                  'aip_budget_reservation','aip_eval_run','aip_eval_report_revision'):
        op.execute(f'''CREATE POLICY route_eval_finalizer_read_{table}_a0v169 ON {table}
          FOR SELECT TO aos_route_eval_finalizer USING({scope})''')


def downgrade():
    raise RuntimeError('Route finalization proof removal requires explicit reconciliation')
