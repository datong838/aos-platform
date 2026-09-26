"""Receipt-first internal daily review target for accepted content feedback."""

from alembic import op


revision = "a0v_099"
down_revision = "a0v_098"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE public.ecommerce_growth_daily_review_target (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          target_id TEXT NOT NULL, command_id TEXT NOT NULL,
          body JSONB NOT NULL CHECK(jsonb_typeof(body)='object'),
          receipt_ref JSONB NOT NULL CHECK(jsonb_typeof(receipt_ref)='object'),
          created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY(org_id,project_id,target_id),
          UNIQUE(org_id,project_id,command_id),
          FOREIGN KEY(org_id,project_id,command_id)
            REFERENCES public.ecommerce_growth_feedback_command(org_id,project_id,command_id)
        )"""
    )
    op.execute("ALTER TABLE public.ecommerce_growth_daily_review_target ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.ecommerce_growth_daily_review_target FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_ecommerce_growth_daily_review_a0v_099
          ON public.ecommerce_growth_daily_review_target TO aos_runtime
          USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute("REVOKE ALL ON public.ecommerce_growth_daily_review_target FROM PUBLIC")
    op.execute("GRANT SELECT ON public.ecommerce_growth_daily_review_target TO aos_runtime")
    op.execute(
        """CREATE FUNCTION public.ecommerce_growth_daily_review_put_a0v_099(
          p_command_id TEXT,p_target_id TEXT,p_lease_token UUID,p_checkpoint_version BIGINT,
          p_payload JSONB,p_review_ref JSONB,p_artifact_ref JSONB,p_task_ref JSONB,p_brief_ref JSONB
        ) RETURNS TABLE(receipt_ref JSONB,replayed BOOLEAN)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
          v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
          v_dispatch RECORD;v_runtime RECORD;v_origin RECORD;v_command RECORD;
          v_segment RECORD;v_checkpoint RECORD;v_existing RECORD;
          v_body JSONB;v_receipt JSONB;v_hash TEXT;v_origin_count BIGINT;
        BEGIN
          IF coalesce(v_org,'')='' OR coalesce(v_project,'')=''
             OR current_setting('transaction_isolation')<>'serializable'
             OR current_setting('transaction_read_only')<>'off'
             OR coalesce(btrim(p_command_id),'')=''
             OR coalesce(btrim(p_target_id),'')=''
             OR p_target_id NOT LIKE 'daily_review-%'
             OR p_lease_token IS NULL OR p_checkpoint_version<1
             OR jsonb_typeof(p_payload)<>'object'
             OR jsonb_typeof(p_review_ref)<>'object'
             OR jsonb_typeof(p_artifact_ref)<>'object'
             OR jsonb_typeof(p_task_ref)<>'object'
             OR jsonb_typeof(p_brief_ref)<>'object'
             OR (p_payload ?& ARRAY['sequence','kind','targetId','businessTitle','businessSummary','targetPhase']) IS DISTINCT FROM TRUE
             OR (p_payload - ARRAY['sequence','kind','targetId','businessTitle','businessSummary','targetPhase']) <> '{}'::jsonb
             OR p_payload->>'kind' IS DISTINCT FROM 'daily_review'
             OR p_payload->>'targetId' IS DISTINCT FROM p_target_id
             OR p_payload->>'sequence' IS DISTINCT FROM '1'
             OR p_payload->'targetPhase' IS DISTINCT FROM 'null'::jsonb
             OR length(btrim(coalesce(p_payload->>'businessTitle',''))) NOT BETWEEN 1 AND 120
             OR length(btrim(coalesce(p_payload->>'businessSummary',''))) NOT BETWEEN 1 AND 500
          THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid daily review target'; END IF;
          SELECT * INTO v_command FROM public.ecommerce_growth_feedback_command
           WHERE org_id=v_org AND project_id=v_project AND command_id=p_command_id;
          IF NOT FOUND OR v_command.decision<>'ACCEPT'
             OR v_command.review_receipt_ref IS DISTINCT FROM p_review_ref
             OR v_command.artifact_ref IS DISTINCT FROM p_artifact_ref
             OR v_command.task_ref IS DISTINCT FROM p_task_ref
             OR v_command.brief_ref IS DISTINCT FROM p_brief_ref
          THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='daily review command lineage drifted'; END IF;
          SELECT count(*) INTO v_origin_count FROM public.ecommerce_growth_runtime_command_receipt
           WHERE org_id=v_org AND project_id=v_project
             AND operation_id='ecommerce_growth_content_review'
             AND target_receipt_ref=p_review_ref;
          IF v_origin_count<>1 THEN
            RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='daily review origin missing or ambiguous'; END IF;
          SELECT * INTO v_origin FROM public.ecommerce_growth_runtime_command_receipt
           WHERE org_id=v_org AND project_id=v_project
             AND operation_id='ecommerce_growth_content_review'
             AND target_receipt_ref=p_review_ref;
          IF v_origin.response->'receiptRef' IS DISTINCT FROM p_review_ref
             OR v_origin.response->>'decision' IS DISTINCT FROM 'ACCEPT'
             OR v_origin.response->'artifactRef' IS DISTINCT FROM p_artifact_ref
             OR v_origin.response->'taskRef' IS DISTINCT FROM p_task_ref
             OR v_origin.response->'briefRef' IS DISTINCT FROM p_brief_ref
          THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='daily review origin content drifted'; END IF;
          SELECT * INTO v_dispatch FROM public.extension_operation_dispatch_binding
           WHERE org_id=v_org AND project_id=v_project
             AND operation_id='ecommerce_growth_content_review' FOR UPDATE;
          IF NOT FOUND OR v_dispatch.handler_kind IS DISTINCT FROM 'extension'
             OR v_dispatch.operation_fence IS DISTINCT FROM FALSE
             OR v_dispatch.revision IS DISTINCT FROM v_origin.dispatch_revision
             OR v_dispatch.installation_id IS DISTINCT FROM v_origin.installation_id
             OR v_dispatch.generation IS DISTINCT FROM v_origin.generation
             OR v_dispatch.execution_epoch IS DISTINCT FROM v_origin.execution_epoch
             OR v_dispatch.cutover_group_id IS DISTINCT FROM v_origin.cutover_group_id
             OR v_dispatch.cutover_group_revision IS DISTINCT FROM v_origin.cutover_group_revision
          THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='daily review dispatch is not current'; END IF;
          SELECT * INTO v_runtime FROM public.extension_runtime_binding
           WHERE org_id=v_org AND project_id=v_project
             AND installation_id=v_origin.installation_id
             AND generation=v_origin.generation FOR UPDATE;
          IF NOT FOUND OR v_runtime.execution_epoch IS DISTINCT FROM v_origin.execution_epoch
             OR v_runtime.revision IS DISTINCT FROM v_origin.runtime_revision
             OR v_runtime.desired_state IS DISTINCT FROM 'enabled'
             OR v_runtime.observed_state IS DISTINCT FROM 'ready'
             OR v_runtime.enabled IS DISTINCT FROM TRUE
             OR v_runtime.operation_fence IS DISTINCT FROM FALSE
          THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='daily review runtime is not current'; END IF;
          SELECT * INTO v_checkpoint FROM public.ecommerce_growth_feedback_checkpoint
           WHERE org_id=v_org AND project_id=v_project AND command_id=p_command_id FOR UPDATE;
          SELECT * INTO v_segment FROM public.ecommerce_growth_feedback_segment
           WHERE org_id=v_org AND project_id=v_project AND command_id=p_command_id
             AND sequence=1 FOR UPDATE;
          IF v_checkpoint.command_id IS NULL OR v_checkpoint.completed_sequence IS DISTINCT FROM 0
             OR v_checkpoint.version IS DISTINCT FROM p_checkpoint_version
             OR v_segment.command_id IS NULL OR v_segment.kind IS DISTINCT FROM 'daily_review'
             OR v_segment.target_id IS DISTINCT FROM p_target_id
             OR v_segment.payload IS DISTINCT FROM p_payload
             OR v_segment.state IS DISTINCT FROM 'claimed'
             OR v_segment.lease_token IS DISTINCT FROM p_lease_token
             OR v_segment.lease_expires_at IS NULL
             OR v_segment.lease_expires_at<=clock_timestamp()
          THEN RAISE EXCEPTION USING ERRCODE='40001',MESSAGE='daily review claim is not current'; END IF;
          v_body:=jsonb_build_object(
            'commandId',p_command_id,'targetId',p_target_id,
            'reviewReceiptRef',p_review_ref,'artifactRef',p_artifact_ref,
            'taskRef',p_task_ref,'briefRef',p_brief_ref,
            'businessTitle',p_payload->>'businessTitle',
            'businessSummary',p_payload->>'businessSummary',
            'installationId',v_origin.installation_id::text,
            'generation',v_origin.generation::text,
            'executionEpoch',v_origin.execution_epoch,
            'effectStatus','AWAITING_OBSERVATION');
          v_hash:='sha256:'||encode(digest(convert_to(v_body::text,'UTF8'),'sha256'),'hex');
          v_receipt:=jsonb_build_object('resourceType','DailyReviewReceipt',
            'resourceId',p_target_id,'revision',1,'contentHash',v_hash,'receiptId',p_target_id);
          SELECT * INTO v_existing FROM public.ecommerce_growth_daily_review_target
           WHERE org_id=v_org AND project_id=v_project AND target_id=p_target_id FOR UPDATE;
          IF FOUND THEN
            IF v_existing.command_id<>p_command_id OR v_existing.body IS DISTINCT FROM v_body
               OR v_existing.receipt_ref IS DISTINCT FROM v_receipt
            THEN RAISE EXCEPTION USING ERRCODE='23505',MESSAGE='daily review target replay drifted'; END IF;
            RETURN QUERY SELECT v_receipt,TRUE; RETURN;
          END IF;
          INSERT INTO public.ecommerce_growth_daily_review_target(
            org_id,project_id,target_id,command_id,body,receipt_ref,created_at)
          VALUES(v_org,v_project,p_target_id,p_command_id,v_body,v_receipt,clock_timestamp());
          RETURN QUERY SELECT v_receipt,FALSE;
        END $$"""
    )
    op.execute(
        """REVOKE ALL ON FUNCTION public.ecommerce_growth_daily_review_put_a0v_099(
          TEXT,TEXT,UUID,BIGINT,JSONB,JSONB,JSONB,JSONB,JSONB) FROM PUBLIC"""
    )
    op.execute(
        """GRANT EXECUTE ON FUNCTION public.ecommerce_growth_daily_review_put_a0v_099(
          TEXT,TEXT,UUID,BIGINT,JSONB,JSONB,JSONB,JSONB,JSONB) TO aos_runtime"""
    )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN IF EXISTS(SELECT 1 FROM public.ecommerce_growth_daily_review_target LIMIT 1)
          THEN RAISE EXCEPTION 'daily review target is not empty'; END IF; END $$"""
    )
    op.execute(
        """DROP FUNCTION public.ecommerce_growth_daily_review_put_a0v_099(
          TEXT,TEXT,UUID,BIGINT,JSONB,JSONB,JSONB,JSONB,JSONB)"""
    )
    op.execute("DROP TABLE public.ecommerce_growth_daily_review_target")
