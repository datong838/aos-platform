CREATE FUNCTION public.aip_budget_consumption_fact_a0v_128(
    p_org text,p_project text,p_proposal text,p_decision text,p_actor text,p_hash text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE
    payload jsonb; expected jsonb; digest text; target_hash text;
    r public.aip_budget_receipt%ROWTYPE; v public.aip_budget_revision%ROWTYPE;
    d public.aip_budget_cost_decision%ROWTYPE;
BEGIN
    payload:=public.aip_budget_cost_actor_a0v_127(p_org,p_project,p_proposal,p_actor,p_hash);
    SELECT * INTO d FROM public.aip_budget_cost_decision WHERE org_id=p_org AND project_id=p_project
        AND proposal_id=p_proposal AND decision_id=p_decision;
    IF NOT FOUND OR d.decision<>'approved' OR d.proposal_hash IS DISTINCT FROM p_hash
       OR d.actor_subject IS DISTINCT FROM payload->>'checkerSubject'
       OR d.source_ref IS DISTINCT FROM payload->'basis'->'provider' THEN
        RAISE EXCEPTION 'BUDGET_RECONCILE_ORIGINAL_DECISION_REQUIRED' USING ERRCODE='42501';
    END IF;
    SELECT * INTO r FROM public.aip_budget_receipt WHERE org_id=p_org AND project_id=p_project
        AND operation='budget_revision.activate_cost' AND idempotency_key=p_proposal;
    IF NOT FOUND THEN RETURN jsonb_build_object('status','unresolved'); END IF;
    digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.budget-cost-consume/v1',
        'tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),'proposalId',p_proposal,
        'proposalHash',p_hash,'decisionId',p_decision));
    target_hash:=public.aip_budget_cost_hash_a0v_126(payload->'target');
    expected:=jsonb_build_object('resourceType','BudgetRevision','resourceId',payload->'target'->>'budgetId',
        'revision',payload->'target'->'revision','contentHash',target_hash,'proposalId',p_proposal,
        'proposalHash',p_hash,'decisionId',p_decision,'receiptId','budget-cost-consume-'||digest);
    IF r.request_hash IS DISTINCT FROM digest OR r.receipt_id IS DISTINCT FROM expected->>'receiptId'
       OR r.created_by IS DISTINCT FROM p_actor OR r.result_ref IS DISTINCT FROM expected THEN
        RETURN jsonb_build_object('status','conflict');
    END IF;
    SELECT * INTO v FROM public.aip_budget_revision WHERE org_id=p_org AND project_id=p_project
        AND budget_id=expected->>'resourceId' AND revision::text=expected->>'revision';
    IF NOT FOUND OR v.lifecycle<>'active' OR v.content_hash IS DISTINCT FROM target_hash
       OR v.payload->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',p_org,'projectId',p_project)
       OR v.payload->>'contentHash' IS DISTINCT FROM target_hash
       OR v.payload-ARRAY['tenant','contentHash','createdBy','createdAt'] IS DISTINCT FROM payload->'target'
       OR NOT EXISTS(SELECT 1 FROM public.aip_budget_cost_runtime_fence WHERE org_id=p_org AND project_id=p_project
            AND budget_id=v.budget_id AND revision=v.revision AND decision_id=p_decision) THEN
        RETURN jsonb_build_object('status','conflict');
    END IF;
    RETURN jsonb_build_object('status','observed','receipt',r.result_ref,'activationEligible',false);
END $$;

CREATE OR REPLACE FUNCTION public.aip_reconcile_budget_as_actor_a0v_127(
 p_org text,p_project text,p_proposal text,p_decision text,p_actor text,p_hash text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF current_setting('transaction_read_only')<>'on' OR current_setting('transaction_isolation')<>'read committed' THEN
  RAISE EXCEPTION 'BUDGET_RECONCILE_READ_ONLY_REQUIRED' USING ERRCODE='42501'; END IF;
 RETURN public.aip_budget_consumption_fact_a0v_128(p_org,p_project,p_proposal,p_decision,p_actor,p_hash);
END $$;

-- Pure derivation after immutable source verification. Not callable by the login role.
CREATE FUNCTION public.aip_cost_configuration_expected_a0v_128(
 p_org text,p_project text,p_proposal text,p_decision text,p_actor text,p_hash text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE fact jsonb; p jsonb; t jsonb; auth jsonb; price jsonb; policy jsonb; digest text;
 stamp jsonb; price_hash text; policy_hash text; budget_ref jsonb; result jsonb;
BEGIN
 fact:=public.aip_budget_consumption_fact_a0v_128(p_org,p_project,p_proposal,p_decision,p_actor,p_hash);
 IF fact->>'status' IS DISTINCT FROM 'observed' THEN
  RAISE EXCEPTION 'COST_CONFIGURATION_CONSUMED_SOURCE_REQUIRED' USING ERRCODE='42501'; END IF;
 p:=public.aip_budget_cost_actor_a0v_127(p_org,p_project,p_proposal,p_actor,p_hash);t:=p->'target';
 IF p->'basis'->>'kind' IS DISTINCT FROM 'development_risk_proposal' THEN
  RAISE EXCEPTION 'COST_CONFIGURATION_DEVELOPMENT_SOURCE_REQUIRED' USING ERRCODE='42501'; END IF;
 SELECT to_jsonb(to_char(created_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"')) INTO stamp FROM public.aip_budget_receipt WHERE org_id=p_org AND project_id=p_project
  AND operation='budget_revision.activate_cost' AND idempotency_key=p_proposal;
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.budget-cost-configuration/v1',
  'tenant',p->'tenant','proposalId',p_proposal,'proposalHash',p_hash,'decisionId',p_decision));
 auth:=jsonb_build_object('tenant',p->'tenant','provider',p->'basis'->'provider',
  'providerModelId',p->'basis'->'providerModelId','approvalRef',p_decision,'environment','development',
  'effectiveFrom',t->'effectiveFrom','effectiveUntil',t->'effectiveUntil');
 price:=jsonb_build_object('priceSnapshotId','cost-price-'||digest,'currency','CNY',
  'inputTokenPrice',NULL,'outputTokenPrice',NULL,'cachedTokenPrice',NULL,'tokenUnit',1000,
  'effectiveFrom',t->'effectiveFrom','effectiveUntil',t->'effectiveUntil','lifecycle','active','developmentCostAuthorization',auth);
 price_hash:=public.aip_budget_cost_hash_a0v_126(price);
 price:=price||jsonb_build_object('tenant',p->'tenant','revision',1,'contentHash',price_hash,'createdBy',p_actor,'createdAt',stamp);
 budget_ref:=jsonb_build_object('assetType','BudgetRevision','assetId',t->'budgetId','revision',t->'revision',
  'contentHash',fact->'receipt'->'contentHash');
 policy:=jsonb_build_object('policyId','cost-policy-'||digest,'revision',1,'environment','development',
  'effectiveFrom',t->'effectiveFrom','effectiveUntil',t->'effectiveUntil','owner',t->'owner','approvalRef',p_decision,
  'lifecycle','active','developmentCostAuthorization',auth,'budgetRevisionRef',budget_ref,'currency','CNY',
  'hardStop',true,'unknownUsageBehavior','block','unknownPriceBehavior','block','allowZeroPrice',false,'zeroPriceApprovalRef',NULL);
 policy_hash:=public.aip_budget_cost_hash_a0v_126(policy);
 policy:=policy||jsonb_build_object('tenant',p->'tenant','contentHash',policy_hash,'createdBy',p_actor,'createdAt',stamp);
 result:=jsonb_build_object('proposalId',p_proposal,'proposalHash',p_hash,'decisionId',p_decision,
  'budgetRef',budget_ref,'priceRef',jsonb_build_object('assetType','ModelPriceSnapshotRevision',
   'assetId',price->'priceSnapshotId','revision',1,'contentHash',price_hash),
  'policyRef',jsonb_build_object('assetType','BudgetPolicyRevision','assetId',policy->'policyId','revision',1,'contentHash',policy_hash),
  'receiptId','cost-configuration-'||digest);
 RETURN jsonb_build_object('price',price,'policy',policy,'receipt',result,'requestHash',digest);
END $$;

CREATE FUNCTION public.aip_cost_configuration_fact_a0v_128(
 p_org text,p_project text,p_proposal text,p_decision text,p_actor text,p_hash text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE expected jsonb; r public.aip_model_governance_policy_receipt%ROWTYPE; price jsonb; policy jsonb;
BEGIN
 expected:=public.aip_cost_configuration_expected_a0v_128(p_org,p_project,p_proposal,p_decision,p_actor,p_hash);
 SELECT * INTO r FROM public.aip_model_governance_policy_receipt WHERE org_id=p_org AND project_id=p_project
  AND operation='budget_cost.configure' AND idempotency_key=p_proposal;
 IF NOT FOUND THEN RETURN jsonb_build_object('status','unresolved'); END IF;
 IF r.request_hash IS DISTINCT FROM expected->>'requestHash' OR r.result_ref IS DISTINCT FROM expected->'receipt'
  OR r.receipt_id IS DISTINCT FROM expected->'receipt'->>'receiptId' OR r.created_by IS DISTINCT FROM p_actor THEN
  RETURN jsonb_build_object('status','conflict'); END IF;
 SELECT payload INTO price FROM public.aip_model_price_snapshot_revision WHERE org_id=p_org AND project_id=p_project
  AND model_price_snapshot_id=expected->'price'->>'priceSnapshotId' AND revision=1
  AND content_hash=expected->'price'->>'contentHash' AND lifecycle='active';
 SELECT payload INTO policy FROM public.aip_model_governance_policy_revision WHERE org_id=p_org AND project_id=p_project
  AND policy_kind='budget' AND policy_id=expected->'policy'->>'policyId' AND revision=1
  AND content_hash=expected->'policy'->>'contentHash' AND lifecycle='active';
 IF price IS DISTINCT FROM expected->'price' OR policy IS DISTINCT FROM expected->'policy' THEN
  RETURN jsonb_build_object('status','conflict'); END IF;
 RETURN jsonb_build_object('status','observed','receipt',r.result_ref,'activationEligible',false);
END $$;

CREATE FUNCTION public.aip_reconcile_cost_configuration_a0v_128(
 p_org text,p_project text,p_proposal text,p_decision text,p_actor text,p_hash text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF current_setting('transaction_read_only')<>'on' OR current_setting('transaction_isolation')<>'read committed' THEN
  RAISE EXCEPTION 'COST_CONFIGURATION_READ_ONLY_REQUIRED' USING ERRCODE='42501'; END IF;
 RETURN public.aip_cost_configuration_fact_a0v_128(p_org,p_project,p_proposal,p_decision,p_actor,p_hash);
END $$;

CREATE FUNCTION public.aip_configure_budget_cost_a0v_128(
 p_org text,p_project text,p_proposal text,p_decision text,p_actor text,p_hash text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE p jsonb; t jsonb; ref jsonb; e jsonb; prior jsonb; price jsonb; policy jsonb;
 h public.aip_budget_head%ROWTYPE; source public.aip_provider_instance_revision%ROWTYPE;
 source_revision bigint; deadline timestamptz; now_at timestamptz;
BEGIN
 IF current_setting('transaction_read_only')<>'off' OR current_setting('transaction_isolation')<>'read committed' THEN
  RAISE EXCEPTION 'COST_CONFIGURATION_WRITE_TRANSACTION_REQUIRED' USING ERRCODE='42501'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('budget-cost-review:'||p_org||':'||p_project||':'||p_proposal,0));
 prior:=public.aip_cost_configuration_fact_a0v_128(p_org,p_project,p_proposal,p_decision,p_actor,p_hash);
 IF prior->>'status'='observed' THEN RETURN prior; END IF;
 IF prior->>'status' IS DISTINCT FROM 'unresolved' THEN
  RAISE EXCEPTION 'COST_CONFIGURATION_RECEIPT_CONFLICT' USING ERRCODE='23514'; END IF;
 p:=public.aip_budget_cost_actor_a0v_127(p_org,p_project,p_proposal,p_actor,p_hash);t:=p->'target';ref:=p->'basis'->'provider';
 PERFORM subject FROM public.meta_membership WHERE org_id=p_org AND project_id=p_project
  AND subject IN(p_actor,p->>'checkerSubject') ORDER BY subject FOR SHARE;
 IF (SELECT count(*) FROM public.meta_membership WHERE org_id=p_org AND project_id=p_project
  AND subject IN(p_actor,p->>'checkerSubject') AND lower(role) IN('owner','admin'))<>2 THEN
  RAISE EXCEPTION 'COST_CONFIGURATION_CURRENT_MEMBERS_REQUIRED' USING ERRCODE='42501'; END IF;
 SELECT expires_at INTO deadline FROM public.aip_budget_cost_decision WHERE org_id=p_org AND project_id=p_project
  AND decision_id=p_decision AND proposal_id=p_proposal;
 IF EXISTS(SELECT 1 FROM public.aip_budget_cost_revocation WHERE org_id=p_org AND project_id=p_project AND decision_id=p_decision) THEN
  RAISE EXCEPTION 'COST_CONFIGURATION_REVOKED' USING ERRCODE='42501'; END IF;
 SELECT * INTO h FROM public.aip_budget_head WHERE org_id=p_org AND project_id=p_project AND budget_id=t->>'budgetId' FOR SHARE;
 IF NOT FOUND OR h.current_revision IS DISTINCT FROM (t->>'revision')::bigint
  OR h.version IS DISTINCT FROM (p->>'expectedHeadVersion')::bigint+1 THEN
  RAISE EXCEPTION 'COST_CONFIGURATION_BUDGET_HEAD_DRIFT' USING ERRCODE='23514'; END IF;
 SELECT current_revision INTO source_revision FROM public.aip_provider_instance_head WHERE org_id=p_org AND project_id=p_project
  AND provider_instance_id=ref->>'assetId' FOR SHARE;
 SELECT * INTO source FROM public.aip_provider_instance_revision WHERE org_id=p_org AND project_id=p_project
  AND provider_instance_id=ref->>'assetId' AND revision=source_revision;
 IF NOT FOUND OR (source_revision=(ref->>'revision')::bigint AND source.content_hash=ref->>'contentHash'
  AND source.lifecycle='active' AND source.payload->'tenant'=p->'tenant'
  AND source.payload->>'providerInstanceId'=source.provider_instance_id AND source.payload->>'lifecycle'='active'
  AND source.payload->>'contentHash'=source.content_hash AND (source.payload->>'revision')::bigint=source_revision
  AND public.aip_budget_cost_hash_a0v_126(source.payload-ARRAY['tenant','revision','contentHash','createdBy','createdAt'])=source.content_hash) IS NOT TRUE THEN
  RAISE EXCEPTION 'COST_CONFIGURATION_PROVIDER_DRIFT' USING ERRCODE='23514'; END IF;
 now_at:=clock_timestamp();
 IF (now_at<deadline AND (t->>'effectiveFrom')::timestamptz<=now_at AND now_at<(t->>'effectiveUntil')::timestamptz) IS NOT TRUE THEN
  RAISE EXCEPTION 'COST_CONFIGURATION_EXPIRED' USING ERRCODE='42501'; END IF;
 e:=public.aip_cost_configuration_expected_a0v_128(p_org,p_project,p_proposal,p_decision,p_actor,p_hash);price:=e->'price';policy:=e->'policy';
 INSERT INTO public.aip_model_price_snapshot_head(org_id,project_id,model_price_snapshot_id,current_revision,version)
  VALUES(p_org,p_project,price->>'priceSnapshotId',1,1);
 INSERT INTO public.aip_model_price_snapshot_revision(org_id,project_id,model_price_snapshot_id,revision,content_hash,lifecycle,payload,created_by,created_at)
  VALUES(p_org,p_project,price->>'priceSnapshotId',1,price->>'contentHash','active',price,p_actor,(price->>'createdAt')::timestamptz);
 INSERT INTO public.aip_model_governance_policy_head(org_id,project_id,policy_kind,policy_id,current_revision,version)
  VALUES(p_org,p_project,'budget',policy->>'policyId',1,1);
 INSERT INTO public.aip_model_governance_policy_revision(org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,
  effective_from,effective_until,payload,created_by,created_at)
  VALUES(p_org,p_project,'budget',policy->>'policyId',1,policy->>'contentHash','active',
   (policy->>'effectiveFrom')::timestamptz,(policy->>'effectiveUntil')::timestamptz,policy,p_actor,(policy->>'createdAt')::timestamptz);
 INSERT INTO public.aip_model_governance_policy_receipt(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by)
  VALUES(p_org,p_project,e->'receipt'->>'receiptId','budget_cost.configure',p_proposal,e->>'requestHash',e->'receipt',p_actor);
 IF clock_timestamp()>=deadline OR clock_timestamp()>=(t->>'effectiveUntil')::timestamptz THEN
  RAISE EXCEPTION 'COST_CONFIGURATION_EXPIRED' USING ERRCODE='42501'; END IF;
 RETURN jsonb_build_object('status','observed','receipt',e->'receipt','activationEligible',false);
END $$;
