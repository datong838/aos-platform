CREATE FUNCTION public.aip_consume_budget_cost_a0v_126(p_org text,p_project text,p_proposal text,p_decision text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE
  p public.aip_budget_cost_proposal%ROWTYPE; d public.aip_budget_cost_decision%ROWTYPE;
  h public.aip_budget_head%ROWTYPE; draft public.aip_budget_revision%ROWTYPE;
  source public.aip_provider_instance_revision%ROWTYPE; prior public.aip_budget_receipt%ROWTYPE;
  t jsonb; basis jsonb; ref jsonb; payload jsonb; result jsonb; expected jsonb;
  request_hash text; target_hash text; source_revision bigint; checked_at timestamptz; number_value jsonb;
BEGIN
  IF session_user<>'aos_budget_consumer_call' OR current_user<>'aos_budget_consumer_owner'
     OR p_org IS DISTINCT FROM 'org-org' OR p_project IS DISTINCT FROM 'dev-project'
     OR p_proposal IS NULL OR p_proposal='' OR p_proposal<>btrim(p_proposal)
     OR p_decision IS NULL OR p_decision='' OR p_decision<>btrim(p_decision)
     OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project
     OR current_setting('transaction_isolation')<>'read committed'
     OR current_setting('transaction_read_only')<>'off' THEN
    RAISE EXCEPTION 'BUDGET_CONSUMER_IDENTITY_SCOPE_REQUIRED' USING ERRCODE='42501';
  END IF;
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname IN (session_user,current_user)
       AND (rolsuper OR rolinherit OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
         OR (rolname=current_user AND rolcanlogin)))
     OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid IN(session_user::regrole,current_user::regrole)
       OR member IN(session_user::regrole,current_user::regrole)) THEN
    RAISE EXCEPTION 'BUDGET_CONSUMER_ROLE_DRIFT' USING ERRCODE='42501';
  END IF;
  -- Same exclusion key as the issuer. READ COMMITTED observes a committed revoke after waiting.
  PERFORM pg_advisory_xact_lock(hashtextextended('budget-cost-review:'||p_org||':'||p_project||':'||p_proposal,0));
  SELECT * INTO p FROM public.aip_budget_cost_proposal WHERE org_id=p_org AND project_id=p_project AND proposal_id=p_proposal;
  IF NOT FOUND OR p.status<>'proposed' OR p.source_verification<>'pending' OR p.activation_eligible
     OR public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.budget-cost-proposal/v1','proposal',p.payload))<>p.proposal_hash THEN
    RAISE EXCEPTION 'BUDGET_CONSUMER_PROPOSAL_DRIFT' USING ERRCODE='23514';
  END IF;
  request_hash:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.budget-cost-consume/v1',
    'tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),'proposalId',p_proposal,
    'proposalHash',p.proposal_hash,'decisionId',p_decision));
  SELECT * INTO prior FROM public.aip_budget_receipt WHERE org_id=p_org AND project_id=p_project
    AND operation='budget_revision.activate_cost' AND idempotency_key=p_proposal;
  IF FOUND THEN
    IF prior.request_hash<>request_hash OR prior.result_ref->>'decisionId' IS DISTINCT FROM p_decision
       OR prior.result_ref->>'proposalId' IS DISTINCT FROM p_proposal
       OR prior.result_ref->>'receiptId' IS DISTINCT FROM prior.receipt_id
       OR NOT EXISTS(SELECT 1 FROM public.aip_budget_cost_runtime_fence f WHERE f.org_id=p_org AND f.project_id=p_project
          AND f.budget_id=prior.result_ref->>'resourceId' AND f.revision=(prior.result_ref->>'revision')::bigint AND f.decision_id=p_decision)
       OR NOT EXISTS(SELECT 1 FROM public.aip_budget_revision r WHERE r.org_id=p_org AND r.project_id=p_project
          AND r.budget_id=prior.result_ref->>'resourceId' AND r.revision=(prior.result_ref->>'revision')::bigint
          AND r.content_hash=prior.result_ref->>'contentHash' AND r.lifecycle='active') THEN
      RAISE EXCEPTION 'BUDGET_CONSUMER_RECEIPT_DRIFT' USING ERRCODE='23514';
    END IF;
    RETURN prior.result_ref;
  END IF;
  t:=p.payload->'target';basis:=p.payload->'basis';ref:=basis->'provider';
  FOREACH number_value IN ARRAY ARRAY[t->'revision',t->'dailyLimitMinor',t->'monthlyLimitMinor',t->'alertThresholdPct',
      p.payload->'draftRevision',p.payload->'expectedHeadVersion',basis->'perRequestRiskMinor',basis->'totalRiskMinor',basis->'maxRequests',ref->'revision'] LOOP
    IF (jsonb_typeof(number_value)='number' AND number_value::text ~ '^[1-9][0-9]*$'
        AND number_value::text::numeric<=9007199254740991) IS NOT TRUE THEN
      RAISE EXCEPTION 'BUDGET_CONSUMER_EXACT_INTEGER_REQUIRED' USING ERRCODE='23514';
    END IF;
  END LOOP;
  SELECT * INTO d FROM public.aip_budget_cost_decision WHERE org_id=p_org AND project_id=p_project
    AND proposal_id=p_proposal AND decision_id=p_decision;
  IF NOT FOUND OR d.decision<>'approved' OR d.proposal_hash<>p.proposal_hash OR d.actor_subject<>p.checker_subject
     OR d.expires_at<>p.expires_at OR d.source_ref IS DISTINCT FROM ref
     OR EXISTS(SELECT 1 FROM public.aip_budget_cost_revocation WHERE org_id=p_org AND project_id=p_project AND decision_id=p_decision) THEN
    RAISE EXCEPTION 'BUDGET_CONSUMER_APPROVAL_UNAVAILABLE' USING ERRCODE='42501';
  END IF;
  PERFORM subject FROM public.meta_membership WHERE org_id=p_org AND project_id=p_project
    AND subject IN(p.maker_subject,p.checker_subject) ORDER BY subject FOR SHARE;
  IF p.maker_subject=p.checker_subject OR (SELECT count(*) FROM public.meta_membership WHERE org_id=p_org
    AND project_id=p_project AND subject IN(p.maker_subject,p.checker_subject) AND lower(role) IN('owner','admin'))<>2 THEN
    RAISE EXCEPTION 'BUDGET_CONSUMER_CURRENT_MEMBER_REQUIRED' USING ERRCODE='42501';
  END IF;
  IF (p.payload->'schemaVersion'='1'::jsonb AND p.payload->'tenant'=jsonb_build_object('orgId',p_org,'projectId',p_project)
      AND p.payload->>'makerSubject'=p.maker_subject AND p.payload->>'checkerSubject'=p.checker_subject
      AND t->>'budgetId'=p.budget_id AND t->>'environment'='development' AND t->>'lifecycle'='active'
      AND t->>'currency'='CNY' AND t->'hardStop'='true'::jsonb AND t->>'unknownUsageBehavior'='block'
      AND p.payload->'accounts'=jsonb_build_object('daily',p.budget_id||':daily','pilot',p.budget_id||':pilot')
      AND p.payload->>'currency'='CNY' AND p.payload->'period'=jsonb_build_object('start',t->'effectiveFrom','end',t->'effectiveUntil')
      AND basis->>'kind'='development_risk_proposal' AND ref->>'assetType'='ProviderInstanceRevision'
      AND length(btrim(basis->>'providerModelId')) BETWEEN 1 AND 240
      AND (basis->>'perRequestRiskMinor')::numeric>0 AND (basis->>'maxRequests')::numeric>0
      AND (basis->>'perRequestRiskMinor')::numeric*(basis->>'maxRequests')::numeric<=(basis->>'totalRiskMinor')::numeric
      AND (basis->>'perRequestRiskMinor')::numeric<=(t->>'dailyLimitMinor')::numeric
      AND (basis->>'totalRiskMinor')::numeric<=(t->>'monthlyLimitMinor')::numeric) IS NOT TRUE THEN
    RAISE EXCEPTION 'BUDGET_CONSUMER_TARGET_INVALID' USING ERRCODE='23514';
  END IF;
  SELECT * INTO h FROM public.aip_budget_head WHERE org_id=p_org AND project_id=p_project AND budget_id=p.budget_id FOR UPDATE;
  IF NOT FOUND OR h.version<>(p.payload->>'expectedHeadVersion')::bigint
     OR h.current_revision<>(p.payload->>'draftRevision')::bigint OR (t->>'revision')::bigint<>h.current_revision+1 THEN
    RAISE EXCEPTION 'BUDGET_CONSUMER_HEAD_DRIFT' USING ERRCODE='23514';
  END IF;
  SELECT * INTO draft FROM public.aip_budget_revision WHERE org_id=p_org AND project_id=p_project
    AND budget_id=p.budget_id AND revision=h.current_revision;
  expected:=draft.payload-ARRAY['tenant','contentHash','createdBy','createdAt'];
  IF NOT FOUND OR draft.lifecycle<>'draft'
     OR public.aip_budget_cost_hash_a0v_126(expected)<>draft.content_hash
     OR (expected-ARRAY['revision','lifecycle','effectiveFrom','effectiveUntil']) IS DISTINCT FROM
        (t-ARRAY['revision','lifecycle','effectiveFrom','effectiveUntil'])
     OR draft.effective_from IS DISTINCT FROM (t->>'effectiveFrom')::timestamptz
     OR draft.effective_until IS DISTINCT FROM (t->>'effectiveUntil')::timestamptz THEN
    RAISE EXCEPTION 'BUDGET_CONSUMER_DRAFT_DRIFT' USING ERRCODE='23514';
  END IF;
  IF EXISTS(SELECT 1 FROM public.aip_capability_invocation WHERE org_id=p_org AND project_id=p_project
      AND policy_ref->>'resourceType'='BudgetRevision' AND policy_ref->>'resourceId'=p.budget_id)
     OR EXISTS(SELECT 1 FROM public.aip_budget_reservation WHERE org_id=p_org AND project_id=p_project
      AND policy_ref->>'resourceType'='BudgetRevision' AND policy_ref->>'resourceId'=p.budget_id)
     OR EXISTS(SELECT 1 FROM public.aip_budget_bucket WHERE org_id=p_org AND project_id=p_project
      AND ((bucket_kind='daily' AND account_id=p.budget_id||':daily') OR (bucket_kind='pilot' AND account_id=p.budget_id||':pilot'))) THEN
    RAISE EXCEPTION 'BUDGET_CONSUMER_LEDGER_NOT_EMPTY' USING ERRCODE='23514';
  END IF;
  SELECT current_revision INTO source_revision FROM public.aip_provider_instance_head WHERE org_id=p_org AND project_id=p_project
    AND provider_instance_id=ref->>'assetId' FOR SHARE;
  SELECT * INTO source FROM public.aip_provider_instance_revision WHERE org_id=p_org AND project_id=p_project
    AND provider_instance_id=ref->>'assetId' AND revision=source_revision;
  IF NOT FOUND OR (source_revision=(ref->>'revision')::bigint AND source.content_hash=ref->>'contentHash'
    AND source.lifecycle='active' AND source.payload->'tenant'=jsonb_build_object('orgId',p_org,'projectId',p_project)
    AND source.payload->>'providerInstanceId'=source.provider_instance_id AND (source.payload->>'revision')::bigint=source.revision
    AND source.payload->>'contentHash'=source.content_hash AND source.payload->>'lifecycle'='active'
    AND public.aip_budget_cost_hash_a0v_126(source.payload-ARRAY['tenant','revision','contentHash','createdBy','createdAt'])=source.content_hash) IS NOT TRUE THEN
    RAISE EXCEPTION 'BUDGET_CONSUMER_SOURCE_DRIFT' USING ERRCODE='23514';
  END IF;
  checked_at:=clock_timestamp();
  IF (checked_at<p.expires_at AND p.created_at<=d.created_at AND d.created_at<d.expires_at
      AND p.expires_at=least(p.created_at+interval '30 minutes',(t->>'effectiveUntil')::timestamptz)
      AND (t->>'effectiveFrom')::timestamptz<=checked_at AND checked_at<(t->>'effectiveUntil')::timestamptz) IS NOT TRUE THEN
    RAISE EXCEPTION 'BUDGET_CONSUMER_EXPIRED' USING ERRCODE='42501';
  END IF;
  target_hash:=public.aip_budget_cost_hash_a0v_126(t);
  payload:=t||jsonb_build_object('tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),
    'contentHash',target_hash,'createdBy',p.maker_subject,'createdAt',checked_at);
  UPDATE public.aip_budget_head SET current_revision=(t->>'revision')::bigint,version=version+1,updated_at=checked_at
    WHERE org_id=p_org AND project_id=p_project AND budget_id=p.budget_id;
  INSERT INTO public.aip_budget_revision(org_id,project_id,budget_id,revision,content_hash,lifecycle,environment,currency,
    daily_limit_minor,monthly_limit_minor,alert_threshold_pct,hard_stop,unknown_usage_behavior,effective_from,effective_until,
    owner,over_budget_approver,payload,created_by,created_at)
    VALUES(p_org,p_project,p.budget_id,(t->>'revision')::bigint,target_hash,'active','development','CNY',
      (t->>'dailyLimitMinor')::bigint,(t->>'monthlyLimitMinor')::bigint,(t->>'alertThresholdPct')::bigint,true,'block',
      (t->>'effectiveFrom')::timestamptz,(t->>'effectiveUntil')::timestamptz,t->>'owner',t->>'overBudgetApprover',payload,p.maker_subject,checked_at);
  result:=jsonb_build_object('resourceType','BudgetRevision','resourceId',p.budget_id,'revision',(t->>'revision')::bigint,
    'contentHash',target_hash,'proposalId',p_proposal,'proposalHash',p.proposal_hash,'decisionId',p_decision,'receiptId','budget-cost-consume-'||request_hash);
  INSERT INTO public.aip_budget_receipt(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by,created_at)
    VALUES(p_org,p_project,result->>'receiptId','budget_revision.activate_cost',p_proposal,request_hash,result,p.maker_subject,checked_at);
  INSERT INTO public.aip_budget_cost_runtime_fence(org_id,project_id,budget_id,revision,decision_id)
    VALUES(p_org,p_project,p.budget_id,(t->>'revision')::bigint,p_decision);
  IF clock_timestamp()>=p.expires_at OR clock_timestamp()>=(t->>'effectiveUntil')::timestamptz THEN
    RAISE EXCEPTION 'BUDGET_CONSUMER_EXPIRED' USING ERRCODE='42501';
  END IF;
  RETURN result;
END $$;
