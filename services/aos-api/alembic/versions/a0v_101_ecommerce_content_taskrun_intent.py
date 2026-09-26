"""Durable one-attempt content TaskRun intent after an exact v2 Review Handoff."""

from alembic import op


revision = "a0v_101"
down_revision = "a0v_100"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE public.ecommerce_growth_content_taskrun_intent (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL,
      review_key TEXT NOT NULL, review_receipt_ref JSONB NOT NULL,
      task_id TEXT NOT NULL, brief_id TEXT NOT NULL,
      origin_request_hash TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'pending'
        CHECK(state IN ('pending','claimed','accepted','unknown')),
      attempt INTEGER NOT NULL DEFAULT 0 CHECK(attempt BETWEEN 0 AND 1),
      claim_token UUID, plan_revision_id TEXT, run_id TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,review_key),
      UNIQUE(org_id,project_id,task_id),
      CHECK((state='pending' AND attempt=0 AND claim_token IS NULL
             AND plan_revision_id IS NULL AND run_id IS NULL)
         OR (state IN ('claimed','unknown') AND attempt=1 AND claim_token IS NOT NULL
             AND plan_revision_id IS NULL AND run_id IS NULL)
         OR (state='accepted' AND attempt=1 AND claim_token IS NOT NULL
             AND plan_revision_id IS NOT NULL AND run_id IS NOT NULL))
    )""")
    op.execute("ALTER TABLE public.ecommerce_growth_content_taskrun_intent ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.ecommerce_growth_content_taskrun_intent FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_content_taskrun_intent_a0v_101
      ON public.ecommerce_growth_content_taskrun_intent TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("REVOKE ALL ON public.ecommerce_growth_content_taskrun_intent FROM PUBLIC")
    op.execute("GRANT SELECT ON public.ecommerce_growth_content_taskrun_intent TO aos_runtime")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_taskrun_intent_put_a0v_101(
      p_review_key TEXT
    ) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
      v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
      v_origin RECORD;v_brief RECORD;v_existing RECORD;v_dispatch RECORD;
      v_runtime RECORD;v_task TEXT;v_brief_id TEXT;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')=''
         OR length(btrim(coalesce(p_review_key,''))) NOT BETWEEN 1 AND 200
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid content TaskRun intent scope'; END IF;
      SELECT request_hash,response,target_receipt_ref,dispatch_revision,
             installation_id,generation,execution_epoch,cutover_group_id,
             cutover_group_revision,runtime_revision INTO v_origin
        FROM public.ecommerce_growth_runtime_command_receipt
       WHERE org_id=v_org AND project_id=v_project
         AND operation_id='ecommerce_growth_review_advance'
         AND idempotency_key=p_review_key FOR SHARE;
      IF NOT FOUND OR v_origin.response->>'decision'<>'ACCEPT'
         OR v_origin.response->'receiptRef'<>v_origin.target_receipt_ref
         OR v_origin.response->>'requestHash'<>v_origin.request_hash
         OR v_origin.response->'sideEffects'->>'taskRunCreatedCount'<>'0'
         OR v_origin.response->'taskRef'->>'resourceType'<>'Task'
         OR v_origin.response->'briefRef'->>'resourceType'<>'TaskBriefRevision'
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content TaskRun Review origin unavailable'; END IF;
      SELECT * INTO v_dispatch FROM public.extension_operation_dispatch_binding
       WHERE org_id=v_org AND project_id=v_project
         AND operation_id='ecommerce_growth_review_advance' FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content TaskRun dispatch unavailable'; END IF;
      SELECT * INTO v_runtime FROM public.extension_runtime_binding
       WHERE org_id=v_org AND project_id=v_project
         AND installation_id=v_origin.installation_id
         AND generation=v_origin.generation FOR UPDATE;
      IF NOT FOUND OR v_dispatch.operation_fence IS DISTINCT FROM FALSE
         OR v_dispatch.handler_kind<>'extension'
         OR v_dispatch.revision<>v_origin.dispatch_revision
         OR v_dispatch.installation_id<>v_origin.installation_id
         OR v_dispatch.generation<>v_origin.generation
         OR v_dispatch.execution_epoch<>v_origin.execution_epoch
         OR v_dispatch.cutover_group_id<>v_origin.cutover_group_id
         OR v_dispatch.cutover_group_revision<>v_origin.cutover_group_revision
         OR v_runtime.operation_fence IS DISTINCT FROM FALSE
         OR v_runtime.enabled IS DISTINCT FROM TRUE
         OR v_runtime.desired_state<>'enabled' OR v_runtime.observed_state<>'ready'
         OR v_runtime.execution_epoch<>v_origin.execution_epoch
         OR v_runtime.revision<>v_origin.runtime_revision
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content TaskRun runtime unavailable'; END IF;
      v_task:=v_origin.response->'taskRef'->>'resourceId';
      v_brief_id:=v_origin.response->'briefRef'->>'resourceId';
      SELECT task_id,schema_ref,spec,content_hash INTO v_brief
        FROM public.aip_task_brief_revision
       WHERE org_id=v_org AND project_id=v_project AND brief_id=v_brief_id
         AND revision=1 FOR SHARE;
      IF NOT FOUND OR v_task IS NULL OR v_brief_id IS NULL
         OR v_brief.task_id<>v_task
         OR v_brief.schema_ref->>'resourceId'<>'schema://aos/ecommerce/content-campaign-brief/v2'
         OR v_brief.spec->'taskRef'<>v_origin.response->'taskRef'
         OR v_brief.spec->'growthPlanRef'<>v_origin.response->'growthPlanRef'
         OR v_origin.response->'briefRef'->>'contentHash'<>'sha256:'||v_brief.content_hash
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content TaskRun Brief origin unavailable'; END IF;
      INSERT INTO public.ecommerce_growth_content_taskrun_intent(
        org_id,project_id,review_key,review_receipt_ref,task_id,brief_id,origin_request_hash)
      VALUES(v_org,v_project,p_review_key,v_origin.target_receipt_ref,
             v_task,v_brief_id,v_origin.request_hash)
      ON CONFLICT(org_id,project_id,review_key) DO NOTHING;
      IF FOUND THEN RETURN TRUE; END IF;
      SELECT * INTO v_existing FROM public.ecommerce_growth_content_taskrun_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key;
      IF NOT FOUND OR v_existing.review_receipt_ref<>v_origin.target_receipt_ref
         OR v_existing.task_id<>v_task OR v_existing.brief_id<>v_brief_id
         OR v_existing.origin_request_hash<>v_origin.request_hash
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content TaskRun intent replay drifted'; END IF;
      RETURN FALSE;
    END $$""")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_taskrun_claim_a0v_101(
      p_review_key TEXT,p_token UUID
    ) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
      v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
      v_origin RECORD;v_dispatch RECORD;v_runtime RECORD;v_intent RECORD;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')='' OR p_token IS NULL
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid content TaskRun claim'; END IF;
      SELECT request_hash,response,target_receipt_ref,dispatch_revision,
             installation_id,generation,execution_epoch,cutover_group_id,
             cutover_group_revision,runtime_revision INTO v_origin
        FROM public.ecommerce_growth_runtime_command_receipt
       WHERE org_id=v_org AND project_id=v_project
         AND operation_id='ecommerce_growth_review_advance'
         AND idempotency_key=p_review_key;
      IF NOT FOUND THEN RETURN FALSE; END IF;
      SELECT * INTO v_dispatch FROM public.extension_operation_dispatch_binding
       WHERE org_id=v_org AND project_id=v_project
         AND operation_id='ecommerce_growth_review_advance' FOR UPDATE;
      IF NOT FOUND THEN RETURN FALSE; END IF;
      SELECT * INTO v_runtime FROM public.extension_runtime_binding
       WHERE org_id=v_org AND project_id=v_project
         AND installation_id=v_origin.installation_id
         AND generation=v_origin.generation FOR UPDATE;
      IF NOT FOUND THEN RETURN FALSE; END IF;
      IF v_dispatch.operation_fence IS DISTINCT FROM FALSE
         OR v_dispatch.handler_kind<>'extension'
         OR v_dispatch.revision<>v_origin.dispatch_revision
         OR v_dispatch.installation_id<>v_origin.installation_id
         OR v_dispatch.generation<>v_origin.generation
         OR v_dispatch.execution_epoch<>v_origin.execution_epoch
         OR v_dispatch.cutover_group_id<>v_origin.cutover_group_id
         OR v_dispatch.cutover_group_revision<>v_origin.cutover_group_revision
         OR v_runtime.operation_fence IS DISTINCT FROM FALSE
         OR v_runtime.enabled IS DISTINCT FROM TRUE
         OR v_runtime.desired_state<>'enabled' OR v_runtime.observed_state<>'ready'
         OR v_runtime.execution_epoch<>v_origin.execution_epoch
         OR v_runtime.revision<>v_origin.runtime_revision
      THEN RETURN FALSE; END IF;
      SELECT * INTO v_intent FROM public.ecommerce_growth_content_taskrun_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key FOR UPDATE;
      IF NOT FOUND OR v_intent.state<>'pending' OR v_intent.attempt<>0
         OR v_intent.review_receipt_ref<>v_origin.target_receipt_ref
         OR v_intent.origin_request_hash<>v_origin.request_hash
         OR v_origin.response->'receiptRef'<>v_origin.target_receipt_ref
         OR v_origin.response->>'decision'<>'ACCEPT'
      THEN RETURN FALSE; END IF;
      UPDATE public.ecommerce_growth_content_taskrun_intent
         SET state='claimed',attempt=1,claim_token=p_token,updated_at=clock_timestamp()
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key;
      RETURN TRUE;
    END $$""")
    op.execute("""CREATE FUNCTION public.ecommerce_growth_content_taskrun_ack_a0v_101(
      p_review_key TEXT,p_token UUID,p_plan_id TEXT,p_run_id TEXT
    ) RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
      v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
      v_intent RECORD;v_origin RECORD;v_dispatch RECORD;v_runtime RECORD;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')='' OR p_token IS NULL
         OR coalesce(p_plan_id,'')='' OR coalesce(p_run_id,'')=''
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid content TaskRun ack'; END IF;
      SELECT request_hash,target_receipt_ref,dispatch_revision,
             installation_id,generation,execution_epoch,cutover_group_id,
             cutover_group_revision,runtime_revision INTO v_origin
        FROM public.ecommerce_growth_runtime_command_receipt
       WHERE org_id=v_org AND project_id=v_project
         AND operation_id='ecommerce_growth_review_advance'
         AND idempotency_key=p_review_key;
      IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content TaskRun ack origin missing'; END IF;
      SELECT * INTO v_dispatch FROM public.extension_operation_dispatch_binding
       WHERE org_id=v_org AND project_id=v_project
         AND operation_id='ecommerce_growth_review_advance' FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content TaskRun ack dispatch missing'; END IF;
      SELECT * INTO v_runtime FROM public.extension_runtime_binding
       WHERE org_id=v_org AND project_id=v_project
         AND installation_id=v_origin.installation_id
         AND generation=v_origin.generation FOR UPDATE;
      IF NOT FOUND OR v_dispatch.operation_fence IS DISTINCT FROM FALSE
         OR v_dispatch.handler_kind<>'extension'
         OR v_dispatch.revision<>v_origin.dispatch_revision
         OR v_dispatch.installation_id<>v_origin.installation_id
         OR v_dispatch.generation<>v_origin.generation
         OR v_dispatch.execution_epoch<>v_origin.execution_epoch
         OR v_dispatch.cutover_group_id<>v_origin.cutover_group_id
         OR v_dispatch.cutover_group_revision<>v_origin.cutover_group_revision
         OR v_runtime.operation_fence IS DISTINCT FROM FALSE
         OR v_runtime.enabled IS DISTINCT FROM TRUE
         OR v_runtime.desired_state<>'enabled' OR v_runtime.observed_state<>'ready'
         OR v_runtime.execution_epoch<>v_origin.execution_epoch
         OR v_runtime.revision<>v_origin.runtime_revision
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content TaskRun ack runtime unavailable'; END IF;
      SELECT * INTO v_intent FROM public.ecommerce_growth_content_taskrun_intent
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key FOR UPDATE;
      IF NOT FOUND OR v_intent.state<>'claimed' OR v_intent.attempt<>1
         OR v_intent.claim_token<>p_token
         OR v_intent.review_receipt_ref<>v_origin.target_receipt_ref
         OR v_intent.origin_request_hash<>v_origin.request_hash
         OR NOT EXISTS(
           SELECT 1 FROM public.aip_task_run r
           JOIN public.aip_plan_revision p ON p.org_id=r.org_id AND p.project_id=r.project_id
             AND p.plan_revision_id=r.plan_revision_id
           JOIN public.aip_task t ON t.org_id=r.org_id AND t.project_id=r.project_id
             AND t.task_id=r.task_id
           WHERE r.org_id=v_org AND r.project_id=v_project AND r.run_id=p_run_id
             AND r.plan_revision_id=p_plan_id AND r.task_id=v_intent.task_id
             AND r.idempotency_key=p_review_key||chr(58)||'content-run'||chr(58)||'run'
             AND p.task_id=v_intent.task_id
             AND p.idempotency_key=p_review_key||chr(58)||'content-run'||chr(58)||'plan'
             AND p.risk->'reviewReceiptRef'=v_intent.review_receipt_ref
             AND r.status='running' AND p.approval_status='approved'
             AND t.status='executing')
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='content TaskRun ack lacks running owner'; END IF;
      UPDATE public.ecommerce_growth_content_taskrun_intent
         SET state='accepted',plan_revision_id=p_plan_id,run_id=p_run_id,
             updated_at=clock_timestamp()
       WHERE org_id=v_org AND project_id=v_project AND review_key=p_review_key;
      RETURN TRUE;
    END $$""")
    for name, signature in (
        ("intent_put", "TEXT"), ("claim", "TEXT,UUID"), ("ack", "TEXT,UUID,TEXT,TEXT"),
    ):
        op.execute(
            f"REVOKE ALL ON FUNCTION public.ecommerce_growth_content_taskrun_{name}_a0v_101({signature}) FROM PUBLIC"
        )
        op.execute(
            f"GRANT EXECUTE ON FUNCTION public.ecommerce_growth_content_taskrun_{name}_a0v_101({signature}) TO aos_runtime"
        )


def downgrade() -> None:
    raise RuntimeError("content TaskRun one-attempt boundary must not be removed")
