"""Immutable schedule bindings to exact approved runtime controls."""
from alembic import op

revision = 'a0v_025'
down_revision = 'a0v_024'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE pipeline_schedule_control_binding (
        org_id text NOT NULL, project_id text NOT NULL,
        schedule_id text NOT NULL CHECK(length(schedule_id) BETWEEN 1 AND 200),
        binding_id uuid NOT NULL, revision bigint NOT NULL CHECK(revision>0),
        installation_id uuid NOT NULL, generation uuid NOT NULL,
        pipeline_id text NOT NULL CHECK(length(pipeline_id) BETWEEN 1 AND 200),
        control_id uuid NOT NULL, control_revision bigint NOT NULL CHECK(control_revision>0),
        control_hash text NOT NULL CHECK(control_hash ~ '^sha256:[0-9a-f]{64}$'),
        actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240 AND actor=btrim(actor)),
        content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
        previous_revision bigint, previous_hash text,
        request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
        idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,schedule_id,revision),
        UNIQUE(org_id,project_id,binding_id,revision,content_hash),
        UNIQUE(org_id,project_id,schedule_id,binding_id,revision,content_hash),
        UNIQUE(org_id,project_id,schedule_id,idempotency_key),
        FOREIGN KEY(org_id,project_id,schedule_id) REFERENCES meta_schedule(org_id,project_id,id),
        FOREIGN KEY(org_id,project_id,installation_id,generation,pipeline_id,control_id,control_revision,control_hash)
            REFERENCES pipeline_runtime_control_revision(org_id,project_id,installation_id,generation,pipeline_id,control_id,revision,content_hash),
        FOREIGN KEY(org_id,project_id,schedule_id,binding_id,previous_revision,previous_hash)
            REFERENCES pipeline_schedule_control_binding(org_id,project_id,schedule_id,binding_id,revision,content_hash),
        CHECK((revision=1 AND previous_revision IS NULL AND previous_hash IS NULL)
            OR (revision>1 AND previous_revision IS NOT NULL AND previous_revision=revision-1
                AND previous_hash IS NOT NULL AND previous_hash ~ '^sha256:[0-9a-f]{64}$'))
    );
    ALTER TABLE pipeline_schedule_control_binding ENABLE ROW LEVEL SECURITY;
    ALTER TABLE pipeline_schedule_control_binding FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON pipeline_schedule_control_binding
        USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
        WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON pipeline_schedule_control_binding
        FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation();
    CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON pipeline_schedule_control_binding
        FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
    REVOKE ALL ON pipeline_schedule_control_binding FROM PUBLIC,aos_runtime;
    GRANT SELECT,INSERT ON pipeline_schedule_control_binding TO aos_runtime;
    ''')


def downgrade():
    raise RuntimeError('schedule approval history must be retained; destructive downgrade is not supported')
