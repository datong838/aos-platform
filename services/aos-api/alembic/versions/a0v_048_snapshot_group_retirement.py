"""Immutable conditional retirement preparation bound to original group link command."""
from alembic import op
revision='a0v_048'
down_revision='a0v_047'
branch_labels=depends_on=None


def upgrade():
    op.execute('''
    ALTER TABLE pipeline_snapshot_group_link_command ADD CONSTRAINT snapshot_group_exact_link_command
        UNIQUE(org_id,project_id,group_id,command_hash);
    CREATE TABLE pipeline_snapshot_group_retirement(
        org_id text NOT NULL,project_id text NOT NULL,group_id uuid NOT NULL,
        parent_command_hash text NOT NULL,
        audit_hash text NOT NULL CHECK(audit_hash ~ '^sha256:[0-9a-f]{64}$'),
        audit jsonb NOT NULL CHECK(jsonb_typeof(audit)='object' AND octet_length(audit::text)<=8388608),
        prepared_at timestamptz NOT NULL,
        preparation_hash text NOT NULL CHECK(preparation_hash ~ '^sha256:[0-9a-f]{64}$'),
        command jsonb CHECK(command IS NULL OR (jsonb_typeof(command)='object' AND octet_length(command::text)<=16777216)),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,group_id),
        FOREIGN KEY(org_id,project_id,group_id,parent_command_hash)
            REFERENCES pipeline_snapshot_group_link_command(org_id,project_id,group_id,command_hash)
    );
    CREATE FUNCTION validate_snapshot_retirement_a0v_048() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE parent_assessment text;n integer;link jsonb;
        keys text[]:=ARRAY['assessmentHash','commandHash','counts','cleanupCandidates','unresolvedExtras'];
    BEGIN
        IF (NEW.audit ?& keys AND NEW.audit-keys='{}'::jsonb
            AND NEW.audit->>'commandHash'=NEW.parent_command_hash
            AND jsonb_typeof(NEW.audit->'counts')='object'
            AND jsonb_typeof(NEW.audit->'cleanupCandidates')='array'
            AND jsonb_typeof(NEW.audit->'unresolvedExtras')='array') IS NOT TRUE THEN
            RAISE EXCEPTION 'retirement audit shape differs' USING ERRCODE='23514';
        END IF;
        EXECUTE format('SELECT assessment_hash FROM %I.pipeline_snapshot_group_link_command WHERE org_id=$1 AND project_id=$2 AND group_id=$3 AND command_hash=$4',TG_TABLE_SCHEMA)
            INTO parent_assessment USING NEW.org_id,NEW.project_id,NEW.group_id,NEW.parent_command_hash;
        IF parent_assessment IS NULL OR NEW.audit->>'assessmentHash' IS DISTINCT FROM parent_assessment THEN
            RAISE EXCEPTION 'retirement parent assessment differs' USING ERRCODE='23514';
        END IF;
        n:=jsonb_array_length(NEW.audit->'cleanupCandidates');
        IF n>24000 OR jsonb_array_length(NEW.audit->'unresolvedExtras')>24000 THEN
            RAISE EXCEPTION 'retirement bounds exceeded' USING ERRCODE='23514';
        END IF;
        IF n=0 THEN
            IF NEW.command IS NOT NULL THEN RAISE EXCEPTION 'empty retirement command forbidden' USING ERRCODE='23514'; END IF;
            RETURN NEW;
        END IF;
        IF (NEW.command IS NOT NULL AND NEW.command->'objects'='[]'::jsonb
            AND jsonb_typeof(NEW.command->'links')='array'
            AND NEW.command->'scope'->>'org_id'=NEW.org_id
            AND NEW.command->'scope'->>'workspace_id'=NEW.project_id
            AND NEW.command->'scope'->>'stream' ~ '^snapshot-group-retirement:[0-9a-f]{64}$'
            AND NEW.command->>'idempotency_key'='snapshot-group-retirement:' || NEW.group_id::text || ':' || substring(NEW.audit_hash from 8)) IS NOT TRUE THEN
            RAISE EXCEPTION 'retirement command binding differs' USING ERRCODE='23514';
        END IF;
        IF jsonb_array_length(NEW.command->'links')<>n THEN
            RAISE EXCEPTION 'retirement command count differs' USING ERRCODE='23514';
        END IF;
        FOR link IN SELECT value FROM jsonb_array_elements(NEW.command->'links') LOOP
            IF (link->'is_deleted'='true'::jsonb
                AND link->'properties'->>'retirementExpectedPayloadHash' ~ '^[0-9a-f]{64}$'
                AND link->'properties'->>'retirementAuditHash'=NEW.audit_hash
                AND link->'properties'->>'retirementAssessmentHash'=parent_assessment
                AND (link->>'source_updated_at')::timestamptz=NEW.prepared_at) IS NOT TRUE THEN
                RAISE EXCEPTION 'retirement tombstone binding differs' USING ERRCODE='23514';
            END IF;
        END LOOP;
        RETURN NEW;
    END $$;
    ALTER TABLE pipeline_snapshot_group_retirement ENABLE ROW LEVEL SECURITY;
    ALTER TABLE pipeline_snapshot_group_retirement FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON pipeline_snapshot_group_retirement
        USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
        WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE TRIGGER immutable_snapshot_retirement BEFORE UPDATE OR DELETE OR TRUNCATE ON pipeline_snapshot_group_retirement
        FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
    CREATE CONSTRAINT TRIGGER snapshot_retirement_complete AFTER INSERT ON pipeline_snapshot_group_retirement
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_snapshot_retirement_a0v_048();
    REVOKE ALL ON pipeline_snapshot_group_retirement FROM PUBLIC,aos_runtime;
    GRANT SELECT,INSERT ON pipeline_snapshot_group_retirement TO aos_runtime;
    ''')


def downgrade():raise RuntimeError('conditional retirement history must be retained')
