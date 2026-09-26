"""One-attempt content budget command after an accepted capacity start."""

from alembic import op


revision = "a0v_104"
down_revision = "a0v_103"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE public.ecommerce_growth_content_budget_command_intent (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, review_key TEXT NOT NULL,
      task_run_id TEXT NOT NULL, agent_run_id TEXT NOT NULL,
      capacity_reservation_id TEXT NOT NULL, command_key TEXT NOT NULL,
      installation_id UUID NOT NULL, generation UUID NOT NULL,
      execution_epoch BIGINT NOT NULL CHECK(execution_epoch>0),
      state TEXT NOT NULL DEFAULT 'pending'
        CHECK(state IN ('pending','claimed','accepted','unknown')),
      attempt INTEGER NOT NULL DEFAULT 0 CHECK(attempt BETWEEN 0 AND 1),
      claim_token UUID, budget_reservation_id UUID,
      created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,review_key),
      UNIQUE(org_id,project_id,command_key),
      CHECK(command_key=review_key),
      CHECK((state='pending' AND attempt=0 AND claim_token IS NULL
             AND budget_reservation_id IS NULL)
         OR (state IN ('claimed','unknown') AND attempt=1 AND claim_token IS NOT NULL
             AND budget_reservation_id IS NULL)
         OR (state='accepted' AND attempt=1 AND claim_token IS NOT NULL
             AND budget_reservation_id IS NOT NULL))
    )""")
    op.execute("ALTER TABLE public.ecommerce_growth_content_budget_command_intent ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.ecommerce_growth_content_budget_command_intent FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_content_budget_command_a0v_104
      ON public.ecommerce_growth_content_budget_command_intent TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("REVOKE ALL ON public.ecommerce_growth_content_budget_command_intent FROM PUBLIC")
    op.execute("GRANT SELECT ON public.ecommerce_growth_content_budget_command_intent TO aos_runtime")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_budget_command_current_a0v_104(
      p_org TEXT,p_project TEXT,p_review_key TEXT
    ) RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      SELECT public.ecommerce_growth_content_capacity_current_a0v_103(
               p_org,p_project,p_review_key)
        AND EXISTS(
          SELECT 1 FROM public.ecommerce_growth_content_capacity_intent c
          JOIN public.aip_agent_run a
            ON a.org_id=c.org_id AND a.project_id=c.project_id
           AND a.agent_run_id=c.agent_run_id AND a.task_run_id=c.task_run_id
          JOIN public.aip_model_capacity_reservation r
            ON r.org_id=a.org_id AND r.project_id=a.project_id
           AND r.agent_run_id=a.agent_run_id AND r.reservation_id=c.capacity_reservation_id
          WHERE c.org_id=p_org AND c.project_id=p_project AND c.review_key=p_review_key
            AND c.state='accepted' AND c.attempt=1 AND a.status='running'
            AND r.status IN ('reserved','consumed') AND r.expires_at>clock_timestamp()
        )
    $$""")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_budget_command_put_a0v_104(
      p_review_key TEXT
    ) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
      v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
      v_prior RECORD;v_existing RECORD;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')=''
         OR length(btrim(coalesce(p_review_key,''))) NOT BETWEEN 1 AND 200
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid content budget command scope'; END IF;
      IF NOT public.ecommerce_growth_content_budget_command_current_a0v_104(v_org,v_project,p_review_key)
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content capacity not current and accepted'; END IF;
      SELECT c.task_run_id,c.agent_run_id,c.capacity_reservation_id,
             o.installation_id,o.generation,o.execution_epoch,
             c.xmin::text AS row_xmin INTO v_prior
        FROM public.ecommerce_growth_content_capacity_intent c
        JOIN public.ecommerce_growth_runtime_command_receipt o
          ON o.org_id=c.org_id AND o.project_id=c.project_id
         AND o.operation_id='ecommerce_growth_review_advance'
         AND o.idempotency_key=c.review_key
       WHERE c.org_id=v_org AND c.project_id=v_project AND c.review_key=p_review_key
         AND c.state='accepted' FOR SHARE OF c,o;
      IF NOT FOUND OR v_prior.row_xmin IS DISTINCT FROM pg_current_xact_id()::text
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content budget intent requires same transaction as capacity ack'; END IF;
      INSERT INTO public.ecommerce_growth_content_budget_command_intent(
        org_id,project_id,review_key,task_run_id,agent_run_id,capacity_reservation_id,
        command_key,installation_id,generation,execution_epoch)
      VALUES(v_org,v_project,p_review_key,v_prior.task_run_id,v_prior.agent_run_id,
             v_prior.capacity_reservation_id,p_review_key,v_prior.installation_id,
             v_prior.generation,v_prior.execution_epoch)
      ON CONFLICT(org_id,project_id,review_key) DO NOTHING;
      IF FOUND THEN RETURN TRUE; END IF;
      SELECT * INTO v_existing FROM public.ecommerce_growth_content_budget_command_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key;
      IF NOT FOUND OR v_existing.task_run_id<>v_prior.task_run_id
         OR v_existing.agent_run_id<>v_prior.agent_run_id
         OR v_existing.capacity_reservation_id<>v_prior.capacity_reservation_id
         OR v_existing.command_key<>p_review_key
         OR v_existing.installation_id<>v_prior.installation_id
         OR v_existing.generation<>v_prior.generation
         OR v_existing.execution_epoch<>v_prior.execution_epoch
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content budget intent replay drifted'; END IF;
      RETURN FALSE;
    END $$""")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_budget_command_claim_a0v_104(
      p_review_key TEXT,p_token UUID
    ) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
      v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
      v_row RECORD;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')='' OR p_token IS NULL
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid content budget command claim'; END IF;
      IF NOT public.ecommerce_growth_content_budget_command_current_a0v_104(v_org,v_project,p_review_key)
      THEN RETURN FALSE; END IF;
      SELECT * INTO v_row FROM public.ecommerce_growth_content_budget_command_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key FOR UPDATE;
      IF NOT FOUND OR v_row.state<>'pending' OR v_row.attempt<>0
         OR EXISTS(
           SELECT 1 FROM public.ecommerce_growth_runtime_command_receipt r
           WHERE r.org_id=v_org AND r.project_id=v_project
             AND r.operation_id='ecommerce_growth_content_generate'
             AND r.idempotency_key=v_row.command_key
         )
      THEN RETURN FALSE; END IF;
      UPDATE public.ecommerce_growth_content_budget_command_intent
         SET state='claimed',attempt=1,claim_token=p_token,updated_at=clock_timestamp()
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key;
      RETURN TRUE;
    END $$""")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_budget_command_ack_a0v_104(
      p_review_key TEXT,p_token UUID,p_budget_reservation_id UUID
    ) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
      v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
      v_row RECORD;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')='' OR p_token IS NULL
         OR p_budget_reservation_id IS NULL
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid content budget command ack'; END IF;
      IF NOT public.ecommerce_growth_content_budget_command_current_a0v_104(v_org,v_project,p_review_key)
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content budget command origin no longer current'; END IF;
      SELECT * INTO v_row FROM public.ecommerce_growth_content_budget_command_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key FOR UPDATE;
      IF NOT FOUND OR v_row.state<>'claimed' OR v_row.attempt<>1
         OR v_row.claim_token<>p_token
         OR NOT EXISTS(
           SELECT 1 FROM public.aip_budget_reservation b
           JOIN public.ecommerce_content_execution_command j
             ON j.org_id=b.org_id AND j.project_id=b.project_id
            AND j.reservation_id=b.reservation_id
           JOIN public.ecommerce_growth_runtime_command_receipt r
             ON r.org_id=b.org_id AND r.project_id=b.project_id
            AND r.operation_id='ecommerce_growth_content_generate'
            AND r.idempotency_key=b.invocation_key
           JOIN public.ecommerce_growth_content_taskrun_intent t
             ON t.org_id=b.org_id AND t.project_id=b.project_id
            AND t.review_key=v_row.review_key AND t.run_id=v_row.task_run_id
           WHERE b.org_id=v_org AND b.project_id=v_project
             AND b.reservation_id=p_budget_reservation_id
             AND b.operation_id='ecommerce_growth_content_generate'
             AND b.invocation_key=v_row.command_key AND b.state='held'
             AND j.budget_request_hash=b.request_hash
             AND j.command_payload->>'idempotencyKey'=v_row.command_key
             AND j.command_payload->'authorityRefs'->'task'->>'resourceId'=t.task_id
             AND j.command_payload->'authorityRefs'->'capacity_reservation'->>'resourceId'=v_row.capacity_reservation_id
             AND r.request_hash='sha256:'||j.command_hash
             AND r.response->>'requestHash'=j.command_payload->>'requestHash'
             AND r.response->>'state'='PENDING'
             AND r.response->>'budgetState'='HELD'
             AND r.response->'budgetReservationRef'->>'resourceId'=p_budget_reservation_id::text
             AND r.response->'authorityRefs'=j.command_payload->'authorityRefs'
             AND r.response->'receiptRef'=r.target_receipt_ref
             AND r.installation_id=v_row.installation_id
             AND r.generation=v_row.generation
             AND r.execution_epoch=v_row.execution_epoch
         )
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content budget command ack lacks exact HELD/PENDING Receipt'; END IF;
      UPDATE public.ecommerce_growth_content_budget_command_intent
         SET state='accepted',budget_reservation_id=p_budget_reservation_id,
             updated_at=clock_timestamp()
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key;
      RETURN TRUE;
    END $$""")
    for name, signature in (
        ("current", "TEXT,TEXT,TEXT"), ("put", "TEXT"),
        ("claim", "TEXT,UUID"), ("ack", "TEXT,UUID,UUID"),
    ):
        op.execute(
            f"REVOKE ALL ON FUNCTION public.ecommerce_growth_content_budget_command_{name}_a0v_104({signature}) FROM PUBLIC"
        )
        if name != "current":
            op.execute(
                f"GRANT EXECUTE ON FUNCTION public.ecommerce_growth_content_budget_command_{name}_a0v_104({signature}) TO aos_runtime"
            )


def downgrade() -> None:
    raise RuntimeError("content budget command one-attempt boundary must not be removed")
