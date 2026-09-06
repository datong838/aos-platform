"""Immutable subordinate configuration revisions; maintenance-only migration."""
from alembic import op

revision = 'ar1_002'
down_revision = 'ar1_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE extension_runtime_configuration (
        org_id text NOT NULL, project_id text NOT NULL, installation_id uuid NOT NULL,
        generation uuid NOT NULL, configuration_id uuid NOT NULL,
        revision bigint NOT NULL CHECK(revision>0),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
        content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
        previous_hash text CHECK(previous_hash ~ '^sha256:[0-9a-f]{64}$'),
        request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
        idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160),
        actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,installation_id,generation,configuration_id,revision),
        UNIQUE(org_id,project_id,installation_id,generation,idempotency_key),
        FOREIGN KEY(org_id,project_id,installation_id,generation)
            REFERENCES extension_runtime_binding(org_id,project_id,installation_id,generation),
        CHECK((revision=1 AND previous_hash IS NULL) OR (revision>1 AND previous_hash IS NOT NULL))
    );
    ALTER TABLE extension_runtime_configuration ENABLE ROW LEVEL SECURITY;
    ALTER TABLE extension_runtime_configuration FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON extension_runtime_configuration
        USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
        WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON extension_runtime_configuration
        FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation();
    CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON extension_runtime_configuration
        FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
    GRANT SELECT,INSERT ON extension_runtime_configuration TO aos_runtime;''')


def downgrade():
    raise RuntimeError('configuration history must be retained; destructive downgrade is not supported')
