"""Repair schedule-control Case hash lookup without changing stored authority."""

from alembic import op


revision = "a0v_079"
down_revision = "a0v_078"
branch_labels = depends_on = None


def upgrade():
    op.execute(r"""
    CREATE OR REPLACE FUNCTION public.ecommerce_schedule_policy_control_put_a0v_078(request jsonb)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE
      v_org text:=NULLIF(current_setting('aos.org_id',true),'');
      v_project text:=NULLIF(current_setting('aos.project_id',true),'');
      v_key text:=request->>'idempotencyKey';v_policy jsonb:=request->'policyRef';
      v_case jsonb:=request->'caseRef';v_approval_ref jsonb:=request->'approvalRef';
      v_dispatch jsonb:=request->'dispatch';v_request_hash text;
      v_existing record;v_command record;v_policy_head record;v_case_head record;
      v_approval record;v_proposal record;v_route record;v_body jsonb;v_hash text;v_authority jsonb;v_receipt uuid;
    BEGIN
      IF request->>'schemaVersion' IS DISTINCT FROM 'aos.ecommerce.schedule-policy-control/v1'
        OR request->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',v_org,'projectId',v_project)
        OR (length(v_key) BETWEEN 1 AND 200 AND btrim(v_key)=v_key) IS NOT TRUE
        OR (SELECT array_agg(k ORDER BY k COLLATE "C") FROM jsonb_object_keys(request) k)
          IS DISTINCT FROM ARRAY['approvalRef','caseRef','dispatch','idempotencyKey','policyRef','schemaVersion','tenant']::text[]
        OR v_policy->>'resourceType' IS DISTINCT FROM 'SchedulePolicyRevision'
        OR v_case->>'resourceType' IS DISTINCT FROM 'BusinessInvestigationCaseRevision'
        OR v_approval_ref->>'resourceType' IS DISTINCT FROM 'ActionApprovalEvent'
        OR (v_policy->>'contentHash' ~ '^sha256:[0-9a-f]{64}$') IS NOT TRUE
        OR (v_case->>'contentHash' ~ '^sha256:[0-9a-f]{64}$') IS NOT TRUE
        OR (v_approval_ref->>'contentHash' ~ '^sha256:[0-9a-f]{64}$') IS NOT TRUE
        OR (v_policy->>'revision' ~ '^[1-9][0-9]*$') IS NOT TRUE
        OR (v_case->>'revision' ~ '^[1-9][0-9]*$') IS NOT TRUE
        OR (v_approval_ref->>'revision' ~ '^[1-9][0-9]*$') IS NOT TRUE
        OR (v_dispatch->>'executionEpoch' ~ '^[1-9][0-9]*$') IS NOT TRUE
      THEN RAISE EXCEPTION 'exact schedule policy control request required' USING ERRCODE='22023'; END IF;
      v_request_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(request),'UTF8')),'hex');
      SELECT * INTO v_existing FROM public.ecommerce_schedule_policy_control_receipt
        WHERE org_id=v_org AND project_id=v_project AND idempotency_key=v_key;
      IF FOUND THEN
        IF v_existing.request_hash IS DISTINCT FROM v_request_hash THEN
          RAISE EXCEPTION 'schedule control idempotency conflict' USING ERRCODE='40001'; END IF;
        RETURN v_existing.authority;
      END IF;
      SELECT current_revision,content_hash INTO v_policy_head FROM public.ecommerce_investigation_schedule_policy_head
        WHERE org_id=v_org AND project_id=v_project AND schedule_policy_id=v_policy->>'resourceId' FOR SHARE;
      SELECT h.current_revision,r.content_hash INTO v_case_head
        FROM public.ecommerce_investigation_case_head h
        JOIN public.ecommerce_investigation_case_revision r
          ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.case_id=h.case_id
         AND r.revision=h.current_revision
        WHERE h.org_id=v_org AND h.project_id=v_project AND h.case_id=v_case->>'resourceId' FOR SHARE OF h;
      IF NOT FOUND OR v_policy_head.current_revision IS DISTINCT FROM (v_policy->>'revision')::bigint
        OR v_policy_head.content_hash IS DISTINCT FROM v_policy->>'contentHash'
        OR v_case_head.current_revision IS DISTINCT FROM (v_case->>'revision')::bigint
        OR v_case_head.content_hash IS DISTINCT FROM v_case->>'contentHash'
      THEN RAISE EXCEPTION 'schedule control current authority differs' USING ERRCODE='40001'; END IF;
      SELECT receipt_id,expected_policy_revision,expected_case_version,policy_authority,case_authority
        INTO v_command FROM public.ecommerce_investigation_schedule_policy_command_receipt
        WHERE org_id=v_org AND project_id=v_project
          AND schedule_policy_id=v_policy->>'resourceId' AND result_policy_revision=(v_policy->>'revision')::bigint
          AND case_id=v_case->>'resourceId' AND result_case_revision=(v_case->>'revision')::bigint;
      IF NOT FOUND OR v_command.policy_authority->>'contentHash' IS DISTINCT FROM v_policy->>'contentHash'
        OR v_command.case_authority->>'contentHash' IS DISTINCT FROM v_case->>'contentHash'
      THEN RAISE EXCEPTION 'schedule command Receipt differs' USING ERRCODE='40001'; END IF;
      SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,actor_id,reason,
             expires_at,created_at,action_binding_hash INTO v_approval
        FROM public.aip_action_approval_event WHERE org_id=v_org AND project_id=v_project
          AND approval_event_id=v_approval_ref->>'resourceId' FOR SHARE;
      SELECT proposal_id,action_type_id,payload,proposal_hash,status,action_binding_hash INTO v_proposal
        FROM public.aip_action_proposal WHERE org_id=v_org AND project_id=v_project
          AND proposal_id=v_approval.proposal_id FOR SHARE;
      IF v_approval.decision IS DISTINCT FROM 'approved'
        OR v_approval.proposal_version IS DISTINCT FROM (v_approval_ref->>'revision')::bigint
        OR v_approval.expires_at IS NULL OR v_approval.expires_at<=clock_timestamp()
        OR v_proposal.action_type_id IS DISTINCT FROM 'ecommerce_growth_schedule_put'
        OR v_proposal.status IS DISTINCT FROM 'approved'
        OR v_proposal.proposal_hash IS DISTINCT FROM v_approval.proposal_hash
        OR v_proposal.action_binding_hash IS DISTINCT FROM v_approval.action_binding_hash
        OR v_proposal.payload->>'caseId' IS DISTINCT FROM v_case->>'resourceId'
        OR v_proposal.payload->>'schedulePolicyId' IS DISTINCT FROM v_policy->>'resourceId'
        OR v_proposal.payload->>'policyHash' IS DISTINCT FROM v_policy->>'contentHash'
        OR v_proposal.payload->'expectedPolicyRevision' IS DISTINCT FROM to_jsonb(v_command.expected_policy_revision)
        OR v_proposal.payload->'expectedCaseVersion' IS DISTINCT FROM to_jsonb(v_command.expected_case_version)
      THEN RAISE EXCEPTION 'schedule control approval differs' USING ERRCODE='40001'; END IF;
      IF v_approval_ref->>'contentHash' IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
        public.canonical_asset_registry_jsonb(jsonb_build_object(
          'approval_event_id',v_approval.approval_event_id,'proposal_id',v_approval.proposal_id,
          'proposal_version',v_approval.proposal_version,'proposal_hash',v_approval.proposal_hash,
          'decision',v_approval.decision,'actor_id',v_approval.actor_id,'reason',v_approval.reason,
          'expires_at',v_approval.expires_at,'created_at',v_approval.created_at,
          'action_binding_hash',v_approval.action_binding_hash)),'UTF8')),'hex')
      THEN RAISE EXCEPTION 'schedule control approval hash differs' USING ERRCODE='40001'; END IF;
      SELECT handler_kind,installation_id,generation,execution_epoch,operation_fence INTO v_route
        FROM public.extension_operation_dispatch_binding WHERE org_id=v_org AND project_id=v_project
          AND operation_id='ecommerce_growth_schedule_put' FOR SHARE;
      IF v_route.handler_kind IS DISTINCT FROM 'extension' OR v_route.operation_fence IS DISTINCT FROM false
        OR v_route.installation_id::text IS DISTINCT FROM v_dispatch->>'installationId'
        OR v_route.generation::text IS DISTINCT FROM v_dispatch->>'generation'
        OR v_route.execution_epoch IS DISTINCT FROM (v_dispatch->>'executionEpoch')::bigint
      THEN RAISE EXCEPTION 'schedule control dispatch differs' USING ERRCODE='40001'; END IF;
      v_receipt:=gen_random_uuid();
      v_body:=jsonb_build_object('schemaVersion','aos.ecommerce.schedule-policy-control-receipt/v1',
        'tenant',request->'tenant','policyRef',v_policy,'caseRef',v_case,'approvalRef',v_approval_ref,
        'commandReceiptId',v_command.receipt_id,'dispatch',v_dispatch);
      v_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(v_body),'UTF8')),'hex');
      v_authority:=v_body||jsonb_build_object('receiptRef',jsonb_build_object(
        'resourceType','SchedulePolicyControlReceipt','resourceId',v_receipt::text,'revision',1,'contentHash',v_hash),
        'contentHash',v_hash);
      INSERT INTO public.ecommerce_schedule_policy_control_receipt(org_id,project_id,receipt_id,idempotency_key,
        request_hash,schedule_policy_id,policy_revision,case_id,case_revision,approval_event_id,command_receipt_id,
        installation_id,generation,execution_epoch,authority,content_hash)
      VALUES(v_org,v_project,v_receipt,v_key,v_request_hash,v_policy->>'resourceId',(v_policy->>'revision')::bigint,
        v_case->>'resourceId',(v_case->>'revision')::bigint,v_approval_ref->>'resourceId',v_command.receipt_id,
        (v_dispatch->>'installationId')::uuid,(v_dispatch->>'generation')::uuid,
        (v_dispatch->>'executionEpoch')::bigint,v_authority,v_hash);
      RETURN v_authority;
    END $$;
    REVOKE ALL ON FUNCTION public.ecommerce_schedule_policy_control_put_a0v_078(jsonb)
      FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.ecommerce_schedule_policy_control_put_a0v_078(jsonb)
      TO aos_runtime,aos_extension_maintainer;

    """)


def downgrade():
    raise RuntimeError("schedule policy control authority repair must be retained")
