"""Independent proposal withdrawal ordering, without granting capacity."""
from alembic import op

revision='a0v_151'
down_revision='a0v_150'
branch_labels=depends_on=None
OWNER='aos_capacity_withdrawal_epoch_owner'
LOCK_BODY="""
DECLARE result bigint; BEGIN
 IF p_org IS DISTINCT FROM 'org-org' OR p_project IS DISTINCT FROM 'dev-project'
 OR p_org IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
 OR p_project IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'')
 OR p_id IS NULL OR p_id='' OR p_id<>btrim(p_id) THEN
  RAISE EXCEPTION 'CAPACITY_WITHDRAWAL_SCOPE_REQUIRED' USING ERRCODE='42501';
 END IF;
 SELECT epoch INTO result FROM public.aip_capacity_withdrawal_epoch
 WHERE org_id=p_org AND project_id=p_project AND proposal_id=p_id FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'CAPACITY_WITHDRAWAL_EPOCH_MISSING' USING ERRCODE='42501'; END IF;
 IF result<>0 THEN RAISE EXCEPTION 'CAPACITY_APPROVAL_WITHDRAWN' USING ERRCODE='42501'; END IF;
 RETURN result;
END;
"""
INIT_BODY="""
BEGIN
 IF NEW.org_id<>'org-org' OR NEW.project_id<>'dev-project' THEN RETURN NEW; END IF;
 IF NEW.org_id IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
 OR NEW.project_id IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'') THEN
  RAISE EXCEPTION 'CAPACITY_WITHDRAWAL_WRITER_SCOPE_REQUIRED' USING ERRCODE='42501';
 END IF;
 INSERT INTO public.aip_capacity_withdrawal_epoch(org_id,project_id,proposal_id)
 VALUES(NEW.org_id,NEW.project_id,NEW.proposal_id) ON CONFLICT DO NOTHING;
 RETURN NEW;
END;
"""
BUMP_BODY="""
BEGIN
 IF NEW.org_id<>'org-org' OR NEW.project_id<>'dev-project' THEN RETURN NEW; END IF;
 IF NEW.org_id IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
 OR NEW.project_id IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'') THEN
  RAISE EXCEPTION 'CAPACITY_WITHDRAWAL_WRITER_SCOPE_REQUIRED' USING ERRCODE='42501';
 END IF;
 INSERT INTO public.aip_capacity_withdrawal_epoch(org_id,project_id,proposal_id,epoch)
 VALUES(NEW.org_id,NEW.project_id,NEW.proposal_id,1)
 ON CONFLICT(org_id,project_id,proposal_id) DO UPDATE
 SET epoch=public.aip_capacity_withdrawal_epoch.epoch+1;
 RETURN NEW;
END;
"""


def upgrade():
 op.execute(f"""DO $$ DECLARE r record; BEGIN
 SELECT * INTO r FROM pg_roles WHERE rolname='{OWNER}';
 IF NOT FOUND THEN CREATE ROLE {OWNER} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls THEN
 RAISE EXCEPTION 'CAPACITY_WITHDRAWAL_OWNER_DRIFT' USING ERRCODE='42501'; END IF;
 IF EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid='{OWNER}'::regrole OR member='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_class WHERE relowner='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspowner='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_database WHERE datdba='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE a.grantee='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_attribute c,LATERAL aclexplode(c.attacl) a WHERE a.grantee='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE a.grantee='{OWNER}'::regrole)
 OR EXISTS(SELECT 1 FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE a.grantee='{OWNER}'::regrole) THEN
 RAISE EXCEPTION 'CAPACITY_WITHDRAWAL_OWNER_DRIFT' USING ERRCODE='42501'; END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='public.aip_action_withdrawal_event'::regclass
 AND tgisinternal AND tgtype=5 AND tgname LIKE 'RI_ConstraintTrigger_%')
 OR EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='public.aip_action_withdrawal_event'::regclass
 AND tgisinternal AND (tgtype & 4)=4 AND (tgdeferrable OR tginitdeferred OR tgtype<>5
 OR tgname>='zz_capacity_withdrawal_epoch_bump_a0v151')) THEN
 RAISE EXCEPTION 'CAPACITY_WITHDRAWAL_FOREIGN_KEY_ORDER_REQUIRED' USING ERRCODE='42501'; END IF;
 END $$""")
 op.execute("""CREATE TABLE public.aip_capacity_withdrawal_epoch(
 org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
 proposal_id text NOT NULL CHECK(proposal_id<>'' AND proposal_id=btrim(proposal_id)),
 epoch bigint NOT NULL DEFAULT 0 CHECK(epoch>=0),PRIMARY KEY(org_id,project_id,proposal_id))""")
 # Backfill before FORCE RLS/ownership handoff, preserving original history.
 op.execute("""INSERT INTO public.aip_capacity_withdrawal_epoch(org_id,project_id,proposal_id,epoch)
 SELECT p.org_id,p.project_id,p.proposal_id,(SELECT count(*) FROM public.aip_action_withdrawal_event w
 WHERE (w.org_id,w.project_id,w.proposal_id)=(p.org_id,p.project_id,p.proposal_id))
 FROM public.aip_action_proposal p WHERE p.org_id='org-org' AND p.project_id='dev-project'""")
 op.execute(f'GRANT USAGE ON SCHEMA public TO {OWNER}')
 op.execute(f'ALTER TABLE public.aip_capacity_withdrawal_epoch OWNER TO {OWNER}')
 op.execute('REVOKE ALL ON public.aip_capacity_withdrawal_epoch FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer')
 op.execute('ALTER TABLE public.aip_capacity_withdrawal_epoch ENABLE ROW LEVEL SECURITY')
 op.execute('ALTER TABLE public.aip_capacity_withdrawal_epoch FORCE ROW LEVEL SECURITY')
 op.execute(f"""CREATE POLICY capacity_withdrawal_epoch_scope ON public.aip_capacity_withdrawal_epoch TO {OWNER}
 USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
 WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
 for name,args,returns,body in [('lock','p_org text,p_project text,p_id text','bigint',LOCK_BODY),('init','','trigger',INIT_BODY),('bump','','trigger',BUMP_BODY)]:
  signature=f"public.aos_capacity_withdrawal_epoch_{name}({'text,text,text' if name=='lock' else ''})"
  op.execute(f'CREATE FUNCTION public.aos_capacity_withdrawal_epoch_{name}({args}) RETURNS {returns} LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body${body}$body$')
  op.execute(f'ALTER FUNCTION {signature} OWNER TO {OWNER}')
  op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer')
  if name=='lock':op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO aos_runtime,aos_provider_capacity_issuer')
 op.execute('CREATE TRIGGER zz_capacity_withdrawal_epoch_init_a0v151 AFTER INSERT ON public.aip_action_proposal FOR EACH ROW EXECUTE FUNCTION public.aos_capacity_withdrawal_epoch_init()')
 op.execute('CREATE TRIGGER zz_capacity_withdrawal_epoch_bump_a0v151 AFTER INSERT ON public.aip_action_withdrawal_event FOR EACH ROW EXECUTE FUNCTION public.aos_capacity_withdrawal_epoch_bump()')


def downgrade():
 raise RuntimeError('Withdrawal ordering requires explicit reconciliation; cannot silently remove')
