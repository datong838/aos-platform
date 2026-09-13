"""Fixed configuration receipt admission and original-subject query functions."""
from alembic import op

revision='a0v_037'
down_revision='a0v_036'
branch_labels=depends_on=None


def upgrade():
    op.execute(r'''
    DO $$ BEGIN
      IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_configuration_stage_api') THEN
        CREATE ROLE aos_configuration_stage_api NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
      END IF;
      IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_configuration_stage_api'
          AND (rolcanlogin OR rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication))
         OR EXISTS(SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='aos_configuration_stage_api'))
      THEN RAISE EXCEPTION 'configuration API role differs'; END IF;
    END $$;

    CREATE FUNCTION public.extension_configuration_stage_principal_a0v_037(p_subject text,p_installation uuid)
    RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_role text; v_count integer:=0; v_member record; v_lock record; v_label jsonb;
    BEGIN
      IF v_org IS NULL OR v_project IS NULL OR p_subject IS NULL
         OR length(p_subject) NOT BETWEEN 1 AND 240 OR p_subject<>btrim(p_subject)
         OR p_subject ~ '[[:cntrl:]]' OR p_subject IS DISTINCT FROM current_setting('aos.subject',true)
         OR current_setting('role') IS DISTINCT FROM 'aos_configuration_stage_api'
         OR current_setting('transaction_isolation') IS DISTINCT FROM 'read committed'
         OR NOT pg_has_role(session_user,'aos_configuration_stage_api','MEMBER')
         OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
      THEN RAISE EXCEPTION 'scoped configuration API principal required' USING ERRCODE='42501'; END IF;
      FOR v_member IN SELECT role FROM public.meta_membership
        WHERE org_id=v_org AND project_id=v_project AND subject=p_subject FOR SHARE LOOP
        v_count:=v_count+1; v_role:=v_member.role;
      END LOOP;
      IF v_count<>1 OR v_role IS NULL OR v_role NOT IN ('admin','asset-installer') THEN
        RAISE EXCEPTION 'current configuration API member denied' USING ERRCODE='42501'; END IF;
      IF p_installation IS NULL THEN RETURN; END IF;
      SELECT l.lock_payload,l.lock_hash,l.permission_diff_json,l.permission_diff_hash,
        r.lock_hash AS installed_lock_hash,r.permission_diff_hash AS installed_permission_hash
        INTO STRICT v_lock FROM public.bundle_installation i
        JOIN public.bundle_installation_revision r ON r.org_id=i.org_id AND r.project_id=i.project_id
          AND r.installation_pk=i.installation_pk AND r.revision=i.current_revision
        JOIN public.bundle_composition_lock l ON l.org_id=r.org_id AND l.project_id=r.project_id
          AND l.composition_pk=r.composition_pk AND l.revision=r.lock_revision
        WHERE i.org_id=v_org AND i.project_id=v_project AND i.installation_id=p_installation FOR SHARE OF i,r,l;
      IF v_lock.lock_hash IS DISTINCT FROM v_lock.installed_lock_hash
         OR v_lock.permission_diff_hash IS DISTINCT FROM v_lock.installed_permission_hash
         OR v_lock.permission_diff_json IS DISTINCT FROM v_lock.lock_payload->'permissionDiff'
         OR v_lock.lock_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(v_lock.lock_payload),'UTF8')),'hex')
         OR v_lock.permission_diff_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(v_lock.permission_diff_json),'UTF8')),'hex')
         OR jsonb_typeof(v_lock.permission_diff_json#>'{target,markings}') IS DISTINCT FROM 'array'
      THEN RAISE EXCEPTION 'current configuration permission lock differs' USING ERRCODE='42501'; END IF;
      IF jsonb_array_length(v_lock.permission_diff_json#>'{target,markings}')>500 THEN
        RAISE EXCEPTION 'configuration marking bound exceeded' USING ERRCODE='42501'; END IF;
      FOR v_label IN SELECT value FROM jsonb_array_elements(v_lock.permission_diff_json#>'{target,markings}') LOOP
        IF jsonb_typeof(v_label) IS DISTINCT FROM 'string' OR v_label#>>'{}'='' OR v_label#>>'{}'<>btrim(v_label#>>'{}')
           OR v_label#>>'{}' ~ '[[:cntrl:]]' THEN
          RAISE EXCEPTION 'configuration marking invalid' USING ERRCODE='42501'; END IF;
        v_count:=0;
        FOR v_member IN SELECT object_key FROM public.authz_tuple WHERE org_id=v_org AND project_id=v_project
          AND user_key='user:'||p_subject AND relation='bearer' AND object_key='marking:'||(v_label#>>'{}') FOR SHARE LOOP
          v_count:=v_count+1;
        END LOOP;
        IF v_count<>1 THEN RAISE EXCEPTION 'current configuration marking denied' USING ERRCODE='42501'; END IF;
      END LOOP;
    END $$;

    CREATE FUNCTION public.extension_configuration_stage_enqueue_a0v_037(p_subject text,p_key text,p_request jsonb)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_digest text; v_tenant bigint; v_subject bigint;
      v_row public.extension_runtime_configuration_stage_request%ROWTYPE;
    BEGIN
      PERFORM public.extension_configuration_stage_principal_a0v_037(p_subject,NULL);
      IF p_key IS NULL OR length(p_key) NOT BETWEEN 1 AND 160 OR p_key<>btrim(p_key) OR p_key ~ '[[:cntrl:]]'
         OR p_request IS NULL OR jsonb_typeof(p_request) IS DISTINCT FROM 'object' OR octet_length(p_request::text)>65536
      THEN RAISE EXCEPTION 'configuration request required' USING ERRCODE='23514'; END IF;
      PERFORM public.extension_configuration_stage_principal_a0v_037(p_subject,(p_request->'target'->>'installationId')::uuid);
      PERFORM pg_advisory_xact_lock(hashtextextended(public.canonical_asset_registry_jsonb(
        jsonb_build_object('kind','configuration-stage-admission','scope',jsonb_build_array(v_org,v_project))),0));
      v_digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(
        jsonb_build_object('tenant',jsonb_build_object('orgId',v_org,'projectId',v_project),
          'subject',p_subject,'request',p_request)),'UTF8')),'hex');
      SELECT * INTO v_row FROM public.extension_runtime_configuration_stage_request
        WHERE org_id=v_org AND project_id=v_project AND subject=p_subject AND idempotency_key=p_key;
      IF FOUND THEN
        IF v_row.request_hash IS DISTINCT FROM v_digest THEN RAISE EXCEPTION 'configuration idempotency conflict' USING ERRCODE='23514'; END IF;
      ELSE
        SELECT count(*),count(*) FILTER(WHERE subject=p_subject) INTO v_tenant,v_subject
          FROM public.extension_runtime_configuration_stage_request WHERE org_id=v_org AND project_id=v_project
          AND state='requested' AND deadline>clock_timestamp();
        IF v_tenant>=64 OR v_subject>=8 THEN RAISE EXCEPTION 'configuration pending capacity exceeded' USING ERRCODE='23514'; END IF;
        INSERT INTO public.extension_runtime_configuration_stage_request
          (org_id,project_id,request_id,subject,idempotency_key,installation_id,generation,
           installation_etag,binding_revision,request_json,request_hash,deadline)
          VALUES(v_org,v_project,gen_random_uuid(),p_subject,p_key,(p_request->'target'->>'installationId')::uuid,
            (p_request->'target'->>'generation')::uuid,(p_request->'target'->>'installationEtag')::bigint,
            (p_request->'target'->>'bindingRevision')::bigint,p_request,v_digest,clock_timestamp()+interval '3 minutes')
          RETURNING * INTO v_row;
      END IF;
      RETURN jsonb_build_object('requestId',v_row.request_id,'requestHash',v_row.request_hash,
        'state',v_row.state,'revision',v_row.revision,'deadline',v_row.deadline);
    END $$;

    CREATE FUNCTION public.extension_configuration_stage_query_a0v_037(p_subject text,p_request uuid)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_row public.extension_runtime_configuration_stage_request%ROWTYPE;
    BEGIN
      PERFORM public.extension_configuration_stage_principal_a0v_037(p_subject,NULL);
      SELECT * INTO v_row FROM public.extension_runtime_configuration_stage_request
        WHERE org_id=v_org AND project_id=v_project AND subject=p_subject AND request_id=p_request;
      IF NOT FOUND THEN RETURN NULL; END IF;
      PERFORM public.extension_configuration_stage_principal_a0v_037(p_subject,v_row.installation_id);
      RETURN jsonb_build_object('requestId',v_row.request_id,'requestHash',v_row.request_hash,
        'state',v_row.state,'revision',v_row.revision,'deadline',v_row.deadline,
        'result',v_row.result_json,'failureCode',v_row.failure_code);
    END $$;
    REVOKE ALL ON public.extension_runtime_configuration_stage_request,public.extension_runtime_configuration FROM aos_configuration_stage_api;
    REVOKE ALL ON FUNCTION public.extension_configuration_stage_principal_a0v_037(text,uuid) FROM PUBLIC;
    REVOKE ALL ON FUNCTION public.extension_configuration_stage_enqueue_a0v_037(text,text,jsonb) FROM PUBLIC;
    REVOKE ALL ON FUNCTION public.extension_configuration_stage_query_a0v_037(text,uuid) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.extension_configuration_stage_principal_a0v_037(text,uuid) TO aos_configuration_stage_api;
    GRANT EXECUTE ON FUNCTION public.extension_configuration_stage_enqueue_a0v_037(text,text,jsonb) TO aos_configuration_stage_api;
    GRANT EXECUTE ON FUNCTION public.extension_configuration_stage_query_a0v_037(text,uuid) TO aos_configuration_stage_api;
    ''')


def downgrade():
    raise RuntimeError('configuration API authority history must be retained')
