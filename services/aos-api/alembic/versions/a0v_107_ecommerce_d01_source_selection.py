"""Append-only D01 decisions; runtime writes only through checked functions."""

from alembic import op


revision = 'a0v_107'
down_revision = 'a0v_106'
branch_labels = depends_on = None


_TABLES = (
    'ecommerce_d01_source_proposal',
    'ecommerce_d01_source_approval',
    'ecommerce_d01_source_revocation',
)


def upgrade() -> None:
    op.execute("""CREATE TABLE public.ecommerce_d01_source_proposal (
      org_id text NOT NULL, project_id text NOT NULL,
      selection_id text NOT NULL CHECK(length(selection_id) BETWEEN 1 AND 200),
      task_run_id text NOT NULL, plan_revision_id text NOT NULL,
      plan_content_hash text NOT NULL CHECK(plan_content_hash ~ '^[0-9a-f]{64}$'),
      source_selection_ref jsonb NOT NULL CHECK(jsonb_typeof(source_selection_ref)='object'),
      packet jsonb NOT NULL CHECK(jsonb_typeof(packet)='object'),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
      proposal_key text NOT NULL CHECK(length(proposal_key) BETWEEN 1 AND 160),
      request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
      content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
      maker text NOT NULL CHECK(length(maker) BETWEEN 1 AND 240),
      proposed_at timestamptz NOT NULL,
      proposal_txid bigint NOT NULL,
      PRIMARY KEY(org_id,project_id,selection_id),
      UNIQUE(org_id,project_id,task_run_id,plan_revision_id),
      UNIQUE(org_id,project_id,proposal_key),
      FOREIGN KEY(org_id,project_id,task_run_id)
        REFERENCES public.aip_task_run(org_id,project_id,run_id),
      FOREIGN KEY(org_id,project_id,plan_revision_id)
        REFERENCES public.aip_plan_revision(org_id,project_id,plan_revision_id)
    )""")
    op.execute("""CREATE TABLE public.ecommerce_d01_source_approval (
      org_id text NOT NULL, project_id text NOT NULL,
      selection_id text NOT NULL,
      approval_key text NOT NULL CHECK(length(approval_key) BETWEEN 1 AND 160),
      request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
      proposal_hash text NOT NULL CHECK(proposal_hash ~ '^[0-9a-f]{64}$'),
      checker text NOT NULL CHECK(length(checker) BETWEEN 1 AND 240),
      approved_at timestamptz NOT NULL,
      receipt_ref jsonb NOT NULL CHECK(jsonb_typeof(receipt_ref)='object'),
      PRIMARY KEY(org_id,project_id,selection_id),
      UNIQUE(org_id,project_id,approval_key),
      FOREIGN KEY(org_id,project_id,selection_id)
        REFERENCES public.ecommerce_d01_source_proposal(org_id,project_id,selection_id)
    )""")
    op.execute("""CREATE TABLE public.ecommerce_d01_source_revocation (
      org_id text NOT NULL, project_id text NOT NULL,
      selection_id text NOT NULL,
      revocation_key text NOT NULL CHECK(length(revocation_key) BETWEEN 1 AND 160),
      request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
      actor text NOT NULL CHECK(length(actor) BETWEEN 1 AND 240),
      reason text NOT NULL CHECK(length(reason) BETWEEN 1 AND 500),
      revoked_at timestamptz NOT NULL,
      receipt_ref jsonb NOT NULL CHECK(jsonb_typeof(receipt_ref)='object'),
      PRIMARY KEY(org_id,project_id,selection_id),
      UNIQUE(org_id,project_id,revocation_key),
      FOREIGN KEY(org_id,project_id,selection_id)
        REFERENCES public.ecommerce_d01_source_approval(org_id,project_id,selection_id)
    )""")
    for table in _TABLES:
        op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY')
        op.execute(f"""CREATE POLICY tenant_scope_{table}_a0v_107 ON public.{table}
          TO aos_runtime
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"""CREATE TRIGGER {table}_immutable_row
          BEFORE UPDATE OR DELETE ON public.{table}
          FOR EACH ROW EXECUTE FUNCTION public.extension_reject_history_mutation()""")
        op.execute(f"""CREATE TRIGGER {table}_immutable_truncate
          BEFORE TRUNCATE ON public.{table}
          FOR EACH STATEMENT EXECUTE FUNCTION public.extension_reject_history_mutation()""")
        op.execute(f'REVOKE ALL ON public.{table} FROM PUBLIC,aos_runtime')
        op.execute(f'GRANT SELECT ON public.{table} TO aos_runtime')
    op.execute("""CREATE FUNCTION public.ecommerce_d01_source_propose_a0v_107(
      p_selection_id text,p_run_id text,p_plan_id text,p_plan_hash text,
      p_source_ref jsonb,p_packet jsonb,p_payload jsonb,p_key text,p_request_hash text,
      p_content_hash text,p_maker text,p_proposed_at timestamptz
    ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public AS $$
    DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
      v_project text:=NULLIF(current_setting('aos.project_id',true),'');
      v_run record;v_plan record;v_task record;v_existing record;v_receipt jsonb;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')=''
         OR current_setting('transaction_isolation')<>'serializable'
         OR current_setting('transaction_read_only')<>'off'
         OR length(btrim(coalesce(p_selection_id,''))) NOT BETWEEN 1 AND 200
         OR length(btrim(coalesce(p_run_id,''))) NOT BETWEEN 1 AND 200
         OR length(btrim(coalesce(p_plan_id,''))) NOT BETWEEN 1 AND 200
         OR length(btrim(coalesce(p_key,''))) NOT BETWEEN 1 AND 160
         OR length(btrim(coalesce(p_maker,''))) NOT BETWEEN 1 AND 240
         OR p_selection_id<>btrim(p_selection_id) OR p_key<>btrim(p_key)
         OR p_maker<>btrim(p_maker)
         OR p_maker IS DISTINCT FROM current_setting('aos.subject',true)
         OR p_plan_hash !~ '^[0-9a-f]{64}$'
         OR p_request_hash !~ '^[0-9a-f]{64}$'
         OR p_content_hash !~ '^[0-9a-f]{64}$'
         OR jsonb_typeof(p_source_ref)<>'object'
         OR jsonb_typeof(p_packet)<>'object'
         OR jsonb_typeof(p_payload)<>'object'
         OR p_source_ref->>'resourceType' IS DISTINCT FROM 'SourceSelectionRevision'
         OR p_source_ref->>'contentHash' !~ '^sha256:[0-9a-f]{64}$'
         OR p_packet->'methodRef'->>'resourceType' IS DISTINCT FROM 'MethodRevision'
         OR p_packet->'evalRef'->>'resourceType' IS DISTINCT FROM 'EvalContractRevision'
         OR jsonb_typeof(p_packet->'metricSources') IS DISTINCT FROM 'array'
         OR p_payload->'sourceSelectionRef' IS DISTINCT FROM p_source_ref
         OR p_payload->'packet' IS DISTINCT FROM p_packet
         OR p_payload->'taskRunRef'->>'resourceId' IS DISTINCT FROM p_run_id
         OR p_payload->'planRef'->>'resourceId' IS DISTINCT FROM p_plan_id
         OR p_payload->>'planContentHash' IS DISTINCT FROM p_plan_hash
         OR p_payload->>'proposedBy' IS DISTINCT FROM p_maker
         OR p_payload->'tenant'->>'orgId' IS DISTINCT FROM v_org
         OR p_payload->'tenant'->>'projectId' IS DISTINCT FROM v_project
         OR p_proposed_at IS NULL OR p_proposed_at>clock_timestamp()+interval '5 minutes'
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid D01 source proposal'; END IF;
      SELECT * INTO v_run FROM public.aip_task_run
       WHERE org_id=v_org AND project_id=v_project AND run_id=p_run_id FOR SHARE;
      SELECT * INTO v_plan FROM public.aip_plan_revision
       WHERE org_id=v_org AND project_id=v_project AND plan_revision_id=p_plan_id FOR SHARE;
      IF v_run.run_id IS NULL OR v_plan.plan_revision_id IS NULL
         OR v_run.plan_revision_id IS DISTINCT FROM p_plan_id
         OR v_run.task_id IS DISTINCT FROM v_plan.task_id
         OR v_run.status IS DISTINCT FROM 'running'
         OR v_plan.approval_status IS DISTINCT FROM 'approved'
         OR v_plan.content_hash IS DISTINCT FROM p_plan_hash
         OR v_plan.created_by IS DISTINCT FROM p_maker
         OR v_plan.approved_by IS NULL OR v_plan.approved_by=p_maker
         OR v_plan.steps->0->>'stepKey' IS DISTINCT FROM 'portrait'
         OR jsonb_typeof(v_plan.steps->0->'inputRefs') IS DISTINCT FROM 'array'
         OR jsonb_array_length(v_plan.steps->0->'inputRefs')<1
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='approved D01 Plan and Run unavailable'; END IF;
      SELECT * INTO v_task FROM public.aip_task
       WHERE org_id=v_org AND project_id=v_project AND task_id=v_run.task_id FOR SHARE;
      IF v_task.task_id IS NULL OR v_task.status IS DISTINCT FROM 'executing'
         OR v_task.current_plan_revision_id IS DISTINCT FROM p_plan_id
         OR v_task.selection_ref->>'resourceType' IS DISTINCT FROM 'SourceSelectionRevision'
         OR v_task.selection_ref->>'resourceId' IS DISTINCT FROM p_source_ref->>'resourceId'
         OR v_task.selection_ref->>'revision' IS DISTINCT FROM p_source_ref->>'revision'
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='original Task source selection drifted'; END IF;
      IF NOT EXISTS(SELECT 1 FROM public.meta_membership
          WHERE org_id=v_org AND project_id=v_project AND subject=p_maker)
      THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='D01 proposal maker membership unavailable'; END IF;
      SELECT * INTO v_existing FROM public.ecommerce_d01_source_proposal
       WHERE org_id=v_org AND project_id=v_project
         AND (selection_id=p_selection_id OR proposal_key=p_key) FOR UPDATE;
      IF FOUND THEN
        IF v_existing.selection_id IS DISTINCT FROM p_selection_id
           OR v_existing.proposal_key IS DISTINCT FROM p_key
           OR v_existing.task_run_id IS DISTINCT FROM p_run_id
           OR v_existing.plan_revision_id IS DISTINCT FROM p_plan_id
           OR v_existing.plan_content_hash IS DISTINCT FROM p_plan_hash
           OR v_existing.source_selection_ref IS DISTINCT FROM p_source_ref
           OR v_existing.packet IS DISTINCT FROM p_packet
           OR v_existing.payload IS DISTINCT FROM p_payload
           OR v_existing.request_hash IS DISTINCT FROM p_request_hash
           OR v_existing.content_hash IS DISTINCT FROM p_content_hash
           OR v_existing.maker IS DISTINCT FROM p_maker
           OR v_existing.proposed_at IS DISTINCT FROM p_proposed_at
        THEN RAISE EXCEPTION USING ERRCODE='23505',MESSAGE='D01 proposal key or payload drifted'; END IF;
      ELSE
        INSERT INTO public.ecommerce_d01_source_proposal
          (org_id,project_id,selection_id,task_run_id,plan_revision_id,
           plan_content_hash,source_selection_ref,packet,payload,proposal_key,
           request_hash,content_hash,maker,proposed_at,proposal_txid)
        VALUES(v_org,v_project,p_selection_id,p_run_id,p_plan_id,p_plan_hash,
          p_source_ref,p_packet,p_payload,p_key,p_request_hash,p_content_hash,p_maker,p_proposed_at,
          txid_current());
      END IF;
      v_receipt:=jsonb_build_object('resourceType','D01SourceSelectionProposal',
        'resourceId',p_selection_id,'revision',1,'contentHash','sha256:'||p_content_hash,
        'receiptId','d01-proposal:'||p_selection_id);
      RETURN v_receipt;
    END $$""")
    signature = 'text,text,text,text,jsonb,jsonb,jsonb,text,text,text,text,timestamptz'
    op.execute(
        f'REVOKE ALL ON FUNCTION public.ecommerce_d01_source_propose_a0v_107({signature}) FROM PUBLIC'
    )
    op.execute(
        f'GRANT EXECUTE ON FUNCTION public.ecommerce_d01_source_propose_a0v_107({signature}) TO aos_runtime'
    )
    op.execute("""CREATE FUNCTION public.ecommerce_d01_source_approve_a0v_107(
      p_selection_id text,p_key text,p_request_hash text,p_proposal_hash text,
      p_checker text,p_approved_at timestamptz
    ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public AS $$
    DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
      v_project text:=NULLIF(current_setting('aos.project_id',true),'');
      v_proposal record;v_plan record;v_run record;v_task record;
      v_existing record;v_receipt jsonb;v_body jsonb;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')=''
         OR current_setting('transaction_isolation')<>'serializable'
         OR current_setting('transaction_read_only')<>'off'
         OR length(btrim(coalesce(p_selection_id,''))) NOT BETWEEN 1 AND 200
         OR length(btrim(coalesce(p_key,''))) NOT BETWEEN 1 AND 160
         OR length(btrim(coalesce(p_checker,''))) NOT BETWEEN 1 AND 240
         OR p_selection_id<>btrim(p_selection_id) OR p_key<>btrim(p_key)
         OR p_checker<>btrim(p_checker)
         OR p_checker IS DISTINCT FROM current_setting('aos.subject',true)
         OR p_request_hash !~ '^[0-9a-f]{64}$'
         OR p_proposal_hash !~ '^[0-9a-f]{64}$'
         OR p_approved_at IS NULL OR p_approved_at>clock_timestamp()+interval '5 minutes'
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid D01 source approval'; END IF;
      SELECT * INTO v_proposal FROM public.ecommerce_d01_source_proposal
       WHERE org_id=v_org AND project_id=v_project AND selection_id=p_selection_id FOR SHARE;
      IF v_proposal.selection_id IS NULL
         OR v_proposal.content_hash IS DISTINCT FROM p_proposal_hash
         OR v_proposal.maker=p_checker
         OR v_proposal.proposal_txid=txid_current()
         OR p_approved_at<v_proposal.proposed_at
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='D01 proposal approval lineage unavailable'; END IF;
      SELECT * INTO v_plan FROM public.aip_plan_revision
       WHERE org_id=v_org AND project_id=v_project
         AND plan_revision_id=v_proposal.plan_revision_id FOR SHARE;
      SELECT * INTO v_run FROM public.aip_task_run
       WHERE org_id=v_org AND project_id=v_project
         AND run_id=v_proposal.task_run_id FOR SHARE;
      SELECT * INTO v_task FROM public.aip_task
       WHERE org_id=v_org AND project_id=v_project AND task_id=v_run.task_id FOR SHARE;
      IF v_plan.plan_revision_id IS NULL OR v_run.run_id IS NULL OR v_task.task_id IS NULL
         OR v_plan.approval_status IS DISTINCT FROM 'approved'
         OR v_plan.approved_by IS DISTINCT FROM p_checker
         OR v_plan.content_hash IS DISTINCT FROM v_proposal.plan_content_hash
         OR v_run.plan_revision_id IS DISTINCT FROM v_plan.plan_revision_id
         OR v_run.task_id IS DISTINCT FROM v_plan.task_id
         OR v_run.status IS DISTINCT FROM 'running'
         OR v_task.status IS DISTINCT FROM 'executing'
         OR v_task.current_plan_revision_id IS DISTINCT FROM v_plan.plan_revision_id
         OR v_task.selection_ref->>'resourceId' IS DISTINCT FROM
              v_proposal.source_selection_ref->>'resourceId'
         OR v_task.selection_ref->>'revision' IS DISTINCT FROM
              v_proposal.source_selection_ref->>'revision'
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='current D01 approval authority drifted'; END IF;
      IF NOT EXISTS(SELECT 1 FROM public.meta_membership
          WHERE org_id=v_org AND project_id=v_project AND subject=p_checker
            AND role IN ('approver','admin','owner'))
      THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='D01 checker membership unavailable'; END IF;
      v_body:=jsonb_build_object('selectionId',p_selection_id,
        'proposalHash',p_proposal_hash,'checker',p_checker,
        'approvedAt',p_approved_at);
      v_receipt:=jsonb_build_object('resourceType','D01SourceSelectionApproval',
        'resourceId',p_selection_id,'revision',1,
        'contentHash','sha256:'||encode(digest(convert_to(v_body::text,'UTF8'),'sha256'),'hex'),
        'receiptId','d01-approval:'||p_selection_id);
      SELECT * INTO v_existing FROM public.ecommerce_d01_source_approval
       WHERE org_id=v_org AND project_id=v_project
         AND (selection_id=p_selection_id OR approval_key=p_key) FOR UPDATE;
      IF FOUND THEN
        IF v_existing.selection_id IS DISTINCT FROM p_selection_id
           OR v_existing.approval_key IS DISTINCT FROM p_key
           OR v_existing.request_hash IS DISTINCT FROM p_request_hash
           OR v_existing.proposal_hash IS DISTINCT FROM p_proposal_hash
           OR v_existing.checker IS DISTINCT FROM p_checker
           OR v_existing.approved_at IS DISTINCT FROM p_approved_at
           OR v_existing.receipt_ref IS DISTINCT FROM v_receipt
        THEN RAISE EXCEPTION USING ERRCODE='23505',MESSAGE='D01 approval key or payload drifted'; END IF;
      ELSE
        INSERT INTO public.ecommerce_d01_source_approval
          (org_id,project_id,selection_id,approval_key,request_hash,
           proposal_hash,checker,approved_at,receipt_ref)
        VALUES(v_org,v_project,p_selection_id,p_key,p_request_hash,
          p_proposal_hash,p_checker,p_approved_at,v_receipt);
      END IF;
      RETURN v_receipt;
    END $$""")
    signature = 'text,text,text,text,text,timestamptz'
    op.execute(
        f'REVOKE ALL ON FUNCTION public.ecommerce_d01_source_approve_a0v_107({signature}) FROM PUBLIC'
    )
    op.execute(
        f'GRANT EXECUTE ON FUNCTION public.ecommerce_d01_source_approve_a0v_107({signature}) TO aos_runtime'
    )
    op.execute("""CREATE FUNCTION public.ecommerce_d01_source_revoke_a0v_107(
      p_selection_id text,p_key text,p_request_hash text,p_actor text,
      p_reason text,p_revoked_at timestamptz
    ) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public AS $$
    DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
      v_project text:=NULLIF(current_setting('aos.project_id',true),'');
      v_approval record;v_existing record;v_receipt jsonb;v_body jsonb;
    BEGIN
      IF coalesce(v_org,'')='' OR coalesce(v_project,'')=''
         OR current_setting('transaction_isolation')<>'serializable'
         OR current_setting('transaction_read_only')<>'off'
         OR length(btrim(coalesce(p_selection_id,''))) NOT BETWEEN 1 AND 200
         OR length(btrim(coalesce(p_key,''))) NOT BETWEEN 1 AND 160
         OR length(btrim(coalesce(p_actor,''))) NOT BETWEEN 1 AND 240
         OR length(btrim(coalesce(p_reason,''))) NOT BETWEEN 1 AND 500
         OR p_selection_id<>btrim(p_selection_id) OR p_key<>btrim(p_key)
         OR p_actor<>btrim(p_actor) OR p_reason<>btrim(p_reason)
         OR p_actor IS DISTINCT FROM current_setting('aos.subject',true)
         OR p_request_hash !~ '^[0-9a-f]{64}$'
         OR p_revoked_at IS NULL OR p_revoked_at>clock_timestamp()+interval '5 minutes'
      THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid D01 source revocation'; END IF;
      SELECT * INTO v_approval FROM public.ecommerce_d01_source_approval
       WHERE org_id=v_org AND project_id=v_project AND selection_id=p_selection_id FOR SHARE;
      IF v_approval.selection_id IS NULL OR p_revoked_at<v_approval.approved_at
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='D01 approved selection unavailable'; END IF;
      IF p_actor IS DISTINCT FROM v_approval.checker
         AND NOT EXISTS(SELECT 1 FROM public.meta_membership
            WHERE org_id=v_org AND project_id=v_project AND subject=p_actor
              AND role IN ('admin','owner'))
      THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='D01 revoker authority unavailable'; END IF;
      v_body:=jsonb_build_object('selectionId',p_selection_id,'actor',p_actor,
        'reason',p_reason,'revokedAt',p_revoked_at);
      v_receipt:=jsonb_build_object('resourceType','D01SourceSelectionRevocation',
        'resourceId',p_selection_id,'revision',1,
        'contentHash','sha256:'||encode(digest(convert_to(v_body::text,'UTF8'),'sha256'),'hex'),
        'receiptId','d01-revocation:'||p_selection_id);
      SELECT * INTO v_existing FROM public.ecommerce_d01_source_revocation
       WHERE org_id=v_org AND project_id=v_project
         AND (selection_id=p_selection_id OR revocation_key=p_key) FOR UPDATE;
      IF FOUND THEN
        IF v_existing.selection_id IS DISTINCT FROM p_selection_id
           OR v_existing.revocation_key IS DISTINCT FROM p_key
           OR v_existing.request_hash IS DISTINCT FROM p_request_hash
           OR v_existing.actor IS DISTINCT FROM p_actor
           OR v_existing.reason IS DISTINCT FROM p_reason
           OR v_existing.revoked_at IS DISTINCT FROM p_revoked_at
           OR v_existing.receipt_ref IS DISTINCT FROM v_receipt
        THEN RAISE EXCEPTION USING ERRCODE='23505',MESSAGE='D01 revocation key or payload drifted'; END IF;
      ELSE
        INSERT INTO public.ecommerce_d01_source_revocation
          (org_id,project_id,selection_id,revocation_key,request_hash,
           actor,reason,revoked_at,receipt_ref)
        VALUES(v_org,v_project,p_selection_id,p_key,p_request_hash,
          p_actor,p_reason,p_revoked_at,v_receipt);
      END IF;
      RETURN v_receipt;
    END $$""")
    op.execute(
        f'REVOKE ALL ON FUNCTION public.ecommerce_d01_source_revoke_a0v_107({signature}) FROM PUBLIC'
    )
    op.execute(
        f'GRANT EXECUTE ON FUNCTION public.ecommerce_d01_source_revoke_a0v_107({signature}) TO aos_runtime'
    )


def downgrade() -> None:
    raise RuntimeError('D01 selection history must be retained')
