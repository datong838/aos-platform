"""Separate budget risk issuer identity and immutable review history."""
from alembic import op

revision = 'a0v_125'
down_revision = 'a0v_124'
branch_labels = depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_budget_cost_issuer') THEN
        CREATE ROLE aos_budget_cost_issuer NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
      ELSIF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_budget_cost_issuer'
        AND (rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)) THEN
        RAISE EXCEPTION 'BUDGET_COST_ISSUER_ROLE_DRIFT';
      END IF;
      IF EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid='aos_budget_cost_issuer'::regrole
        OR (member='aos_budget_cost_issuer'::regrole AND (roleid<>'aos_runtime'::regrole OR admin_option))) THEN
        RAISE EXCEPTION 'BUDGET_COST_ISSUER_MEMBERSHIP_DRIFT';
      END IF;
    END $$""")
    op.execute('GRANT aos_runtime TO aos_budget_cost_issuer')
    op.execute("""CREATE TABLE public.aip_budget_cost_decision(
      org_id text NOT NULL,project_id text NOT NULL,decision_id text NOT NULL,proposal_id text NOT NULL,
      proposal_hash text NOT NULL CHECK(proposal_hash ~ '^[0-9a-f]{64}$'),actor_subject text NOT NULL,
      decision text NOT NULL CHECK(decision IN ('approved','rejected')),source_ref jsonb,
      expires_at timestamptz NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,decision_id),UNIQUE(org_id,project_id,proposal_id),
      FOREIGN KEY(org_id,project_id,proposal_id) REFERENCES public.aip_budget_cost_proposal(org_id,project_id,proposal_id),
      CHECK(decision<>'approved' OR (source_ref IS NOT NULL AND jsonb_typeof(source_ref)='object'))
    )""")
    op.execute("""CREATE TABLE public.aip_budget_cost_revocation(
      org_id text NOT NULL,project_id text NOT NULL,revocation_id text NOT NULL,decision_id text NOT NULL,
      actor_subject text NOT NULL,reason text NOT NULL CHECK(length(reason) BETWEEN 1 AND 500),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,revocation_id),UNIQUE(org_id,project_id,decision_id),
      FOREIGN KEY(org_id,project_id,decision_id) REFERENCES public.aip_budget_cost_decision(org_id,project_id,decision_id)
    )""")
    op.execute("""CREATE TABLE public.aip_budget_cost_issuer_receipt(
      org_id text NOT NULL,project_id text NOT NULL,actor_subject text NOT NULL,
      operation text NOT NULL CHECK(operation IN ('decide','revoke')),
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160),
      request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),result jsonb NOT NULL,
      PRIMARY KEY(org_id,project_id,actor_subject,operation,idempotency_key),CHECK(jsonb_typeof(result)='object')
    )""")
    op.execute("""CREATE FUNCTION public.aip_budget_cost_issuer_guard_a0v_125() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
      IF session_user<>'aos_budget_cost_issuer' OR current_user<>'aos_runtime'
         OR current_setting('aos.org_id',true) IS DISTINCT FROM NEW.org_id
         OR current_setting('aos.project_id',true) IS DISTINCT FROM NEW.project_id
         OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND
           (NOT rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
         OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=session_user::regrole
           OR (member=session_user::regrole AND (roleid<>'aos_runtime'::regrole OR admin_option))) THEN
        RAISE EXCEPTION 'BUDGET_COST_ISSUER_REQUIRED' USING ERRCODE='42501';
      END IF;
      IF TG_TABLE_NAME='aip_budget_cost_decision' THEN
        IF NEW.expires_at<=clock_timestamp() OR NOT EXISTS(
          SELECT 1 FROM public.aip_budget_cost_proposal p WHERE p.org_id=NEW.org_id
            AND p.project_id=NEW.project_id AND p.proposal_id=NEW.proposal_id
            AND p.proposal_hash=NEW.proposal_hash AND p.checker_subject=NEW.actor_subject
            AND p.expires_at=NEW.expires_at) THEN
          RAISE EXCEPTION 'BUDGET_COST_EXACT_CURRENT_PROPOSAL_REQUIRED' USING ERRCODE='42501';
        END IF;
      END IF;
      RETURN NEW; END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.aip_budget_cost_issuer_guard_a0v_125() FROM PUBLIC')
    for table in ('aip_budget_cost_decision','aip_budget_cost_revocation','aip_budget_cost_issuer_receipt'):
        op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY')
        op.execute(f"""CREATE POLICY {table}_tenant ON public.{table} TO aos_runtime
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f'REVOKE ALL ON public.{table} FROM PUBLIC,aos_app,aos_runtime')
        op.execute(f'GRANT SELECT,INSERT ON public.{table} TO aos_runtime')
        op.execute(f"CREATE TRIGGER {table}_issuer BEFORE INSERT ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.aip_budget_cost_issuer_guard_a0v_125()")
        op.execute(f"CREATE TRIGGER {table}_immutable_row BEFORE UPDATE OR DELETE ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.extension_reject_history_mutation()")
        op.execute(f"CREATE TRIGGER {table}_immutable_truncate BEFORE TRUNCATE ON public.{table} FOR EACH STATEMENT EXECUTE FUNCTION public.extension_reject_history_mutation()")


def downgrade():
    raise RuntimeError('budget cost issuer history and boundary must not be removed')
