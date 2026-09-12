"""Bind each controlled source attempt to its existing run and exact approval."""
from alembic import op

revision = 'a0v_024'
down_revision = 'a0v_023'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE pipeline_controlled_source_claim (
        org_id text NOT NULL, project_id text NOT NULL,
        run_id text NOT NULL CHECK(length(run_id) BETWEEN 1 AND 200),
        installation_id uuid NOT NULL, generation uuid NOT NULL,
        pipeline_id text NOT NULL CHECK(length(pipeline_id) BETWEEN 1 AND 200),
        control_id uuid NOT NULL, control_revision bigint NOT NULL CHECK(control_revision>0),
        control_hash text NOT NULL CHECK(control_hash ~ '^sha256:[0-9a-f]{64}$'),
        call_ordinal smallint NOT NULL CHECK(call_ordinal BETWEEN 1 AND 32),
        actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240 AND actor=btrim(actor)),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,run_id),
        UNIQUE(org_id,project_id,control_id,control_revision,call_ordinal),
        FOREIGN KEY(org_id,project_id,run_id) REFERENCES meta_schedule_run(org_id,project_id,id),
        FOREIGN KEY(org_id,project_id,installation_id,generation,pipeline_id,control_id,control_revision,control_hash)
            REFERENCES pipeline_runtime_control_revision(org_id,project_id,installation_id,generation,pipeline_id,control_id,revision,content_hash)
    );
    ALTER TABLE pipeline_controlled_source_claim ENABLE ROW LEVEL SECURITY;
    ALTER TABLE pipeline_controlled_source_claim FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON pipeline_controlled_source_claim
        USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
        WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON pipeline_controlled_source_claim
        FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation();
    CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON pipeline_controlled_source_claim
        FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
    REVOKE ALL ON pipeline_controlled_source_claim FROM PUBLIC,aos_runtime;
    GRANT SELECT,INSERT ON pipeline_controlled_source_claim TO aos_runtime;
    ''')


def downgrade():
    raise RuntimeError('controlled source attempt history must be retained; destructive downgrade is not supported')
