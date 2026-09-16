"""Immutable atomic schedule-group claims, separate from source-call claims."""
from alembic import op

revision = 'a0v_062'
down_revision = 'a0v_061'
branch_labels = depends_on = None


def upgrade():
    op.execute('''
    CREATE TABLE pipeline_snapshot_schedule_claim(
        org_id text NOT NULL, project_id text NOT NULL, group_id uuid NOT NULL,
        actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240 AND actor=btrim(actor)),
        scheduled_for timestamptz NOT NULL, trigger text NOT NULL CHECK(trigger IN ('cron','manual')),
        request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
        request jsonb NOT NULL CHECK(jsonb_typeof(request)='object' AND octet_length(request::text)<=65536),
        content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
        record jsonb NOT NULL CHECK(jsonb_typeof(record)='object' AND octet_length(record::text)<=65536),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,group_id)
    );
    CREATE TABLE pipeline_snapshot_schedule_member(
        org_id text NOT NULL, project_id text NOT NULL, group_id uuid NOT NULL,
        ordinal smallint NOT NULL CHECK(ordinal BETWEEN 1 AND 12),
        schedule_id text NOT NULL, binding_id uuid NOT NULL,
        binding_revision bigint NOT NULL, binding_hash text NOT NULL, run_id text NOT NULL,
        PRIMARY KEY(org_id,project_id,group_id,ordinal),
        UNIQUE(org_id,project_id,group_id,schedule_id), UNIQUE(org_id,project_id,run_id),
        FOREIGN KEY(org_id,project_id,group_id) REFERENCES pipeline_snapshot_schedule_claim(org_id,project_id,group_id),
        FOREIGN KEY(org_id,project_id,schedule_id,binding_id,binding_revision,binding_hash)
            REFERENCES pipeline_schedule_control_binding(org_id,project_id,schedule_id,binding_id,revision,content_hash),
        FOREIGN KEY(org_id,project_id,run_id) REFERENCES meta_schedule_run(org_id,project_id,id)
    );
    CREATE FUNCTION validate_snapshot_schedule_claim_a0v_062() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE h public.pipeline_snapshot_schedule_claim; m record; expected jsonb; n integer;
    BEGIN
        SELECT * INTO STRICT h FROM public.pipeline_snapshot_schedule_claim
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND group_id=NEW.group_id;
        SELECT count(*) INTO n FROM public.pipeline_snapshot_schedule_member
            WHERE org_id=h.org_id AND project_id=h.project_id AND group_id=h.group_id;
        IF (n=12 AND h.request_hash=public.canonical_bundle_control_sha256(h.request)
            AND h.content_hash=public.canonical_bundle_control_sha256(h.record)
            AND h.record->>'schemaVersion'='aos.snapshot-schedule-claim/v1'
            AND h.record-ARRAY['schemaVersion','request','members']='{}'::jsonb
            AND h.record->'request'=h.request
            AND jsonb_typeof(h.record->'members')='array' AND jsonb_array_length(h.record->'members')=12
            AND h.request->>'schemaVersion'='aos.snapshot-schedule-request/v1'
            AND h.request-ARRAY['schemaVersion','orgId','projectId','groupId','actor','scheduledFor','trigger','members']='{}'::jsonb
            AND h.request->>'orgId'=h.org_id AND h.request->>'projectId'=h.project_id
            AND h.request->>'groupId'=h.group_id::text AND h.request->>'actor'=h.actor
            AND h.request->>'trigger'=h.trigger AND (h.request->>'scheduledFor')::timestamptz=h.scheduled_for
            AND jsonb_typeof(h.request->'members')='array' AND jsonb_array_length(h.request->'members')=12) IS NOT TRUE THEN
            RAISE EXCEPTION 'snapshot schedule claim incomplete or hash differs' USING ERRCODE='23514';
        END IF;
        FOR m IN SELECT x.*,b.pipeline_id,b.control_id,b.control_revision,b.control_hash,b.actor,
                r.schedule_id AS run_schedule,r.scheduled_for AS run_slot,r.trigger AS run_trigger
            FROM public.pipeline_snapshot_schedule_member x
            JOIN public.pipeline_schedule_control_binding b ON (b.org_id,b.project_id,b.schedule_id,b.binding_id,b.revision,b.content_hash)=
                (x.org_id,x.project_id,x.schedule_id,x.binding_id,x.binding_revision,x.binding_hash)
            JOIN public.meta_schedule_run r ON (r.org_id,r.project_id,r.id)=(x.org_id,x.project_id,x.run_id)
            WHERE x.org_id=h.org_id AND x.project_id=h.project_id AND x.group_id=h.group_id ORDER BY x.ordinal
        LOOP
            expected=jsonb_build_object('scheduleId',m.schedule_id,'pipelineId',m.pipeline_id,
                'bindingRef',jsonb_build_object('resourceType','PipelineScheduleControlBinding',
                    'resourceId','schedule-control-'||m.binding_id::text,'revision',m.binding_revision,'contentHash',m.binding_hash),
                'controlRef',jsonb_build_object('resourceType','PipelineRuntimeControlRevision',
                    'resourceId','pipeline-control-'||m.control_id::text,'revision',m.control_revision,'contentHash',m.control_hash));
            IF (m.actor=h.actor AND m.run_schedule=m.schedule_id AND m.run_slot=h.scheduled_for AND m.run_trigger=h.trigger
                AND h.request->'members'->(m.ordinal-1)=expected
                AND h.record->'members'->(m.ordinal-1)=expected||jsonb_build_object('runId',m.run_id)) IS NOT TRUE THEN
                RAISE EXCEPTION 'snapshot schedule member differs from original binding or run' USING ERRCODE='23514';
            END IF;
        END LOOP;
        RETURN NEW;
    END $$;
    ''')
    for table in ('pipeline_snapshot_schedule_claim', 'pipeline_snapshot_schedule_member'):
        op.execute(f'''
        ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_scope ON {table}
            USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
            WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
        CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION extension_reject_history_mutation();
        CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION extension_reject_history_mutation();
        REVOKE ALL ON {table} FROM PUBLIC,aos_runtime;
        GRANT SELECT,INSERT ON {table} TO aos_runtime;
        ''')
    op.execute('''
    CREATE CONSTRAINT TRIGGER snapshot_schedule_claim_complete AFTER INSERT ON pipeline_snapshot_schedule_claim
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_snapshot_schedule_claim_a0v_062();
    CREATE CONSTRAINT TRIGGER snapshot_schedule_member_complete AFTER INSERT ON pipeline_snapshot_schedule_member
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_snapshot_schedule_claim_a0v_062();
    ''')


def downgrade():
    raise RuntimeError('snapshot schedule claims must be retained')
