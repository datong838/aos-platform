"""Restricted UI delivery role and fixed entry points; no execution privileges."""
from alembic import op

revision = 'a0v_032'
down_revision = 'a0v_031'
branch_labels = depends_on = None


def upgrade():
    op.execute(r'''
    DO $$ BEGIN
      IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_ui_read_api') THEN
        CREATE ROLE aos_ui_read_api NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
      END IF;
      IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_ui_read_api'
        AND (rolcanlogin OR rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication)) THEN
        RAISE EXCEPTION 'UI delivery role properties differ';
      END IF;
      IF EXISTS(SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='aos_ui_read_api')) THEN
        RAISE EXCEPTION 'UI delivery role must not inherit other roles';
      END IF;
    END $$;

    CREATE FUNCTION public.extension_ui_read_principal_a0v_032(p_subject text,p_markings text[])
    RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_role text; v_row record; v_count integer:=0; v_label text;
    BEGIN
      IF v_org IS NULL OR v_project IS NULL OR p_subject IS NULL
         OR length(p_subject) NOT BETWEEN 1 AND 240 OR p_subject<>btrim(p_subject)
         OR p_subject ~ '[[:cntrl:]]' OR p_subject IS DISTINCT FROM current_setting('aos.subject',true)
         OR current_setting('role') IS DISTINCT FROM 'aos_ui_read_api'
         OR current_setting('transaction_isolation') IS DISTINCT FROM 'read committed'
         OR NOT pg_has_role(session_user,'aos_ui_read_api','MEMBER')
         OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
         OR p_markings IS NULL OR cardinality(p_markings)>500
         OR EXISTS(SELECT 1 FROM unnest(p_markings) x WHERE x IS NULL OR x='' OR x<>btrim(x) OR x ~ '[[:cntrl:]]')
         OR cardinality(p_markings)<>(SELECT count(DISTINCT x) FROM unnest(p_markings) x)
      THEN RAISE EXCEPTION 'scoped UI principal required' USING ERRCODE='42501'; END IF;
      FOR v_row IN SELECT m.role FROM public.meta_membership m
        WHERE m.org_id=v_org AND m.project_id=v_project AND m.subject=p_subject FOR SHARE LOOP
        v_role:=v_row.role; v_count:=v_count+1;
      END LOOP;
      IF v_count<>1 OR v_role IS NULL OR v_role='' OR v_role<>btrim(v_role) OR v_role ~ '[[:cntrl:]]'
      THEN RAISE EXCEPTION 'current UI membership unavailable' USING ERRCODE='42501'; END IF;
      FOREACH v_label IN ARRAY p_markings LOOP
        v_count:=0;
        FOR v_row IN SELECT a.object_key FROM public.authz_tuple a
          WHERE a.org_id=v_org AND a.project_id=v_project AND a.user_key='user:'||p_subject
            AND a.relation='bearer' AND a.object_key='marking:'||v_label FOR SHARE LOOP
          v_count:=v_count+1;
        END LOOP;
        IF v_count<>1 THEN RAISE EXCEPTION 'current UI marking unavailable' USING ERRCODE='42501'; END IF;
      END LOOP;
      RETURN v_role;
    END $$;

    CREATE FUNCTION public.extension_ui_read_enqueue_a0v_032(p_subject text,p_key text,p_request jsonb)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_digest text; v_lock text; v_row public.extension_runtime_ui_read_request%ROWTYPE;
      v_tenant_count bigint; v_subject_count bigint;
    BEGIN
      PERFORM public.extension_ui_read_principal_a0v_032(p_subject,ARRAY[]::text[]);
      IF p_key IS NULL OR length(p_key) NOT BETWEEN 1 AND 240 OR p_key<>btrim(p_key) OR p_key ~ '[[:cntrl:]]'
         OR p_request IS NULL OR jsonb_typeof(p_request) IS DISTINCT FROM 'object'
         OR p_request-ARRAY['schemaVersion','operationId','moduleId','target','caseLimit','runLimit']<>'{}'::jsonb
         OR NOT(p_request ?& ARRAY['schemaVersion','operationId','moduleId','target','caseLimit','runLimit'])
         OR p_request->>'schemaVersion' IS DISTINCT FROM 'aos.runtime-ui-read-request/v1'
         OR p_request->>'operationId' IS DISTINCT FROM 'analyst_workspace_view_v1'
         OR p_request->>'moduleId' IS DISTINCT FROM 'ecommerce.analyst'
         OR jsonb_typeof(p_request->'caseLimit') IS DISTINCT FROM 'number'
         OR jsonb_typeof(p_request->'runLimit') IS DISTINCT FROM 'number'
         OR p_request->>'caseLimit' !~ '^[1-9][0-9]*$'
         OR p_request->>'runLimit' !~ '^[1-9][0-9]*$'
      THEN RAISE EXCEPTION 'fixed UI read request required' USING ERRCODE='23514'; END IF;
      v_lock:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(
        jsonb_build_object('kind','runtime-ui-read-admission','scope',jsonb_build_array(v_org,v_project))),'UTF8')),'hex');
      PERFORM pg_advisory_xact_lock(hashtextextended(v_lock,0));
      v_digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(
        jsonb_build_object('tenant',jsonb_build_object('orgId',v_org,'projectId',v_project),
          'subject',p_subject,'request',p_request)),'UTF8')),'hex');
      SELECT * INTO v_row FROM public.extension_runtime_ui_read_request q
        WHERE q.org_id=v_org AND q.project_id=v_project AND q.subject=p_subject AND q.idempotency_key=p_key;
      IF FOUND THEN
        IF v_row.request_hash<>v_digest THEN RAISE EXCEPTION 'UI read idempotency conflict' USING ERRCODE='23514'; END IF;
      ELSE
        SELECT count(*),count(*) FILTER(WHERE subject=p_subject) INTO v_tenant_count,v_subject_count
          FROM public.extension_runtime_ui_read_request WHERE org_id=v_org AND project_id=v_project
          AND state IN ('requested','claimed') AND deadline>clock_timestamp();
        IF v_tenant_count>=64 OR v_subject_count>=8 THEN RAISE EXCEPTION 'UI read capacity reached' USING ERRCODE='23514'; END IF;
        INSERT INTO public.extension_runtime_ui_read_request
          (org_id,project_id,request_id,subject,idempotency_key,request_hash,installation_id,generation,
           execution_epoch,operation_id,module_id,target_json,case_limit,run_limit,state,deadline)
          VALUES(v_org,v_project,gen_random_uuid(),p_subject,p_key,v_digest,
            (p_request->'target'->>'installationId')::uuid,(p_request->'target'->>'generation')::uuid,
            (p_request->'target'->>'executionEpoch')::bigint,p_request->>'operationId',p_request->>'moduleId',
            p_request->'target',(p_request->>'caseLimit')::integer,(p_request->>'runLimit')::integer,
            'requested',clock_timestamp()+interval '60 seconds') RETURNING * INTO v_row;
      END IF;
      RETURN jsonb_build_object('requestId',v_row.request_id,'requestHash',v_row.request_hash,
        'state',v_row.state,'revision',v_row.revision,'deadline',v_row.deadline);
    END $$;
    REVOKE ALL ON FUNCTION public.extension_ui_read_principal_a0v_032(text,text[]) FROM PUBLIC;
    REVOKE ALL ON FUNCTION public.extension_ui_read_enqueue_a0v_032(text,text,jsonb) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.extension_ui_read_principal_a0v_032(text,text[]) TO aos_ui_read_api;
    GRANT EXECUTE ON FUNCTION public.extension_ui_read_enqueue_a0v_032(text,text,jsonb) TO aos_ui_read_api;
    ''')


def downgrade():
    raise RuntimeError('UI delivery authorization boundary must be retained')
