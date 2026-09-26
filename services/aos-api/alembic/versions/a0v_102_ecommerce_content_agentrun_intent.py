"""One-attempt AgentRun handoff after the accepted content TaskRun."""

from alembic import op


revision = "a0v_102"
down_revision = "a0v_101"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE public.ecommerce_growth_content_agentrun_intent (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, review_key TEXT NOT NULL,
      review_receipt_ref JSONB NOT NULL, task_id TEXT NOT NULL,
      plan_revision_id TEXT NOT NULL, task_run_id TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'pending'
        CHECK(state IN ('pending','claimed','accepted','unknown')),
      attempt INTEGER NOT NULL DEFAULT 0 CHECK(attempt BETWEEN 0 AND 1),
      claim_token UUID, agent_run_id TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,review_key),
      UNIQUE(org_id,project_id,task_run_id),
      CHECK((state='pending' AND attempt=0 AND claim_token IS NULL AND agent_run_id IS NULL)
         OR (state IN ('claimed','unknown') AND attempt=1 AND claim_token IS NOT NULL
             AND agent_run_id IS NULL)
         OR (state='accepted' AND attempt=1 AND claim_token IS NOT NULL
             AND agent_run_id IS NOT NULL))
    )""")
    op.execute("ALTER TABLE public.ecommerce_growth_content_agentrun_intent ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.ecommerce_growth_content_agentrun_intent FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_content_agentrun_intent_a0v_102
      ON public.ecommerce_growth_content_agentrun_intent TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("REVOKE ALL ON public.ecommerce_growth_content_agentrun_intent FROM PUBLIC")
    op.execute("GRANT SELECT ON public.ecommerce_growth_content_agentrun_intent TO aos_runtime")

    # A private definer predicate is shared by put, claim and ack. It does not
    # grant a caller execution rights; the full group is rechecked by Python.
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_agentrun_current_a0v_102(
      p_org TEXT,p_project TEXT,p_review_key TEXT
    ) RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
      SELECT EXISTS(
        SELECT 1 FROM public.ecommerce_growth_content_taskrun_intent p
        JOIN public.ecommerce_growth_runtime_command_receipt o
          ON o.org_id=p.org_id AND o.project_id=p.project_id
         AND o.operation_id='ecommerce_growth_review_advance'
         AND o.idempotency_key=p.review_key
        JOIN public.extension_operation_dispatch_binding d
          ON d.org_id=o.org_id AND d.project_id=o.project_id
         AND d.operation_id=o.operation_id
        JOIN public.extension_runtime_binding b
          ON b.org_id=o.org_id AND b.project_id=o.project_id
         AND b.installation_id=o.installation_id AND b.generation=o.generation
        JOIN public.aip_task_run r
          ON r.org_id=p.org_id AND r.project_id=p.project_id
         AND r.run_id=p.run_id AND r.task_id=p.task_id
         AND r.plan_revision_id=p.plan_revision_id
        JOIN public.aip_task t
          ON t.org_id=r.org_id AND t.project_id=r.project_id AND t.task_id=r.task_id
        JOIN public.aip_plan_revision plan
          ON plan.org_id=r.org_id AND plan.project_id=r.project_id
         AND plan.plan_revision_id=r.plan_revision_id AND plan.task_id=r.task_id
        WHERE p.org_id=p_org AND p.project_id=p_project AND p.review_key=p_review_key
          AND p.state='accepted' AND p.attempt=1
          AND p.review_receipt_ref=o.target_receipt_ref
          AND p.origin_request_hash=o.request_hash
          AND o.response->'receiptRef'=o.target_receipt_ref
          AND o.response->>'decision'='ACCEPT'
          AND r.status='running' AND t.status='executing'
          AND t.current_plan_revision_id=p.plan_revision_id
          AND plan.approval_status='approved'
          AND plan.risk->'reviewReceiptRef'=p.review_receipt_ref
          AND d.handler_kind='extension' AND d.operation_fence=false
          AND d.revision=o.dispatch_revision
          AND d.installation_id=o.installation_id AND d.generation=o.generation
          AND d.execution_epoch=o.execution_epoch
          AND d.cutover_group_id=o.cutover_group_id
          AND d.cutover_group_revision=o.cutover_group_revision
          AND b.revision=o.runtime_revision AND b.execution_epoch=o.execution_epoch
          AND b.desired_state='enabled' AND b.observed_state='ready'
          AND b.enabled=true AND b.operation_fence=false
      )
    $$""")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_agentrun_put_a0v_102(
      p_review_key TEXT
    ) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
      v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
      v_prior RECORD;v_existing RECORD;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')=''
         OR length(btrim(coalesce(p_review_key,''))) NOT BETWEEN 1 AND 200
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid content AgentRun scope'; END IF;
      IF NOT public.ecommerce_growth_content_agentrun_current_a0v_102(v_org,v_project,p_review_key)
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content TaskRun not current and accepted'; END IF;
      SELECT review_receipt_ref,task_id,plan_revision_id,run_id,
             xmin::text AS row_xmin INTO v_prior
        FROM public.ecommerce_growth_content_taskrun_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key FOR SHARE;
      IF v_prior.row_xmin IS DISTINCT FROM pg_current_xact_id()::text
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content AgentRun intent requires same transaction as Run ack'; END IF;
      INSERT INTO public.ecommerce_growth_content_agentrun_intent(
        org_id,project_id,review_key,review_receipt_ref,task_id,plan_revision_id,task_run_id)
      VALUES(v_org,v_project,p_review_key,v_prior.review_receipt_ref,
             v_prior.task_id,v_prior.plan_revision_id,v_prior.run_id)
      ON CONFLICT(org_id,project_id,review_key) DO NOTHING;
      IF FOUND THEN RETURN TRUE; END IF;
      SELECT * INTO v_existing FROM public.ecommerce_growth_content_agentrun_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key;
      IF NOT FOUND OR v_existing.review_receipt_ref<>v_prior.review_receipt_ref
         OR v_existing.task_id<>v_prior.task_id
         OR v_existing.plan_revision_id<>v_prior.plan_revision_id
         OR v_existing.task_run_id<>v_prior.run_id
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content AgentRun intent replay drifted'; END IF;
      RETURN FALSE;
    END $$""")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_agentrun_claim_a0v_102(
      p_review_key TEXT,p_token UUID
    ) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
      v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
      v_row RECORD;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')='' OR p_token IS NULL
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid content AgentRun claim'; END IF;
      IF NOT public.ecommerce_growth_content_agentrun_current_a0v_102(v_org,v_project,p_review_key)
      THEN RETURN FALSE; END IF;
      SELECT * INTO v_row FROM public.ecommerce_growth_content_agentrun_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key FOR UPDATE;
      IF NOT FOUND OR v_row.state<>'pending' OR v_row.attempt<>0 THEN RETURN FALSE; END IF;
      UPDATE public.ecommerce_growth_content_agentrun_intent
         SET state='claimed',attempt=1,claim_token=p_token,updated_at=clock_timestamp()
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key;
      RETURN TRUE;
    END $$""")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_agentrun_ack_a0v_102(
      p_review_key TEXT,p_token UUID,p_agent_run_id TEXT
    ) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
      v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
      v_row RECORD;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')='' OR p_token IS NULL
         OR coalesce(p_agent_run_id,'')=''
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid content AgentRun ack'; END IF;
      IF NOT public.ecommerce_growth_content_agentrun_current_a0v_102(v_org,v_project,p_review_key)
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content AgentRun origin no longer current'; END IF;
      SELECT * INTO v_row FROM public.ecommerce_growth_content_agentrun_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key FOR UPDATE;
      IF NOT FOUND OR v_row.state<>'claimed' OR v_row.attempt<>1
         OR v_row.claim_token<>p_token
         OR NOT EXISTS(
           SELECT 1 FROM public.aip_agent_run a
           JOIN public.aip_agent_registry_receipt receipt
             ON receipt.org_id=a.org_id AND receipt.project_id=a.project_id
            AND receipt.operation='agent_run.create'
            AND receipt.idempotency_key=p_review_key
            AND receipt.result_ref->>'resourceId'=a.agent_run_id
            AND receipt.status='applied'
           WHERE a.org_id=v_org AND a.project_id=v_project
             AND a.agent_run_id=p_agent_run_id
             AND a.task_id=v_row.task_id AND a.task_run_id=v_row.task_run_id
             AND a.status='queued'
         )
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content AgentRun ack lacks queued Owner'; END IF;
      UPDATE public.ecommerce_growth_content_agentrun_intent
         SET state='accepted',agent_run_id=p_agent_run_id,updated_at=clock_timestamp()
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key;
      RETURN TRUE;
    END $$""")
    for name, signature in (
        ("current", "TEXT,TEXT,TEXT"), ("put", "TEXT"),
        ("claim", "TEXT,UUID"), ("ack", "TEXT,UUID,TEXT"),
    ):
        op.execute(
            f"REVOKE ALL ON FUNCTION public.ecommerce_growth_content_agentrun_{name}_a0v_102({signature}) FROM PUBLIC"
        )
        if name != "current":
            op.execute(
                f"GRANT EXECUTE ON FUNCTION public.ecommerce_growth_content_agentrun_{name}_a0v_102({signature}) TO aos_runtime"
            )


def downgrade() -> None:
    raise RuntimeError("content AgentRun one-attempt boundary must not be removed")
