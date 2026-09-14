"""Immutable relationship preparation bound to an exact original snapshot group."""
from alembic import op
revision='a0v_046'
down_revision='a0v_045'
branch_labels=depends_on=None


def upgrade():
    op.execute('''
    ALTER TABLE pipeline_snapshot_group_input ADD CONSTRAINT snapshot_group_input_exact_manifest
        UNIQUE(org_id,project_id,group_id,manifest_hash);
    CREATE TABLE pipeline_snapshot_group_relationship(
        org_id text NOT NULL,project_id text NOT NULL,group_id uuid NOT NULL,
        input_manifest_hash text NOT NULL,
        policy_ref jsonb NOT NULL CHECK(jsonb_typeof(policy_ref)='object' AND octet_length(policy_ref::text)<=4096),
        policy_hash text NOT NULL CHECK(policy_hash ~ '^sha256:[0-9a-f]{64}$'),
        assessment_hash text NOT NULL CHECK(assessment_hash ~ '^sha256:[0-9a-f]{64}$'),
        assessment jsonb NOT NULL CHECK(jsonb_typeof(assessment)='object' AND octet_length(assessment::text)<=8388608),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,group_id),
        FOREIGN KEY(org_id,project_id,group_id,input_manifest_hash)
            REFERENCES pipeline_snapshot_group_input(org_id,project_id,group_id,manifest_hash)
    );
    CREATE FUNCTION validate_snapshot_relationship_a0v_046() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE input_request text;input_started timestamptz;input_completed timestamptz;
        item jsonb;stats jsonb;v jsonb;n integer;
        keys text[]:=ARRAY['schemaVersion','tenant','groupId','claimRequestHash','inputManifestHash','policyRef','policyHash','readStartedAt','readCompletedAt','counts','candidateLinks'];
    BEGIN
        IF (NEW.assessment ?& keys AND NEW.assessment-keys='{}'::jsonb
            AND NEW.assessment->>'schemaVersion'='aos.snapshot-group-relationship-assessment/v1'
            AND NEW.assessment->'tenant'=jsonb_build_object('orgId',NEW.org_id,'projectId',NEW.project_id)
            AND NEW.assessment->>'groupId'=NEW.group_id::text
            AND NEW.assessment->>'inputManifestHash'=NEW.input_manifest_hash
            AND NEW.assessment->'policyRef'=NEW.policy_ref AND NEW.assessment->>'policyHash'=NEW.policy_hash
            AND jsonb_typeof(NEW.assessment->'readStartedAt')='string'
            AND jsonb_typeof(NEW.assessment->'readCompletedAt')='string'
            AND jsonb_typeof(NEW.assessment->'counts')='object'
            AND jsonb_typeof(NEW.assessment->'candidateLinks')='array') IS NOT TRUE THEN
            RAISE EXCEPTION 'relationship assessment binding shape differs' USING ERRCODE='23514';
        END IF;
        EXECUTE format('SELECT request_hash,read_started_at,read_completed_at FROM %I.pipeline_snapshot_group_input WHERE org_id=$1 AND project_id=$2 AND group_id=$3 AND manifest_hash=$4',TG_TABLE_SCHEMA)
            INTO input_request,input_started,input_completed USING NEW.org_id,NEW.project_id,NEW.group_id,NEW.input_manifest_hash;
        IF input_request IS NULL OR NEW.assessment->>'claimRequestHash' IS DISTINCT FROM input_request
            OR (NEW.assessment->>'readStartedAt')::timestamptz IS DISTINCT FROM input_started
            OR (NEW.assessment->>'readCompletedAt')::timestamptz IS DISTINCT FROM input_completed THEN
            RAISE EXCEPTION 'relationship original input differs' USING ERRCODE='23514';
        END IF;
        SELECT count(*) INTO n FROM jsonb_object_keys(NEW.assessment->'counts');
        IF n NOT BETWEEN 1 AND 32 OR jsonb_array_length(NEW.assessment->'candidateLinks')>24000 THEN
            RAISE EXCEPTION 'relationship preparation bounds exceeded' USING ERRCODE='23514';
        END IF;
        FOR stats IN SELECT value FROM jsonb_each(NEW.assessment->'counts') LOOP
            IF (jsonb_typeof(stats)='object' AND stats ?& ARRAY['rows','matched','missingReference','invalidReference','missingParent','deletedEndpoint','allowedUnset']
                AND stats-ARRAY['rows','matched','missingReference','invalidReference','missingParent','deletedEndpoint','allowedUnset']='{}'::jsonb) IS NOT TRUE THEN
                RAISE EXCEPTION 'relationship count shape differs' USING ERRCODE='23514';
            END IF;
            FOR v IN SELECT value FROM jsonb_each(stats) LOOP
                IF (jsonb_typeof(v)='number' AND v::text ~ '^(0|[1-9][0-9]{0,4})$') IS NOT TRUE THEN
                    RAISE EXCEPTION 'relationship count invalid' USING ERRCODE='23514';
                END IF;
                IF v::text::integer>24000 THEN RAISE EXCEPTION 'relationship count too large' USING ERRCODE='23514'; END IF;
            END LOOP;
            IF (stats->>'rows')::integer>=1000 THEN RAISE EXCEPTION 'relationship row limit exceeded' USING ERRCODE='23514'; END IF;
        END LOOP;
        FOR item IN SELECT value FROM jsonb_array_elements(NEW.assessment->'candidateLinks') LOOP
            IF (jsonb_typeof(item)='object'
                AND item ?& ARRAY['link_type','source_type','source_pk','target_type','target_source_pk','source_updated_at','source_timezone','is_deleted','properties']
                AND item-ARRAY['link_type','source_type','source_pk','target_type','target_source_pk','source_updated_at','source_timezone','is_deleted','properties']='{}'::jsonb
                AND jsonb_typeof(item->'source_updated_at')='string' AND item->>'source_timezone'='+00:00'
                AND item->'is_deleted'='false'::jsonb
                AND item->'properties'=jsonb_build_object('sourceModificationTimeKnown',false,'sourceUpdatedAtBasis','observation')
                AND jsonb_typeof(item->'source_pk')='string' AND item->>'source_pk' ~ '^[1-9][0-9]{0,18}$'
                AND jsonb_typeof(item->'target_source_pk')='string' AND item->>'target_source_pk' ~ '^[1-9][0-9]{0,18}$') IS NOT TRUE THEN
                RAISE EXCEPTION 'relationship candidate shape differs' USING ERRCODE='23514';
            END IF;
            IF (item->>'source_updated_at')::timestamptz IS DISTINCT FROM input_completed THEN
                RAISE EXCEPTION 'relationship observation time differs' USING ERRCODE='23514';
            END IF;
        END LOOP;
        RETURN NEW;
    END $$;
    ALTER TABLE pipeline_snapshot_group_relationship ENABLE ROW LEVEL SECURITY;
    ALTER TABLE pipeline_snapshot_group_relationship FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON pipeline_snapshot_group_relationship
        USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
        WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE TRIGGER immutable_snapshot_relationship BEFORE UPDATE OR DELETE OR TRUNCATE ON pipeline_snapshot_group_relationship
        FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
    CREATE CONSTRAINT TRIGGER snapshot_relationship_complete AFTER INSERT ON pipeline_snapshot_group_relationship
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_snapshot_relationship_a0v_046();
    REVOKE ALL ON pipeline_snapshot_group_relationship FROM PUBLIC,aos_runtime;
    GRANT SELECT,INSERT ON pipeline_snapshot_group_relationship TO aos_runtime;
    ''')


def downgrade():raise RuntimeError('relationship preparation history must be retained')
