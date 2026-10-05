"""Neutral Evidence epoch for capacity review and future issuer commit ordering."""
from alembic import op

revision='a0v_149'
down_revision='a0v_148'
branch_labels=depends_on=None
OWNER='aos_capacity_evidence_epoch_owner'

LOCK_BODY="""
DECLARE result bigint; BEGIN
  IF p_org IS DISTINCT FROM 'org-org' OR p_project IS DISTINCT FROM 'dev-project'
    OR p_org IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
    OR p_project IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'')
    OR p_id IS NULL OR p_id='' OR p_id<>btrim(p_id) OR length(p_id)>200 THEN
    RAISE EXCEPTION 'CAPACITY_EVIDENCE_READER_SCOPE_REQUIRED' USING ERRCODE='42501';
  END IF;
  SELECT epoch INTO result FROM public.aip_capacity_evidence_epoch
    WHERE org_id=p_org AND project_id=p_project AND bundle_id=p_id FOR SHARE;
  IF NOT FOUND THEN
    INSERT INTO public.aip_capacity_evidence_epoch(org_id,project_id,bundle_id)
      VALUES(p_org,p_project,p_id) ON CONFLICT DO NOTHING;
    SELECT epoch INTO result FROM public.aip_capacity_evidence_epoch
      WHERE org_id=p_org AND project_id=p_project AND bundle_id=p_id FOR SHARE;
  END IF;
  IF NOT FOUND THEN RAISE EXCEPTION 'CAPACITY_EVIDENCE_EPOCH_MISSING' USING ERRCODE='42501'; END IF;
  RETURN result;
END;
"""

TOUCH_BODY="""
BEGIN
  IF NEW.org_id IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
    OR NEW.project_id IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'') THEN
    RAISE EXCEPTION 'CAPACITY_EVIDENCE_WRITER_SCOPE_REQUIRED' USING ERRCODE='42501';
  END IF;
  INSERT INTO public.aip_capacity_evidence_epoch(org_id,project_id,bundle_id)
    VALUES(NEW.org_id,NEW.project_id,NEW.bundle_id) ON CONFLICT DO NOTHING;
  PERFORM epoch FROM public.aip_capacity_evidence_epoch
    WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND bundle_id=NEW.bundle_id FOR UPDATE;
  RETURN NEW;
END;
"""

BUMP_BODY="""
BEGIN
  IF NEW.org_id IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
    OR NEW.project_id IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'') THEN
    RAISE EXCEPTION 'CAPACITY_EVIDENCE_WRITER_SCOPE_REQUIRED' USING ERRCODE='42501';
  END IF;
  UPDATE public.aip_capacity_evidence_epoch SET epoch=epoch+1
    WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND bundle_id=NEW.bundle_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'CAPACITY_EVIDENCE_EPOCH_MISSING' USING ERRCODE='42501'; END IF;
  RETURN NEW;
END;
"""


def upgrade():
    op.execute(f"""DO $$ DECLARE r record; BEGIN
      SELECT * INTO r FROM pg_roles WHERE rolname='{OWNER}';
      IF NOT FOUND THEN
        CREATE ROLE {OWNER} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
      ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls THEN
        RAISE EXCEPTION 'CAPACITY_EVIDENCE_OWNER_DRIFT' USING ERRCODE='42501';
      END IF;
      IF EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid='{OWNER}'::regrole OR member='{OWNER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_class WHERE relowner='{OWNER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner='{OWNER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspowner='{OWNER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_database WHERE datdba='{OWNER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE a.grantee='{OWNER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_attribute c,LATERAL aclexplode(c.attacl) a WHERE a.grantee='{OWNER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE a.grantee='{OWNER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE a.grantee='{OWNER}'::regrole) THEN
        RAISE EXCEPTION 'CAPACITY_EVIDENCE_OWNER_DRIFT' USING ERRCODE='42501';
      END IF;
    END $$""")
    op.execute(f'GRANT USAGE ON SCHEMA public TO {OWNER}')
    op.execute("""CREATE TABLE public.aip_capacity_evidence_epoch (
      org_id text NOT NULL,project_id text NOT NULL,bundle_id text NOT NULL,
      epoch bigint NOT NULL DEFAULT 0 CHECK(epoch>=0),PRIMARY KEY(org_id,project_id,bundle_id))""")
    op.execute(f'ALTER TABLE public.aip_capacity_evidence_epoch OWNER TO {OWNER}')
    op.execute('REVOKE ALL ON public.aip_capacity_evidence_epoch FROM PUBLIC,aos_runtime')
    op.execute('ALTER TABLE public.aip_capacity_evidence_epoch ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE public.aip_capacity_evidence_epoch FORCE ROW LEVEL SECURITY')
    op.execute(f"""CREATE POLICY capacity_evidence_epoch_scope ON public.aip_capacity_evidence_epoch TO {OWNER}
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    definitions=[('lock','p_org text,p_project text,p_id text','bigint',LOCK_BODY),
        ('touch','','trigger',TOUCH_BODY),('bump','','trigger',BUMP_BODY)]
    for name,args,result,body in definitions:
        signature=f"public.aos_capacity_evidence_epoch_{name}({'text,text,text' if name=='lock' else ''})"
        op.execute(f'CREATE FUNCTION public.aos_capacity_evidence_epoch_{name}({args}) RETURNS {result} '
            f'LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body${body}$body$')
        op.execute(f'ALTER FUNCTION {signature} OWNER TO {OWNER}')
        op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC,aos_runtime')
        if name=='lock':op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO aos_runtime')
        else:
            phase='BEFORE' if name=='touch' else 'AFTER'
            op.execute(f'CREATE TRIGGER capacity_evidence_epoch_{name}_a0v149 {phase} INSERT ON public.aip_evidence_bundle_revoke_event '
                f'FOR EACH ROW EXECUTE FUNCTION {signature}')


def downgrade():
    raise RuntimeError('Capacity Evidence commit coordination cannot be silently removed')
