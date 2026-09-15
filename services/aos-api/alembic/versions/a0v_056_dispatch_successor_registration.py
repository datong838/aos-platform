"""Register a successor against retained, exactly detached dispatch history."""
from alembic import op

revision = 'a0v_056'
down_revision = 'a0v_055'
branch_labels = depends_on = None


def upgrade():
    op.execute(r"""CREATE TABLE extension_dispatch_successor_registration_receipt (
        org_id text NOT NULL, project_id text NOT NULL,
        receipt_id uuid NOT NULL, installation_id uuid NOT NULL, generation uuid NOT NULL,
        group_id uuid NOT NULL,
        idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160 AND idempotency_key=btrim(idempotency_key)),
        request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
        payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
        content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,receipt_id),
        UNIQUE(org_id,project_id,idempotency_key),
        FOREIGN KEY(org_id,project_id,installation_id,generation)
          REFERENCES extension_runtime_binding(org_id,project_id,installation_id,generation)
    );
    ALTER TABLE extension_dispatch_successor_registration_receipt ENABLE ROW LEVEL SECURITY;
    ALTER TABLE extension_dispatch_successor_registration_receipt FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON extension_dispatch_successor_registration_receipt
      USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));
    CREATE FUNCTION extension_dispatch_successor_registration_guard_a0v_056() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
    BEGIN
      IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'registration history is immutable' USING ERRCODE='55000';
      END IF;
      IF NEW.payload->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.successor-dispatch-registration-receipt/v1'
        OR NEW.payload#>>'{tenant,orgId}' IS DISTINCT FROM NEW.org_id
        OR NEW.payload#>>'{tenant,projectId}' IS DISTINCT FROM NEW.project_id
        OR NEW.payload->>'receiptId' IS DISTINCT FROM NEW.receipt_id::text
        OR NEW.payload->>'installationId' IS DISTINCT FROM NEW.installation_id::text
        OR NEW.payload->>'generation' IS DISTINCT FROM NEW.generation::text
        OR NEW.payload->>'groupId' IS DISTINCT FROM NEW.group_id::text
        OR NEW.payload->>'idempotencyKey' IS DISTINCT FROM NEW.idempotency_key
        OR NEW.payload->>'requestHash' IS DISTINCT FROM NEW.request_hash
        OR NEW.content_hash IS DISTINCT FROM 'sha256:' || encode(public.digest(
            convert_to(public.canonical_asset_registry_jsonb(NEW.payload),'UTF8'),'sha256'),'hex')
      THEN RAISE EXCEPTION 'registration receipt integrity differs' USING ERRCODE='23514'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER immutable_history BEFORE INSERT OR UPDATE OR DELETE ON extension_dispatch_successor_registration_receipt
      FOR EACH ROW EXECUTE FUNCTION extension_dispatch_successor_registration_guard_a0v_056();
    CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON extension_dispatch_successor_registration_receipt
      FOR EACH STATEMENT EXECUTE FUNCTION extension_dispatch_successor_registration_guard_a0v_056();
    REVOKE ALL ON extension_dispatch_successor_registration_receipt FROM PUBLIC,aos_runtime;
    GRANT SELECT ON extension_dispatch_successor_registration_receipt TO aos_runtime;
    REVOKE ALL ON FUNCTION extension_dispatch_successor_registration_guard_a0v_056() FROM PUBLIC;
    """)
    op.execute(r"""CREATE FUNCTION extension_dispatch_successor_register_a0v_056(p_request jsonb,p_actor text)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE
      v_org text:=current_setting('aos.org_id',true);
      v_project text:=current_setting('aos.project_id',true);
      v_install uuid; v_generation uuid; v_group uuid; v_pk uuid; v_lock record;
      v_existing record; v_binding record; v_ref jsonb; v_config jsonb; v_label text;
      v_hash text; v_body jsonb; v_snapshot jsonb; v_content_hash text;
      v_receipt uuid:=gen_random_uuid(); v_key text; v_name text; v_number jsonb;
      v_successor jsonb:=p_request; v_parent_ref jsonb; v_parent record; v_activation record;
      v_old_binding record; v_old_operation record; v_expected bigint;
      v_operations text[]:=ARRAY[
        'ecommerce_growth_analysis_advance','ecommerce_growth_case_put',
        'ecommerce_growth_content_generate','ecommerce_growth_content_review',
        'ecommerce_growth_data_fulfill','ecommerce_growth_investigation_describe',
        'ecommerce_growth_review_advance','ecommerce_growth_schedule_put','ecommerce_growth_schedule_trigger'];
    BEGIN
      IF jsonb_typeof(p_request) IS DISTINCT FROM 'object'
        OR p_request->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.successor-dispatch-registration/v1'
        OR p_request-ARRAY['schemaVersion','registration','expectedGroupRevision','predecessorDetachReceiptRef']<>'{}'::jsonb
        OR jsonb_typeof(p_request->'expectedGroupRevision') IS DISTINCT FROM 'number'
        OR (p_request->>'expectedGroupRevision') !~ '^[1-9][0-9]*$'
      THEN RAISE EXCEPTION 'invalid successor registration envelope' USING ERRCODE='22023'; END IF;
      v_expected:=(p_request->>'expectedGroupRevision')::bigint;
      v_parent_ref:=p_request->'predecessorDetachReceiptRef';
      IF jsonb_typeof(v_parent_ref) IS DISTINCT FROM 'object'
        OR v_parent_ref-ARRAY['resourceType','resourceId','revision','contentHash']<>'{}'::jsonb
        OR v_parent_ref->>'resourceType' IS DISTINCT FROM 'DispatchDisableDetachReceipt'
        OR v_parent_ref->'revision' IS DISTINCT FROM '1'::jsonb
        OR coalesce(v_parent_ref->>'contentHash','') !~ '^sha256:[0-9a-f]{64}$'
        OR (v_parent_ref->>'resourceId')::uuid::text IS DISTINCT FROM v_parent_ref->>'resourceId'
      THEN RAISE EXCEPTION 'exact predecessor detach ref required' USING ERRCODE='22023'; END IF;
      p_request:=p_request->'registration';
      IF current_setting('role',true) IS DISTINCT FROM 'aos_extension_maintainer'
        OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
        OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
        OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
      THEN RAISE EXCEPTION 'dedicated registration maintainer required' USING ERRCODE='42501'; END IF;
      IF v_org IS NULL OR v_org='' OR v_project IS NULL OR v_project=''
        OR p_actor IS NULL OR length(p_actor) NOT BETWEEN 1 AND 240
        OR p_actor<>btrim(p_actor) OR p_actor ~ '[[:cntrl:]]'
        OR jsonb_typeof(p_request) IS DISTINCT FROM 'object'
        OR p_request->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.first-dispatch-registration/v1'
        OR p_request-ARRAY['schemaVersion','installationRef','generation','bindingRevision','executionEpoch','configRef','groupId','idempotencyKey'] <> '{}'::jsonb
      THEN RAISE EXCEPTION 'invalid registration request' USING ERRCODE='22023'; END IF;
      v_ref:=p_request->'installationRef'; v_config:=p_request->'configRef'; v_key:=p_request->>'idempotencyKey';
      FOREACH v_name IN ARRAY ARRAY['generation','groupId','idempotencyKey'] LOOP
        IF jsonb_typeof(p_request->v_name) IS DISTINCT FROM 'string'
        THEN RAISE EXCEPTION 'registration string field required' USING ERRCODE='22023'; END IF;
      END LOOP;
      IF jsonb_typeof(v_ref) IS DISTINCT FROM 'object' OR jsonb_typeof(v_config) IS DISTINCT FROM 'object'
        OR v_ref-ARRAY['installationId','revision','lockHash','overlayRevision']<>'{}'::jsonb
        OR v_config-ARRAY['configurationId','revision','hash']<>'{}'::jsonb
        OR v_key IS NULL OR length(v_key) NOT BETWEEN 1 AND 160 OR v_key<>btrim(v_key) OR v_key ~ '[[:cntrl:]]'
        OR coalesce(v_ref->>'lockHash','') !~ '^sha256:[0-9a-f]{64}$'
        OR coalesce(v_config->>'hash','') !~ '^sha256:[0-9a-f]{64}$'
        OR coalesce(v_ref->>'overlayRevision','')=''
      THEN RAISE EXCEPTION 'invalid registration references' USING ERRCODE='22023'; END IF;
      FOREACH v_name IN ARRAY ARRAY['installationId','lockHash','overlayRevision'] LOOP
        IF jsonb_typeof(v_ref->v_name) IS DISTINCT FROM 'string'
        THEN RAISE EXCEPTION 'registration reference string required' USING ERRCODE='22023'; END IF;
      END LOOP;
      FOREACH v_name IN ARRAY ARRAY['configurationId','hash'] LOOP
        IF jsonb_typeof(v_config->v_name) IS DISTINCT FROM 'string'
        THEN RAISE EXCEPTION 'configuration reference string required' USING ERRCODE='22023'; END IF;
      END LOOP;
      FOREACH v_number IN ARRAY ARRAY[v_ref->'revision',v_config->'revision',p_request->'bindingRevision',p_request->'executionEpoch'] LOOP
        IF jsonb_typeof(v_number) IS DISTINCT FROM 'number' OR coalesce(v_number::text,'') !~ '^[1-9][0-9]*$'
          OR (v_number::text)::numeric>9223372036854775807
        THEN RAISE EXCEPTION 'invalid registration revision' USING ERRCODE='22023'; END IF;
      END LOOP;
      v_install:=(v_ref->>'installationId')::uuid; v_generation:=(p_request->>'generation')::uuid;
      v_group:=(p_request->>'groupId')::uuid;
      IF v_install IS NULL OR v_generation IS NULL OR v_group IS NULL
        OR v_install::text IS DISTINCT FROM v_ref->>'installationId'
        OR v_generation::text IS DISTINCT FROM p_request->>'generation'
        OR v_group::text IS DISTINCT FROM p_request->>'groupId'
        OR (v_config->>'configurationId')::uuid::text IS DISTINCT FROM v_config->>'configurationId'
        OR v_config->>'configurationId' IS NULL
      THEN RAISE EXCEPTION 'noncanonical registration identity' USING ERRCODE='22023'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(v_org||chr(31)||v_project||chr(31)||'ecommerce-first-registration',0));
      PERFORM pg_advisory_xact_lock(hashtextextended(v_org||chr(31)||v_project||chr(31)||v_group::text,0));
      PERFORM 1 FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project AND subject=p_actor FOR SHARE;
      IF (SELECT count(*) FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project AND subject=p_actor)<>1
        OR NOT EXISTS(SELECT 1 FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project
          AND subject=p_actor AND role IN ('admin','asset-installer'))
      THEN RAISE EXCEPTION 'current registration actor denied' USING ERRCODE='42501'; END IF;
      SELECT installation_pk INTO v_pk FROM public.bundle_installation
        WHERE org_id=v_org AND project_id=v_project AND installation_id=v_install
          AND current_revision=(v_ref->>'revision')::bigint AND active_revision=(v_ref->>'revision')::bigint
          AND etag_version=(v_ref->>'revision')::bigint FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'registration installation drifted' USING ERRCODE='40001'; END IF;
      SELECT l.lock_payload,l.permission_diff_json INTO v_lock FROM public.bundle_installation_revision r
        JOIN public.bundle_composition_lock l ON l.org_id=r.org_id AND l.project_id=r.project_id
          AND l.composition_pk=r.composition_pk AND l.revision=r.lock_revision
        WHERE r.org_id=v_org AND r.project_id=v_project AND r.installation_pk=v_pk
          AND r.revision=(v_ref->>'revision')::bigint AND r.state='active'
          AND r.lock_hash=v_ref->>'lockHash' AND r.overlay_revision=v_ref->>'overlayRevision';
      IF NOT FOUND THEN RAISE EXCEPTION 'registration lock differs' USING ERRCODE='40001'; END IF;
      IF jsonb_typeof(v_lock.lock_payload->'resolved') IS DISTINCT FROM 'array'
        OR (SELECT count(*) FROM jsonb_array_elements(v_lock.lock_payload->'resolved') p WHERE p->>'id'='solution.ecommerce.growth')<>1
        OR jsonb_typeof(v_lock.permission_diff_json#>'{target,markings}') IS DISTINCT FROM 'array'
      THEN RAISE EXCEPTION 'registration package unavailable' USING ERRCODE='55000'; END IF;
      FOR v_label IN SELECT jsonb_array_elements_text(v_lock.permission_diff_json#>'{target,markings}') LOOP
        PERFORM 1 FROM public.authz_tuple WHERE org_id=v_org AND project_id=v_project
          AND user_key='user:'||p_actor AND relation='bearer' AND object_key='marking:'||v_label FOR SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'registration marking denied' USING ERRCODE='42501'; END IF;
      END LOOP;
      SELECT * INTO v_binding FROM public.extension_runtime_binding WHERE org_id=v_org AND project_id=v_project
        AND installation_id=v_install AND generation=v_generation FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'registration runtime unavailable' USING ERRCODE='40001'; END IF;
      IF (SELECT count(*) FROM public.extension_runtime_binding WHERE org_id=v_org AND project_id=v_project AND installation_id=v_install)<>1
        OR v_binding.revision IS DISTINCT FROM (p_request->>'bindingRevision')::bigint
        OR v_binding.execution_epoch IS DISTINCT FROM (p_request->>'executionEpoch')::bigint
        OR v_binding.installation_revision IS DISTINCT FROM (v_ref->>'revision')::bigint
        OR v_binding.config_ref IS DISTINCT FROM v_config OR v_binding.enabled IS NOT TRUE
        OR v_binding.operation_fence IS NOT FALSE OR v_binding.desired_state IS DISTINCT FROM 'enabled'
        OR v_binding.observed_state IS DISTINCT FROM 'ready'
      THEN RAISE EXCEPTION 'registration runtime drifted' USING ERRCODE='40001'; END IF;
      PERFORM 1 FROM public.extension_runtime_configuration WHERE org_id=v_org AND project_id=v_project
        AND installation_id=v_install AND generation=v_generation
        AND configuration_id=(v_config->>'configurationId')::uuid AND revision=(v_config->>'revision')::bigint
        AND content_hash=v_config->>'hash';
      IF NOT FOUND THEN RAISE EXCEPTION 'registration configuration unavailable' USING ERRCODE='40001'; END IF;
      p_request:=v_successor;
      v_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(p_request),'UTF8')),'hex');
      SELECT * INTO v_existing FROM public.extension_dispatch_successor_registration_receipt
        WHERE org_id=v_org AND project_id=v_project AND idempotency_key=v_key;
      IF FOUND THEN
        IF v_existing.request_hash IS DISTINCT FROM v_hash OR v_existing.payload->>'actor' IS DISTINCT FROM p_actor
          OR v_existing.payload->'request' IS DISTINCT FROM p_request
        THEN RAISE EXCEPTION 'successor idempotency conflict' USING ERRCODE='40001'; END IF;
        RETURN v_existing.payload||jsonb_build_object('contentHash',v_existing.content_hash,'replayed',true);
      END IF;
      SELECT r.*,l.activation_operation_id,l.cutover_group_id,l.status AS lifecycle_status,
             l.request_hash AS lifecycle_request_hash,l.operation_ids,l.fenced_group_revision,
             e.payload AS event_payload,e.payload_hash
        INTO v_parent FROM public.extension_dispatch_lifecycle_receipt r
        JOIN public.extension_dispatch_lifecycle_operation l USING(org_id,project_id,runtime_operation_id)
        JOIN public.extension_dispatch_lifecycle_event e USING(org_id,project_id,runtime_operation_id)
        WHERE r.org_id=v_org AND r.project_id=v_project
          AND r.receipt_id=(v_parent_ref->>'resourceId')::uuid AND r.phase='detach'
          AND e.sequence=2 AND e.event_type='DISPATCH_DISABLED_DETACHED';
      IF NOT FOUND OR v_parent.lifecycle_status<>'detached' OR v_parent.cutover_group_id<>v_group
        OR v_parent.request_hash IS DISTINCT FROM v_parent.lifecycle_request_hash
        OR v_parent.fenced_group_revision+1 IS DISTINCT FROM v_expected
        OR v_parent.operation_ids IS DISTINCT FROM to_jsonb(v_operations)
        OR v_parent.authority_data->'operationIds' IS DISTINCT FROM v_parent.operation_ids
        OR v_parent.content_hash IS DISTINCT FROM v_parent_ref->>'contentHash'
        OR v_parent.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(v_parent.authority_data),'UTF8')),'hex')
        OR v_parent.authority_data->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',v_org,'projectId',v_project)
        OR v_parent.authority_data->>'phase' IS DISTINCT FROM 'detach'
        OR v_parent.authority_data->>'status' IS DISTINCT FROM 'detached'
        OR v_parent.authority_data->>'runtimeOperationId' IS DISTINCT FROM v_parent.runtime_operation_id::text
        OR v_parent.authority_data->>'activationOperationId' IS DISTINCT FROM v_parent.activation_operation_id::text
        OR v_parent.authority_data->>'requestHash' IS DISTINCT FROM v_parent.request_hash
        OR v_parent.event_payload IS DISTINCT FROM jsonb_build_object('runtimeOperationId',v_parent.runtime_operation_id::text,
              'phase','detach','receiptId',v_parent.receipt_id::text,'contentHash',v_parent.content_hash)
        OR v_parent.payload_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(v_parent.event_payload),'UTF8')),'hex')
      THEN RAISE EXCEPTION 'exact detached predecessor receipt required' USING ERRCODE='40001'; END IF;
      SELECT * INTO v_activation FROM public.extension_dispatch_cutover_operation
        WHERE org_id=v_org AND project_id=v_project AND cutover_operation_id=v_parent.activation_operation_id FOR UPDATE;
      IF NOT FOUND OR v_activation.kind<>'activate' OR v_activation.status<>'resumed'
        OR v_activation.cutover_group_id<>v_group OR v_activation.target_installation_id=v_install
      THEN RAISE EXCEPTION 'distinct retired predecessor activation required' USING ERRCODE='40001'; END IF;
      SELECT * INTO v_old_operation FROM public.extension_runtime_operation
        WHERE org_id=v_org AND project_id=v_project AND operation_id=v_parent.runtime_operation_id FOR UPDATE;
      IF NOT FOUND OR v_old_operation.installation_id<>v_activation.target_installation_id
        OR v_old_operation.kind<>'disable' OR v_old_operation.status<>'succeeded' OR v_old_operation.phase<>'succeeded'
      THEN RAISE EXCEPTION 'completed predecessor disable required' USING ERRCODE='40001'; END IF;
      SELECT * INTO v_old_binding FROM public.extension_runtime_binding
        WHERE org_id=v_org AND project_id=v_project AND installation_id=v_activation.target_installation_id
          AND generation=v_activation.target_generation FOR UPDATE;
      IF NOT FOUND OR v_old_binding.enabled OR NOT v_old_binding.operation_fence
        OR v_old_binding.desired_state<>'disabled' OR v_old_binding.observed_state<>'unknown'
      THEN RAISE EXCEPTION 'predecessor must remain disabled' USING ERRCODE='40001'; END IF;
      IF EXISTS(SELECT 1 FROM public.extension_dispatch_claim_gate
          WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group)
        OR EXISTS(SELECT 1 FROM public.extension_runtime_execution_attempt
          WHERE org_id=v_org AND project_id=v_project AND installation_id=v_activation.target_installation_id
            AND generation=v_activation.target_generation AND state='running')
        OR EXISTS(SELECT 1 FROM public.automation_occurrence o
          WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=v_activation.target_installation_id
            AND o.generation=v_activation.target_generation AND o.status='claimed')
        OR EXISTS(SELECT 1 FROM public.automation_occurrence_dispatch_attempt a
          JOIN public.automation_occurrence o USING(org_id,project_id,occurrence_id)
          WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=v_activation.target_installation_id
            AND o.generation=v_activation.target_generation AND a.status IN ('claimed','unknown'))
        OR EXISTS(SELECT 1 FROM public.extension_runtime_resource_lease l JOIN public.extension_runtime_operation o
            USING(org_id,project_id,operation_id)
          WHERE o.org_id=v_org AND o.project_id=v_project AND o.installation_id=v_activation.target_installation_id
            AND l.generation=v_activation.target_generation AND (l.cleanup_state<>'released' OR NOT l.observed_release))
      THEN RAISE EXCEPTION 'predecessor work or resources remain undrained' USING ERRCODE='55000'; END IF;
      PERFORM 1 FROM public.extension_operation_dispatch_binding WHERE org_id=v_org AND project_id=v_project
        AND cutover_group_id=v_group ORDER BY operation_id FOR UPDATE;
      SELECT jsonb_agg(jsonb_build_object('operationId',operation_id,'handlerKind',handler_kind,
        'installationId',installation_id::text,'generation',generation::text,'executionEpoch',execution_epoch,
        'operationFence',operation_fence,'revision',revision,'cutoverGroupId',cutover_group_id::text,
        'cutoverGroupRevision',cutover_group_revision) ORDER BY operation_id)
        INTO v_snapshot FROM public.extension_operation_dispatch_binding
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_group;
      IF jsonb_typeof(v_snapshot) IS DISTINCT FROM 'array'
        OR v_snapshot IS DISTINCT FROM v_parent.authority_data->'dispatchSnapshot'
        OR jsonb_array_length(v_snapshot)<>9
        OR EXISTS(SELECT 1 FROM public.extension_operation_dispatch_binding WHERE org_id=v_org AND project_id=v_project
          AND cutover_group_id=v_group AND (handler_kind<>'legacy' OR NOT operation_fence
            OR installation_id IS NOT NULL OR generation IS NOT NULL OR execution_epoch IS NOT NULL
            OR cutover_group_revision<>v_expected OR operation_id<>ALL(v_operations)))
      THEN RAISE EXCEPTION 'exact successor legacy snapshot required' USING ERRCODE='40001'; END IF;
      v_body:=jsonb_build_object('schemaVersion','aos.ecommerce.successor-dispatch-registration-receipt/v1',
        'tenant',jsonb_build_object('orgId',v_org,'projectId',v_project),'receiptId',v_receipt::text,
        'installationId',v_install::text,'generation',v_generation::text,'groupId',v_group::text,
        'requestHash',v_hash,'idempotencyKey',v_key,'actor',p_actor,'request',p_request,
        'dispatchSnapshot',v_snapshot,'executable',false,'createdAt',clock_timestamp());
      v_content_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(v_body),'UTF8')),'hex');
      INSERT INTO public.extension_dispatch_successor_registration_receipt(org_id,project_id,receipt_id,
        installation_id,generation,group_id,idempotency_key,request_hash,payload,content_hash)
        VALUES(v_org,v_project,v_receipt,v_install,v_generation,v_group,v_key,v_hash,v_body,v_content_hash);
      RETURN v_body||jsonb_build_object('contentHash',v_content_hash,'replayed',false);
    END $$;
    REVOKE ALL ON FUNCTION extension_dispatch_successor_register_a0v_056(jsonb,text) FROM PUBLIC,aos_runtime;
    GRANT EXECUTE ON FUNCTION extension_dispatch_successor_register_a0v_056(jsonb,text) TO aos_extension_maintainer;
""")


def downgrade():
    raise RuntimeError("successor registration history must be retained")
