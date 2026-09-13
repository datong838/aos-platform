"""Runtime-owned UI read locks and bounded delivery column updates."""
from alembic import op

revision='a0v_033'
down_revision='a0v_032'
branch_labels=depends_on=None


def upgrade():
    op.execute(r'''
    CREATE FUNCTION public.extension_ui_read_host_principal_a0v_033(p_subject text,p_markings text[])
    RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=nullif(current_setting('aos.org_id',true),'');
      v_project text:=nullif(current_setting('aos.project_id',true),'');
      v_role text; v_row record; v_count integer:=0; v_label text;
    BEGIN
      IF v_org IS NULL OR v_project IS NULL OR p_subject IS NULL
         OR length(p_subject) NOT BETWEEN 1 AND 240 OR p_subject<>btrim(p_subject)
         OR p_subject ~ '[[:cntrl:]]' OR p_subject IS DISTINCT FROM current_setting('aos.subject',true)
         OR current_setting('role') IS DISTINCT FROM 'aos_runtime'
         OR current_setting('transaction_isolation') NOT IN ('repeatable read','serializable')
         OR NOT pg_has_role(session_user,'aos_runtime','MEMBER')
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

    REVOKE ALL ON FUNCTION public.extension_ui_read_host_principal_a0v_033(text,text[]) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.extension_ui_read_host_principal_a0v_033(text,text[]) TO aos_runtime;
    GRANT UPDATE(state,revision,claimed_at,completed_at,owner_token_hash,attempt_id,snapshot_hash,
        attempt_request_hash,result_json,result_hash,failure_code)
        ON public.extension_runtime_ui_read_request TO aos_runtime;
    ''')


def downgrade():
    raise RuntimeError('Runtime UI delivery boundary must be retained')
