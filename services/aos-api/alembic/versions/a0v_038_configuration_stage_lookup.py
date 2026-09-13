"""Recover a lost receipt by original subject and key, without resubmitting."""
from alembic import op

revision='a0v_038'
down_revision='a0v_037'
branch_labels=depends_on=None


def upgrade():
    op.execute(r'''
    CREATE FUNCTION public.extension_configuration_stage_lookup_a0v_038(p_subject text,p_key text)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),''); v_request uuid;
    BEGIN
      PERFORM public.extension_configuration_stage_principal_a0v_037(p_subject,NULL);
      IF p_key IS NULL OR length(p_key) NOT BETWEEN 1 AND 160 OR p_key<>btrim(p_key) OR p_key ~ '[[:cntrl:]]' THEN
        RAISE EXCEPTION 'exact configuration request key required' USING ERRCODE='23514'; END IF;
      SELECT request_id INTO v_request FROM public.extension_runtime_configuration_stage_request
        WHERE org_id=v_org AND project_id=v_project AND subject=p_subject AND idempotency_key=p_key;
      IF NOT FOUND THEN RETURN NULL; END IF;
      RETURN public.extension_configuration_stage_query_a0v_037(p_subject,v_request);
    END $$;
    REVOKE ALL ON FUNCTION public.extension_configuration_stage_lookup_a0v_038(text,text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.extension_configuration_stage_lookup_a0v_038(text,text) TO aos_configuration_stage_api;
    ''')


def downgrade():
    raise RuntimeError('configuration receipt recovery must be retained')
