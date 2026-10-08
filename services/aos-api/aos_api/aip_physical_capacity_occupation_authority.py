"""Explicit necessary-fact bridge artifact. No install, admission or dispatch."""
OWNER = 'aos_physical_capacity_occupation_owner'
FACT = 'public.capacity_occupation_eval_fact(bytea,jsonb,uuid,text,text)'
ENTRY = 'public.read_capacity_occupation_eval_fact(bytea,jsonb,uuid,text,text)'
SOURCE_FACT = 'public.capacity_occupation_source_fact(bytea,jsonb)'
GUARD = 'public.prepare_capacity_occupation_account_guard(bytea,jsonb)'
SCHEMA = 'aos_physical_capacity_occupation_private'
DEBIT = 'public.prepare_capacity_parent_debit(bytea,jsonb,uuid,text,text,uuid,bigint)'
CASE_FACT = 'public.capacity_occupation_eval_case_fact(bytea,jsonb,uuid,text,text,bytea,text)'
CASE_DEBIT = 'public.prepare_capacity_case_parent_debit(bytea,jsonb,uuid,text,text,uuid,bigint,bytea,text)'

JUDGE_FACT = 'public.capacity_occupation_judge_fact(bytea,jsonb,uuid,text,text)'
JUDGE_ENTRY = 'public.read_capacity_occupation_judge_fact(bytea,jsonb,uuid,text,text)'


def occupation_judge_fact_statements():
    """Necessary original-row facts only; not Rule trust or joint admission.

    The joint Owner must still use the original signed Rule/current approval
    guard and risk fences. This artifact is deliberately disconnected from
    Intent/finalization and must not be installed by a runtime caller.
    """
    body = """DECLARE
      s record; document jsonb; application jsonb; governance jsonb; graph jsonb;
      h public.aip_model_judge_budget_reservation%ROWTYPE;
      r public.aip_model_eval_judge_request%ROWTYPE;
      a public.aip_action_approval_event%ROWTYPE; p public.aip_action_proposal%ROWTYPE;
      original public.aip_model_eval_request%ROWTYPE;
      oa public.aip_action_approval_event%ROWTYPE; op public.aip_action_proposal%ROWTYPE;
      q record; budget_policy record; budget record; suite record;
      token_upper bigint; n bigint; exact_rows boolean; approval_digest text;
      now_at timestamptz; deadline timestamptz;
      xid_value text:=pg_current_xact_id()::text;
      xid_low bigint:=(pg_current_xact_id()::text::numeric % 4294967296)::bigint;
    BEGIN
      IF current_user<>'aos_runtime' OR session_user<>'aos_provider_capacity_occupation'
        OR current_setting('transaction_isolation')<>'serializable'
        OR current_setting('transaction_read_only')<>'off'
        OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
        OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project' THEN
        RAISE EXCEPTION 'CAPACITY_JUDGE_FACT_CALLER_REQUIRED' USING ERRCODE='42501';
      END IF;
      SELECT * INTO STRICT s FROM public.read_capacity_source_for_occupation(p_raw,p_source);
      document:=convert_from(s.source_raw,'UTF8')::jsonb;
      SELECT * INTO h FROM public.aip_model_judge_budget_reservation
        WHERE org_id='org-org' AND project_id='dev-project' AND reservation_id=p_hold
          AND request_id=p_request AND request_hash=p_hash AND purpose='model-judge-call'
          AND state='held' AND xmin::text::bigint=xid_low;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'CAPACITY_JUDGE_CURRENT_PARENT_REQUIRED' USING ERRCODE='23514';
      END IF;
      SELECT * INTO STRICT r FROM public.aip_model_eval_judge_request
        WHERE org_id=h.org_id AND project_id=h.project_id AND request_id=h.request_id
          AND request_hash=h.request_hash;
      application:=r.request_json;
      governance:=application->'judgeGovernanceApplication'->'request';
      SELECT * INTO STRICT a FROM public.aip_action_approval_event
        WHERE org_id=h.org_id AND project_id=h.project_id
          AND approval_event_id=h.approval_event_id AND decision='approved';
      SELECT * INTO STRICT p FROM public.aip_action_proposal
        WHERE org_id=h.org_id AND project_id=h.project_id AND proposal_id=a.proposal_id;
      -- Match the original budget hash's datetime default=str (space, fixed
      -- six fractional digits when nonzero), not a JSON timestamp encoding.
      approval_digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(
        jsonb_build_object('approval_event_id',a.approval_event_id,'proposal_id',a.proposal_id,
          'proposal_version',a.proposal_version,'proposal_hash',a.proposal_hash,'decision',a.decision,
          'actor_id',a.actor_id,'reason',a.reason,'action_binding_hash',a.action_binding_hash,
          'expires_at',to_char(a.expires_at AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')||
            CASE WHEN extract(microseconds FROM a.expires_at)::bigint%1000000=0 THEN ''
              ELSE '.'||to_char(a.expires_at,'US') END||'+00:00',
          'created_at',to_char(a.created_at AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')||
            CASE WHEN extract(microseconds FROM a.created_at)::bigint%1000000=0 THEN ''
              ELSE '.'||to_char(a.created_at,'US') END||'+00:00')),'UTF8')),'hex');
      IF application->>'schemaVersion' IS DISTINCT FROM 'aos.model-judge-call-request/v2'
        OR application->>'purpose' IS DISTINCT FROM 'model-judge-call'
        OR application->'executionAllowed' IS DISTINCT FROM 'false'::jsonb
        OR application->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',h.org_id,'projectId',h.project_id)
        OR r.request_hash IS DISTINCT FROM encode(sha256(convert_to(
          public.canonical_asset_registry_jsonb(application),'UTF8')),'hex')
        OR p.purpose IS DISTINCT FROM 'model-judge-call' OR p.status IS DISTINCT FROM 'approved'
        OR p.version IS DISTINCT FROM a.proposal_version+1
        OR p.proposal_hash IS DISTINCT FROM a.proposal_hash
        OR h.proposal_hash IS DISTINCT FROM p.proposal_hash OR h.proposal_id IS DISTINCT FROM p.proposal_id
        OR p.payload IS DISTINCT FROM jsonb_build_object('requestId',r.request_id,'requestHash',r.request_hash)
        OR p.action_binding_hash IS DISTINCT FROM a.action_binding_hash
        OR p.approval_policy_hash IS DISTINCT FROM a.approval_policy_hash
        OR a.slot_id IS DISTINCT FROM 'checker.1'
        OR nullif(r.created_by,'') IS NULL OR nullif(a.actor_id,'') IS NULL
        OR p.created_by IS DISTINCT FROM r.created_by OR a.actor_id IS NOT DISTINCT FROM r.created_by
        OR h.approval_ref IS DISTINCT FROM jsonb_build_object('resourceType','ActionApprovalEvent',
          'resourceId',a.approval_event_id,'revision',a.proposal_version,'contentHash',approval_digest)
        OR application->'targetApplication'->>'requestId' IS NOT DISTINCT FROM
           application->'judgeGovernanceApplication'->>'requestId'
        OR h.budget_policy_ref IS DISTINCT FROM governance->'budgetPolicyRef'
        OR h.price_ref IS DISTINCT FROM jsonb_build_object('resourceType',governance->'priceRef'->>'assetType',
             'resourceId',governance->'priceRef'->>'assetId','revision',governance->'priceRef'->'revision',
             'contentHash','sha256:'||(governance->'priceRef'->>'contentHash'))
        OR h.currency IS DISTINCT FROM application->>'currency'
        OR h.upper_bound_minor IS DISTINCT FROM (application->>'upperBoundMinor')::bigint
        OR h.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
          public.canonical_asset_registry_jsonb(to_jsonb(h)-ARRAY['org_id','project_id','created_at','content_hash']),
          'UTF8')),'hex') THEN
        RAISE EXCEPTION 'CAPACITY_JUDGE_ORIGINAL_BINDING_REQUIRED' USING ERRCODE='23514';
      END IF;
      deadline:=least(r.expires_at,a.expires_at,p.expires_at,
        (document->>'validUntil')::timestamptz,(application->'ruleFacts'->>'validUntil')::timestamptz);
      IF a.expires_at IS NULL OR application->'ruleFacts'->>'validUntil' IS NULL THEN
        RAISE EXCEPTION 'CAPACITY_JUDGE_DEADLINES_REQUIRED' USING ERRCODE='23514';
      END IF;
      FOR graph IN SELECT value FROM jsonb_array_elements(jsonb_build_array(
          application->'targetApplication',application->'judgeGovernanceApplication')) LOOP
        SELECT * INTO STRICT original FROM public.aip_model_eval_request
          WHERE org_id=h.org_id AND project_id=h.project_id AND request_id=graph->>'requestId';
        SELECT * INTO STRICT oa FROM public.aip_action_approval_event
          WHERE org_id=h.org_id AND project_id=h.project_id AND approval_event_id=graph->>'approvalEventId';
        SELECT * INTO STRICT op FROM public.aip_action_proposal
          WHERE org_id=h.org_id AND project_id=h.project_id AND proposal_id=oa.proposal_id;
        IF original.request_hash IS DISTINCT FROM graph->>'requestHash'
          OR original.request_json IS DISTINCT FROM graph->'request'
          OR original.request_hash IS DISTINCT FROM encode(sha256(convert_to(
             public.canonical_asset_registry_jsonb(original.request_json),'UTF8')),'hex')
          OR oa.decision IS DISTINCT FROM 'approved' OR oa.expires_at IS NULL
          OR op.status IS DISTINCT FROM 'approved' OR op.version IS DISTINCT FROM oa.proposal_version+1
          OR op.proposal_id IS DISTINCT FROM graph->>'proposalId'
          OR op.proposal_hash IS DISTINCT FROM graph->>'proposalHash'
          OR oa.proposal_hash IS DISTINCT FROM op.proposal_hash
          OR op.payload IS DISTINCT FROM jsonb_build_object('requestId',original.request_id,'requestHash',original.request_hash)
          OR op.created_by IS DISTINCT FROM original.created_by
          OR oa.actor_id IS NOT DISTINCT FROM original.created_by THEN
          RAISE EXCEPTION 'CAPACITY_JUDGE_ORIGINAL_GRAPH_REQUIRED' USING ERRCODE='23514';
        END IF;
        deadline:=least(deadline,original.expires_at,oa.expires_at,op.expires_at);
      END LOOP;
      IF (document->'providerRefs' @> jsonb_build_array(governance->'providerRef')) IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'CAPACITY_JUDGE_SOURCE_PROVIDER_REQUIRED' USING ERRCODE='23514';
      END IF;
      SELECT v.payload,v.content_hash,v.lifecycle,v.effective_from,v.effective_until INTO q
        FROM public.aip_model_governance_policy_head head
        JOIN public.aip_model_governance_policy_revision v USING(org_id,project_id,policy_kind,policy_id)
        WHERE head.org_id=h.org_id AND head.project_id=h.project_id AND head.policy_kind='quota'
          AND head.policy_id=governance->'quotaPolicyRef'->>'assetId'
          AND v.revision=head.current_revision AND v.revision=(governance->'quotaPolicyRef'->>'revision')::integer
        FOR SHARE OF head;
      IF NOT FOUND OR q.lifecycle IS DISTINCT FROM 'active'
        OR governance->'quotaPolicyRef'->>'assetType' IS DISTINCT FROM 'QuotaPolicyRevision'
        OR q.content_hash IS DISTINCT FROM governance->'quotaPolicyRef'->>'contentHash'
        OR q.payload->>'contentHash' IS DISTINCT FROM q.content_hash
        OR q.payload->'tenant' IS DISTINCT FROM application->'tenant'
        OR q.content_hash IS DISTINCT FROM encode(sha256(convert_to(public.canonical_asset_registry_jsonb(
           q.payload-ARRAY['tenant','contentHash','createdBy','createdAt']),'UTF8')),'hex')
        OR jsonb_typeof(q.payload->'maxInputTokens') IS DISTINCT FROM 'number'
        OR jsonb_typeof(q.payload->'maxOutputTokens') IS DISTINCT FROM 'number'
        OR (q.payload->>'maxInputTokens') !~ '^[0-9]+$' OR (q.payload->>'maxOutputTokens') !~ '^[0-9]+$'
        OR (q.payload->>'maxInputTokens')::bigint NOT BETWEEN 1 AND 8000
        OR (q.payload->>'maxOutputTokens')::bigint NOT BETWEEN 1 AND 2000 THEN
        RAISE EXCEPTION 'CAPACITY_JUDGE_CURRENT_QUOTA_REQUIRED' USING ERRCODE='23514';
      END IF;
      token_upper:=(q.payload->>'maxInputTokens')::bigint+(q.payload->>'maxOutputTokens')::bigint;
      SELECT v.payload,v.content_hash,v.lifecycle,v.effective_from,v.effective_until INTO budget_policy
        FROM public.aip_model_governance_policy_head head
        JOIN public.aip_model_governance_policy_revision v USING(org_id,project_id,policy_kind,policy_id)
        WHERE head.org_id=h.org_id AND head.project_id=h.project_id AND head.policy_kind='budget'
          AND head.policy_id=governance->'budgetPolicyRef'->>'assetId'
          AND v.revision=head.current_revision AND v.revision=(governance->'budgetPolicyRef'->>'revision')::integer
        FOR SHARE OF head;
      IF NOT FOUND OR budget_policy.lifecycle IS DISTINCT FROM 'active'
        OR budget_policy.content_hash IS DISTINCT FROM governance->'budgetPolicyRef'->>'contentHash'
        OR budget_policy.payload->'tenant' IS DISTINCT FROM application->'tenant'
        OR budget_policy.payload->>'currency' IS DISTINCT FROM h.currency
        OR budget_policy.content_hash IS DISTINCT FROM encode(sha256(convert_to(
          public.canonical_asset_registry_jsonb(budget_policy.payload-
            ARRAY['tenant','contentHash','createdBy','createdAt']),'UTF8')),'hex')
        OR h.budget_revision_ref IS DISTINCT FROM jsonb_build_object('resourceType','BudgetRevision',
          'resourceId',budget_policy.payload->'budgetRevisionRef'->>'assetId',
          'revision',budget_policy.payload->'budgetRevisionRef'->'revision',
          'contentHash','sha256:'||(budget_policy.payload->'budgetRevisionRef'->>'contentHash')) THEN
        RAISE EXCEPTION 'CAPACITY_JUDGE_CURRENT_BUDGET_POLICY_REQUIRED' USING ERRCODE='23514';
      END IF;
      SELECT v.* INTO budget FROM public.aip_budget_head head
        JOIN public.aip_budget_revision v USING(org_id,project_id,budget_id)
        WHERE head.org_id=h.org_id AND head.project_id=h.project_id
          AND head.budget_id=h.budget_revision_ref->>'resourceId'
          AND v.revision=head.current_revision AND v.revision=(h.budget_revision_ref->>'revision')::integer
        FOR SHARE OF head;
      IF NOT FOUND OR budget.lifecycle IS DISTINCT FROM 'active'
        OR 'sha256:'||budget.content_hash IS DISTINCT FROM h.budget_revision_ref->>'contentHash' THEN
        RAISE EXCEPTION 'CAPACITY_JUDGE_CURRENT_BUDGET_REQUIRED' USING ERRCODE='23514';
      END IF;
      now_at:=clock_timestamp();
      SELECT count(*),bool_and(l.reserved_minor=h.upper_bound_minor AND b.held_minor>=l.reserved_minor
        AND l.xmin::text::bigint=xid_low AND b.xmin::text::bigint=xid_low AND l.currency=h.currency
        AND b.period_start<=now_at AND now_at<b.period_end
        AND ((l.bucket_kind='task' AND l.account_id='model-judge/'||h.request_id AND b.limit_minor=h.upper_bound_minor)
          OR (l.bucket_kind='daily' AND l.account_id=(h.budget_revision_ref->>'resourceId')||':daily'
              AND b.limit_minor=budget.daily_limit_minor)
          OR (l.bucket_kind='pilot' AND l.account_id=(h.budget_revision_ref->>'resourceId')||':pilot'
              AND b.limit_minor=budget.monthly_limit_minor))) INTO n,exact_rows
        FROM public.aip_model_judge_budget_reservation_bucket l
        JOIN public.aip_budget_bucket b USING(org_id,project_id,bucket_kind,account_id,period_start,currency)
        WHERE l.org_id=h.org_id AND l.project_id=h.project_id AND l.reservation_id=h.reservation_id;
      IF n<>3 OR exact_rows IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'CAPACITY_JUDGE_THREE_CURRENT_BUCKETS_REQUIRED' USING ERRCODE='23514';
      END IF;
      SELECT cases,content_hash,judge_ref INTO suite FROM public.aip_eval_suite_revision
        WHERE org_id=h.org_id AND project_id=h.project_id AND suite_id=application->'suiteRef'->>'assetId'
          AND revision=(application->'suiteRef'->>'revision')::integer;
      IF NOT FOUND OR suite.cases IS DISTINCT FROM application->'cases'
        OR suite.content_hash IS DISTINCT FROM application->'suiteRef'->>'contentHash'
        OR suite.judge_ref IS DISTINCT FROM application->'judgeRef'
        OR application->>'caseSetHash' IS DISTINCT FROM encode(sha256(convert_to(
           public.canonical_asset_registry_jsonb(suite.cases),'UTF8')),'hex') THEN
        RAISE EXCEPTION 'CAPACITY_JUDGE_ORIGINAL_CASE_SET_REQUIRED' USING ERRCODE='23514';
      END IF;
      now_at:=clock_timestamp();
      IF deadline<=now_at OR (document->>'validFrom')::timestamptz>now_at
        OR q.effective_from IS NULL OR q.effective_until IS NULL
        OR NOT(q.effective_from<=now_at AND now_at<q.effective_until)
        OR budget_policy.effective_from IS NULL OR budget_policy.effective_until IS NULL
        OR NOT(budget_policy.effective_from<=now_at AND now_at<budget_policy.effective_until)
        OR NOT(budget.effective_from<=now_at AND now_at<budget.effective_until) THEN
        RAISE EXCEPTION 'CAPACITY_JUDGE_CURRENT_DEADLINES_REQUIRED' USING ERRCODE='23514';
      END IF;
      RETURN jsonb_build_object('schemaVersion','aos.capacity-model-judge-necessary-fact/v1',
        'application',application,'requestId',r.request_id,'requestHash',r.request_hash,
        'reservationId',h.reservation_id,'contentHash',h.content_hash,'purpose',h.purpose,
        'approvalEventId',a.approval_event_id,'approvalSnapshot',to_jsonb(a),
        'requestMaker',r.created_by,'approvalChecker',a.actor_id,
        'sourceRef',p_source,'physicalAccountId',document->>'physicalAccountId',
        'providerRef',governance->'providerRef','quotaRef',governance->'quotaPolicyRef',
        'tokenUpperBound',token_upper,'upperBoundMinor',h.upper_bound_minor,'currency',h.currency,
        'caseSetHash',application->>'caseSetHash','xid',xid_value,'pid',pg_backend_pid(),
        'checkedAt',now_at,'approvalAllowed',false,'executionAllowed',false);
    END"""
    arguments = 'p_raw bytea,p_source jsonb,p_hold uuid,p_request text,p_hash text'
    return (
        f'CREATE FUNCTION {JUDGE_FACT.split("(")[0]}({arguments}) RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $judgefact${body}$judgefact$;',
        f'ALTER FUNCTION {JUDGE_FACT} OWNER TO aos_runtime',
        f'REVOKE ALL ON FUNCTION {JUDGE_FACT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {JUDGE_FACT} TO {OWNER}',
        f'''CREATE FUNCTION {JUDGE_ENTRY.split("(")[0]}({arguments}) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $judgeentry$
          BEGIN RETURN public.capacity_occupation_judge_fact(p_raw,p_source,p_hold,p_request,p_hash); END $judgeentry$;''',
        f'ALTER FUNCTION {JUDGE_ENTRY} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {JUDGE_ENTRY} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {JUDGE_ENTRY} TO aos_runtime',
    )


INTENT = 'public.prepare_capacity_execution_intent(bytea,jsonb,uuid,text,text,uuid,bigint,bytea,text,bytea,uuid)'


def occupation_intent_statements():
    """Immutable per-call preparation Intent, never finalized admission."""
    return (
        f'''CREATE TABLE {SCHEMA}.prepared_execution_intent (
          org_id text NOT NULL,project_id text NOT NULL,intent_id uuid PRIMARY KEY,
          debit_id uuid NOT NULL UNIQUE REFERENCES {SCHEMA}.case_input_binding(debit_id),
          request_id text NOT NULL,case_id text NOT NULL,purpose text NOT NULL CHECK(purpose='target'),
          attempt integer NOT NULL CHECK(attempt=1),state text NOT NULL CHECK(state='prepared'),
          immutable jsonb NOT NULL,content_hash text NOT NULL,
          origin_xid xid8 NOT NULL,origin_pid integer NOT NULL,
          UNIQUE(org_id,project_id,request_id,case_id,purpose,attempt))''',
        f'ALTER TABLE {SCHEMA}.prepared_execution_intent OWNER TO {OWNER}',
        f'ALTER TABLE {SCHEMA}.prepared_execution_intent ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {SCHEMA}.prepared_execution_intent FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {SCHEMA}.prepared_execution_intent TO {OWNER}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'REVOKE ALL ON {SCHEMA}.prepared_execution_intent FROM PUBLIC,aos_runtime',
        f'''CREATE FUNCTION {SCHEMA}.immutable_prepared_intent() RETURNS trigger
          LANGUAGE plpgsql SET search_path=pg_catalog AS $immutableintent$
          BEGIN RAISE EXCEPTION 'CAPACITY_INTENT_IMMUTABLE' USING ERRCODE='42501'; END $immutableintent$''',
        f'ALTER FUNCTION {SCHEMA}.immutable_prepared_intent() OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {SCHEMA}.immutable_prepared_intent() FROM PUBLIC,aos_runtime',
        f'CREATE TRIGGER immutable_prepared_intent BEFORE UPDATE OR DELETE ON {SCHEMA}.prepared_execution_intent FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.immutable_prepared_intent()',
        f'CREATE TRIGGER no_truncate_prepared_intent BEFORE TRUNCATE ON {SCHEMA}.prepared_execution_intent FOR EACH STATEMENT EXECUTE FUNCTION {SCHEMA}.immutable_prepared_intent()',
        f'''CREATE FUNCTION {INTENT.split('(')[0]}(p_raw bytea,p_source jsonb,p_hold uuid,
          p_request text,p_hash text,p_debit uuid,p_minor bigint,p_suite_raw bytea,p_case text,p_input_raw bytea,p_intent uuid)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $intent$
          DECLARE fact jsonb; binding jsonb; body jsonb; digest text; debit_body jsonb;
            old {SCHEMA}.prepared_execution_intent%ROWTYPE;
          BEGIN
            IF p_intent IS NULL THEN RAISE EXCEPTION 'CAPACITY_INTENT_ID_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT * INTO old FROM {SCHEMA}.prepared_execution_intent
              WHERE org_id='org-org' AND project_id='dev-project' AND request_id=p_request
                AND case_id=p_case AND purpose='target' AND attempt=1;
            IF FOUND AND old.intent_id IS DISTINCT FROM p_intent THEN
              RAISE EXCEPTION 'CAPACITY_INTENT_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            SELECT * INTO old FROM {SCHEMA}.prepared_execution_intent WHERE intent_id=p_intent;
            IF FOUND AND (old.debit_id IS DISTINCT FROM p_debit OR old.request_id IS DISTINCT FROM p_request
              OR old.case_id IS DISTINCT FROM p_case) THEN
              RAISE EXCEPTION 'CAPACITY_INTENT_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            fact:=public.capacity_occupation_eval_case_fact(p_raw,p_source,p_hold,p_request,p_hash,p_suite_raw,p_case);
            binding:=public.prepare_capacity_input_parent_debit(p_raw,p_source,p_hold,p_request,p_hash,p_debit,p_minor,p_suite_raw,p_case,p_input_raw);
            SELECT immutable INTO STRICT debit_body FROM {SCHEMA}.prepared_parent_debit WHERE debit_id=p_debit;
            body:=jsonb_build_object('intentId',p_intent,'state','prepared','tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
              'requestId',p_request,'requestHash',p_hash,'requestMaker',fact->>'requestMaker',
              'approvalChecker',fact->>'approvalChecker','approvalSnapshot',fact->'approvalSnapshot',
              'proposalId',fact->>'proposalId','proposalHash',fact->>'proposalHash',
              'originalIdempotencyKey',fact->>'requestIdempotencyKey','application',fact->'application',
              'debit',debit_body,'caseBinding',binding->'caseBinding','caseBindingHash',binding->>'caseBindingHash',
              'inputHash',binding->>'verifiedInputHash','purpose','target','attempt',1,
              'callerLogin',session_user,'callerXid',pg_current_xact_id()::text,'callerPid',pg_backend_pid());
            digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
            IF old.intent_id IS NOT NULL THEN
              IF old.immutable IS DISTINCT FROM body OR old.content_hash IS DISTINCT FROM digest
                OR old.origin_xid IS DISTINCT FROM pg_current_xact_id() OR old.origin_pid IS DISTINCT FROM pg_backend_pid() THEN
                RAISE EXCEPTION 'CAPACITY_INTENT_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            ELSE
              INSERT INTO {SCHEMA}.prepared_execution_intent(org_id,project_id,intent_id,debit_id,request_id,case_id,purpose,attempt,state,immutable,content_hash,origin_xid,origin_pid)
              VALUES('org-org','dev-project',p_intent,p_debit,p_request,p_case,'target',1,'prepared',body,digest,pg_current_xact_id(),pg_backend_pid()) RETURNING * INTO old;
            END IF;
            RETURN jsonb_build_object('intentId',old.intent_id,'state',old.state,'immutable',old.immutable,'contentHash',old.content_hash,'executionAllowed',false);
          END $intent$''',
        f'ALTER FUNCTION {INTENT} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {INTENT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {INTENT} TO aos_runtime',
    )


INPUT_DEBIT = 'public.prepare_capacity_input_parent_debit(bytea,jsonb,uuid,text,text,uuid,bigint,bytea,text,bytea)'


def occupation_input_binding_statements():
    """Original input byte evidence before debit; never execution authority."""
    return (
        f'''CREATE FUNCTION {INPUT_DEBIT.split('(')[0]}(p_raw bytea,p_source jsonb,p_hold uuid,
          p_request text,p_hash text,p_debit uuid,p_minor bigint,p_suite_raw bytea,p_case text,p_input_raw bytea)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $inputbind$
          DECLARE fact jsonb; value jsonb; debit jsonb;
          BEGIN
            fact:=public.capacity_occupation_eval_case_fact(p_raw,p_source,p_hold,p_request,p_hash,p_suite_raw,p_case);
            IF p_input_raw IS NULL OR octet_length(p_input_raw)=0 OR octet_length(p_input_raw)>1048576
              OR encode(sha256(p_input_raw),'hex') IS DISTINCT FROM fact->>'inputHash' THEN
              RAISE EXCEPTION 'CAPACITY_CASE_INPUT_BYTES_REQUIRED' USING ERRCODE='23514'; END IF;
            value:=convert_from(p_input_raw,'UTF8')::jsonb;
            debit:=public.prepare_capacity_case_parent_debit(p_raw,p_source,p_hold,p_request,p_hash,p_debit,p_minor,p_suite_raw,p_case);
            RETURN debit||jsonb_build_object('verifiedInputHash',fact->>'inputHash','inputValue',value,'executionAllowed',false);
          END $inputbind$''',
        f'ALTER FUNCTION {INPUT_DEBIT} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {INPUT_DEBIT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {INPUT_DEBIT} TO aos_runtime',
    )


def occupation_case_binding_statements():
    """Bind original Suite bytes and target input refs; no Intent or execution."""
    return (
        f'''CREATE TABLE {SCHEMA}.case_input_binding (
          org_id text NOT NULL,project_id text NOT NULL,
          debit_id uuid PRIMARY KEY REFERENCES {SCHEMA}.prepared_parent_debit(debit_id),
          parent_hold uuid NOT NULL,case_id text NOT NULL,purpose text NOT NULL CHECK(purpose='target'),
          immutable jsonb NOT NULL,content_hash text NOT NULL,origin_xid xid8 NOT NULL,origin_pid integer NOT NULL,
          UNIQUE(org_id,project_id,parent_hold,case_id,purpose))''',
        f'ALTER TABLE {SCHEMA}.case_input_binding OWNER TO {OWNER}',
        f'ALTER TABLE {SCHEMA}.case_input_binding ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {SCHEMA}.case_input_binding FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {SCHEMA}.case_input_binding TO {OWNER}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'REVOKE ALL ON {SCHEMA}.case_input_binding FROM PUBLIC,aos_runtime',
        f'''CREATE FUNCTION {CASE_FACT.split('(')[0]}(p_raw bytea,p_source jsonb,p_hold uuid,
          p_request text,p_hash text,p_suite_raw bytea,p_case text) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $casefact$
          DECLARE fact jsonb; request_body jsonb; s public.aip_eval_suite_revision%ROWTYPE;
            contract record; witness jsonb; selected jsonb; selected_case jsonb;
          BEGIN
            fact:=public.capacity_occupation_eval_fact(p_raw,p_source,p_hold,p_request,p_hash);
            SELECT request_json INTO STRICT request_body FROM public.aip_model_eval_request
              WHERE org_id='org-org' AND project_id='dev-project' AND request_id=p_request AND request_hash=p_hash;
            SELECT * INTO s FROM public.aip_eval_suite_revision WHERE org_id='org-org' AND project_id='dev-project'
              AND suite_id=request_body->'suiteRef'->>'assetId'
              AND revision=(request_body->'suiteRef'->>'revision')::integer;
            IF NOT FOUND OR p_suite_raw IS NULL OR octet_length(p_suite_raw)>1048576
              OR s.content_hash IS DISTINCT FROM request_body->'suiteRef'->>'contentHash'
              OR encode(sha256(p_suite_raw),'hex') IS DISTINCT FROM s.content_hash THEN
              RAISE EXCEPTION 'CAPACITY_CASE_SUITE_BYTES_REQUIRED' USING ERRCODE='23514'; END IF;
            witness:=convert_from(p_suite_raw,'UTF8')::jsonb;
            IF witness IS DISTINCT FROM jsonb_build_object('suiteId',s.suite_id,'revision',s.revision,
              'target',s.target_ref,'dataset',s.dataset_ref,'judge',s.judge_ref,'cases',s.cases,'gateThreshold',s.gate_threshold)
              OR s.target_ref IS DISTINCT FROM jsonb_build_object('assetType','registered_model',
                 'assetId',request_body->'targetRef'->>'assetId','revision',request_body->'targetRef'->>'revision',
                 'contentHash',request_body->'targetRef'->>'contentHash') THEN
              RAISE EXCEPTION 'CAPACITY_CASE_SUITE_ORIGINAL_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT r.* INTO contract FROM public.aip_eval_contract_head head
              JOIN public.aip_eval_contract_revision r USING(org_id,project_id,contract_id)
              WHERE head.org_id='org-org' AND head.project_id='dev-project'
                AND head.contract_id=request_body->'evalContractRef'->>'assetId'
                AND r.revision=head.current_revision
                AND r.revision=(request_body->'evalContractRef'->>'revision')::integer FOR SHARE OF head;
            IF NOT FOUND OR contract.lifecycle IS DISTINCT FROM 'frozen'
              OR contract.content_hash IS DISTINCT FROM request_body->'evalContractRef'->>'contentHash'
              OR contract.suite_ref IS DISTINCT FROM jsonb_build_object('resourceType','EvalSuiteRevision',
                 'resourceId',s.suite_id,'revision',s.revision,'contentHash',s.content_hash) THEN
              RAISE EXCEPTION 'CAPACITY_CASE_CURRENT_CONTRACT_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT jsonb_agg(item) INTO selected FROM jsonb_array_elements(s.cases) item WHERE item->>'caseId'=p_case;
            IF selected IS NULL OR jsonb_array_length(selected)<>1 THEN
              RAISE EXCEPTION 'CAPACITY_CASE_ORIGINAL_REQUIRED' USING ERRCODE='23514'; END IF;
            selected_case:=selected->0;
            IF selected_case->'inputArtifact'->>'contentHash' IS NULL
              OR (selected_case->'inputArtifact'->>'contentHash') !~ '^[0-9a-f]{{64}}$'
              OR nullif(selected_case->'inputArtifact'->>'artifactId','') IS NULL
              OR nullif(selected_case->'inputArtifact'->>'revision','') IS NULL THEN
              RAISE EXCEPTION 'CAPACITY_CASE_INPUT_REF_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN fact||jsonb_build_object('suiteRef',request_body->'suiteRef','targetRef',request_body->'targetRef',
              'caseId',p_case,'inputRef',selected_case->'inputArtifact',
              'inputHash',selected_case->'inputArtifact'->>'contentHash',
              'judgeRef',s.judge_ref,'expectedRef',selected_case->'expectedArtifact');
          END $casefact$''',
        f'ALTER FUNCTION {CASE_FACT} OWNER TO aos_runtime',
        f'REVOKE ALL ON FUNCTION {CASE_FACT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {CASE_FACT} TO {OWNER}',
        f'''CREATE FUNCTION {CASE_DEBIT.split('(')[0]}(p_raw bytea,p_source jsonb,p_hold uuid,
          p_request text,p_hash text,p_debit uuid,p_minor bigint,p_suite_raw bytea,p_case text) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $casebind$
          DECLARE fact jsonb; debit jsonb; body jsonb; digest text; old {SCHEMA}.case_input_binding%ROWTYPE;
          BEGIN
            fact:=public.capacity_occupation_eval_case_fact(p_raw,p_source,p_hold,p_request,p_hash,p_suite_raw,p_case);
            SELECT * INTO old FROM {SCHEMA}.case_input_binding
              WHERE parent_hold=p_hold AND case_id=p_case AND purpose='target';
            IF FOUND AND old.debit_id IS DISTINCT FROM p_debit THEN
              RAISE EXCEPTION 'CAPACITY_CASE_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            debit:=public.prepare_capacity_parent_debit(p_raw,p_source,p_hold,p_request,p_hash,p_debit,p_minor);
            body:=jsonb_build_object('parentHold',p_hold,'requestHash',p_hash,'suiteRef',fact->'suiteRef',
              'targetRef',fact->'targetRef','caseId',p_case,'purpose','target','attempt',1,
              'inputRef',fact->'inputRef','inputHash',fact->>'inputHash',
              'judgeRef',fact->'judgeRef','expectedRef',fact->'expectedRef',
              'debitId',p_debit,'debitHash',debit->>'contentHash');
            digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
            IF old.debit_id IS NOT NULL THEN
              IF old.immutable IS DISTINCT FROM body OR old.content_hash IS DISTINCT FROM digest
                OR old.origin_xid IS DISTINCT FROM pg_current_xact_id() OR old.origin_pid IS DISTINCT FROM pg_backend_pid() THEN
                RAISE EXCEPTION 'CAPACITY_CASE_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            ELSE
              INSERT INTO {SCHEMA}.case_input_binding
                (org_id,project_id,debit_id,parent_hold,case_id,purpose,immutable,content_hash,origin_xid,origin_pid)
                VALUES('org-org','dev-project',p_debit,p_hold,p_case,'target',body,digest,pg_current_xact_id(),pg_backend_pid());
            END IF;
            RETURN debit||jsonb_build_object('caseBindingHash',digest,'caseBinding',body,'inputHash',fact->>'inputHash');
          END $casebind$''',
        f'ALTER FUNCTION {CASE_DEBIT} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {CASE_DEBIT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {CASE_DEBIT} TO aos_runtime',
    )


def occupation_parent_debit_statements():
    """Explicit preparation ledger; no debit can commit without a future protocol.

    This artifact deliberately has no finalizer, Intent, settlement or release.
    It cannot install itself or convert preparation into execution authority.
    """
    tables = (
        ('parent_debit_guard', '''parent_hold uuid PRIMARY KEY,
          request_hash text NOT NULL,parent_hash text NOT NULL,
          cap_minor bigint NOT NULL CHECK(cap_minor>0),
          allocated_minor bigint NOT NULL CHECK(allocated_minor>=0 AND allocated_minor<=cap_minor),
          version bigint NOT NULL CHECK(version>0)'''),
        ('prepared_parent_debit', '''debit_id uuid PRIMARY KEY,
          parent_hold uuid NOT NULL REFERENCES {schema}.parent_debit_guard(parent_hold),
          immutable jsonb NOT NULL,content_hash text NOT NULL,
          upper_bound_minor bigint NOT NULL CHECK(upper_bound_minor>0),
          physical_account_id uuid NOT NULL,token_units bigint NOT NULL CHECK(token_units>0),
          origin_xid xid8 NOT NULL,origin_pid integer NOT NULL CHECK(origin_pid>0)'''),
    )
    statements = []
    for name, fields in tables:
        table = f'{SCHEMA}.{name}'
        statements.extend((
            f'CREATE TABLE {table} (org_id text NOT NULL,project_id text NOT NULL,{fields.format(schema=SCHEMA)})',
            f'ALTER TABLE {table} OWNER TO {OWNER}',
            f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
            f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
            f'''CREATE POLICY exact_scope ON {table} TO {OWNER}
              USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
              WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
            f'REVOKE ALL ON {table} FROM PUBLIC,aos_runtime',
        ))
    statements.extend((
        f'''CREATE FUNCTION {SCHEMA}.reject_unfinalized_parent_debit() RETURNS trigger
          LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $deny$
          BEGIN RAISE EXCEPTION 'CAPACITY_PARENT_FINALIZE_REQUIRED' USING ERRCODE='23514'; END $deny$''',
        f'ALTER FUNCTION {SCHEMA}.reject_unfinalized_parent_debit() OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {SCHEMA}.reject_unfinalized_parent_debit() FROM PUBLIC,aos_runtime',
        f'''CREATE CONSTRAINT TRIGGER require_joint_finalization AFTER INSERT OR UPDATE
          ON {SCHEMA}.prepared_parent_debit DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION {SCHEMA}.reject_unfinalized_parent_debit()''',
        f'''CREATE FUNCTION {DEBIT.split('(')[0]}(p_raw bytea,p_source jsonb,p_hold uuid,
          p_request text,p_hash text,p_debit uuid,p_minor bigint) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $debit$
          DECLARE fact jsonb; g {SCHEMA}.parent_debit_guard%ROWTYPE;
            prior {SCHEMA}.prepared_parent_debit%ROWTYPE; body jsonb; digest text;
            used_requests bigint; used_tokens numeric;
            xid_value xid8:=pg_current_xact_id(); pid_value integer:=pg_backend_pid();
          BEGIN
            IF p_debit IS NULL OR p_minor IS NULL OR p_minor<=0 THEN
              RAISE EXCEPTION 'CAPACITY_PARENT_DEBIT_INPUT_REQUIRED' USING ERRCODE='23514'; END IF;
            fact:=public.capacity_occupation_eval_fact(p_raw,p_source,p_hold,p_request,p_hash);
            IF fact->'tokenLimit'->>'mode' IS DISTINCT FROM 'inflight_upper_bound' THEN
              RAISE EXCEPTION 'CAPACITY_PHYSICAL_TOKEN_MODE_REQUIRED' USING ERRCODE='23514'; END IF;
            IF NOT EXISTS(SELECT 1 FROM {SCHEMA}.account_guard
              WHERE physical_account_id=(fact->>'physicalAccountId')::uuid
                AND org_id='org-org' AND project_id='dev-project'
                AND xmin::text::numeric=(xid_value::text::numeric % 4294967296)) THEN
              RAISE EXCEPTION 'CAPACITY_PARENT_CURRENT_PHYSICAL_GUARD_REQUIRED' USING ERRCODE='23514'; END IF;
            INSERT INTO {SCHEMA}.parent_debit_guard AS d
              (org_id,project_id,parent_hold,request_hash,parent_hash,cap_minor,allocated_minor,version)
              VALUES('org-org','dev-project',p_hold,p_hash,fact->>'contentHash',
                     (fact->>'upperBoundMinor')::bigint,0,1)
              ON CONFLICT(parent_hold) DO UPDATE SET version=d.version+1
                WHERE d.org_id='org-org' AND d.project_id='dev-project'
                  AND d.request_hash=p_hash AND d.parent_hash=fact->>'contentHash'
                  AND d.cap_minor=(fact->>'upperBoundMinor')::bigint RETURNING * INTO g;
            IF NOT FOUND THEN RAISE EXCEPTION 'CAPACITY_PARENT_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
            body:=jsonb_build_object('debitId',p_debit,'parentHold',p_hold,'requestId',p_request,
              'requestHash',p_hash,'parentHash',fact->>'contentHash','sourceRef',p_source,
              'physicalAccountId',fact->>'physicalAccountId','upperBoundMinor',p_minor,
              'currency',fact->>'currency','purpose','model-eval-preparation',
              'quotaRef',fact->'quotaRef','tokenUnits',fact->'tokenUpperBound');
            digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
            SELECT * INTO prior FROM {SCHEMA}.prepared_parent_debit WHERE debit_id=p_debit;
            IF FOUND THEN
              IF prior.immutable IS DISTINCT FROM body OR prior.content_hash IS DISTINCT FROM digest
                OR prior.origin_xid IS DISTINCT FROM xid_value OR prior.origin_pid IS DISTINCT FROM pid_value THEN
                RAISE EXCEPTION 'CAPACITY_PARENT_DEBIT_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            ELSE
              IF p_minor>g.cap_minor-g.allocated_minor THEN
                RAISE EXCEPTION 'CAPACITY_PARENT_CAP_EXCEEDED' USING ERRCODE='23514'; END IF;
              SELECT count(*),coalesce(sum(token_units),0) INTO used_requests,used_tokens
                FROM {SCHEMA}.prepared_parent_debit
                WHERE physical_account_id=(fact->>'physicalAccountId')::uuid;
              IF used_requests>=(fact->>'maxConcurrency')::bigint
                OR used_tokens+(fact->>'tokenUpperBound')::bigint>(fact->'tokenLimit'->>'maxTokens')::numeric THEN
                RAISE EXCEPTION 'CAPACITY_PHYSICAL_CAPACITY_EXCEEDED' USING ERRCODE='23514'; END IF;
              UPDATE {SCHEMA}.parent_debit_guard SET allocated_minor=allocated_minor+p_minor WHERE parent_hold=p_hold
                RETURNING * INTO g;
              INSERT INTO {SCHEMA}.prepared_parent_debit
                (org_id,project_id,debit_id,parent_hold,immutable,content_hash,upper_bound_minor,
                 physical_account_id,token_units,origin_xid,origin_pid)
                VALUES('org-org','dev-project',p_debit,p_hold,body,digest,p_minor,
                       (fact->>'physicalAccountId')::uuid,(fact->>'tokenUpperBound')::bigint,xid_value,pid_value);
            END IF;
            SELECT count(*),coalesce(sum(token_units),0) INTO used_requests,used_tokens
              FROM {SCHEMA}.prepared_parent_debit WHERE physical_account_id=(fact->>'physicalAccountId')::uuid;
            RETURN jsonb_build_object('debitId',p_debit,'contentHash',digest,'allocatedMinor',g.allocated_minor,
              'parentCapMinor',g.cap_minor,'physicalRequests',used_requests,'physicalTokens',used_tokens,
              'xid',xid_value::text,'pid',pid_value,'executionAllowed',false);
          END $debit$''',
        f'ALTER FUNCTION {DEBIT} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {DEBIT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {DEBIT} TO aos_runtime',
    ))
    return tuple(statements)


def occupation_account_guard_statements():
    """Source-only guard before budgets, explicit artifact on an empty schema."""
    return (
        f'CREATE SCHEMA {SCHEMA} AUTHORIZATION {OWNER}',
        f'''CREATE TABLE {SCHEMA}.account_guard (
          physical_account_id uuid PRIMARY KEY,org_id text NOT NULL,project_id text NOT NULL,
          supplier_id text NOT NULL,supplier_account_fingerprint text NOT NULL,
          version bigint NOT NULL CHECK(version>0))''',
        f'ALTER TABLE {SCHEMA}.account_guard OWNER TO {OWNER}',
        f'ALTER TABLE {SCHEMA}.account_guard ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {SCHEMA}.account_guard FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {SCHEMA}.account_guard TO {OWNER}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'REVOKE ALL ON {SCHEMA}.account_guard FROM PUBLIC,aos_runtime',
        f'''CREATE FUNCTION {SOURCE_FACT.split('(')[0]}(p_raw bytea,p_source jsonb) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $source$
          DECLARE s record;
          BEGIN
            SELECT * INTO STRICT s FROM public.read_capacity_source_for_occupation(p_raw,p_source);
            RETURN convert_from(s.source_raw,'UTF8')::jsonb;
          END $source$;''',
        f'ALTER FUNCTION {SOURCE_FACT} OWNER TO aos_runtime',
        f'REVOKE ALL ON FUNCTION {SOURCE_FACT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {SOURCE_FACT} TO {OWNER}',
        f'''CREATE FUNCTION {GUARD.split('(')[0]}(p_raw bytea,p_source jsonb) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $guard$
          DECLARE document jsonb; guard_version bigint; now_at timestamptz;
          BEGIN
            document:=public.capacity_occupation_source_fact(p_raw,p_source);
            INSERT INTO {SCHEMA}.account_guard AS g
              (physical_account_id,org_id,project_id,supplier_id,supplier_account_fingerprint,version)
              VALUES((document->>'physicalAccountId')::uuid,'org-org','dev-project',
                     document->>'supplierId',document->>'supplierAccountFingerprint',1)
              ON CONFLICT(physical_account_id) DO UPDATE SET version=g.version+1
                WHERE g.org_id='org-org' AND g.project_id='dev-project'
                  AND g.supplier_id=EXCLUDED.supplier_id
                  AND g.supplier_account_fingerprint=EXCLUDED.supplier_account_fingerprint
              RETURNING version INTO guard_version;
            IF NOT FOUND THEN RAISE EXCEPTION 'PHYSICAL_ACCOUNT_MAPPING_REQUIRED' USING ERRCODE='23514'; END IF;
            now_at:=clock_timestamp();
            IF (document->>'validUntil')::timestamptz<=now_at THEN
              RAISE EXCEPTION 'PHYSICAL_ACCOUNT_CURRENT_SOURCE_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('sourceRef',p_source,'physicalAccountId',document->>'physicalAccountId',
              'version',guard_version,'xid',pg_current_xact_id()::text,'pid',pg_backend_pid(),
              'checkedAt',now_at,'executionAllowed',false);
          END $guard$;''',
        f'ALTER FUNCTION {GUARD} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {GUARD} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {GUARD} TO aos_runtime',
    )


def occupation_eval_fact_statements():
    """Compile fixed SQL; installation needs its own authorized deployment gate."""
    body = """DECLARE
      s record; document jsonb; h public.aip_model_eval_budget_reservation%ROWTYPE;
      r public.aip_model_eval_request%ROWTYPE; a public.aip_action_approval_event%ROWTYPE;
      p public.aip_action_proposal%ROWTYPE; q record; token_upper bigint;
      n bigint; exact_rows boolean; now_at timestamptz;
      xid_value text:=pg_current_xact_id()::text;
      xid_low bigint:=(pg_current_xact_id()::text::numeric % 4294967296)::bigint;
    BEGIN
      IF current_user<>'aos_runtime' OR session_user<>'aos_provider_capacity_occupation'
        OR current_setting('transaction_isolation')<>'serializable'
        OR current_setting('transaction_read_only')<>'off'
        OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
        OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project' THEN
        RAISE EXCEPTION 'CAPACITY_EVAL_FACT_CALLER_REQUIRED' USING ERRCODE='42501';
      END IF;
      SELECT * INTO STRICT s FROM public.read_capacity_source_for_occupation(p_raw,p_source);
      document:=convert_from(s.source_raw,'UTF8')::jsonb;
      SELECT * INTO h FROM public.aip_model_eval_budget_reservation
        WHERE org_id='org-org' AND project_id='dev-project' AND reservation_id=p_hold
          AND request_id=p_request AND request_hash=p_hash AND state='held'
          AND xmin::text::bigint=xid_low;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'CAPACITY_EVAL_FACT_CURRENT_HOLD_REQUIRED' USING ERRCODE='23514';
      END IF;
      SELECT * INTO STRICT r FROM public.aip_model_eval_request
        WHERE org_id=h.org_id AND project_id=h.project_id AND request_id=h.request_id
          AND request_hash=h.request_hash;
      SELECT * INTO STRICT a FROM public.aip_action_approval_event
        WHERE org_id=h.org_id AND project_id=h.project_id AND approval_event_id=h.approval_event_id
          AND decision='approved';
      SELECT * INTO STRICT p FROM public.aip_action_proposal
        WHERE org_id=h.org_id AND project_id=h.project_id AND proposal_id=a.proposal_id;
      IF (document->'providerRefs' @> jsonb_build_array(r.request_json->'providerRef')) IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'CAPACITY_EVAL_FACT_PROVIDER_REQUIRED' USING ERRCODE='23514';
      END IF;
      IF r.request_hash<>encode(sha256(convert_to(public.canonical_asset_registry_jsonb(r.request_json),'UTF8')),'hex')
        OR h.proposal_hash IS DISTINCT FROM p.proposal_hash
        OR h.proposal_id IS DISTINCT FROM a.proposal_id
        OR p.status IS DISTINCT FROM 'approved' OR p.version IS DISTINCT FROM a.proposal_version+1
        OR p.payload IS DISTINCT FROM jsonb_build_object('requestId',r.request_id,'requestHash',r.request_hash)
        OR h.budget_policy_ref IS DISTINCT FROM r.request_json->'budgetPolicyRef'
        OR h.price_ref IS DISTINCT FROM jsonb_build_object(
          'resourceType',r.request_json->'priceRef'->>'assetType',
          'resourceId',r.request_json->'priceRef'->>'assetId',
          'revision',r.request_json->'priceRef'->'revision',
          'contentHash','sha256:'||(r.request_json->'priceRef'->>'contentHash'))
        OR h.upper_bound_minor IS DISTINCT FROM (r.request_json->>'upperBoundMinor')::bigint
        OR h.currency IS DISTINCT FROM r.request_json->>'currency'
        OR h.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
          public.canonical_asset_registry_jsonb(jsonb_build_object(
            'reservationId',h.reservation_id,'requestId',h.request_id,'requestHash',h.request_hash,
            'proposalId',h.proposal_id,'proposalHash',h.proposal_hash,'approvalEventId',h.approval_event_id,
            'budgetPolicyRef',h.budget_policy_ref,'budgetRevisionRef',h.budget_revision_ref,
            'priceRef',h.price_ref,'currency',h.currency,'upperBoundMinor',h.upper_bound_minor,'state',h.state)),
          'UTF8')),'hex') THEN
        RAISE EXCEPTION 'CAPACITY_EVAL_FACT_ORIGINAL_BINDING_REQUIRED' USING ERRCODE='23514';
      END IF;
      SELECT count(*),bool_and(l.reserved_minor=h.upper_bound_minor
          AND b.held_minor>=l.reserved_minor AND l.xmin::text::bigint=xid_low
          AND b.xmin::text::bigint=xid_low AND l.currency=h.currency
          AND ((l.bucket_kind='task' AND l.account_id='model-eval/'||h.request_id)
            OR (l.bucket_kind='daily' AND l.account_id=(h.budget_revision_ref->>'resourceId')||':daily')
            OR (l.bucket_kind='pilot' AND l.account_id=(h.budget_revision_ref->>'resourceId')||':pilot'))) INTO n,exact_rows
        FROM public.aip_model_eval_budget_reservation_bucket l
        JOIN public.aip_budget_bucket b USING(org_id,project_id,bucket_kind,account_id,period_start,currency)
        WHERE l.org_id=h.org_id AND l.project_id=h.project_id AND l.reservation_id=h.reservation_id;
      IF n<>3 OR exact_rows IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'CAPACITY_EVAL_FACT_THREE_CURRENT_BUCKETS_REQUIRED' USING ERRCODE='23514';
      END IF;
      SELECT v.payload,v.content_hash,v.lifecycle,v.effective_from,v.effective_until INTO q
        FROM public.aip_model_governance_policy_head head
        JOIN public.aip_model_governance_policy_revision v USING(org_id,project_id,policy_kind,policy_id)
        WHERE head.org_id=h.org_id AND head.project_id=h.project_id AND head.policy_kind='quota'
          AND head.policy_id=r.request_json->'quotaPolicyRef'->>'assetId'
          AND v.revision=head.current_revision AND v.revision=(r.request_json->'quotaPolicyRef'->>'revision')::integer
        FOR SHARE OF head;
      IF NOT FOUND THEN RAISE EXCEPTION 'CAPACITY_EVAL_CURRENT_QUOTA_REQUIRED' USING ERRCODE='23514'; END IF;
      IF r.request_json->'quotaPolicyRef'->>'assetType' IS DISTINCT FROM 'QuotaPolicyRevision'
        OR q.lifecycle IS DISTINCT FROM 'active'
        OR q.content_hash IS DISTINCT FROM r.request_json->'quotaPolicyRef'->>'contentHash'
        OR q.payload->>'contentHash' IS DISTINCT FROM q.content_hash
        OR q.payload->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',h.org_id,'projectId',h.project_id)
        OR q.content_hash IS DISTINCT FROM encode(sha256(convert_to(public.canonical_asset_registry_jsonb(
             q.payload-ARRAY['tenant','contentHash','createdBy','createdAt']),'UTF8')),'hex')
        OR jsonb_typeof(q.payload->'maxInputTokens') IS DISTINCT FROM 'number'
        OR jsonb_typeof(q.payload->'maxOutputTokens') IS DISTINCT FROM 'number'
        OR (q.payload->>'maxInputTokens') !~ '^[0-9]+$'
        OR (q.payload->>'maxOutputTokens') !~ '^[0-9]+$'
        OR (q.payload->>'maxInputTokens')::bigint NOT BETWEEN 1 AND 8000
        OR (q.payload->>'maxOutputTokens')::bigint NOT BETWEEN 1 AND 2000 THEN
        RAISE EXCEPTION 'CAPACITY_EVAL_EXACT_QUOTA_REQUIRED' USING ERRCODE='23514'; END IF;
      token_upper:=(q.payload->>'maxInputTokens')::bigint+(q.payload->>'maxOutputTokens')::bigint;
      now_at:=clock_timestamp();
      IF r.expires_at<=now_at OR a.expires_at IS NULL OR a.expires_at<=now_at
         OR q.effective_from IS NULL OR q.effective_until IS NULL
         OR q.effective_from>now_at OR q.effective_until<=now_at
         OR (document->>'validFrom')::timestamptz>now_at
         OR (document->>'validUntil')::timestamptz<=now_at THEN
        RAISE EXCEPTION 'CAPACITY_EVAL_FACT_CURRENT_DEADLINES_REQUIRED' USING ERRCODE='23514';
      END IF;
      IF p.created_by IS DISTINCT FROM r.created_by OR a.actor_id IS NOT DISTINCT FROM r.created_by
        OR nullif(r.created_by,'') IS NULL OR nullif(a.actor_id,'') IS NULL THEN
        RAISE EXCEPTION 'CAPACITY_EVAL_FACT_INDEPENDENT_ACTORS_REQUIRED' USING ERRCODE='23514'; END IF;
      RETURN jsonb_build_object('application',r.request_json,'requestMaker',r.created_by,
        'approvalChecker',a.actor_id,'approvalSnapshot',to_jsonb(a),
        'proposalId',p.proposal_id,'proposalHash',p.proposal_hash,'requestIdempotencyKey',r.idempotency_key,
        'sourceRef',p_source,'physicalAccountId',document->>'physicalAccountId',
        'quotaRef',r.request_json->'quotaPolicyRef','tokenUpperBound',token_upper,
        'maxConcurrency',document->'maxConcurrency','tokenLimit',document->'tokenLimit',
        'providerRef',r.request_json->'providerRef','reservationId',h.reservation_id,
        'requestId',r.request_id,'requestHash',r.request_hash,'contentHash',h.content_hash,
        'approvalEventId',a.approval_event_id,'upperBoundMinor',h.upper_bound_minor,
        'currency',h.currency,'xid',xid_value,'pid',pg_backend_pid(),'checkedAt',now_at,
        'executionAllowed',false);
    END"""
    arguments='p_raw bytea,p_source jsonb,p_hold uuid,p_request text,p_hash text'
    return (
        f'CREATE FUNCTION {FACT.split("(")[0]}({arguments}) RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $fact${body}$fact$;',
        f'ALTER FUNCTION {FACT} OWNER TO aos_runtime',
        f'REVOKE ALL ON FUNCTION {FACT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {FACT} TO {OWNER}',
        f'''CREATE FUNCTION {ENTRY.split("(")[0]}({arguments}) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $entry$
          BEGIN RETURN public.capacity_occupation_eval_fact(p_raw,p_source,p_hold,p_request,p_hash); END $entry$;''',
        f'ALTER FUNCTION {ENTRY} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {ENTRY} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {ENTRY} TO aos_runtime',
    )


JUDGE_DEBIT = 'public.prepare_capacity_judge_parent_debit(bytea,jsonb,uuid,text,text,uuid,bigint,text)'


def occupation_judge_parent_debit_statements():
    """Prepare a Judge case in the original shared ledger; never finalization.

    Requires the joint caller's original Source/Rule/risk prefix. Necessary
    fact readers alone are insufficient for execution. The original deferred
    rejection on prepared_parent_debit remains in force for these rows too.
    """
    return (
        f'''CREATE FUNCTION {JUDGE_DEBIT.split('(')[0]}(p_raw bytea,p_source jsonb,p_hold uuid,
          p_request text,p_hash text,p_debit uuid,p_minor bigint,p_case text) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $judgedebit$
          DECLARE fact jsonb; source_body jsonb; after_fact jsonb; selected jsonb;
            g {SCHEMA}.parent_debit_guard%ROWTYPE;
            prior {SCHEMA}.prepared_parent_debit%ROWTYPE;
            body jsonb; digest text; used_requests bigint; used_tokens numeric;
            xid_value xid8:=pg_current_xact_id(); pid_value integer:=pg_backend_pid();
          BEGIN
            IF current_user<>'{OWNER}' OR session_user<>'aos_provider_capacity_occupation'
              OR current_setting('transaction_isolation')<>'serializable'
              OR current_setting('transaction_read_only')<>'off'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project' THEN
              RAISE EXCEPTION 'CAPACITY_JUDGE_DEBIT_CALLER_REQUIRED' USING ERRCODE='42501';
            END IF;
            IF p_debit IS NULL OR p_minor IS NULL OR p_minor<=0 OR p_case IS NULL OR p_case='' THEN
              RAISE EXCEPTION 'CAPACITY_JUDGE_DEBIT_INPUT_REQUIRED' USING ERRCODE='23514';
            END IF;
            fact:=public.capacity_occupation_judge_fact(p_raw,p_source,p_hold,p_request,p_hash);
            source_body:=public.capacity_occupation_source_fact(p_raw,p_source);
            SELECT jsonb_agg(item) INTO selected
              FROM jsonb_array_elements(fact->'application'->'cases') item WHERE item->>'caseId'=p_case;
            IF fact->>'purpose' IS DISTINCT FROM 'model-judge-call'
              OR fact->>'requestId' IS DISTINCT FROM p_request OR fact->>'requestHash' IS DISTINCT FROM p_hash
              OR fact->>'reservationId' IS DISTINCT FROM p_hold::text
              OR fact->>'xid' IS DISTINCT FROM xid_value::text
              OR (fact->>'pid')::integer IS DISTINCT FROM pid_value
              OR selected IS NULL OR jsonb_array_length(selected)<>1
              OR source_body->'tokenLimit'->>'mode' IS DISTINCT FROM 'inflight_upper_bound'
              OR source_body->>'physicalAccountId' IS DISTINCT FROM fact->>'physicalAccountId'
              OR (fact->>'tokenUpperBound')::bigint IS NULL OR (fact->>'tokenUpperBound')::bigint<=0
              OR (source_body->>'maxConcurrency')::bigint IS NULL OR (source_body->>'maxConcurrency')::bigint<=0
              OR (source_body->'tokenLimit'->>'maxTokens')::numeric IS NULL
              OR (source_body->'tokenLimit'->>'maxTokens')::numeric<=0 THEN
              RAISE EXCEPTION 'CAPACITY_JUDGE_DEBIT_ORIGINAL_FACTS_REQUIRED' USING ERRCODE='23514';
            END IF;
            PERFORM 1 FROM {SCHEMA}.account_guard
              WHERE physical_account_id=(fact->>'physicalAccountId')::uuid
                AND org_id='org-org' AND project_id='dev-project'
                AND xmin::text::numeric=(xid_value::text::numeric % 4294967296) FOR UPDATE;
            IF NOT FOUND THEN
              RAISE EXCEPTION 'CAPACITY_JUDGE_DEBIT_CURRENT_PHYSICAL_GUARD_REQUIRED' USING ERRCODE='23514';
            END IF;
            INSERT INTO {SCHEMA}.parent_debit_guard AS d
              (org_id,project_id,parent_hold,request_hash,parent_hash,cap_minor,allocated_minor,version)
              VALUES('org-org','dev-project',p_hold,p_hash,fact->>'contentHash',
                (fact->>'upperBoundMinor')::bigint,0,1)
              ON CONFLICT(parent_hold) DO UPDATE SET version=d.version+1
                WHERE d.org_id='org-org' AND d.project_id='dev-project'
                  AND d.request_hash=p_hash AND d.parent_hash=fact->>'contentHash'
                  AND d.cap_minor=(fact->>'upperBoundMinor')::bigint RETURNING * INTO g;
            IF NOT FOUND THEN RAISE EXCEPTION 'CAPACITY_JUDGE_DEBIT_PARENT_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
            body:=jsonb_build_object('debitId',p_debit,'parentHold',p_hold,'requestId',p_request,
              'requestHash',p_hash,'parentHash',fact->>'contentHash','sourceRef',p_source,
              'physicalAccountId',fact->>'physicalAccountId','upperBoundMinor',p_minor,
              'currency',fact->>'currency','purpose','model-judge-preparation','caseId',p_case,
              'originalCase',selected->0,'caseSetHash',fact->>'caseSetHash',
              'approvalEventId',fact->>'approvalEventId','quotaRef',fact->'quotaRef',
              'tokenUnits',fact->'tokenUpperBound');
            digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
            IF EXISTS(SELECT 1 FROM {SCHEMA}.prepared_parent_debit
              WHERE org_id='org-org' AND project_id='dev-project'
                AND immutable->>'purpose'='model-judge-preparation'
                AND immutable->>'requestId'=p_request AND immutable->>'caseId'=p_case
                AND debit_id<>p_debit) THEN
              RAISE EXCEPTION 'CAPACITY_JUDGE_CASE_ALLOCATION_CONFLICT' USING ERRCODE='23514';
            END IF;
            SELECT * INTO prior FROM {SCHEMA}.prepared_parent_debit WHERE debit_id=p_debit;
            IF FOUND THEN
              IF prior.immutable IS DISTINCT FROM body OR prior.content_hash IS DISTINCT FROM digest
                OR prior.origin_xid IS DISTINCT FROM xid_value OR prior.origin_pid IS DISTINCT FROM pid_value THEN
                RAISE EXCEPTION 'CAPACITY_JUDGE_DEBIT_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            ELSE
              IF p_minor>g.cap_minor-g.allocated_minor THEN
                RAISE EXCEPTION 'CAPACITY_PARENT_CAP_EXCEEDED' USING ERRCODE='23514'; END IF;
              SELECT count(*),coalesce(sum(token_units),0) INTO used_requests,used_tokens
                FROM {SCHEMA}.prepared_parent_debit WHERE physical_account_id=(fact->>'physicalAccountId')::uuid;
              IF used_requests>=(source_body->>'maxConcurrency')::bigint
                OR used_tokens+(fact->>'tokenUpperBound')::bigint>(source_body->'tokenLimit'->>'maxTokens')::numeric THEN
                RAISE EXCEPTION 'CAPACITY_PHYSICAL_CAPACITY_EXCEEDED' USING ERRCODE='23514'; END IF;
              UPDATE {SCHEMA}.parent_debit_guard SET allocated_minor=allocated_minor+p_minor
                WHERE parent_hold=p_hold RETURNING * INTO g;
              INSERT INTO {SCHEMA}.prepared_parent_debit(org_id,project_id,debit_id,parent_hold,
                immutable,content_hash,upper_bound_minor,physical_account_id,token_units,origin_xid,origin_pid)
                VALUES('org-org','dev-project',p_debit,p_hold,body,digest,p_minor,
                  (fact->>'physicalAccountId')::uuid,(fact->>'tokenUpperBound')::bigint,xid_value,pid_value);
            END IF;
            -- All original time/currentness checks follow the possible guard waits.
            after_fact:=public.capacity_occupation_judge_fact(p_raw,p_source,p_hold,p_request,p_hash);
            IF after_fact->>'contentHash' IS DISTINCT FROM fact->>'contentHash'
              OR after_fact->>'caseSetHash' IS DISTINCT FROM fact->>'caseSetHash'
              OR after_fact->>'physicalAccountId' IS DISTINCT FROM fact->>'physicalAccountId'
              OR after_fact->>'xid' IS DISTINCT FROM xid_value::text
              OR (after_fact->>'pid')::integer IS DISTINCT FROM pid_value
              OR (source_body->>'validUntil')::timestamptz IS NULL
              OR (source_body->>'validUntil')::timestamptz<=clock_timestamp() THEN
              RAISE EXCEPTION 'CAPACITY_JUDGE_DEBIT_CURRENT_AFTER_WAITS_REQUIRED' USING ERRCODE='23514';
            END IF;
            RETURN jsonb_build_object('debitId',p_debit,'contentHash',digest,'immutable',body,
              'allocatedMinor',g.allocated_minor,'parentCapMinor',g.cap_minor,
              'xid',xid_value::text,'pid',pid_value,'executionAllowed',false);
          END $judgedebit$''',
        f'ALTER FUNCTION {JUDGE_DEBIT} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {JUDGE_DEBIT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {JUDGE_DEBIT} TO aos_runtime',
    )


JUDGE_INTENT = 'public.prepare_capacity_judge_execution_intent(bytea,jsonb,uuid,text,text,uuid,bigint,text,uuid,uuid)'


def occupation_judge_intent_statements():
    """Original new-purpose Intent awaiting an original Target result.

    Explicit isolated artifact only. A pending dependency is never actual
    Judge input or execution authority; both old and new commit-denial gates
    remain unconditional until the complete joint finalizer is implemented.
    """
    table = SCHEMA + '.prepared_judge_intent'
    return (
        f'''CREATE TABLE {table} (
          org_id text NOT NULL,project_id text NOT NULL,intent_id uuid PRIMARY KEY,
          debit_id uuid NOT NULL UNIQUE REFERENCES {SCHEMA}.prepared_parent_debit(debit_id),
          target_intent_id uuid NOT NULL REFERENCES {SCHEMA}.prepared_execution_intent(intent_id),
          request_id text NOT NULL,case_id text NOT NULL,
          purpose text NOT NULL CHECK(purpose='judge'),attempt integer NOT NULL CHECK(attempt=1),
          state text NOT NULL CHECK(state='awaiting_target_result'),
          immutable jsonb NOT NULL,content_hash text NOT NULL,origin_xid xid8 NOT NULL,origin_pid integer NOT NULL,
          UNIQUE(org_id,project_id,request_id,case_id,purpose,attempt))''',
        f'ALTER TABLE {table} OWNER TO {OWNER}',
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {table} TO {OWNER}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'REVOKE ALL ON {table} FROM PUBLIC,aos_runtime',
        f'CREATE TRIGGER immutable_prepared_judge_intent BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.immutable_prepared_intent()',
        f'CREATE TRIGGER no_truncate_prepared_judge_intent BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {SCHEMA}.immutable_prepared_intent()',
        f'CREATE CONSTRAINT TRIGGER no_unfinalized_judge_intent AFTER INSERT ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.reject_unfinalized_parent_debit()',
        f'''CREATE FUNCTION {JUDGE_INTENT.split('(')[0]}(p_raw bytea,p_source jsonb,p_hold uuid,
          p_request text,p_hash text,p_debit uuid,p_minor bigint,p_case text,p_target uuid,p_intent uuid)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $judgeintent$
          DECLARE fact jsonb; original_case jsonb; debit jsonb; debit_body jsonb; body jsonb; digest text;
            target {SCHEMA}.prepared_execution_intent%ROWTYPE;
            old {table}%ROWTYPE;
          BEGIN
            IF p_intent IS NULL OR p_target IS NULL THEN
              RAISE EXCEPTION 'CAPACITY_JUDGE_INTENT_ID_REQUIRED' USING ERRCODE='23514'; END IF;
            -- This original native reader authenticates the occupation caller
            -- before any private Target/Intent lookup or mutation.
            fact:=public.capacity_occupation_judge_fact(p_raw,p_source,p_hold,p_request,p_hash);
            SELECT jsonb_agg(item) INTO original_case
              FROM jsonb_array_elements(fact->'application'->'cases') item WHERE item->>'caseId'=p_case;
            IF original_case IS NULL OR jsonb_array_length(original_case)<>1
              OR fact->'application'->'ruleFacts'->'rule'->>'inputProtocol'
                 IS DISTINCT FROM 'aos.model-eval-judge-input/v1' THEN
              RAISE EXCEPTION 'CAPACITY_JUDGE_INTENT_ORIGINAL_CASE_REQUIRED' USING ERRCODE='23514'; END IF;
            original_case:=original_case->0;
            SELECT * INTO target FROM {SCHEMA}.prepared_execution_intent
              WHERE intent_id=p_target AND org_id='org-org' AND project_id='dev-project' FOR SHARE;
            IF NOT FOUND OR target.origin_xid IS DISTINCT FROM pg_current_xact_id()
              OR target.origin_pid IS DISTINCT FROM pg_backend_pid()
              OR target.purpose IS DISTINCT FROM 'target' OR target.attempt IS DISTINCT FROM 1
              OR target.state IS DISTINCT FROM 'prepared' OR target.case_id IS DISTINCT FROM p_case
              OR target.request_id IS DISTINCT FROM fact->'application'->'targetApplication'->>'requestId'
              OR target.immutable->>'requestHash' IS DISTINCT FROM fact->'application'->'targetApplication'->>'requestHash'
              OR target.immutable->'application' IS DISTINCT FROM fact->'application'->'targetApplication'->'request'
              OR target.immutable->>'inputHash' IS DISTINCT FROM original_case->'inputArtifact'->>'contentHash'
              OR target.immutable->>'callerLogin' IS DISTINCT FROM session_user
              OR target.immutable->>'intentId' IS DISTINCT FROM p_target::text
              OR target.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                   public.canonical_asset_registry_jsonb(target.immutable),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'CAPACITY_JUDGE_INTENT_ORIGINAL_TARGET_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT * INTO old FROM {table} WHERE org_id='org-org' AND project_id='dev-project'
              AND request_id=p_request AND case_id=p_case AND purpose='judge' AND attempt=1;
            IF FOUND AND old.intent_id IS DISTINCT FROM p_intent THEN
              RAISE EXCEPTION 'CAPACITY_JUDGE_INTENT_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            SELECT * INTO old FROM {table} WHERE intent_id=p_intent;
            IF FOUND AND (old.debit_id IS DISTINCT FROM p_debit OR old.target_intent_id IS DISTINCT FROM p_target
              OR old.request_id IS DISTINCT FROM p_request OR old.case_id IS DISTINCT FROM p_case) THEN
              RAISE EXCEPTION 'CAPACITY_JUDGE_INTENT_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            debit:=public.prepare_capacity_judge_parent_debit(p_raw,p_source,p_hold,p_request,p_hash,p_debit,p_minor,p_case);
            SELECT immutable INTO STRICT debit_body FROM {SCHEMA}.prepared_parent_debit WHERE debit_id=p_debit;
            body:=jsonb_build_object('intentId',p_intent,'state','awaiting_target_result',
              'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
              'requestId',p_request,'requestHash',p_hash,'requestMaker',fact->>'requestMaker',
              'approvalChecker',fact->>'approvalChecker','approvalSnapshot',fact->'approvalSnapshot',
              'proposalId',fact->'approvalSnapshot'->>'proposal_id','proposalHash',fact->'approvalSnapshot'->>'proposal_hash',
              'approvalIdempotencyKey',fact->'approvalSnapshot'->>'idempotency_key','application',fact->'application',
              'originalCase',original_case,'debit',debit_body,'debitHash',debit->>'contentHash',
              'targetIntentId',p_target,'targetIntentHash',target.content_hash,
              'inputDependency',jsonb_build_object('protocol','aos.model-eval-judge-input/v1',
                'state','awaiting_target_result','targetIntentId',p_target,
                'targetIntentHash',target.content_hash,'expectedArtifact',original_case->'expectedArtifact'),
              'purpose','judge','attempt',1,'callerLogin',session_user,
              'callerXid',pg_current_xact_id()::text,'callerPid',pg_backend_pid());
            digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
            IF old.intent_id IS NOT NULL THEN
              IF old.immutable IS DISTINCT FROM body OR old.content_hash IS DISTINCT FROM digest
                OR old.origin_xid IS DISTINCT FROM pg_current_xact_id() OR old.origin_pid IS DISTINCT FROM pg_backend_pid() THEN
                RAISE EXCEPTION 'CAPACITY_JUDGE_INTENT_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            ELSE
              INSERT INTO {table}(org_id,project_id,intent_id,debit_id,target_intent_id,request_id,
                case_id,purpose,attempt,state,immutable,content_hash,origin_xid,origin_pid)
                VALUES('org-org','dev-project',p_intent,p_debit,p_target,p_request,p_case,'judge',1,
                  'awaiting_target_result',body,digest,pg_current_xact_id(),pg_backend_pid()) RETURNING * INTO old;
            END IF;
            fact:=public.capacity_occupation_judge_fact(p_raw,p_source,p_hold,p_request,p_hash);
            IF fact->>'contentHash' IS DISTINCT FROM debit_body->>'parentHash'
              OR fact->>'xid' IS DISTINCT FROM pg_current_xact_id()::text THEN
              RAISE EXCEPTION 'CAPACITY_JUDGE_INTENT_CURRENT_AFTER_WAITS_REQUIRED' USING ERRCODE='23514'; END IF;
            -- Allocation performs the original currentness recheck after waits;
            -- no future Target result or arbitrary input is asserted here.
            RETURN jsonb_build_object('intentId',old.intent_id,'state',old.state,'immutable',old.immutable,
              'contentHash',old.content_hash,'executionAllowed',false);
          END $judgeintent$''',
        f'ALTER FUNCTION {JUDGE_INTENT} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {JUDGE_INTENT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {JUDGE_INTENT} TO aos_runtime',
    )


PLAN_FACT = 'public.capacity_occupation_plan_risk_fact(bytea,jsonb,uuid,text,text,uuid,text,text)'
PLAN_RISK = 'public.prepare_capacity_plan_risk(bytea,jsonb,uuid,text,text,uuid,text,text,uuid)'


def occupation_plan_risk_statements():
    """Complete original case coverage, separate from actual inflight admission.

    Explicit isolated artifact; reserves no extra money and grants no call.
    The two original held parent caps remain the only risk authority here.
    """
    table = SCHEMA + '.prepared_plan_risk'
    args = 'p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,p_judge uuid,p_jr text,p_jh text'
    bridge = f'''CREATE FUNCTION {PLAN_FACT.split('(')[0]}({args}) RETURNS jsonb
      LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $planfact$
      DECLARE t jsonb; j jsonb; cases jsonb; suite_hash text;
      BEGIN
        t:=public.capacity_occupation_eval_fact(p_raw,p_source,p_target,p_tr,p_th);
        j:=public.capacity_occupation_judge_fact(p_raw,p_source,p_judge,p_jr,p_jh);
        IF p_target IS NOT DISTINCT FROM p_judge OR p_tr IS NOT DISTINCT FROM p_jr
          OR j->'application'->'targetApplication'->>'requestId' IS DISTINCT FROM p_tr
          OR j->'application'->'targetApplication'->>'requestHash' IS DISTINCT FROM p_th
          OR j->'application'->'targetApplication'->'request' IS DISTINCT FROM t->'application'
          OR t->>'physicalAccountId' IS DISTINCT FROM j->>'physicalAccountId'
          OR t->>'xid' IS DISTINCT FROM j->>'xid' OR t->>'pid' IS DISTINCT FROM j->>'pid' THEN
          RAISE EXCEPTION 'CAPACITY_PLAN_ORIGINAL_PAIR_REQUIRED' USING ERRCODE='23514'; END IF;
        SELECT v.cases,v.content_hash INTO cases,suite_hash FROM public.aip_eval_suite_revision v
          WHERE v.org_id='org-org' AND v.project_id='dev-project'
            AND v.suite_id=t->'application'->'suiteRef'->>'assetId'
            AND v.revision=(t->'application'->'suiteRef'->>'revision')::integer FOR SHARE;
        IF cases IS NULL OR jsonb_typeof(cases)<>'array' OR jsonb_array_length(cases)=0
          OR suite_hash IS DISTINCT FROM t->'application'->'suiteRef'->>'contentHash'
          OR cases IS DISTINCT FROM j->'application'->'cases'
          OR (SELECT count(DISTINCT item->>'caseId') FROM jsonb_array_elements(cases) item)
              <>jsonb_array_length(cases) THEN
          RAISE EXCEPTION 'CAPACITY_PLAN_COMPLETE_CASES_REQUIRED' USING ERRCODE='23514'; END IF;
        RETURN jsonb_build_object('target',t-'checkedAt','judge',j-'checkedAt','cases',cases);
      END $planfact$'''
    producer = f'''CREATE FUNCTION {PLAN_RISK.split('(')[0]}({args},p_plan uuid) RETURNS jsonb
      LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $planrisk$
      DECLARE facts jsonb; after_facts jsonb; item jsonb; legs jsonb:='[]'; body jsonb; digest text;
        prior {table}%ROWTYPE;
      BEGIN
        IF p_plan IS NULL THEN RAISE EXCEPTION 'CAPACITY_PLAN_ID_REQUIRED' USING ERRCODE='23514'; END IF;
        facts:=public.capacity_occupation_plan_risk_fact(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh);
        FOR item IN SELECT value FROM jsonb_array_elements(facts->'cases') LOOP
          legs:=legs||jsonb_build_array(
            jsonb_build_object('case',item,'purpose','target','parentHold',p_target,
              'state','awaiting_input_binding'),
            jsonb_build_object('case',item,'purpose','judge','parentHold',p_judge,
              'state','awaiting_target_result'));
        END LOOP;
        body:=jsonb_build_object('schemaVersion','aos.capacity-complete-plan-risk/v1','planId',p_plan,
          'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
          'originalFacts',facts,'legs',legs,'riskMode','original_shared_parent_caps',
          'parentRisks',jsonb_build_array(
            jsonb_build_object('purpose','target','parentHold',p_target,'parentHash',facts->'target'->>'contentHash',
              'upperBoundMinor',facts->'target'->'upperBoundMinor','currency',facts->'target'->'currency'),
            jsonb_build_object('purpose','judge','parentHold',p_judge,'parentHash',facts->'judge'->>'contentHash',
              'upperBoundMinor',facts->'judge'->'upperBoundMinor','currency',facts->'judge'->'currency')),
          'callerLogin',session_user,'callerXid',pg_current_xact_id()::text,'callerPid',pg_backend_pid(),
          'state','prepared_risk_only','executionAllowed',false);
        digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
        SELECT * INTO prior FROM {table} WHERE org_id='org-org' AND project_id='dev-project'
          AND target_request=p_tr AND judge_request=p_jr;
        IF FOUND AND prior.plan_id IS DISTINCT FROM p_plan THEN
          RAISE EXCEPTION 'CAPACITY_PLAN_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
        SELECT * INTO prior FROM {table} WHERE plan_id=p_plan;
        IF FOUND THEN
          IF prior.immutable IS DISTINCT FROM body OR prior.content_hash IS DISTINCT FROM digest
            OR prior.origin_xid IS DISTINCT FROM pg_current_xact_id() OR prior.origin_pid IS DISTINCT FROM pg_backend_pid() THEN
            RAISE EXCEPTION 'CAPACITY_PLAN_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
        ELSE
          INSERT INTO {table}(org_id,project_id,plan_id,target_request,judge_request,immutable,content_hash,origin_xid,origin_pid)
            VALUES('org-org','dev-project',p_plan,p_tr,p_jr,body,digest,pg_current_xact_id(),pg_backend_pid());
        END IF;
        after_facts:=public.capacity_occupation_plan_risk_fact(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh);
        IF after_facts IS DISTINCT FROM facts THEN
          RAISE EXCEPTION 'CAPACITY_PLAN_CURRENT_AFTER_WAITS_REQUIRED' USING ERRCODE='23514'; END IF;
        RETURN jsonb_build_object('planId',p_plan,'immutable',body,'contentHash',digest,'executionAllowed',false,
          'physicalPreparedRequests',(SELECT count(*) FROM {SCHEMA}.prepared_parent_debit
            WHERE physical_account_id=(facts->'target'->>'physicalAccountId')::uuid),
          'physicalPreparedTokens',(SELECT coalesce(sum(token_units),0) FROM {SCHEMA}.prepared_parent_debit
            WHERE physical_account_id=(facts->'target'->>'physicalAccountId')::uuid));
      END $planrisk$'''
    return (
        f'''CREATE TABLE {table}(org_id text NOT NULL,project_id text NOT NULL,plan_id uuid PRIMARY KEY,
          target_request text NOT NULL,judge_request text NOT NULL,immutable jsonb NOT NULL,content_hash text NOT NULL,
          origin_xid xid8 NOT NULL,origin_pid integer NOT NULL,UNIQUE(org_id,project_id,target_request,judge_request))''',
        f'ALTER TABLE {table} OWNER TO {OWNER}',
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {table} TO {OWNER}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'REVOKE ALL ON {table} FROM PUBLIC,aos_runtime',
        f'CREATE TRIGGER immutable_plan_risk BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.immutable_prepared_intent()',
        f'CREATE TRIGGER no_truncate_plan_risk BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {SCHEMA}.immutable_prepared_intent()',
        f'CREATE CONSTRAINT TRIGGER no_unfinalized_plan_risk AFTER INSERT ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.reject_unfinalized_parent_debit()',
        bridge,
        f'ALTER FUNCTION {PLAN_FACT} OWNER TO aos_runtime',
        f'REVOKE ALL ON FUNCTION {PLAN_FACT} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {PLAN_FACT} TO {OWNER}',
        producer,
        f'ALTER FUNCTION {PLAN_RISK} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {PLAN_RISK} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {PLAN_RISK} TO aos_runtime',
    )


def occupation_prepared_call_statements():
    """Private preparation storage only; no admission or state transition.

    Explicit installation artifact. Runtime has no producer or DML permission;
    the original unconditional commit rejection remains in force. A future
    trusted producer must verify all original plan/input/Intent facts first.
    """
    table = SCHEMA + '.prepared_call_occupation'
    return (
        f'''CREATE TABLE {table} (
          org_id text NOT NULL,project_id text NOT NULL,call_id uuid PRIMARY KEY,
          plan_id uuid NOT NULL REFERENCES {SCHEMA}.prepared_plan_risk(plan_id),
          case_id text NOT NULL CHECK(length(case_id)>0),
          purpose text NOT NULL CHECK(purpose IN ('target','judge')),
          parent_hold uuid NOT NULL,intent_id uuid NOT NULL,
          physical_account_id uuid NOT NULL REFERENCES {SCHEMA}.account_guard(physical_account_id),
          token_upper_bound bigint NOT NULL CHECK(token_upper_bound>0),
          input_hash text NOT NULL CHECK(input_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          state text NOT NULL CHECK(state='prepared_only'),
          immutable jsonb NOT NULL CHECK(jsonb_typeof(immutable)='object'),
          content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          origin_xid xid8 NOT NULL,origin_pid integer NOT NULL CHECK(origin_pid>0),
          UNIQUE(org_id,project_id,plan_id,purpose,case_id),UNIQUE(intent_id))''',
        f'ALTER TABLE {table} OWNER TO {OWNER}',
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {table} TO {OWNER}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'REVOKE ALL ON {table} FROM PUBLIC,aos_runtime',
        f'''CREATE TRIGGER immutable_prepared_call BEFORE UPDATE OR DELETE ON {table}
          FOR EACH ROW EXECUTE FUNCTION {SCHEMA}.immutable_prepared_intent()''',
        f'''CREATE TRIGGER no_truncate_prepared_call BEFORE TRUNCATE ON {table}
          FOR EACH STATEMENT EXECUTE FUNCTION {SCHEMA}.immutable_prepared_intent()''',
        f'''CREATE CONSTRAINT TRIGGER require_joint_finalization AFTER INSERT OR UPDATE ON {table}
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
          EXECUTE FUNCTION {SCHEMA}.reject_unfinalized_parent_debit()''',
    )
