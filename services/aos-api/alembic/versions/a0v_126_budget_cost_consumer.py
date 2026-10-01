"""Independent atomic consumer for cost-approved initial BudgetRevision."""
from pathlib import Path
from alembic import op

revision='a0v_126'
down_revision='a0v_125'
branch_labels=depends_on=None


def upgrade():
    op.execute("""DO $$ DECLARE r text; BEGIN
      FOREACH r IN ARRAY ARRAY['aos_budget_consumer_call','aos_budget_consumer_owner'] LOOP
        IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r) THEN
          EXECUTE format('CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',r);
        END IF;
        IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r AND (rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
          OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=r::regrole OR member=r::regrole)
          OR EXISTS(SELECT 1 FROM pg_class WHERE relowner=r::regrole)
          OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner=r::regrole)
          OR EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE a.grantee=r::regrole) THEN
          RAISE EXCEPTION 'BUDGET_CONSUMER_ROLE_DRIFT';
        END IF;
      END LOOP;
      IF EXISTS(SELECT 1 FROM public.aip_budget_receipt WHERE operation='budget_revision.activate_cost') THEN
        RAISE EXCEPTION 'BUDGET_CONSUMER_HISTORY_RECONCILIATION_REQUIRED';
      END IF;
    END $$""")
    op.execute('GRANT USAGE ON SCHEMA public TO aos_budget_consumer_call,aos_budget_consumer_owner')
    op.execute("""CREATE TABLE public.aip_budget_cost_runtime_fence(
      org_id text NOT NULL,project_id text NOT NULL,budget_id text NOT NULL,revision bigint NOT NULL,
      decision_id text NOT NULL,version bigint NOT NULL DEFAULT 1 CHECK(version>=1),
      PRIMARY KEY(org_id,project_id,budget_id,revision),UNIQUE(org_id,project_id,decision_id),
      FOREIGN KEY(org_id,project_id,decision_id) REFERENCES public.aip_budget_cost_decision(org_id,project_id,decision_id))""")
    op.execute('ALTER TABLE public.aip_budget_cost_runtime_fence ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE public.aip_budget_cost_runtime_fence FORCE ROW LEVEL SECURITY')
    op.execute("""CREATE POLICY budget_cost_runtime_scope ON public.aip_budget_cost_runtime_fence TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    # Platform default privileges also apply to new tables; explicitly remove them.
    op.execute('REVOKE ALL ON public.aip_budget_cost_runtime_fence FROM PUBLIC,aos_runtime')
    op.execute('GRANT SELECT,UPDATE(version) ON public.aip_budget_cost_runtime_fence TO aos_runtime')
    tables=('aip_budget_cost_proposal','aip_budget_cost_decision','aip_budget_cost_revocation','meta_membership',
        'aip_budget_head','aip_budget_revision','aip_budget_receipt','aip_provider_instance_head','aip_provider_instance_revision',
        'aip_capability_invocation','aip_budget_reservation','aip_budget_bucket','aip_budget_cost_runtime_fence')
    for table in tables:
        op.execute(f'GRANT SELECT ON public.{table} TO aos_budget_consumer_owner')
        op.execute(f"""CREATE POLICY budget_consumer_a0v126 ON public.{table} TO aos_budget_consumer_owner
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute('GRANT UPDATE(subject) ON public.meta_membership TO aos_budget_consumer_owner')
    op.execute('GRANT UPDATE(provider_instance_id) ON public.aip_provider_instance_head TO aos_budget_consumer_owner')
    op.execute('GRANT UPDATE(current_revision,version,updated_at) ON public.aip_budget_head TO aos_budget_consumer_owner')
    op.execute('GRANT INSERT ON public.aip_budget_revision,public.aip_budget_receipt TO aos_budget_consumer_owner')
    op.execute('GRANT INSERT ON public.aip_budget_cost_runtime_fence TO aos_budget_consumer_owner')
    op.execute("""CREATE FUNCTION public.aip_budget_cost_fence_guard_a0v_126() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
      IF TG_OP='INSERT' THEN
        IF session_user<>'aos_budget_consumer_call' OR current_user<>'aos_budget_consumer_owner' OR NEW.version<>1 THEN
          RAISE EXCEPTION 'BUDGET_COST_FENCE_CONSUMER_REQUIRED' USING ERRCODE='42501'; END IF;
      ELSIF TG_OP='UPDATE' THEN
        IF (NEW.org_id,NEW.project_id,NEW.budget_id,NEW.revision,NEW.decision_id) IS DISTINCT FROM
           (OLD.org_id,OLD.project_id,OLD.budget_id,OLD.revision,OLD.decision_id) OR NEW.version<>OLD.version+1 THEN
          RAISE EXCEPTION 'BUDGET_COST_FENCE_DRIFT' USING ERRCODE='23514'; END IF;
      ELSE RAISE EXCEPTION 'BUDGET_COST_FENCE_HISTORY_REQUIRED'; END IF;
      RETURN NEW; END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.aip_budget_cost_fence_guard_a0v_126() FROM PUBLIC')
    op.execute('CREATE TRIGGER budget_cost_fence_guard BEFORE INSERT OR UPDATE OR DELETE ON public.aip_budget_cost_runtime_fence FOR EACH ROW EXECUTE FUNCTION public.aip_budget_cost_fence_guard_a0v_126()')
    op.execute('CREATE TRIGGER budget_cost_fence_truncate BEFORE TRUNCATE ON public.aip_budget_cost_runtime_fence FOR EACH STATEMENT EXECUTE FUNCTION public.extension_reject_history_mutation()')
    op.execute("""CREATE FUNCTION public.aip_budget_cost_revoke_fence_a0v_126() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
      UPDATE public.aip_budget_cost_runtime_fence SET version=version+1
        WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND decision_id=NEW.decision_id;
      RETURN NEW; END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.aip_budget_cost_revoke_fence_a0v_126() FROM PUBLIC')
    op.execute('CREATE TRIGGER budget_cost_revoke_fence AFTER INSERT ON public.aip_budget_cost_revocation FOR EACH ROW EXECUTE FUNCTION public.aip_budget_cost_revoke_fence_a0v_126()')
    op.execute("""CREATE FUNCTION public.aip_budget_cost_hash_a0v_126(value jsonb) RETURNS text
      LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog AS $$
      SELECT encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(value),'UTF8'),'sha256'),'hex') $$""")
    op.execute('REVOKE ALL ON FUNCTION public.aip_budget_cost_hash_a0v_126(jsonb) FROM PUBLIC')
    op.execute('GRANT EXECUTE ON FUNCTION public.aip_budget_cost_hash_a0v_126(jsonb) TO aos_budget_consumer_owner')
    source=Path(__file__).resolve().parents[2]/'aos_api/aip_budget_cost_consumer.sql'
    op.get_bind().exec_driver_sql(source.read_text().replace('%','%%'))
    signature='public.aip_consume_budget_cost_a0v_126(text,text,text,text)'
    op.execute(f'ALTER FUNCTION {signature} OWNER TO aos_budget_consumer_owner')
    op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
    op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO aos_budget_consumer_call')
    op.execute("""CREATE OR REPLACE FUNCTION public.aip_budget_active_insert_guard() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
      IF NEW.lifecycle='active' AND (session_user<>'aos_budget_consumer_call' OR current_user<>'aos_budget_consumer_owner') THEN
        RAISE EXCEPTION 'BUDGET_ACTIVATION_CONSUMPTION_REQUIRED' USING ERRCODE='23514'; END IF;
      RETURN NEW; END $$""")
    op.execute("""CREATE FUNCTION public.aip_budget_cost_receipt_guard_a0v_126() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
      IF NEW.operation='budget_revision.activate_cost' AND (session_user<>'aos_budget_consumer_call' OR current_user<>'aos_budget_consumer_owner') THEN
        RAISE EXCEPTION 'BUDGET_CONSUMER_IDENTITY_REQUIRED' USING ERRCODE='42501'; END IF;
      RETURN NEW; END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.aip_budget_cost_receipt_guard_a0v_126() FROM PUBLIC')
    op.execute('CREATE TRIGGER aip_budget_cost_receipt_guard_a0v_126 BEFORE INSERT ON public.aip_budget_receipt FOR EACH ROW EXECUTE FUNCTION public.aip_budget_cost_receipt_guard_a0v_126()')


def downgrade():
    raise RuntimeError('budget consumption history must not be removed')
