-- Versioned with a0v_130. No table-owner authority or dynamic SQL.
CREATE FUNCTION public.aip_quota_activation_a0v_130(
  p_org text,p_project text,p_proposal text,p_event text,p_actor text,
  p_hash text,p_target text,p_binding text,p_write boolean) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE
  p public.aip_action_proposal%ROWTYPE;
  a public.aip_action_approval_event%ROWTYPE;
  h public.aip_model_governance_policy_head%ROWTYPE;
  src public.aip_model_governance_policy_revision%ROWTYPE;
  prior public.aip_model_governance_policy_receipt%ROWTYPE;
  saved public.aip_model_governance_policy_revision%ROWTYPE;
  stable jsonb; candidate jsonb; content jsonb; meta jsonb; obj jsonb;
  result jsonb; target_payload jsonb; source_ref jsonb;
  kind text; object_id text; title text; policy_id_value text; operation_value text;
  maker_role text; checker_role text; digest_value text; binding_value text; receipt_id_value text;
  target_revision bigint; source_revision bigint; source_version bigint;
  checked_at timestamptz; starts_at timestamptz; ends_at timestamptz;
  expected_policy jsonb := '{"floor":"R2","reasons":["formal_policy_activation"],"makerChecker":true,
    "minimumApprovals":1,"executionAllowed":true,"draftOnly":false}';
BEGIN
  IF session_user <> 'aos_guard_policy_consumer_call' OR current_user <> 'aos_guard_policy_consumer_owner'
     OR p_write IS NULL OR p_org IS NULL OR p_org='' OR p_project IS NULL OR p_project=''
     OR p_actor IS NULL OR p_actor='' OR p_proposal IS NULL OR p_proposal='' OR p_event IS NULL OR p_event=''
     OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
     OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_SCOPE_IDENTITY_REQUIRED' USING ERRCODE='42501';
  END IF;
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname IN(session_user,current_user)
      AND (rolsuper OR rolbypassrls OR rolinherit OR rolcreatedb OR rolcreaterole OR rolreplication
           OR (rolname=current_user AND rolcanlogin) OR (rolname=session_user AND NOT rolcanlogin)))
    OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid IN(session_user::regrole,current_user::regrole)
                OR member IN(session_user::regrole,current_user::regrole)) THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_ROLE_DRIFT' USING ERRCODE='42501';
  END IF;
  IF (p_write AND (current_setting('transaction_isolation')<>'serializable'
                    OR current_setting('transaction_read_only')<>'off'))
     OR (NOT p_write AND (current_setting('transaction_isolation')<>'repeatable read'
                          OR current_setting('transaction_read_only')<>'on')) THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_TRANSACTION_REQUIRED' USING ERRCODE='42501';
  END IF;
  IF p_write THEN
    PERFORM proposal_id FROM public.aip_action_proposal
      WHERE org_id=p_org AND project_id=p_project AND proposal_id=p_proposal FOR UPDATE;
  END IF;
  SELECT * INTO p FROM public.aip_action_proposal
    WHERE org_id=p_org AND project_id=p_project AND proposal_id=p_proposal;
  IF NOT FOUND OR p.action_type_id<>'aip_activate_quota_policy'
     OR p.created_by IS DISTINCT FROM p_actor OR p.proposal_hash IS DISTINCT FROM p_hash
     OR p.action_binding_hash IS DISTINCT FROM p_binding OR p.payload->>'targetContentHash' IS DISTINCT FROM p_target THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_PROPOSAL_DRIFT' USING ERRCODE='42501';
  END IF;
  kind := 'quota';
  object_id := 'QuotaPolicyRevision';
  title := '配额策略';
  operation_value := 'model_governance_policy.quota.activate';
  IF p_write THEN
    PERFORM subject FROM public.meta_membership WHERE org_id=p_org AND project_id=p_project
      AND subject=p_actor FOR SHARE;
  END IF;
  SELECT lower(role) INTO maker_role FROM public.meta_membership
    WHERE org_id=p_org AND project_id=p_project AND subject=p_actor;
  IF (maker_role IN('owner','admin')) IS NOT TRUE THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_CURRENT_MAKER_REQUIRED' USING ERRCODE='42501';
  END IF;
  digest_value := public.aip_network_consumer_hash_a0v_120(jsonb_build_object(
    'operation',operation_value,'tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),
    'proposalId',p_proposal,'approvalEventId',p_event,'actorId',p_actor,
    'proposalHash',p_hash,'targetContentHash',p_target,'bindingHash',p_binding));
  SELECT * INTO prior FROM public.aip_model_governance_policy_receipt WHERE org_id=p_org AND project_id=p_project
    AND operation=operation_value AND idempotency_key=p_proposal;
  IF FOUND THEN
    SELECT * INTO saved FROM public.aip_model_governance_policy_revision WHERE org_id=p_org AND project_id=p_project
      AND policy_kind=kind AND policy_id=prior.result_ref->>'resourceId'
      AND revision=(prior.result_ref->>'revision')::bigint;
    IF NOT FOUND OR prior.request_hash IS DISTINCT FROM digest_value OR prior.created_by IS DISTINCT FROM p_actor
       OR saved.content_hash IS DISTINCT FROM p_target OR saved.lifecycle IS DISTINCT FROM 'active'
       OR saved.policy_id IS DISTINCT FROM p.payload->'candidate'->>'policyId'
       OR saved.revision IS DISTINCT FROM (p.payload->'candidate'->>'revision')::bigint
       OR saved.created_by IS DISTINCT FROM p_actor OR saved.payload->>'createdBy' IS DISTINCT FROM saved.created_by
       OR (saved.payload->>'createdAt')::timestamptz IS DISTINCT FROM saved.created_at
       OR saved.payload-ARRAY['tenant','contentHash','createdBy','createdAt'] IS DISTINCT FROM p.payload->'candidate'
       OR public.aip_network_consumer_hash_a0v_120(saved.payload-ARRAY['tenant','contentHash','createdBy','createdAt']) IS DISTINCT FROM p_target
       OR saved.payload->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',p_org,'projectId',p_project)
       OR saved.payload->>'contentHash' IS DISTINCT FROM p_target
       OR NOT EXISTS(SELECT 1 FROM public.aip_action_approval_event WHERE org_id=p_org AND project_id=p_project
          AND proposal_id=p_proposal AND approval_event_id=p_event AND decision='approved'
          AND proposal_hash=p_hash AND action_binding_hash=p_binding AND actor_id<>p_actor)
       OR prior.result_ref IS DISTINCT FROM jsonb_build_object('resourceType',object_id,'resourceId',saved.policy_id,
          'revision',saved.revision,'contentHash',p_target,'proposalId',p_proposal,'approvalEventId',p_event,
          'receiptId',prior.receipt_id) THEN
      RAISE EXCEPTION 'QUOTA_CONSUMER_RECEIPT_DRIFT' USING ERRCODE='42501';
    END IF;
    RETURN jsonb_build_object('status','observed','result',prior.result_ref);
  END IF;
  IF p.status IS DISTINCT FROM 'approved' OR p.version<>2 OR p.risk_level IS DISTINCT FROM 'R2'
     OR p.policy_snapshot IS DISTINCT FROM expected_policy
     OR p.approval_policy_hash IS DISTINCT FROM public.aip_network_consumer_hash_a0v_120(expected_policy)
     OR p.task_id IS NOT NULL OR p.run_id IS NOT NULL OR p.impact_preview_id IS NOT NULL
     OR p.source_draft_id IS NOT NULL OR p.client_risk_hint IS NOT NULL
     OR (p.object_ref IS NOT NULL AND p.object_ref<>'null'::jsonb)
     OR p.diff IS DISTINCT FROM '{}'::jsonb OR p.evidence_refs IS DISTINCT FROM '[]'::jsonb THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_PROPOSAL_INVALID' USING ERRCODE='42501';
  END IF;
  IF p_write THEN
    PERFORM approval_event_id FROM public.aip_action_approval_event WHERE org_id=p_org AND project_id=p_project
      AND proposal_id=p_proposal ORDER BY approval_event_id FOR SHARE;
    PERFORM proposal_id FROM public.aip_action_draft WHERE org_id=p_org AND project_id=p_project
      AND proposal_id=p_proposal FOR SHARE;
  END IF;
  SELECT * INTO a FROM public.aip_action_approval_event WHERE org_id=p_org AND project_id=p_project
    AND proposal_id=p_proposal AND approval_event_id=p_event;
  IF NOT FOUND OR a.decision IS DISTINCT FROM 'approved' OR a.slot_id IS DISTINCT FROM 'checker.1'
     OR a.actor_id IS NOT DISTINCT FROM p_actor OR a.expires_at IS NULL OR a.proposal_version<>1
     OR a.proposal_hash IS DISTINCT FROM p_hash OR a.action_binding_hash IS DISTINCT FROM p_binding
     OR a.approval_policy_hash IS DISTINCT FROM p.approval_policy_hash
     OR (SELECT count(*) FROM public.aip_action_approval_event WHERE org_id=p_org AND project_id=p_project
          AND proposal_id=p_proposal)<>1
     OR EXISTS(SELECT 1 FROM public.aip_action_withdrawal_event WHERE org_id=p_org AND project_id=p_project
          AND proposal_id=p_proposal) THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_APPROVAL_INVALID' USING ERRCODE='42501';
  END IF;
  SELECT snapshot INTO stable FROM public.aip_action_draft WHERE org_id=p_org AND project_id=p_project
    AND proposal_id=p_proposal;
  IF NOT FOUND OR public.aip_network_consumer_hash_a0v_120(stable) IS DISTINCT FROM p_hash
     OR stable->'tenantScope' IS DISTINCT FROM jsonb_build_object('orgId',p_org,'projectId',p_project)
     OR stable->>'createdBy' IS DISTINCT FROM p_actor OR stable->'actionType' IS DISTINCT FROM p.action_type_snapshot
     OR stable->'payload' IS DISTINCT FROM p.payload OR stable->'policy' IS DISTINCT FROM p.policy_snapshot
     OR stable->>'actionBindingHash' IS DISTINCT FROM p_binding
     OR stable->>'approvalPolicyHash' IS DISTINCT FROM p.approval_policy_hash
     OR (stable->>'expiresAt')::timestamptz IS DISTINCT FROM p.expires_at THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_DRAFT_DRIFT' USING ERRCODE='42501';
  END IF;
  IF p_write THEN
    PERFORM subject FROM public.meta_membership WHERE org_id=p_org AND project_id=p_project AND subject=a.actor_id FOR SHARE;
    PERFORM id FROM public.meta_object_type WHERE id=object_id FOR SHARE;
    PERFORM id FROM public.meta_action_type WHERE id=p.action_type_id FOR SHARE;
  END IF;
  SELECT lower(role) INTO checker_role FROM public.meta_membership
    WHERE org_id=p_org AND project_id=p_project AND subject=a.actor_id;
  IF (checker_role IN('owner','admin')) IS NOT TRUE
     OR a.eligibility_snapshot_hash IS DISTINCT FROM public.aip_network_consumer_hash_a0v_120(jsonb_build_object(
       'tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),'actorId',a.actor_id,
       'roles',jsonb_build_array(checker_role),'slotId','checker.1','approvalPolicyHash',p.approval_policy_hash)) THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_CURRENT_CHECKER_REQUIRED' USING ERRCODE='42501';
  END IF;
  SELECT jsonb_build_object('id',id,'name',name,'description',description,'published',published,
    'properties',properties,'requiredMarkings',required_markings) INTO obj FROM public.meta_object_type WHERE id=object_id;
  SELECT jsonb_build_object('id',id,'name',name,'objectType',object_type,'parameters',parameters,
    'requiredMarkings',required_markings,'submissionCriteria',submission_criteria) INTO meta
    FROM public.meta_action_type WHERE id=p.action_type_id;
  IF obj IS DISTINCT FROM jsonb_build_object('id',object_id,'name',title||'修订','description','受控'||title||'激活目标',
       'published',true,'properties','[]'::jsonb,'requiredMarkings','[]'::jsonb)
     OR meta IS DISTINCT FROM jsonb_build_object('id',p.action_type_id,'name','激活'||title,'objectType',object_id,
       'parameters','[]'::jsonb,'requiredMarkings','[]'::jsonb,'submissionCriteria','[]'::jsonb)
     OR p.action_type_snapshot IS DISTINCT FROM meta||jsonb_build_object('revisionHash',public.aip_network_consumer_hash_a0v_120(meta))
     OR p.action_type_revision_hash IS DISTINCT FROM public.aip_network_consumer_hash_a0v_120(meta) THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_METADATA_DRIFT' USING ERRCODE='42501';
  END IF;
  candidate:=p.payload->'candidate'; policy_id_value:=candidate->>'policyId';
  target_revision:=(candidate->>'revision')::bigint;
  source_revision:=(p.payload->>'expectedHeadRevision')::bigint;
  source_version:=(p.payload->>'expectedHeadVersion')::bigint;
  starts_at:=(candidate->>'effectiveFrom')::timestamptz; ends_at:=(candidate->>'effectiveUntil')::timestamptz;
  IF p_write THEN
    PERFORM policy_id FROM public.aip_model_governance_policy_head WHERE org_id=p_org AND project_id=p_project
      AND policy_kind=kind AND policy_id=policy_id_value FOR UPDATE;
  END IF;
  SELECT * INTO h FROM public.aip_model_governance_policy_head WHERE org_id=p_org AND project_id=p_project
    AND policy_kind=kind AND policy_id=policy_id_value;
  IF NOT FOUND OR h.current_revision<>source_revision OR h.version<>source_version THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_HEAD_DRIFT' USING ERRCODE='42501';
  END IF;
  SELECT * INTO src FROM public.aip_model_governance_policy_revision WHERE org_id=p_org AND project_id=p_project
    AND policy_kind=kind AND policy_id=policy_id_value AND revision=source_revision;
  content:=src.payload-ARRAY['tenant','contentHash','createdBy','createdAt'];
  source_ref:=jsonb_build_object('resourceType',object_id,'resourceId',policy_id_value,'revision',source_revision,'contentHash',src.content_hash);
  IF src.policy_id IS NULL OR src.lifecycle IS DISTINCT FROM 'draft'
     OR src.content_hash IS DISTINCT FROM public.aip_network_consumer_hash_a0v_120(content)
     OR src.content_hash IS DISTINCT FROM p.payload->>'sourceContentHash'
     OR src.payload->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',p_org,'projectId',p_project)
     OR src.payload->>'policyId' IS DISTINCT FROM src.policy_id OR (src.payload->>'revision')::bigint IS DISTINCT FROM src.revision
     OR src.payload->>'contentHash' IS DISTINCT FROM src.content_hash OR src.payload->>'lifecycle' IS DISTINCT FROM src.lifecycle
     OR src.payload->>'createdBy' IS DISTINCT FROM src.created_by
     OR (src.payload->>'createdAt')::timestamptz IS DISTINCT FROM src.created_at
     OR (src.payload->>'effectiveFrom')::timestamptz IS DISTINCT FROM src.effective_from
     OR (src.payload->>'effectiveUntil')::timestamptz IS DISTINCT FROM src.effective_until
     OR candidate IS DISTINCT FROM content||jsonb_build_object('revision',source_revision+1,'lifecycle','active')
     OR (SELECT count(*) FROM public.aip_model_governance_policy_receipt WHERE org_id=p_org AND project_id=p_project
           AND operation='model_governance_policy.'||kind||'.publish' AND result_ref=source_ref)<>1
     OR NOT EXISTS(SELECT 1 FROM public.aip_model_governance_policy_receipt WHERE org_id=p_org AND project_id=p_project
           AND operation='model_governance_policy.'||kind||'.publish' AND result_ref=source_ref AND created_by=src.created_by
           AND request_hash=public.aip_network_consumer_hash_a0v_120(jsonb_build_object('expectedVersion',source_version-1,'revision',content))) THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_SOURCE_DRIFT' USING ERRCODE='42501';
  END IF;
  binding_value:=public.aip_network_consumer_hash_a0v_120(jsonb_build_object('schema','aos-guard-policy-activation/v1',
    'tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),'actionTypeId',p.action_type_id,
    'policyKind',kind,'policyId',policy_id_value,'revision',target_revision,'expectedHeadRevision',source_revision,
    'expectedHeadVersion',source_version,'sourceContentHash',src.content_hash,'targetContentHash',p_target));
  IF (source_revision>=1 AND source_version>=1 AND target_revision=source_revision+1
      AND jsonb_typeof(candidate->'revision')='number' AND candidate->>'revision'~'^[1-9][0-9]*$'
      AND jsonb_typeof(p.payload->'expectedHeadRevision')='number' AND p.payload->>'expectedHeadRevision'~'^[1-9][0-9]*$'
      AND jsonb_typeof(p.payload->'expectedHeadVersion')='number' AND p.payload->>'expectedHeadVersion'~'^[1-9][0-9]*$'
      AND candidate->>'environment'='development' AND candidate->>'lifecycle'='active'
      AND length(btrim(candidate->>'owner')) BETWEEN 1 AND 160
      AND length(btrim(candidate->>'approvalRef')) BETWEEN 1 AND 240
      AND length(policy_id_value) BETWEEN 1 AND 200 AND policy_id_value=btrim(policy_id_value)
      AND starts_at<ends_at AND candidate->>'effectiveFrom'~'(Z|[+-][0-9]{2}:[0-9]{2})$'
      AND candidate->>'effectiveUntil'~'(Z|[+-][0-9]{2}:[0-9]{2})$') IS NOT TRUE
     OR public.aip_network_consumer_hash_a0v_120(candidate) IS DISTINCT FROM p_target
     OR binding_value IS DISTINCT FROM p_binding OR p.payload->>'bindingHash' IS DISTINCT FROM p_binding THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_TARGET_DRIFT' USING ERRCODE='42501';
  END IF;
  IF (candidate->'allowPublicProviderFallback'='false'::jsonb
      AND candidate->'allowAutoScale'='false'::jsonb
      AND candidate->>'overflowBehavior' IN('queue','reject')
      AND (candidate->>'maxConcurrency')::bigint BETWEEN 1 AND 2
      AND (candidate->>'maxInputTokens')::bigint BETWEEN 1 AND 8000
      AND (candidate->>'maxOutputTokens')::bigint BETWEEN 1 AND 2000
      AND (candidate->>'hourlyRequestLimit')::bigint BETWEEN 1 AND 50
      AND (candidate->>'dailyRequestLimit')::bigint BETWEEN 1 AND 200
      AND (candidate->>'dailyRequestLimit')::bigint >= (candidate->>'hourlyRequestLimit')::bigint
      AND candidate->'reservationLeaseSeconds'='60'::jsonb
      AND ((candidate->'rpmLimit'='null'::jsonb AND candidate->'tpmLimit'='null'::jsonb)
        OR (jsonb_typeof(candidate->'rpmLimit')='number' AND candidate->>'rpmLimit'~'^[1-9][0-9]*$'
          AND jsonb_typeof(candidate->'tpmLimit')='number' AND candidate->>'tpmLimit'~'^[1-9][0-9]*$'
          AND (candidate->>'rpmLimit')::bigint BETWEEN 1 AND 10000
          AND (candidate->>'tpmLimit')::bigint BETWEEN 1 AND 10000000))) IS NOT TRUE
    OR EXISTS(SELECT 1 FROM unnest(ARRAY['maxConcurrency','maxInputTokens','maxOutputTokens',
         'hourlyRequestLimit','dailyRequestLimit','reservationLeaseSeconds']) field
       WHERE jsonb_typeof(candidate->field) IS DISTINCT FROM 'number'
          OR (candidate->>field~'^[1-9][0-9]*$') IS NOT TRUE)
    OR candidate-ARRAY['policyId','revision','environment','effectiveFrom','effectiveUntil','owner',
       'approvalRef','lifecycle','rpmLimit','tpmLimit','maxConcurrency','maxInputTokens','maxOutputTokens',
       'hourlyRequestLimit','dailyRequestLimit','reservationLeaseSeconds','overflowBehavior',
       'allowPublicProviderFallback','allowAutoScale']<>'{}'::jsonb THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_LIMITS_INVALID' USING ERRCODE='42501';
  END IF;
  checked_at:=clock_timestamp();
  IF (checked_at<p.expires_at AND checked_at<a.expires_at AND starts_at<=checked_at AND checked_at<ends_at) IS NOT TRUE THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_EXPIRED' USING ERRCODE='42501';
  END IF;
  IF NOT p_write THEN RETURN jsonb_build_object('status','ready'); END IF;
  target_payload:=candidate||jsonb_build_object('tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),
    'contentHash',p_target,'createdBy',p_actor,'createdAt',checked_at);
  INSERT INTO public.aip_model_governance_policy_revision(org_id,project_id,policy_kind,policy_id,revision,content_hash,
    lifecycle,effective_from,effective_until,payload,created_by,created_at)
    VALUES(p_org,p_project,kind,policy_id_value,target_revision,p_target,'active',starts_at,ends_at,target_payload,p_actor,checked_at);
  UPDATE public.aip_model_governance_policy_head SET current_revision=target_revision,version=version+1,updated_at=checked_at
    WHERE org_id=p_org AND project_id=p_project AND policy_kind=kind AND policy_id=policy_id_value;
  receipt_id_value:='quota-consume-'||digest_value;
  result:=jsonb_build_object('resourceType',object_id,'resourceId',policy_id_value,'revision',target_revision,
    'contentHash',p_target,'proposalId',p_proposal,'approvalEventId',p_event,'receiptId',receipt_id_value);
  INSERT INTO public.aip_model_governance_policy_receipt(org_id,project_id,receipt_id,operation,idempotency_key,
    request_hash,result_ref,created_by,created_at)
    VALUES(p_org,p_project,receipt_id_value,operation_value,p_proposal,digest_value,result,p_actor,checked_at);
  checked_at:=clock_timestamp();
  IF checked_at>=least(p.expires_at,a.expires_at,ends_at) THEN
    RAISE EXCEPTION 'QUOTA_CONSUMER_EXPIRED_BEFORE_RETURN' USING ERRCODE='42501';
  END IF;
  RETURN jsonb_build_object('status','observed','result',result);
END $$;
