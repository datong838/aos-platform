"""Allow an audited replacement to renew one immutable saved snapshot group."""
from alembic import op

revision='a0v_085'
down_revision='a0v_084'
branch_labels=depends_on=None


def upgrade():
    op.execute(r'''
    CREATE OR REPLACE FUNCTION validate_snapshot_recovery_a0v_065() RETURNS trigger
        LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE original public.pipeline_snapshot_schedule_definition_revision;
        renewed public.pipeline_snapshot_schedule_definition_revision;
        transferred_revision public.pipeline_snapshot_schedule_definition_revision;
        transfer_predecessor public.pipeline_snapshot_schedule_definition_revision;
        claim public.pipeline_snapshot_schedule_claim;
        source_claim public.pipeline_snapshot_group_claim;
        saved public.pipeline_snapshot_group_input;
        old_ref jsonb; new_ref jsonb; prior_ref jsonb; expected jsonb; m record; n integer:=0;
        start_at timestamptz;end_at timestamptz;prior_definition_revision bigint;transferred boolean:=false;
    BEGIN
        old_ref=jsonb_build_object('resourceType','SnapshotScheduleDefinitionRevision',
            'resourceId','snapshot-schedule-'||NEW.definition_id::text,
            'revision',NEW.original_definition_revision,'contentHash',NEW.original_definition_hash);
        new_ref=jsonb_build_object('resourceType','SnapshotScheduleDefinitionRevision',
            'resourceId','snapshot-schedule-'||NEW.definition_id::text,
            'revision',NEW.current_definition_revision,'contentHash',NEW.current_definition_hash);
        prior_ref=CASE WHEN NEW.revision=1 THEN 'null'::jsonb ELSE jsonb_build_object(
            'resourceType','SnapshotGroupRecoveryRevision','resourceId','snapshot-recovery-'||NEW.group_id::text,
            'revision',NEW.previous_revision,'contentHash',NEW.previous_hash) END;
        expected=jsonb_build_object('schemaVersion','aos.snapshot-group-recovery/v1','mode','saved-input-only',
            'orgId',NEW.org_id,'projectId',NEW.project_id,'groupId',NEW.group_id::text,'revision',NEW.revision,
            'priorRef',prior_ref,'originalDefinitionRef',old_ref,'currentDefinitionRef',new_ref,
            'originalScheduleClaimHash',NEW.original_schedule_hash,'originalSourceClaimHash',NEW.original_source_hash,
            'inputManifestHash',NEW.input_manifest_hash,'actor',NEW.actor,'executor',NEW.executor,
            'policyRef',NEW.policy_ref,'requestHash',NEW.request_hash,'createdAt',NEW.body->'createdAt');
        IF (NEW.body=expected AND jsonb_typeof(NEW.body->'createdAt')='string'
            AND (NEW.body->>'createdAt')::timestamptz=NEW.created_at
            AND NEW.created_at<=clock_timestamp()
            AND public.canonical_bundle_control_sha256(NEW.body)=NEW.content_hash
            AND public.canonical_bundle_control_sha256(NEW.request)=NEW.request_hash
            AND NEW.request->>'schemaVersion'='aos.snapshot-group-recovery-request/v1'
            AND NEW.request->>'orgId'=NEW.org_id AND NEW.request->>'projectId'=NEW.project_id
            AND NEW.request->>'groupId'=NEW.group_id::text AND NEW.request->>'actor'=NEW.actor
            AND NEW.request->'expectedRecoveryRef'=prior_ref
            AND NEW.request->>'inputManifestHash'=NEW.input_manifest_hash
            AND NEW.request-ARRAY['schemaVersion','orgId','projectId','groupId','actor','expectedDefinitionRef',
                'expectedRecoveryRef','inputManifestHash','notBefore','expiresAt']='{}'::jsonb
            AND jsonb_typeof(NEW.request->'notBefore')='string' AND jsonb_typeof(NEW.request->'expiresAt')='string') IS NOT TRUE THEN
            RAISE EXCEPTION 'snapshot recovery receipt shape or hash differs' USING ERRCODE='23514';
        END IF;
        start_at=(NEW.request->>'notBefore')::timestamptz;end_at=(NEW.request->>'expiresAt')::timestamptz;
        IF NOT (end_at>start_at AND end_at-start_at<=interval '24 hours') THEN
            RAISE EXCEPTION 'snapshot recovery execution window differs' USING ERRCODE='23514';
        END IF;
        IF NEW.revision>1 THEN
            SELECT current_definition_revision INTO STRICT prior_definition_revision
                FROM public.pipeline_snapshot_group_recovery_receipt
                WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND group_id=NEW.group_id AND revision=NEW.previous_revision;
            IF NEW.current_definition_revision<=prior_definition_revision THEN
                RAISE EXCEPTION 'snapshot recovery definition history must advance' USING ERRCODE='23514';
            END IF;
        END IF;
        SELECT * INTO STRICT original FROM public.pipeline_snapshot_schedule_definition_revision
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND definition_id=NEW.definition_id AND revision=NEW.original_definition_revision;
        SELECT * INTO STRICT renewed FROM public.pipeline_snapshot_schedule_definition_revision
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND definition_id=NEW.definition_id AND revision=NEW.current_definition_revision;
        transferred=(original.installation_id,original.generation)<>(renewed.installation_id,renewed.generation);
        IF transferred THEN
            SELECT * INTO STRICT transferred_revision FROM public.pipeline_snapshot_schedule_definition_revision
                WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND definition_id=NEW.definition_id
                  AND revision=renewed.previous_revision;
            SELECT * INTO STRICT transfer_predecessor FROM public.pipeline_snapshot_schedule_definition_revision
                WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND definition_id=NEW.definition_id
                  AND revision=transferred_revision.previous_revision;
            IF (transferred_revision.state='disabled' AND transfer_predecessor.state='disabled'
                AND (transferred_revision.installation_id,transferred_revision.generation)=
                    (renewed.installation_id,renewed.generation)
                AND (transfer_predecessor.installation_id,transfer_predecessor.generation)=
                    (original.installation_id,original.generation)
                AND transferred_revision.request->>'intent'='transfer_saved_recovery'
                AND transferred_revision.request->'settings'='null'::jsonb
                AND transferred_revision.request->'expectedRef'=transferred_revision.body->'priorRef'
                AND transferred_revision.request->'transfer'->>'groupId'=NEW.group_id::text
                AND transferred_revision.request->'transfer'->'expectedRecoveryRef'=prior_ref
                AND transferred_revision.request-ARRAY['orgId','projectId','definitionId','actor','intent',
                    'expectedRef','settings','transfer']='{}'::jsonb) IS NOT TRUE THEN
                RAISE EXCEPTION 'snapshot replacement transfer authority differs' USING ERRCODE='23514';
            END IF;
        END IF;
        SELECT * INTO STRICT claim FROM public.pipeline_snapshot_schedule_claim
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND group_id=NEW.group_id;
        SELECT * INTO STRICT source_claim FROM public.pipeline_snapshot_group_claim
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND group_id=NEW.group_id;
        SELECT * INTO STRICT saved FROM public.pipeline_snapshot_group_input
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND group_id=NEW.group_id;
        IF (claim.record->>'schemaVersion'='aos.snapshot-schedule-claim/v2'
            AND claim.content_hash=NEW.original_schedule_hash AND claim.request->'definitionRef'=old_ref
            AND claim.actor=NEW.executor AND source_claim.actor=NEW.executor AND source_claim.member_count=12
            AND saved.request_hash=NEW.original_source_hash AND source_claim.request_hash=NEW.original_source_hash
            AND saved.manifest_hash=NEW.input_manifest_hash AND saved.read_completed_at<=NEW.created_at
            AND public.canonical_bundle_control_sha256(saved.manifest)=saved.manifest_hash
            AND original.state='enabled' AND renewed.state='enabled'
            AND ((original.installation_id,original.generation)=(renewed.installation_id,renewed.generation) OR transferred)
            AND original.body->>'executor'=NEW.executor AND renewed.body->>'executor'=NEW.executor
            AND original.body->'policyRef'=NEW.policy_ref AND renewed.body->'policyRef'=NEW.policy_ref
            AND original.body->'cron'=renewed.body->'cron' AND original.body->'timezone'=renewed.body->'timezone'
            AND renewed.request->>'intent'='renew_saved_group'
            AND renewed.body->'priorRef'=NEW.request->'expectedDefinitionRef') IS NOT TRUE THEN
            RAISE EXCEPTION 'snapshot recovery original authority differs' USING ERRCODE='23514';
        END IF;
        FOR m IN SELECT om.schedule_id,ob.pipeline_id AS old_pipeline,nb.pipeline_id AS new_pipeline,
                ob.binding_id AS old_binding_id,nb.binding_id AS new_binding_id,
                ob.revision AS old_binding_revision,nb.revision AS new_binding_revision,
                ob.actor AS old_actor,nb.actor AS new_actor,
                oc.control_id AS old_control_id,nc.control_id AS new_control_id,
                oc.revision AS old_control_revision,nc.revision AS new_control_revision,
                oc.selection_id AS old_selection_id,nc.selection_id AS new_selection_id,
                oc.selection_revision AS old_selection_revision,nc.selection_revision AS new_selection_revision,
                oc.actor AS old_control_actor,nc.actor AS new_control_actor,
                oc.payload->'draft' AS old_draft,nc.payload->'draft' AS new_draft,
                sc.control_id AS source_control_id,sc.control_revision AS source_control_revision,
                sc.control_hash AS source_control_hash,oc.content_hash AS old_control_hash
            FROM public.pipeline_snapshot_schedule_definition_member om
            JOIN public.pipeline_snapshot_schedule_definition_member nm
                ON (nm.org_id,nm.project_id,nm.definition_id,nm.schedule_id)=(om.org_id,om.project_id,om.definition_id,om.schedule_id)
                AND nm.revision=NEW.current_definition_revision
            JOIN public.pipeline_schedule_control_binding ob
                ON (ob.org_id,ob.project_id,ob.schedule_id,ob.binding_id,ob.revision,ob.content_hash)=
                   (om.org_id,om.project_id,om.schedule_id,om.binding_id,om.binding_revision,om.binding_hash)
            JOIN public.pipeline_schedule_control_binding nb
                ON (nb.org_id,nb.project_id,nb.schedule_id,nb.binding_id,nb.revision,nb.content_hash)=
                   (nm.org_id,nm.project_id,nm.schedule_id,nm.binding_id,nm.binding_revision,nm.binding_hash)
            JOIN public.pipeline_runtime_control_revision oc
                ON (oc.org_id,oc.project_id,oc.control_id,oc.revision,oc.content_hash)=
                   (ob.org_id,ob.project_id,ob.control_id,ob.control_revision,ob.control_hash)
            JOIN public.pipeline_runtime_control_revision nc
                ON (nc.org_id,nc.project_id,nc.control_id,nc.revision,nc.content_hash)=
                   (nb.org_id,nb.project_id,nb.control_id,nb.control_revision,nb.control_hash)
            JOIN public.pipeline_snapshot_schedule_member sm
                ON (sm.org_id,sm.project_id,sm.schedule_id,sm.binding_id,sm.binding_revision,sm.binding_hash)=
                   (om.org_id,om.project_id,om.schedule_id,om.binding_id,om.binding_revision,om.binding_hash)
                AND sm.group_id=NEW.group_id
            JOIN public.pipeline_snapshot_group_member gm
                ON (gm.org_id,gm.project_id,gm.group_id,gm.run_id)=(sm.org_id,sm.project_id,sm.group_id,sm.run_id)
            JOIN public.pipeline_controlled_source_claim sc
                ON (sc.org_id,sc.project_id,sc.run_id)=(gm.org_id,gm.project_id,gm.run_id)
            WHERE om.org_id=NEW.org_id AND om.project_id=NEW.project_id
                AND om.definition_id=NEW.definition_id AND om.revision=NEW.original_definition_revision
        LOOP
            n=n+1;
            IF (m.old_pipeline=m.new_pipeline
                AND m.old_actor=NEW.executor AND m.new_actor=NEW.executor
                AND m.old_control_actor=NEW.executor AND m.new_control_actor=NEW.executor
                AND ((NOT transferred AND m.old_binding_id=m.new_binding_id
                    AND m.new_binding_revision>m.old_binding_revision
                    AND m.old_control_id=m.new_control_id AND m.new_control_revision>m.old_control_revision
                    AND m.old_selection_id=m.new_selection_id AND m.new_selection_revision>m.old_selection_revision
                    AND m.old_draft-ARRAY['notBefore','expiresAt','sourceSelectionRef']=
                        m.new_draft-ARRAY['notBefore','expiresAt','sourceSelectionRef'])
                  OR (transferred
                    AND m.new_draft->'installationRef'->>'installationId'=renewed.installation_id::text
                    AND m.new_draft->>'generation'=renewed.generation::text
                    AND m.old_draft-ARRAY['notBefore','expiresAt','sourceSelectionRef','installationRef',
                        'generation','executionEpoch','configurationRef','packageRef']=
                        m.new_draft-ARRAY['notBefore','expiresAt','sourceSelectionRef','installationRef',
                        'generation','executionEpoch','configurationRef','packageRef']))
                AND (m.source_control_id,m.source_control_revision,m.source_control_hash)=
                    (m.old_control_id,m.old_control_revision,m.old_control_hash)
                AND (m.new_draft->>'notBefore')::timestamptz=start_at
                AND (m.new_draft->>'expiresAt')::timestamptz=end_at
                AND start_at>=(m.old_draft->>'notBefore')::timestamptz
                AND end_at>(m.old_draft->>'expiresAt')::timestamptz
                AND (m.old_draft->>'expiresAt')::timestamptz>(m.old_draft->>'notBefore')::timestamptz
                AND (m.old_draft->>'expiresAt')::timestamptz-(m.old_draft->>'notBefore')::timestamptz<=interval '24 hours'
                AND saved.read_started_at>=(m.old_draft->>'notBefore')::timestamptz
                AND saved.read_completed_at<(m.old_draft->>'expiresAt')::timestamptz) IS NOT TRUE THEN
                RAISE EXCEPTION 'snapshot recovery member semantics differ' USING ERRCODE='23514';
            END IF;
        END LOOP;
        IF n<>12 THEN RAISE EXCEPTION 'snapshot recovery requires twelve original members' USING ERRCODE='23514'; END IF;
        RETURN NEW;
    END $$;
    ''')


def downgrade():
    raise RuntimeError('replacement recovery receipt history must be retained')
