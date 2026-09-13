"""Atomic withdrawal of unused first-registration occupancy, preserving history."""
from alembic import op

revision='a0v_030'
down_revision='a0v_029'
branch_labels=depends_on=None


def upgrade():
    op.execute(r'''CREATE FUNCTION extension_dispatch_withdraw_a0v_030(p_request jsonb,p_actor text)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE
      v_org text:=current_setting('aos.org_id',true); v_project text:=current_setting('aos.project_id',true);
      v_ref jsonb; v_origin record; v_install record; v_lock record; v_prior record;
      v_key text; v_request_hash text; v_snapshot jsonb; v_ids text[]; v_label text;
      v_receipt uuid:=gen_random_uuid(); v_body jsonb; v_hash text; v_deleted bigint;
      v_operations text[]:=ARRAY['ecommerce_growth_analysis_advance','ecommerce_growth_case_put',
        'ecommerce_growth_content_generate','ecommerce_growth_content_review','ecommerce_growth_data_fulfill',
        'ecommerce_growth_investigation_describe','ecommerce_growth_review_advance',
        'ecommerce_growth_schedule_put','ecommerce_growth_schedule_trigger'];
    BEGIN
      IF current_setting('role',true) IS DISTINCT FROM 'aos_extension_maintainer'
        OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
        OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
        OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
      THEN RAISE EXCEPTION 'dedicated withdrawal maintainer required' USING ERRCODE='42501'; END IF;
      IF v_org IS NULL OR v_org='' OR v_project IS NULL OR v_project=''
        OR p_actor IS NULL OR length(p_actor) NOT BETWEEN 1 AND 240 OR p_actor<>btrim(p_actor) OR p_actor ~ '[[:cntrl:]]'
        OR jsonb_typeof(p_request) IS DISTINCT FROM 'object'
        OR p_request->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.first-dispatch-withdrawal/v1'
        OR p_request-ARRAY['schemaVersion','registrationReceiptRef','expectedInstallationEtag','idempotencyKey']<>'{}'::jsonb
        OR jsonb_typeof(p_request->'idempotencyKey') IS DISTINCT FROM 'string'
        OR length(p_request->>'idempotencyKey') NOT BETWEEN 1 AND 160
        OR p_request->>'idempotencyKey'<>btrim(p_request->>'idempotencyKey')
        OR p_request->>'idempotencyKey' ~ '[[:cntrl:]]'
        OR jsonb_typeof(p_request->'expectedInstallationEtag') IS DISTINCT FROM 'number'
        OR coalesce((p_request->'expectedInstallationEtag')::text,'') !~ '^[1-9][0-9]*$'
      THEN RAISE EXCEPTION 'invalid withdrawal request' USING ERRCODE='22023'; END IF;
      IF (p_request->>'expectedInstallationEtag')::numeric>9223372036854775807
      THEN RAISE EXCEPTION 'invalid withdrawal revision' USING ERRCODE='22023'; END IF;
      v_ref:=p_request->'registrationReceiptRef'; v_key:=p_request->>'idempotencyKey';
      IF jsonb_typeof(v_ref) IS DISTINCT FROM 'object'
        OR v_ref-ARRAY['resourceType','resourceId','revision','contentHash']<>'{}'::jsonb
        OR v_ref->>'resourceType' IS DISTINCT FROM 'FirstDispatchRegistrationReceipt'
        OR v_ref->'revision' IS DISTINCT FROM '1'::jsonb
        OR (v_ref->'revision')::text IS DISTINCT FROM '1'
        OR jsonb_typeof(v_ref->'resourceId') IS DISTINCT FROM 'string'
        OR coalesce(v_ref->>'contentHash','') !~ '^sha256:[0-9a-f]{64}$'
      THEN RAISE EXCEPTION 'invalid withdrawal origin reference' USING ERRCODE='22023'; END IF;
      IF (v_ref->>'resourceId')::uuid::text IS DISTINCT FROM v_ref->>'resourceId'
      THEN RAISE EXCEPTION 'noncanonical withdrawal origin' USING ERRCODE='22023'; END IF;
      SELECT * INTO v_origin FROM public.extension_dispatch_registration_receipt
        WHERE org_id=v_org AND project_id=v_project AND receipt_id=(v_ref->>'resourceId')::uuid
          AND content_hash=v_ref->>'contentHash';
      IF NOT FOUND THEN RAISE EXCEPTION 'withdrawal origin unavailable' USING ERRCODE='42501'; END IF;
      PERFORM pg_advisory_xact_lock(hashtextextended(v_org||chr(31)||v_project||chr(31)||'ecommerce-first-registration',0));
      PERFORM pg_advisory_xact_lock(hashtextextended(v_org||chr(31)||v_project||chr(31)||v_origin.group_id::text,0));
      PERFORM pg_advisory_xact_lock(hashtextextended(v_org||chr(31)||v_project||chr(31)||v_origin.installation_id::text,0));
      PERFORM pg_advisory_xact_lock(hashtextextended(v_org||chr(31)||v_project||chr(31)||v_origin.installation_id::text||chr(31)||v_origin.generation::text,0));
      SELECT installation_pk,current_revision,etag_version INTO v_install FROM public.bundle_installation
        WHERE org_id=v_org AND project_id=v_project AND installation_id=v_origin.installation_id FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'withdrawal installation unavailable' USING ERRCODE='42501'; END IF;
      PERFORM 1 FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project AND subject=p_actor FOR SHARE;
      IF (SELECT count(*) FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project AND subject=p_actor)<>1
        OR NOT EXISTS(SELECT 1 FROM public.meta_membership WHERE org_id=v_org AND project_id=v_project
          AND subject=p_actor AND role IN ('admin','asset-installer'))
      THEN RAISE EXCEPTION 'current withdrawal actor denied' USING ERRCODE='42501'; END IF;
      SELECT l.permission_diff_json INTO v_lock FROM public.bundle_installation_revision r
        JOIN public.bundle_composition_lock l ON l.org_id=r.org_id AND l.project_id=r.project_id
          AND l.composition_pk=r.composition_pk AND l.revision=r.lock_revision
        WHERE r.org_id=v_org AND r.project_id=v_project AND r.installation_pk=v_install.installation_pk
          AND r.revision=v_install.current_revision;
      IF NOT FOUND OR jsonb_typeof(v_lock.permission_diff_json#>'{target,markings}') IS DISTINCT FROM 'array'
      THEN RAISE EXCEPTION 'withdrawal permission context unavailable' USING ERRCODE='42501'; END IF;
      FOR v_label IN SELECT jsonb_array_elements_text(v_lock.permission_diff_json#>'{target,markings}') LOOP
        PERFORM 1 FROM public.authz_tuple WHERE org_id=v_org AND project_id=v_project
          AND user_key='user:'||p_actor AND relation='bearer' AND object_key='marking:'||v_label FOR SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'withdrawal marking denied' USING ERRCODE='42501'; END IF;
      END LOOP;
      v_request_hash:='sha256:'||encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(p_request),'UTF8'),'sha256'),'hex');
      SELECT * INTO v_prior FROM public.extension_dispatch_withdrawal_receipt
        WHERE org_id=v_org AND project_id=v_project AND idempotency_key=v_key;
      IF FOUND THEN
        IF v_prior.request_hash IS DISTINCT FROM v_request_hash OR v_prior.payload->>'actor' IS DISTINCT FROM p_actor
          OR v_prior.payload->'request' IS DISTINCT FROM p_request
        THEN RAISE EXCEPTION 'withdrawal idempotency conflict' USING ERRCODE='40001'; END IF;
        RETURN v_prior.payload||jsonb_build_object('contentHash',v_prior.content_hash,'replayed',true);
      END IF;
      IF v_install.etag_version IS DISTINCT FROM (p_request->>'expectedInstallationEtag')::bigint
      THEN RAISE EXCEPTION 'withdrawal installation revision drifted' USING ERRCODE='40001'; END IF;
      IF EXISTS(SELECT 1 FROM public.extension_dispatch_withdrawal_receipt
        WHERE org_id=v_org AND project_id=v_project AND registration_receipt_id=v_origin.receipt_id)
      THEN RAISE EXCEPTION 'registration already withdrawn' USING ERRCODE='40001'; END IF;
      IF EXISTS(SELECT 1 FROM public.extension_dispatch_cutover_operation
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_origin.group_id)
      THEN RAISE EXCEPTION 'registration has entered cutover' USING ERRCODE='55000'; END IF;
      PERFORM 1 FROM public.extension_operation_dispatch_binding
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_origin.group_id ORDER BY operation_id FOR UPDATE;
      SELECT array_agg(operation_id ORDER BY operation_id),jsonb_agg(jsonb_build_object(
        'operationId',operation_id,'handlerKind',handler_kind,'installationId',installation_id,
        'generation',generation,'executionEpoch',execution_epoch,'operationFence',operation_fence,
        'revision',revision,'cutoverGroupId',cutover_group_id::text,'cutoverGroupRevision',cutover_group_revision) ORDER BY operation_id)
        INTO v_ids,v_snapshot FROM public.extension_operation_dispatch_binding
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_origin.group_id;
      IF v_ids IS DISTINCT FROM v_operations OR v_snapshot IS DISTINCT FROM v_origin.payload->'dispatchSnapshot'
        OR EXISTS(SELECT 1 FROM public.extension_operation_dispatch_binding
          WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_origin.group_id
          AND (handler_kind<>'legacy' OR operation_fence IS NOT TRUE OR revision<>1 OR cutover_group_revision<>1))
      THEN RAISE EXCEPTION 'withdrawal requires pristine registration' USING ERRCODE='40001'; END IF;
      IF EXISTS(SELECT 1 FROM public.automation_schedule_binding WHERE org_id=v_org AND project_id=v_project AND operation_id=ANY(v_operations))
        OR EXISTS(SELECT 1 FROM public.ecommerce_growth_runtime_command_receipt WHERE org_id=v_org AND project_id=v_project AND operation_id=ANY(v_operations))
      THEN RAISE EXCEPTION 'registration has dependent history' USING ERRCODE='55000'; END IF;
      v_body:=jsonb_build_object('schemaVersion','aos.ecommerce.first-dispatch-withdrawal-receipt/v1',
        'tenant',jsonb_build_object('orgId',v_org,'projectId',v_project),'receiptId',v_receipt::text,
        'registrationReceiptRef',v_ref,'installationId',v_origin.installation_id::text,
        'generation',v_origin.generation::text,'groupId',v_origin.group_id::text,
        'idempotencyKey',v_key,'requestHash',v_request_hash,'actor',p_actor,'request',p_request,
        'oldDispatchSnapshot',v_snapshot,'releasedOperationCount',9,'executable',false,'createdAt',clock_timestamp());
      v_hash:='sha256:'||encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(v_body),'UTF8'),'sha256'),'hex');
      INSERT INTO public.extension_dispatch_withdrawal_receipt
        (org_id,project_id,receipt_id,registration_receipt_id,idempotency_key,request_hash,payload,content_hash)
        VALUES(v_org,v_project,v_receipt,v_origin.receipt_id,v_key,v_request_hash,v_body,v_hash);
      DELETE FROM public.extension_operation_dispatch_binding
        WHERE org_id=v_org AND project_id=v_project AND cutover_group_id=v_origin.group_id;
      GET DIAGNOSTICS v_deleted = ROW_COUNT;
      IF v_deleted<>9 THEN RAISE EXCEPTION 'withdrawal occupancy changed' USING ERRCODE='40001'; END IF;
      RETURN v_body||jsonb_build_object('contentHash',v_hash,'replayed',false);
    END $$;
    REVOKE ALL ON FUNCTION extension_dispatch_withdraw_a0v_030(jsonb,text) FROM PUBLIC,aos_runtime;
    GRANT EXECUTE ON FUNCTION extension_dispatch_withdraw_a0v_030(jsonb,text) TO aos_extension_maintainer;
    ''')


def downgrade():
    raise RuntimeError('withdrawal history and authority must be retained')
