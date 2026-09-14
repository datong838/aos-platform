"""Persist exact link-only command before any independently committed application."""
from alembic import op
revision = 'a0v_047'
down_revision = 'a0v_046'
branch_labels = depends_on = None


def upgrade():
    op.execute('''
    ALTER TABLE pipeline_snapshot_group_relationship ADD CONSTRAINT snapshot_relationship_exact_assessment
        UNIQUE(org_id,project_id,group_id,assessment_hash);
    CREATE TABLE pipeline_snapshot_group_link_command(
        org_id text NOT NULL,project_id text NOT NULL,group_id uuid NOT NULL,
        assessment_hash text NOT NULL,
        link_count integer NOT NULL CHECK(link_count BETWEEN 0 AND 24000),
        command_hash text NOT NULL CHECK(command_hash ~ '^sha256:[0-9a-f]{64}$'),
        command jsonb,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,group_id),
        FOREIGN KEY(org_id,project_id,group_id,assessment_hash)
            REFERENCES pipeline_snapshot_group_relationship(org_id,project_id,group_id,assessment_hash),
        CHECK ((link_count=0 AND command IS NULL) OR
            (link_count>0 AND command IS NOT NULL AND jsonb_typeof(command)='object'
             AND octet_length(command::text)<=16777216))
    );
    CREATE FUNCTION validate_snapshot_link_command_a0v_047() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE body jsonb;keys text[]:=ARRAY['scope','idempotency_key','expected_checkpoint_version','next_checkpoint','objects','links'];
    BEGIN
        IF NEW.command IS NULL THEN RETURN NEW; END IF;
        body:=NEW.command;
        IF (body ?& keys AND body-keys='{}'::jsonb
            AND body->'objects'='[]'::jsonb
            AND jsonb_typeof(body->'links')='array'
            AND body->'scope'->>'org_id'=NEW.org_id
            AND body->'scope'->>'workspace_id'=NEW.project_id
            AND jsonb_typeof(body->'scope'->'stream')='string'
            AND body->'scope'->>'stream' ~ '^snapshot-group-links:[0-9a-f]{64}$'
            AND body->>'idempotency_key'='snapshot-group-links:' || NEW.group_id::text || ':' || substring(NEW.assessment_hash from 8)
            AND jsonb_typeof(body->'expected_checkpoint_version')='number'
            AND body->>'expected_checkpoint_version' ~ '^(0|[1-9][0-9]*)$'
            AND jsonb_typeof(body->'next_checkpoint')='object') IS NOT TRUE THEN
            RAISE EXCEPTION 'link command binding shape differs' USING ERRCODE='23514';
        END IF;
        IF jsonb_array_length(body->'links')<>NEW.link_count THEN
            RAISE EXCEPTION 'link command count differs' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
    END $$;
    ALTER TABLE pipeline_snapshot_group_link_command ENABLE ROW LEVEL SECURITY;
    ALTER TABLE pipeline_snapshot_group_link_command FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON pipeline_snapshot_group_link_command
        USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
        WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE TRIGGER immutable_snapshot_link_command BEFORE UPDATE OR DELETE OR TRUNCATE ON pipeline_snapshot_group_link_command
        FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
    CREATE CONSTRAINT TRIGGER snapshot_link_command_complete AFTER INSERT ON pipeline_snapshot_group_link_command
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_snapshot_link_command_a0v_047();
    REVOKE ALL ON pipeline_snapshot_group_link_command FROM PUBLIC,aos_runtime;
    GRANT SELECT,INSERT ON pipeline_snapshot_group_link_command TO aos_runtime;
    ''')


def downgrade():
    raise RuntimeError('original link command history must be retained')
