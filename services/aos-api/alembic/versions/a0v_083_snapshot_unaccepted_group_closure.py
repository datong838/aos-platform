"""Audited terminal closure for a snapshot group rejected before any source call."""

from alembic import op


revision = "a0v_083"
down_revision = "a0v_082"
branch_labels = depends_on = None


def upgrade():
    op.execute(r"""
    CREATE TABLE public.pipeline_snapshot_unaccepted_group_closure_receipt(
      org_id text NOT NULL, project_id text NOT NULL, receipt_id uuid NOT NULL,
      group_id uuid NOT NULL, idempotency_key text NOT NULL,
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      actor text NOT NULL, authority_data jsonb NOT NULL,
      content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      created_at timestamptz NOT NULL,
      PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,idempotency_key), UNIQUE(org_id,project_id,group_id),
      FOREIGN KEY(org_id,project_id,group_id)
        REFERENCES public.pipeline_snapshot_schedule_claim(org_id,project_id,group_id)
    );
    ALTER TABLE public.pipeline_snapshot_unaccepted_group_closure_receipt ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.pipeline_snapshot_unaccepted_group_closure_receipt FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON public.pipeline_snapshot_unaccepted_group_closure_receipt
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    REVOKE ALL ON public.pipeline_snapshot_unaccepted_group_closure_receipt
      FROM PUBLIC,aos_runtime,aos_extension_maintainer;
    GRANT SELECT ON public.pipeline_snapshot_unaccepted_group_closure_receipt
      TO aos_runtime,aos_extension_maintainer;
    CREATE TRIGGER snapshot_unaccepted_group_history_guard BEFORE UPDATE OR DELETE
      ON public.pipeline_snapshot_unaccepted_group_closure_receipt FOR EACH ROW
      EXECUTE FUNCTION public.extension_reject_history_mutation();
    CREATE TRIGGER snapshot_unaccepted_group_no_truncate BEFORE TRUNCATE
      ON public.pipeline_snapshot_unaccepted_group_closure_receipt FOR EACH STATEMENT
      EXECUTE FUNCTION public.extension_reject_history_mutation();

    CREATE FUNCTION public.snapshot_unaccepted_group_terminal_guard_a0v_083()
    RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    BEGIN
      IF NEW.status='failed' AND NEW.error_code='SOURCE_BUDGET_REJECTED_BEFORE_GROUP_CLAIM'
        AND NOT EXISTS(
          SELECT 1 FROM public.pipeline_snapshot_schedule_member m
          JOIN public.pipeline_snapshot_unaccepted_group_closure_receipt r
            ON (r.org_id,r.project_id,r.group_id)=(m.org_id,m.project_id,m.group_id)
          WHERE (m.org_id,m.project_id,m.run_id)=(NEW.org_id,NEW.project_id,NEW.id))
      THEN RAISE EXCEPTION 'immutable snapshot group closure receipt required' USING ERRCODE='55000'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER snapshot_unaccepted_group_terminal BEFORE INSERT OR UPDATE ON public.meta_schedule_run
      FOR EACH ROW EXECUTE FUNCTION public.snapshot_unaccepted_group_terminal_guard_a0v_083();

    CREATE FUNCTION public.pipeline_snapshot_unaccepted_group_close_a0v_083(
      p_request jsonb,p_actor text)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE
      v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_key text:=p_request->>'idempotencyKey'; v_group uuid; v_definition uuid;
      v_claim record; v_head record; v_current record; v_original record; v_old record;
      v_hash text; v_body jsonb; v_content_hash text; v_now timestamptz;
      v_receipt_id uuid:=gen_random_uuid(); v_member_count bigint; v_run_count bigint;
      v_group_claims bigint; v_group_inputs bigint; v_group_members bigint;
      v_source_claims bigint; v_ingress_commands bigint; v_derived_commands bigint;
      v_dataset_receipts bigint;
    BEGIN
      IF current_setting('role',true) IS DISTINCT FROM 'aos_extension_maintainer'
        OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
        OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
        OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        OR v_org IS NULL OR v_project IS NULL
      THEN RAISE EXCEPTION 'scoped snapshot closure maintainer required' USING ERRCODE='42501'; END IF;
      IF jsonb_typeof(p_request) IS DISTINCT FROM 'object'
        OR p_request->>'schemaVersion' IS DISTINCT FROM 'aos.pipeline-snapshot.unaccepted-group-closure/v1'
        OR p_request-ARRAY['schemaVersion','groupId','originalDefinitionRef','currentDisabledDefinitionRef',
                           'reasonCode','idempotencyKey']<>'{}'::jsonb
        OR p_request->>'reasonCode' IS DISTINCT FROM 'SOURCE_BUDGET_REJECTED_BEFORE_GROUP_CLAIM'
        OR jsonb_typeof(p_request->'originalDefinitionRef') IS DISTINCT FROM 'object'
        OR jsonb_typeof(p_request->'currentDisabledDefinitionRef') IS DISTINCT FROM 'object'
        OR v_key IS NULL OR v_key<>btrim(v_key) OR length(v_key) NOT BETWEEN 1 AND 160 OR v_key ~ '[[:cntrl:]]'
        OR p_actor IS NULL OR p_actor<>btrim(p_actor) OR length(p_actor) NOT BETWEEN 1 AND 240 OR p_actor ~ '[[:cntrl:]]'
      THEN RAISE EXCEPTION 'invalid snapshot group closure request' USING ERRCODE='22023'; END IF;
      v_group:=(p_request->>'groupId')::uuid;
      IF v_group IS NULL OR v_group::text<>p_request->>'groupId'
      THEN RAISE EXCEPTION 'canonical snapshot group identity required' USING ERRCODE='22023'; END IF;
      PERFORM 1 FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project
        AND subject=p_actor FOR SHARE;
      IF NOT EXISTS(SELECT 1 FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project
          AND subject=p_actor AND lower(role) IN ('admin','owner'))
      THEN RAISE EXCEPTION 'current snapshot closure administrator required' USING ERRCODE='42501'; END IF;
      v_hash:='sha256:'||encode(sha256(convert_to(
        public.canonical_asset_registry_jsonb(p_request),'UTF8')),'hex');
      SELECT * INTO v_old FROM public.pipeline_snapshot_unaccepted_group_closure_receipt
        WHERE org_id=v_org AND project_id=v_project AND idempotency_key=v_key;
      IF FOUND THEN
        IF v_old.request_hash<>v_hash OR v_old.actor<>p_actor
        THEN RAISE EXCEPTION 'snapshot closure idempotency drift' USING ERRCODE='40001'; END IF;
        RETURN v_old.authority_data||jsonb_build_object('contentHash',v_old.content_hash,'replayed',true);
      END IF;

      SELECT * INTO v_claim FROM public.pipeline_snapshot_schedule_claim
        WHERE org_id=v_org AND project_id=v_project AND group_id=v_group FOR UPDATE;
      IF NOT FOUND OR v_claim.request->>'schemaVersion'<>'aos.snapshot-schedule-request/v2'
        OR v_claim.record->>'schemaVersion'<>'aos.snapshot-schedule-claim/v2'
        OR v_claim.request_hash<>public.canonical_bundle_control_sha256(v_claim.request)
        OR v_claim.content_hash<>public.canonical_bundle_control_sha256(v_claim.record)
        OR v_claim.record->'request' IS DISTINCT FROM v_claim.request
      THEN RAISE EXCEPTION 'exact snapshot schedule claim required' USING ERRCODE='40001'; END IF;
      v_definition:=replace(v_claim.request#>>'{definitionRef,resourceId}','snapshot-schedule-','')::uuid;
      IF v_definition IS NULL OR p_request->'originalDefinitionRef' IS DISTINCT FROM v_claim.request->'definitionRef'
      THEN RAISE EXCEPTION 'original definition reference differs' USING ERRCODE='40001'; END IF;
      SELECT * INTO v_head FROM public.pipeline_snapshot_schedule_definition_head
        WHERE org_id=v_org AND project_id=v_project AND definition_id=v_definition FOR UPDATE;
      SELECT * INTO v_current FROM public.pipeline_snapshot_schedule_definition_revision
        WHERE org_id=v_org AND project_id=v_project AND definition_id=v_definition AND revision=v_head.revision;
      SELECT * INTO v_original FROM public.pipeline_snapshot_schedule_definition_revision
        WHERE org_id=v_org AND project_id=v_project AND definition_id=v_definition
          AND revision=(v_claim.request#>>'{definitionRef,revision}')::bigint;
      IF NOT FOUND OR v_head.state<>'disabled' OR v_current.state<>'disabled'
        OR v_head.content_hash<>v_current.content_hash
        OR v_current.previous_revision<>v_original.revision OR v_current.previous_hash<>v_original.content_hash
        OR v_original.state<>'enabled'
        OR p_request->'currentDisabledDefinitionRef' IS DISTINCT FROM jsonb_build_object(
          'resourceType','SnapshotScheduleDefinitionRevision',
          'resourceId','snapshot-schedule-'||v_definition::text,
          'revision',v_current.revision,'contentHash',v_current.content_hash)
        OR p_request->'originalDefinitionRef' IS DISTINCT FROM jsonb_build_object(
          'resourceType','SnapshotScheduleDefinitionRevision',
          'resourceId','snapshot-schedule-'||v_definition::text,
          'revision',v_original.revision,'contentHash',v_original.content_hash)
        OR v_current.installation_id<>v_original.installation_id OR v_current.generation<>v_original.generation
        OR v_head.installation_id<>v_current.installation_id OR v_head.generation<>v_current.generation
      THEN RAISE EXCEPTION 'current disabled definition chain differs' USING ERRCODE='40001'; END IF;

      PERFORM 1 FROM public.pipeline_snapshot_schedule_member
        WHERE org_id=v_org AND project_id=v_project AND group_id=v_group ORDER BY ordinal FOR UPDATE;
      SELECT count(*) INTO v_member_count FROM public.pipeline_snapshot_schedule_member
        WHERE org_id=v_org AND project_id=v_project AND group_id=v_group;
      PERFORM 1 FROM public.meta_schedule_run r JOIN public.pipeline_snapshot_schedule_member m
        ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
        WHERE m.org_id=v_org AND m.project_id=v_project AND m.group_id=v_group ORDER BY m.ordinal FOR UPDATE OF r;
      SELECT count(*) INTO v_run_count FROM public.meta_schedule_run r
        JOIN public.pipeline_snapshot_schedule_member m ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
        JOIN public.meta_schedule s ON (s.org_id,s.project_id,s.id)=(m.org_id,m.project_id,m.schedule_id)
        WHERE m.org_id=v_org AND m.project_id=v_project AND m.group_id=v_group
          AND r.status='running' AND r.finished_at IS NULL AND r.executor_id='' AND NOT r.executor_stopped
          AND r.rows_written=0 AND r.error_code='' AND r.error_message='' AND NOT s.enabled;
      IF v_member_count<>12 OR v_run_count<>12
      THEN RAISE EXCEPTION 'twelve disabled unaccepted schedule runs required' USING ERRCODE='55000'; END IF;

      SELECT count(*) INTO v_group_claims FROM public.pipeline_snapshot_group_claim
        WHERE org_id=v_org AND project_id=v_project AND group_id=v_group;
      SELECT count(*) INTO v_group_inputs FROM public.pipeline_snapshot_group_input
        WHERE org_id=v_org AND project_id=v_project AND group_id=v_group;
      SELECT count(*) INTO v_group_members FROM public.pipeline_snapshot_group_member
        WHERE org_id=v_org AND project_id=v_project AND group_id=v_group;
      SELECT count(*) INTO v_source_claims FROM public.pipeline_controlled_source_claim c
        JOIN public.pipeline_snapshot_schedule_member m ON (m.org_id,m.project_id,m.run_id)=(c.org_id,c.project_id,c.run_id)
        WHERE m.org_id=v_org AND m.project_id=v_project AND m.group_id=v_group;
      SELECT count(*) INTO v_ingress_commands FROM public.ecommerce_ingress_command c
        JOIN public.pipeline_snapshot_schedule_member m ON (m.org_id,m.project_id,m.run_id)=(c.org_id,c.project_id,c.run_id)
        WHERE m.org_id=v_org AND m.project_id=v_project AND m.group_id=v_group;
      SELECT count(*) INTO v_derived_commands FROM public.ecommerce_ingress_derived_command c
        JOIN public.pipeline_snapshot_schedule_member m ON (m.org_id,m.project_id,m.run_id)=(c.org_id,c.project_id,c.run_id)
        WHERE m.org_id=v_org AND m.project_id=v_project AND m.group_id=v_group;
      SELECT count(*) INTO v_dataset_receipts FROM public.ecommerce_ingress_dataset_receipt c
        JOIN public.pipeline_snapshot_schedule_member m ON (m.org_id,m.project_id,m.run_id)=(c.org_id,c.project_id,c.run_id)
        WHERE m.org_id=v_org AND m.project_id=v_project AND m.group_id=v_group;
      IF v_group_claims<>0 OR v_group_inputs<>0 OR v_group_members<>0 OR v_source_claims<>0
        OR v_ingress_commands<>0 OR v_derived_commands<>0 OR v_dataset_receipts<>0
      THEN RAISE EXCEPTION 'snapshot group accepted or has source effects' USING ERRCODE='55000'; END IF;

      v_now:=clock_timestamp();
      v_body:=jsonb_build_object(
        'schemaVersion','aos.pipeline-snapshot.unaccepted-group-closure-receipt/v1',
        'receiptId',v_receipt_id::text,'tenant',jsonb_build_object('orgId',v_org,'projectId',v_project),
        'request',p_request,'requestHash',v_hash,'actor',p_actor,'createdAt',v_now,
        'businessAccepted',false,'priorScheduleClaim',v_claim.record,
        'runEvidence',jsonb_build_object('memberCount',v_member_count,'runningCount',v_run_count),
        'noEffectEvidence',jsonb_build_object('groupClaimCount',v_group_claims,'groupInputCount',v_group_inputs,
          'groupMemberCount',v_group_members,'sourceClaimCount',v_source_claims,
          'ingressCommandCount',v_ingress_commands,'derivedCommandCount',v_derived_commands,
          'datasetReceiptCount',v_dataset_receipts,'checkedAt',v_now));
      v_content_hash:='sha256:'||encode(sha256(convert_to(
        public.canonical_asset_registry_jsonb(v_body),'UTF8')),'hex');
      INSERT INTO public.pipeline_snapshot_unaccepted_group_closure_receipt(
        org_id,project_id,receipt_id,group_id,idempotency_key,request_hash,actor,
        authority_data,content_hash,created_at)
      VALUES(v_org,v_project,v_receipt_id,v_group,v_key,v_hash,p_actor,v_body,v_content_hash,v_now);
      UPDATE public.meta_schedule_run r SET status='failed',finished_at=v_now,
        duration_ms=greatest(0,(extract(epoch FROM (v_now-r.started_at))*1000)::integer),
        rows_written=0,error_code='SOURCE_BUDGET_REJECTED_BEFORE_GROUP_CLAIM',
        error_message='governed source budget rejected before snapshot group claim',
        executor_id='pipeline-live-v1',executor_stopped=true
        FROM public.pipeline_snapshot_schedule_member m
        WHERE (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
          AND m.org_id=v_org AND m.project_id=v_project AND m.group_id=v_group;
      UPDATE public.meta_schedule s SET last_run=jsonb_build_object(
          'id',r.id,'at',v_now,'status',r.status,'trigger',r.trigger,
          'durationMs',r.duration_ms,'rowsWritten',r.rows_written,'errorCode',r.error_code),updated_at=v_now
        FROM public.meta_schedule_run r JOIN public.pipeline_snapshot_schedule_member m
          ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
        WHERE (s.org_id,s.project_id,s.id)=(m.org_id,m.project_id,m.schedule_id)
          AND m.org_id=v_org AND m.project_id=v_project AND m.group_id=v_group;
      RETURN v_body||jsonb_build_object('contentHash',v_content_hash,'replayed',false);
    END $$;
    REVOKE ALL ON FUNCTION public.pipeline_snapshot_unaccepted_group_close_a0v_083(jsonb,text)
      FROM PUBLIC,aos_runtime;
    GRANT EXECUTE ON FUNCTION public.pipeline_snapshot_unaccepted_group_close_a0v_083(jsonb,text)
      TO aos_extension_maintainer;
    """)


def downgrade():
    raise RuntimeError("snapshot unaccepted group closure history must be retained")
