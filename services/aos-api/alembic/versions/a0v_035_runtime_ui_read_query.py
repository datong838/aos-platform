"""Original-subject UI delivery queries without direct table access."""
from alembic import op

revision = 'a0v_035'
down_revision = 'a0v_034'
branch_labels = depends_on = None


def upgrade():
    op.execute(r'''
    CREATE FUNCTION public.extension_ui_read_metadata_a0v_035(p_subject text,p_id uuid)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE q public.extension_runtime_ui_read_request%ROWTYPE;
    BEGIN
      PERFORM public.extension_ui_read_principal_a0v_032(p_subject,ARRAY[]::text[]);
      SELECT * INTO q FROM public.extension_runtime_ui_read_request r
        WHERE r.org_id=current_setting('aos.org_id') AND r.project_id=current_setting('aos.project_id')
          AND r.subject=p_subject AND r.request_id=p_id;
      IF NOT FOUND THEN RETURN NULL; END IF;
      RETURN jsonb_build_object('requestId',q.request_id,'requestHash',q.request_hash,
        'request',jsonb_build_object('schemaVersion','aos.runtime-ui-read-request/v1',
          'operationId',q.operation_id,'moduleId',q.module_id,'target',q.target_json,
          'caseLimit',q.case_limit,'runLimit',q.run_limit));
    END $$;

    CREATE FUNCTION public.extension_ui_read_result_a0v_035(p_subject text,p_id uuid,p_hash text)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE q public.extension_runtime_ui_read_request%ROWTYPE; b record;
    BEGIN
      PERFORM public.extension_ui_read_principal_a0v_032(p_subject,ARRAY[]::text[]);
      SELECT * INTO q FROM public.extension_runtime_ui_read_request r
        WHERE r.org_id=current_setting('aos.org_id') AND r.project_id=current_setting('aos.project_id')
          AND r.subject=p_subject AND r.request_id=p_id AND r.request_hash=p_hash FOR SHARE;
      IF NOT FOUND THEN RETURN NULL; END IF;
      SELECT * INTO b FROM public.extension_runtime_binding r
        WHERE r.org_id=q.org_id AND r.project_id=q.project_id
          AND r.installation_id=q.installation_id AND r.generation=q.generation FOR SHARE;
      IF NOT FOUND OR b.enabled IS DISTINCT FROM true OR b.operation_fence IS DISTINCT FROM false
        OR b.desired_state IS DISTINCT FROM 'enabled' OR b.observed_state IS DISTINCT FROM 'ready'
        OR b.execution_epoch IS DISTINCT FROM q.execution_epoch
        OR b.installation_revision IS DISTINCT FROM (q.target_json->>'installationRevision')::bigint
        OR b.revision IS DISTINCT FROM (q.target_json->>'bindingRevision')::bigint
      THEN RAISE EXCEPTION 'current UI delivery target unavailable' USING ERRCODE='42501'; END IF;
      RETURN jsonb_build_object('requestId',q.request_id,'requestHash',q.request_hash,
        'state',q.state,'revision',q.revision,'deadline',q.deadline,'completedAt',q.completed_at,
        'result',CASE WHEN q.state='succeeded' THEN q.result_json ELSE NULL END,
        'resultHash',CASE WHEN q.state='succeeded' THEN q.result_hash ELSE NULL END,
        'failureCode',q.failure_code);
    END $$;
    REVOKE ALL ON FUNCTION public.extension_ui_read_metadata_a0v_035(text,uuid) FROM PUBLIC;
    REVOKE ALL ON FUNCTION public.extension_ui_read_result_a0v_035(text,uuid,text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.extension_ui_read_metadata_a0v_035(text,uuid) TO aos_ui_read_api;
    GRANT EXECUTE ON FUNCTION public.extension_ui_read_result_a0v_035(text,uuid,text) TO aos_ui_read_api;
    ''')


def downgrade():
    raise RuntimeError('UI delivery query authorization boundary must be retained')
