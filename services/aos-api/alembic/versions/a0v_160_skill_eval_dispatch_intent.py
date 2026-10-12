"""Durable Skill dispatch journal; no executor or production identity enabled."""
from alembic import op

revision = 'a0v_160'
down_revision = 'a0v_159'
branch_labels = depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_aip_eval_writer') THEN
        CREATE ROLE aos_aip_eval_writer NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS
          NOCREATEROLE NOCREATEDB NOREPLICATION;
      END IF;
      IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_aip_eval_writer'
        AND (rolcanlogin OR rolinherit OR rolsuper OR rolbypassrls OR rolcreaterole
          OR rolcreatedb OR rolreplication)) THEN
        RAISE EXCEPTION 'unsafe Eval writer role' USING ERRCODE='42501';
      END IF;
    END $$""")
    op.execute("""CREATE TABLE aip_skill_eval_intent (
      org_id text NOT NULL, project_id text NOT NULL, intent_id text NOT NULL,
      run_id text NOT NULL, idempotency_key text NOT NULL, request_hash text NOT NULL,
      version bigint NOT NULL DEFAULT 1 CHECK(version>=1),
      created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(org_id,project_id,intent_id),
      UNIQUE(org_id,project_id,idempotency_key), UNIQUE(org_id,project_id,run_id),
      CHECK(length(intent_id) BETWEEN 1 AND 160),
      CHECK(length(idempotency_key) BETWEEN 1 AND 160 AND idempotency_key=btrim(idempotency_key)),
      CHECK(request_hash ~ '^[0-9a-f]{64}$'),
      FOREIGN KEY(org_id,project_id,run_id) REFERENCES aip_eval_run(org_id,project_id,run_id)
    )""")
    op.execute("""CREATE TABLE aip_skill_eval_dispatch (
      org_id text NOT NULL, project_id text NOT NULL, dispatch_id text NOT NULL,
      intent_id text NOT NULL, case_id text NOT NULL, purpose text NOT NULL,
      input_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(org_id,project_id,dispatch_id),
      UNIQUE(org_id,project_id,intent_id,case_id,purpose),
      CHECK(length(case_id) BETWEEN 1 AND 160 AND case_id=btrim(case_id)),
      CHECK(purpose IN ('target','judge')), CHECK(input_hash ~ '^[0-9a-f]{64}$'),
      FOREIGN KEY(org_id,project_id,intent_id) REFERENCES aip_skill_eval_intent(org_id,project_id,intent_id)
    )""")
    op.execute("""CREATE TABLE aip_skill_eval_dispatch_observation (
      org_id text NOT NULL, project_id text NOT NULL, dispatch_id text NOT NULL,
      state text NOT NULL, result_hash text, observed_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(org_id,project_id,dispatch_id,state),
      CHECK(state IN ('unknown','result_observed')),
      CHECK((state='unknown' AND result_hash IS NULL) OR
        (state='result_observed' AND result_hash IS NOT NULL AND result_hash ~ '^[0-9a-f]{64}$')),
      FOREIGN KEY(org_id,project_id,dispatch_id) REFERENCES aip_skill_eval_dispatch(org_id,project_id,dispatch_id)
    )""")
    scope = "org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),'')"
    for table in ('aip_skill_eval_intent', 'aip_skill_eval_dispatch', 'aip_skill_eval_dispatch_observation'):
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'CREATE POLICY skill_dispatch_writer_{table} ON {table} TO aos_aip_eval_writer USING ({scope}) WITH CHECK ({scope})')
        op.execute(f'CREATE POLICY skill_dispatch_reader_{table} ON {table} FOR SELECT TO aos_runtime USING ({scope})')
        op.execute(f'GRANT SELECT,INSERT ON {table} TO aos_aip_eval_writer')
        op.execute(f'GRANT SELECT ON {table} TO aos_runtime')
    op.execute('GRANT UPDATE(version) ON aip_skill_eval_intent TO aos_aip_eval_writer')
    op.execute('GRANT SELECT ON aip_eval_run TO aos_aip_eval_writer')
    op.execute(f'CREATE POLICY skill_dispatch_writer_run_read ON aip_eval_run FOR SELECT TO aos_aip_eval_writer USING ({scope})')
    op.execute("""CREATE FUNCTION guard_skill_eval_dispatch_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_TABLE_NAME='aip_skill_eval_intent' AND TG_OP='UPDATE' THEN
          IF (to_jsonb(NEW)-'version') IS DISTINCT FROM (to_jsonb(OLD)-'version')
            OR NEW.version<>OLD.version+1 THEN
            RAISE EXCEPTION 'Skill intent identity or version drift' USING ERRCODE='55000';
          END IF;
          RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Skill dispatch evidence is immutable' USING ERRCODE='55000';
      END $$""")
    for table in ('aip_skill_eval_intent', 'aip_skill_eval_dispatch', 'aip_skill_eval_dispatch_observation'):
        op.execute(f'CREATE TRIGGER skill_dispatch_frozen BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION guard_skill_eval_dispatch_frozen()')
        op.execute(f'CREATE TRIGGER skill_dispatch_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION guard_skill_eval_dispatch_frozen()')


def downgrade():
    raise RuntimeError('Dispatch evidence requires explicit reconciliation; no destructive rollback')
