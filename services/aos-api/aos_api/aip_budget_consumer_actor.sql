CREATE FUNCTION public.aip_budget_cost_actor_a0v_127(
    p_org text,p_project text,p_proposal text,p_actor text,p_hash text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE p public.aip_budget_cost_proposal%ROWTYPE;
BEGIN
    IF session_user<>'aos_budget_consumer_call' OR current_user<>'aos_budget_consumer_owner'
       OR p_org IS DISTINCT FROM 'org-org' OR p_project IS DISTINCT FROM 'dev-project'
       OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
       OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project
       OR p_actor IS NULL OR p_actor='' OR p_actor<>btrim(p_actor)
       OR p_hash IS NULL OR p_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'BUDGET_CONSUMER_ACTOR_REQUIRED' USING ERRCODE='42501';
    END IF;
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname IN(session_user,current_user)
        AND (rolsuper OR rolinherit OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
          OR (rolname=current_user AND rolcanlogin)))
       OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid IN(session_user::regrole,current_user::regrole)
          OR member IN(session_user::regrole,current_user::regrole)) THEN
        RAISE EXCEPTION 'BUDGET_CONSUMER_ROLE_DRIFT' USING ERRCODE='42501';
    END IF;
    SELECT * INTO p FROM public.aip_budget_cost_proposal
        WHERE org_id=p_org AND project_id=p_project AND proposal_id=p_proposal;
    IF NOT FOUND OR p.maker_subject IS DISTINCT FROM p_actor OR p.proposal_hash IS DISTINCT FROM p_hash
       OR p.status<>'proposed' OR p.source_verification<>'pending' OR p.activation_eligible
       OR public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.budget-cost-proposal/v1','proposal',p.payload)) IS DISTINCT FROM p_hash
       OR p.payload->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',p_org,'projectId',p_project)
       OR p.payload->>'makerSubject' IS DISTINCT FROM p_actor
       OR NOT EXISTS(SELECT 1 FROM public.meta_membership WHERE org_id=p_org AND project_id=p_project
           AND subject=p_actor AND lower(role) IN('owner','admin')) THEN
        RAISE EXCEPTION 'BUDGET_CONSUMER_ACTOR_REQUIRED' USING ERRCODE='42501';
    END IF;
    RETURN p.payload;
END $$;

CREATE FUNCTION public.aip_consume_budget_as_actor_a0v_127(
    p_org text,p_project text,p_proposal text,p_decision text,p_actor text,p_hash text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    IF current_setting('transaction_read_only')<>'off'
       OR current_setting('transaction_isolation')<>'read committed' THEN
        RAISE EXCEPTION 'BUDGET_CONSUMER_WRITE_TRANSACTION_REQUIRED' USING ERRCODE='42501';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('budget-cost-review:'||p_org||':'||p_project||':'||p_proposal,0));
    PERFORM public.aip_budget_cost_actor_a0v_127(p_org,p_project,p_proposal,p_actor,p_hash);
    RETURN public.aip_consume_budget_cost_a0v_126(p_org,p_project,p_proposal,p_decision);
END $$;

CREATE FUNCTION public.aip_reconcile_budget_as_actor_a0v_127(
    p_org text,p_project text,p_proposal text,p_decision text,p_actor text,p_hash text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE
    payload jsonb; expected jsonb; digest text; target_hash text;
    r public.aip_budget_receipt%ROWTYPE; v public.aip_budget_revision%ROWTYPE;
    d public.aip_budget_cost_decision%ROWTYPE;
BEGIN
    IF current_setting('transaction_read_only') IS DISTINCT FROM 'on'
       OR current_setting('transaction_isolation')<>'read committed' THEN
        RAISE EXCEPTION 'BUDGET_RECONCILE_READ_ONLY_REQUIRED' USING ERRCODE='42501';
    END IF;
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
