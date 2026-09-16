"""Bind new schedule claims to exact enabled configuration; retain v1 history."""
from alembic import op
revision='a0v_064'
down_revision='a0v_063'
branch_labels=depends_on=None


def upgrade():
    op.execute('''
    CREATE OR REPLACE FUNCTION validate_snapshot_schedule_claim_a0v_062() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE h public.pipeline_snapshot_schedule_claim; m record; expected jsonb; n integer; d public.pipeline_snapshot_schedule_definition_revision;
    BEGIN
        SELECT * INTO STRICT h FROM public.pipeline_snapshot_schedule_claim
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND group_id=NEW.group_id;
        SELECT count(*) INTO n FROM public.pipeline_snapshot_schedule_member
            WHERE org_id=h.org_id AND project_id=h.project_id AND group_id=h.group_id;
        IF (n=12 AND h.request_hash=public.canonical_bundle_control_sha256(h.request)
            AND h.content_hash=public.canonical_bundle_control_sha256(h.record)
            AND h.record->>'schemaVersion' IN ('aos.snapshot-schedule-claim/v1','aos.snapshot-schedule-claim/v2')
            AND h.record-ARRAY['schemaVersion','request','members']='{}'::jsonb
            AND h.record->'request'=h.request
            AND jsonb_typeof(h.record->'members')='array' AND jsonb_array_length(h.record->'members')=12
            AND ((h.record->>'schemaVersion'='aos.snapshot-schedule-claim/v1'
                  AND h.request->>'schemaVersion'='aos.snapshot-schedule-request/v1'
                  AND h.request-ARRAY['schemaVersion','orgId','projectId','groupId','actor','scheduledFor','trigger','members']='{}'::jsonb)
              OR (h.record->>'schemaVersion'='aos.snapshot-schedule-claim/v2'
                  AND h.request->>'schemaVersion'='aos.snapshot-schedule-request/v2'
                  AND h.request-ARRAY['schemaVersion','orgId','projectId','groupId','actor','scheduledFor','trigger','members','definitionRef']='{}'::jsonb))
            AND h.request->>'orgId'=h.org_id AND h.request->>'projectId'=h.project_id
            AND h.request->>'groupId'=h.group_id::text AND h.request->>'actor'=h.actor
            AND h.request->>'trigger'=h.trigger AND (h.request->>'scheduledFor')::timestamptz=h.scheduled_for
            AND jsonb_typeof(h.request->'members')='array' AND jsonb_array_length(h.request->'members')=12) IS NOT TRUE THEN
            RAISE EXCEPTION 'snapshot schedule claim incomplete or hash differs' USING ERRCODE='23514';
        END IF;
        IF h.record->>'schemaVersion'='aos.snapshot-schedule-claim/v1' AND EXISTS(
            SELECT 1 FROM public.pipeline_snapshot_schedule_member member_row
            JOIN public.pipeline_snapshot_schedule_current_member c
            ON (member_row.org_id,member_row.project_id,member_row.schedule_id)=(c.org_id,c.project_id,c.schedule_id)
            WHERE member_row.org_id=h.org_id AND member_row.project_id=h.project_id AND member_row.group_id=h.group_id) THEN
            RAISE EXCEPTION 'assigned snapshot schedule requires definition authority' USING ERRCODE='23514';
        END IF;
        IF h.record->>'schemaVersion'='aos.snapshot-schedule-claim/v2' THEN
            SELECT r.* INTO d FROM public.pipeline_snapshot_schedule_definition_revision r
                JOIN public.pipeline_snapshot_schedule_definition_head x
                ON (r.org_id,r.project_id,r.definition_id,r.revision,r.content_hash)=
                   (x.org_id,x.project_id,x.definition_id,x.revision,x.content_hash)
                WHERE r.org_id=h.org_id AND r.project_id=h.project_id
                  AND 'snapshot-schedule-'||r.definition_id::text=h.request->'definitionRef'->>'resourceId';
            IF (d.state='enabled' AND h.request->'definitionRef'=jsonb_build_object(
                    'resourceType','SnapshotScheduleDefinitionRevision',
                    'resourceId','snapshot-schedule-'||d.definition_id::text,
                    'revision',d.revision,'contentHash',d.content_hash)
                    AND d.body->>'executor'=h.actor AND d.body->'members'=h.request->'members') IS NOT TRUE THEN
                RAISE EXCEPTION 'snapshot schedule definition authority differs' USING ERRCODE='23514';
            END IF;
            SELECT count(*) INTO n FROM public.pipeline_snapshot_schedule_current_member
                WHERE org_id=h.org_id AND project_id=h.project_id
                  AND definition_id=d.definition_id AND revision=d.revision;
            IF n<>12 THEN
                RAISE EXCEPTION 'snapshot definition current membership incomplete' USING ERRCODE='23514';
            END IF;
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


def downgrade():
    raise RuntimeError('defined schedule claim evidence must be retained')
