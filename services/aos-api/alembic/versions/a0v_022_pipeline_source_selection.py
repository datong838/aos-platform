"""Immutable source selection history; no runtime activation or business writes."""
from alembic import op

revision = 'a0v_022'
down_revision = 'a0v_021'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE pipeline_source_selection_revision (
        org_id text NOT NULL, project_id text NOT NULL,
        installation_id uuid NOT NULL, generation uuid NOT NULL,
        pipeline_id text NOT NULL CHECK(length(pipeline_id) BETWEEN 1 AND 200),
        selection_id uuid NOT NULL, revision bigint NOT NULL CHECK(revision>0),
        source_id text NOT NULL, source_configuration_revision uuid NOT NULL,
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
        content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
        previous_revision bigint, previous_hash text,
        request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
        idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160),
        actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,installation_id,generation,pipeline_id,revision),
        UNIQUE(org_id,project_id,selection_id,revision),
        UNIQUE(org_id,project_id,installation_id,generation,idempotency_key),
        UNIQUE(org_id,project_id,installation_id,generation,pipeline_id,selection_id,revision,content_hash),
        FOREIGN KEY(org_id,project_id,installation_id,generation)
            REFERENCES extension_runtime_binding(org_id,project_id,installation_id,generation),
        FOREIGN KEY(org_id,project_id,source_id,source_configuration_revision)
            REFERENCES data_source_configuration_revision(org_id,project_id,source_id,revision_id),
        FOREIGN KEY(org_id,project_id,installation_id,generation,pipeline_id,
                    selection_id,previous_revision,previous_hash)
            REFERENCES pipeline_source_selection_revision(org_id,project_id,installation_id,generation,
                        pipeline_id,selection_id,revision,content_hash),
        CHECK((revision=1 AND previous_revision IS NULL AND previous_hash IS NULL)
            OR (revision>1 AND previous_revision IS NOT NULL AND previous_revision=revision-1
                AND previous_hash IS NOT NULL AND previous_hash ~ '^sha256:[0-9a-f]{64}$')),
        CHECK((payload->>'schemaVersion'='aos.pipeline-source-selection-revision/v1'
            AND payload->>'orgId'=org_id AND payload->>'projectId'=project_id
            AND payload->>'installationId'=installation_id::text AND payload->>'generation'=generation::text
            AND payload->>'pipelineId'=pipeline_id AND payload->>'selectionId'=selection_id::text
            AND payload->>'revision'=revision::text AND payload->>'sourceId'=source_id
            AND payload->>'sourceConfigurationRevision'=source_configuration_revision::text
            AND payload->>'actor'=actor) IS TRUE)
    );
    ALTER TABLE pipeline_source_selection_revision ENABLE ROW LEVEL SECURITY;
    ALTER TABLE pipeline_source_selection_revision FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON pipeline_source_selection_revision
        USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
        WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON pipeline_source_selection_revision
        FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation();
    CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON pipeline_source_selection_revision
        FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
    ''')
    restrict_history_permissions()


def restrict_history_permissions():
    # Older installations may grant ALL through default privileges.
    op.execute('REVOKE ALL ON pipeline_source_selection_revision FROM PUBLIC,aos_runtime; GRANT SELECT,INSERT ON pipeline_source_selection_revision TO aos_runtime;')


def downgrade():
    raise RuntimeError('source selection history must be retained; destructive downgrade is not supported')
