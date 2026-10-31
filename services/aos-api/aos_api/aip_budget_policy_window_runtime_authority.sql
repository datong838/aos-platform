-- Child provenance only. Parent authorization and current head locks belong to
-- the original verifier in this same caller-owned transaction. No execution grant.
CREATE FUNCTION public.aip_policy_window_risk_fact_v1(budget_ref jsonb, price_ref jsonb)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE login pg_catalog.pg_roles%ROWTYPE; profile pg_catalog.pg_roles%ROWTYPE;
 b public.aip_budget_policy_window_binding%ROWTYPE;
 d public.aip_budget_policy_window_decision%ROWTYPE;
 r public.aip_budget_policy_window_receipt%ROWTYPE;
 f public.aip_budget_policy_window_fence%ROWTYPE;
 price_row public.aip_model_price_snapshot_revision%ROWTYPE;
 policy_row public.aip_model_governance_policy_revision%ROWTYPE;
 p jsonb; c jsonb; dc jsonb; tenant jsonb:=jsonb_build_object('orgId','org-org','projectId','dev-project');
 ident text; expected_binding jsonb; expected_result jsonb; expected_decision jsonb;
 policy_hash text; price_hash text; policy_ref jsonb; policy jsonb; price jsonb;
 stamp text; digest text; receipt_id text; binding_id text; from_at timestamptz; until_at timestamptz;
BEGIN
 IF (current_user='aos_budget_consumer_owner'
  AND current_setting('transaction_isolation')='serializable'
  AND current_setting('transaction_read_only')='off'
  AND current_setting('aos.org_id',true)='org-org'
  AND current_setting('aos.project_id',true)='dev-project') IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_NATIVE_TRANSACTION_REQUIRED' USING ERRCODE='42501'; END IF;
 SELECT * INTO STRICT login FROM pg_catalog.pg_roles WHERE rolname=session_user;
 IF (login.rolcanlogin AND NOT (login.rolsuper OR login.rolbypassrls OR login.rolinherit
    OR login.rolcreatedb OR login.rolcreaterole OR login.rolreplication)
    AND NOT has_schema_privilege(session_user,'public','CREATE')) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_LOGIN_PROFILE_REQUIRED' USING ERRCODE='42501'; END IF;
 SELECT * INTO STRICT profile FROM pg_catalog.pg_roles WHERE rolname=current_user;
 IF profile.rolcanlogin OR profile.rolsuper OR profile.rolbypassrls OR profile.rolinherit
  OR profile.rolcreatedb OR profile.rolcreaterole OR profile.rolreplication
  OR EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members WHERE roleid=profile.oid OR member=profile.oid) THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_OWNER_PROFILE_REQUIRED' USING ERRCODE='42501'; END IF;
 IF session_user='aos_a0v_runtime_20260912' AND current_setting('role')='aos_runtime' THEN
  SELECT * INTO STRICT profile FROM pg_catalog.pg_roles WHERE rolname='aos_runtime';
  IF profile.rolcanlogin OR profile.rolsuper OR profile.rolbypassrls OR profile.rolinherit
   OR profile.rolcreatedb OR profile.rolcreaterole OR profile.rolreplication
   OR EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members WHERE member=profile.oid)
   OR (SELECT count(*) FROM pg_catalog.pg_auth_members WHERE member=login.oid)<>1
   OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members WHERE member=login.oid AND roleid=profile.oid
      AND set_option AND NOT inherit_option AND NOT admin_option) THEN
   RAISE EXCEPTION 'POLICY_WINDOW_RISK_RUNTIME_PROFILE_REQUIRED' USING ERRCODE='42501'; END IF;
 ELSIF session_user='aos_aip_binding_evaluator'
   AND current_setting('role') IN('none','aos_aip_binding_evaluator') THEN
  IF EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members WHERE roleid=login.oid OR member=login.oid) THEN
   RAISE EXCEPTION 'POLICY_WINDOW_RISK_EVALUATOR_PROFILE_REQUIRED' USING ERRCODE='42501'; END IF;
 ELSE RAISE EXCEPTION 'POLICY_WINDOW_RISK_ACTUAL_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
 IF (jsonb_typeof(budget_ref)='object' AND jsonb_typeof(price_ref)='object') IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_EXACT_REFS_REQUIRED' USING ERRCODE='22023'; END IF;
 IF (budget_ref-ARRAY['assetType','assetId','revision','contentHash']='{}'::jsonb
  AND price_ref-ARRAY['assetType','assetId','revision','contentHash']='{}'::jsonb
  AND budget_ref ?& ARRAY['assetType','assetId','revision','contentHash']
  AND price_ref ?& ARRAY['assetType','assetId','revision','contentHash']
  AND budget_ref->>'assetType'='BudgetRevision' AND price_ref->>'assetType'='ModelPriceSnapshotRevision'
  AND jsonb_typeof(budget_ref->'assetId')='string' AND length(budget_ref->>'assetId') BETWEEN 1 AND 240
  AND budget_ref->>'assetId'=btrim(budget_ref->>'assetId')
  AND jsonb_typeof(price_ref->'assetId')='string' AND price_ref->>'assetId' ~ '^window-price-[0-9a-f]{64}$'
  AND jsonb_typeof(budget_ref->'revision')='number' AND budget_ref->>'revision' ~ '^[1-9][0-9]{0,15}$'
  AND (budget_ref->>'revision')::bigint<=9007199254740991
  AND jsonb_typeof(price_ref->'revision')='number' AND price_ref->>'revision'='1'
  AND jsonb_typeof(budget_ref->'contentHash')='string' AND budget_ref->>'contentHash' ~ '^[0-9a-f]{64}$'
  AND jsonb_typeof(price_ref->'contentHash')='string' AND price_ref->>'contentHash' ~ '^[0-9a-f]{64}$'
  AND octet_length(budget_ref::text)<=4096 AND octet_length(price_ref::text)<=4096) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_EXACT_REFS_REQUIRED' USING ERRCODE='22023'; END IF;
 SELECT * INTO STRICT b FROM public.aip_budget_policy_window_binding AS binding
  WHERE binding.org_id='org-org' AND binding.project_id='dev-project'
  AND binding.price_ref=aip_policy_window_risk_fact_v1.price_ref;
 -- This literal false branch verifies immutable proof without calling the
 -- purpose-only parent/current/command-execution paths or borrowing their login.
 p:=public.aip_policy_window_proposal_fact_v1(b.proposal_id,b.payload->>'proposalHash',false);
 c:=p->'request';
 ident:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.window-proposal-id/v1',
  'tenant',tenant,'maker',p->>'makerSubject','key',c->>'idempotencyKey'));
 IF (b.proposal_id='window-proposal-'||ident AND p->>'approvalSlot'='window-approval-'||ident
  AND p->'parent'->'budgetRef'=budget_ref AND c->'expectedBudgetRef'=budget_ref
  AND p->'parent'->>'costProposalId'=c->>'parentCostProposalId'
  AND p->'parent'->>'costProposalHash'=c->>'parentCostProposalHash'
  AND p->'parent'->>'costDecisionId'=c->>'parentCostDecisionId'
  AND p->'parent'->>'consumptionReceiptId'=c->>'parentConsumptionReceiptId'
  AND p->'parent'->'budgetHeadVersion'=c->'expectedBudgetHeadVersion'
  AND p->'parent'->'providerRef'=c->'expectedProviderRef'
  AND p->'parent'->'providerModelId'=c->'expectedProviderModelId') IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_PARENT_LINK_DRIFT' USING ERRCODE='23514'; END IF;
 PERFORM subject FROM public.meta_membership WHERE org_id='org-org' AND project_id='dev-project'
  AND subject IN(p->>'makerSubject',p->>'checkerSubject') ORDER BY subject FOR SHARE;
 IF (SELECT count(*) FROM public.meta_membership WHERE org_id='org-org' AND project_id='dev-project'
  AND subject IN(p->>'makerSubject',p->>'checkerSubject') AND lower(role) IN('owner','admin'))<>2 THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_CURRENT_CHILD_MEMBERS_REQUIRED' USING ERRCODE='42501'; END IF;
 SELECT * INTO STRICT f FROM public.aip_budget_policy_window_fence WHERE org_id=b.org_id
  AND project_id=b.project_id AND proposal_id=b.proposal_id FOR SHARE;
 IF f.revoked OR f.version<>2 OR EXISTS(SELECT 1 FROM public.aip_budget_policy_window_decision
  WHERE org_id=b.org_id AND project_id=b.project_id AND proposal_id=b.proposal_id AND decision='revoked') THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_CHILD_REVOKED' USING ERRCODE='42501'; END IF;
 SELECT * INTO STRICT d FROM public.aip_budget_policy_window_decision WHERE org_id=b.org_id
  AND project_id=b.project_id AND decision_id=b.decision_id AND proposal_id=b.proposal_id;
 dc:=d.payload->'command';PERFORM public.aip_policy_window_command_v1(dc,'decide');
 expected_decision:=jsonb_build_object('operation','decide','command',dc,'actorSubject',p->>'checkerSubject',
  'proposalId',b.proposal_id,'proposalHash',b.payload->>'proposalHash','targetPairHash',p->'targetPairHash',
  'decisionId',p->>'approvalSlot','decision','approved','createdAt',d.payload->>'createdAt');
 IF (d.decision='approved' AND d.decision_id=p->>'approvalSlot' AND d.actor_subject=p->>'checkerSubject'
  AND d.payload=expected_decision AND dc->>'decision'='approved'
  AND dc->>'proposalId'=b.proposal_id AND dc->>'proposalHash'=b.payload->>'proposalHash'
  AND dc->'targetPairHash'=p->'targetPairHash'
  AND d.decision_hash=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
    'domain','aos.budget-policy-window.decision/v1','decision',d.payload))
  AND d.created_at=(d.payload->>'createdAt')::timestamptz
  AND d.created_at>=(p->>'createdAt')::timestamptz AND d.created_at<(p->>'expiresAt')::timestamptz) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_EXACT_CHILD_APPROVAL_REQUIRED' USING ERRCODE='23514'; END IF;
 SELECT * INTO STRICT r FROM public.aip_budget_policy_window_receipt WHERE org_id=b.org_id
  AND project_id=b.project_id AND proposal_id=b.proposal_id AND operation='consume';
 c:=r.payload->'command';PERFORM public.aip_policy_window_command_v1(c,'consume');
 policy_hash:=public.aip_budget_cost_hash_a0v_126(p->'targets'->'policy');
 price_hash:=public.aip_budget_cost_hash_a0v_126(p->'targets'->'price');
 policy_ref:=jsonb_build_object('assetType','BudgetPolicyRevision',
  'assetId',p->'targets'->'policy'->>'policyId','revision',1,'contentHash',policy_hash);
 IF price_ref IS DISTINCT FROM jsonb_build_object('assetType','ModelPriceSnapshotRevision',
  'assetId',p->'targets'->'price'->>'priceSnapshotId','revision',1,'contentHash',price_hash) THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_EXACT_CHILD_PRICE_REQUIRED' USING ERRCODE='23514'; END IF;
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
  'domain','aos.budget-policy-window.consume/v1','command',c-'idempotencyKey'));
 receipt_id:='window-consume-'||public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
  'domain','aos.policy-window-receipt-id/v1','operation','consume','actor',p->>'makerSubject',
  'tenant',tenant,'key',c->>'idempotencyKey'));
 binding_id:='window-binding-'||public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
  'domain','aos.policy-window-binding-id/v1','tenant',tenant,'proposalId',b.proposal_id,
  'decisionId',d.decision_id,'targetPairHash',p->'targetPairHash'));
 expected_binding:=jsonb_build_object('bindingId',binding_id,'tenant',tenant,'parent',p->'parent',
  'proposalId',b.proposal_id,'proposalHash',b.payload->>'proposalHash','decisionId',d.decision_id,
  'decisionHash',d.decision_hash,'targetPairHash',p->'targetPairHash','policyRef',policy_ref,
  'priceRef',price_ref,'receiptId',receipt_id);
 expected_result:=jsonb_build_object('status','observed','operation','consume','command',c,'requestHash',digest,
  'proposalId',b.proposal_id,'proposalHash',b.payload->>'proposalHash','decisionId',d.decision_id,
  'decisionHash',d.decision_hash,'targetPairHash',p->'targetPairHash','budgetRef',budget_ref,
  'policyRef',policy_ref,'priceRef',price_ref,'bindingId',binding_id,'bindingHash',b.binding_hash,
  'receiptId',receipt_id,'activationEligible',false);
 IF (b.binding_id=binding_id AND b.payload=expected_binding
  AND b.binding_hash=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
   'domain','aos.budget-policy-window.binding/v1','binding',expected_binding))
  AND b.policy_ref=policy_ref AND b.price_ref=price_ref AND b.receipt_id=receipt_id
  AND b.transaction_id=r.transaction_id AND r.receipt_id=receipt_id AND r.decision_id=d.decision_id
  AND r.actor_subject=p->>'makerSubject' AND r.request_hash=digest
  AND r.idempotency_key=c->>'idempotencyKey' AND r.payload=expected_result
  AND c->>'proposalId'=b.proposal_id AND c->>'proposalHash'=b.payload->>'proposalHash'
  AND c->>'decisionId'=d.decision_id AND c->>'decisionHash'=d.decision_hash
  AND c->'targetPairHash'=p->'targetPairHash'
  AND r.created_at>=d.created_at AND r.created_at<(p->>'expiresAt')::timestamptz) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_ATOMIC_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
 SELECT * INTO STRICT price_row FROM public.aip_model_price_snapshot_revision WHERE org_id=b.org_id
  AND project_id=b.project_id AND model_price_snapshot_id=price_ref->>'assetId'
  AND revision=1 AND content_hash=price_hash AND lifecycle='active';
 SELECT * INTO STRICT policy_row FROM public.aip_model_governance_policy_revision WHERE org_id=b.org_id
  AND project_id=b.project_id AND policy_kind='budget' AND policy_id=policy_ref->>'assetId'
  AND revision=1 AND content_hash=policy_hash AND lifecycle='active';
 price:=price_row.payload;policy:=policy_row.payload;stamp:=price->>'createdAt';
 IF (price=(p->'targets'->'price')||jsonb_build_object('tenant',tenant,'revision',1,
    'contentHash',price_hash,'createdBy',p->>'makerSubject','createdAt',stamp)
  AND policy=(p->'targets'->'policy')||jsonb_build_object('tenant',tenant,
    'contentHash',policy_hash,'createdBy',p->>'makerSubject','createdAt',stamp)
  AND price_row.created_by=p->>'makerSubject' AND policy_row.created_by=p->>'makerSubject'
  AND price_row.created_at=stamp::timestamptz AND policy_row.created_at=stamp::timestamptz
  AND policy_row.effective_from=(p->'request'->>'effectiveFrom')::timestamptz
  AND policy_row.effective_until=(p->'request'->>'effectiveUntil')::timestamptz
  AND EXISTS(SELECT 1 FROM public.aip_model_price_snapshot_head WHERE org_id=b.org_id
   AND project_id=b.project_id AND model_price_snapshot_id=price_ref->>'assetId' AND current_revision=1 AND version=1)
  AND EXISTS(SELECT 1 FROM public.aip_model_governance_policy_head WHERE org_id=b.org_id
   AND project_id=b.project_id AND policy_kind='budget' AND policy_id=policy_ref->>'assetId'
   AND current_revision=1 AND version=1)) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_CURRENT_PAIR_REQUIRED' USING ERRCODE='23514'; END IF;
 from_at:=(p->'request'->>'effectiveFrom')::timestamptz;
 until_at:=(p->'request'->>'effectiveUntil')::timestamptz;
 IF (from_at<=clock_timestamp() AND clock_timestamp()<until_at
  AND (p->'parent'->'budgetWindow'->>'effectiveFrom')::timestamptz<=from_at
  AND until_at<(p->'parent'->'budgetWindow'->>'effectiveUntil')::timestamptz) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RISK_CURRENT_WINDOW_REQUIRED' USING ERRCODE='23514'; END IF;
 RETURN jsonb_build_object('schema','aos-policy-window-risk-fact/v1','factOnly',true,'activationEligible',false,
  'parent',p->'parent','policyRef',policy_ref,'priceRef',price_ref,'proposalId',b.proposal_id,
  'proposalHash',b.payload->>'proposalHash','decisionId',d.decision_id,'decisionHash',d.decision_hash,
  'receiptId',r.receipt_id,'bindingId',b.binding_id,'bindingHash',b.binding_hash,'fenceVersion',f.version,
  'effectiveFrom',p->'request'->'effectiveFrom','effectiveUntil',p->'request'->'effectiveUntil');
END $$;
