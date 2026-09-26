"""One-attempt capacity start after the accepted content AgentRun."""

from alembic import op


revision = "a0v_103"
down_revision = "a0v_102"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE public.ecommerce_growth_content_capacity_intent (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, review_key TEXT NOT NULL,
      task_run_id TEXT NOT NULL, agent_run_id TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'pending'
        CHECK(state IN ('pending','claimed','accepted','unknown')),
      attempt INTEGER NOT NULL DEFAULT 0 CHECK(attempt BETWEEN 0 AND 1),
      claim_token UUID, capacity_reservation_id TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,review_key),
      UNIQUE(org_id,project_id,agent_run_id),
      CHECK((state='pending' AND attempt=0 AND claim_token IS NULL
             AND capacity_reservation_id IS NULL)
         OR (state IN ('claimed','unknown') AND attempt=1 AND claim_token IS NOT NULL
             AND capacity_reservation_id IS NULL)
         OR (state='accepted' AND attempt=1 AND claim_token IS NOT NULL
             AND capacity_reservation_id IS NOT NULL))
    )""")
    op.execute("ALTER TABLE public.ecommerce_growth_content_capacity_intent ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.ecommerce_growth_content_capacity_intent FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_content_capacity_intent_a0v_103
      ON public.ecommerce_growth_content_capacity_intent TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("REVOKE ALL ON public.ecommerce_growth_content_capacity_intent FROM PUBLIC")
    op.execute("GRANT SELECT ON public.ecommerce_growth_content_capacity_intent TO aos_runtime")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_capacity_current_a0v_103(
      p_org TEXT,p_project TEXT,p_review_key TEXT
    ) RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      SELECT public.ecommerce_growth_content_agentrun_current_a0v_102(
               p_org,p_project,p_review_key)
        AND EXISTS(
          SELECT 1 FROM public.ecommerce_growth_content_agentrun_intent i
          JOIN public.aip_agent_run a
            ON a.org_id=i.org_id AND a.project_id=i.project_id
           AND a.agent_run_id=i.agent_run_id AND a.task_run_id=i.task_run_id
          JOIN public.aip_agent_registry_receipt receipt
            ON receipt.org_id=a.org_id AND receipt.project_id=a.project_id
           AND receipt.operation='agent_run.create'
           AND receipt.idempotency_key=i.review_key
           AND receipt.result_ref->>'resourceId'=a.agent_run_id
           AND receipt.status='applied'
          WHERE i.org_id=p_org AND i.project_id=p_project AND i.review_key=p_review_key
            AND i.state='accepted' AND i.attempt=1
            AND a.status IN ('queued','running')
        )
    $$""")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_capacity_put_a0v_103(
      p_review_key TEXT
    ) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
      v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
      v_prior RECORD;v_existing RECORD;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')=''
         OR length(btrim(coalesce(p_review_key,''))) NOT BETWEEN 1 AND 200
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid content capacity scope'; END IF;
      IF NOT public.ecommerce_growth_content_capacity_current_a0v_103(v_org,v_project,p_review_key)
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content AgentRun not current and accepted'; END IF;
      SELECT task_run_id,agent_run_id,xmin::text AS row_xmin INTO v_prior
        FROM public.ecommerce_growth_content_agentrun_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key FOR SHARE;
      IF v_prior.row_xmin IS DISTINCT FROM pg_current_xact_id()::text
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content capacity intent requires same transaction as AgentRun ack'; END IF;
      INSERT INTO public.ecommerce_growth_content_capacity_intent(
        org_id,project_id,review_key,task_run_id,agent_run_id)
      VALUES(v_org,v_project,p_review_key,v_prior.task_run_id,v_prior.agent_run_id)
      ON CONFLICT(org_id,project_id,review_key) DO NOTHING;
      IF FOUND THEN RETURN TRUE; END IF;
      SELECT * INTO v_existing FROM public.ecommerce_growth_content_capacity_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key;
      IF NOT FOUND OR v_existing.task_run_id<>v_prior.task_run_id
         OR v_existing.agent_run_id<>v_prior.agent_run_id
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content capacity intent replay drifted'; END IF;
      RETURN FALSE;
    END $$""")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_capacity_claim_a0v_103(
      p_review_key TEXT,p_token UUID
    ) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
      v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
      v_row RECORD;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')='' OR p_token IS NULL
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid content capacity claim'; END IF;
      IF NOT public.ecommerce_growth_content_capacity_current_a0v_103(v_org,v_project,p_review_key)
      THEN RETURN FALSE; END IF;
      SELECT * INTO v_row FROM public.ecommerce_growth_content_capacity_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key FOR UPDATE;
      IF NOT FOUND OR v_row.state<>'pending' OR v_row.attempt<>0 THEN RETURN FALSE; END IF;
      UPDATE public.ecommerce_growth_content_capacity_intent
         SET state='claimed',attempt=1,claim_token=p_token,updated_at=clock_timestamp()
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key;
      RETURN TRUE;
    END $$""")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_capacity_ack_a0v_103(
      p_review_key TEXT,p_token UUID,p_capacity_reservation_id TEXT
    ) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
      v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
      v_row RECORD;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')='' OR p_token IS NULL
         OR coalesce(p_capacity_reservation_id,'')=''
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid content capacity ack'; END IF;
      IF NOT public.ecommerce_growth_content_capacity_current_a0v_103(v_org,v_project,p_review_key)
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content capacity origin no longer current'; END IF;
      SELECT * INTO v_row FROM public.ecommerce_growth_content_capacity_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key FOR UPDATE;
      IF NOT FOUND OR v_row.state<>'claimed' OR v_row.attempt<>1
         OR v_row.claim_token<>p_token
         OR NOT EXISTS(
           SELECT 1 FROM public.aip_agent_run a
           JOIN public.aip_model_capacity_reservation r
             ON r.org_id=a.org_id AND r.project_id=a.project_id
            AND r.agent_run_id=a.agent_run_id
           WHERE a.org_id=v_org AND a.project_id=v_project
             AND a.agent_run_id=v_row.agent_run_id
             AND a.task_run_id=v_row.task_run_id AND a.status='running'
             AND r.reservation_id=p_capacity_reservation_id
             AND r.status IN ('reserved','consumed') AND r.expires_at>clock_timestamp()
         )
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content capacity ack lacks running Owner and live reservation'; END IF;
      UPDATE public.ecommerce_growth_content_capacity_intent
         SET state='accepted',capacity_reservation_id=p_capacity_reservation_id,
             updated_at=clock_timestamp()
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key;
      RETURN TRUE;
    END $$""")
    for name, signature in (
        ("current", "TEXT,TEXT,TEXT"), ("put", "TEXT"),
        ("claim", "TEXT,UUID"), ("ack", "TEXT,UUID,TEXT"),
    ):
        op.execute(
            f"REVOKE ALL ON FUNCTION public.ecommerce_growth_content_capacity_{name}_a0v_103({signature}) FROM PUBLIC"
        )
        if name != "current":
            op.execute(
                f"GRANT EXECUTE ON FUNCTION public.ecommerce_growth_content_capacity_{name}_a0v_103({signature}) TO aos_runtime"
            )


def downgrade() -> None:
    raise RuntimeError("content capacity one-attempt boundary must not be removed")
