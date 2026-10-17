-- New-family native authority. Loaded transactionally by its closed migration.
-- No role creation, LOGIN enablement, credential or external execution here.
CREATE TABLE public.aip_budget_policy_window_proposal (
 org_id text NOT NULL, project_id text NOT NULL, proposal_id text NOT NULL,
 proposal_hash text NOT NULL CHECK(proposal_hash ~ '^[0-9a-f]{64}$'),
 maker_subject text NOT NULL, checker_subject text NOT NULL,
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 created_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
 PRIMARY KEY(org_id,project_id,proposal_id),
 CHECK(org_id='org-org' AND project_id='dev-project'),
 CHECK(maker_subject<>checker_subject AND expires_at>created_at)
);
CREATE TABLE public.aip_budget_policy_window_decision (
 org_id text NOT NULL, project_id text NOT NULL, proposal_id text NOT NULL,
 decision_id text NOT NULL, decision_hash text NOT NULL CHECK(decision_hash ~ '^[0-9a-f]{64}$'),
 decision text NOT NULL CHECK(decision IN('approved','rejected','revoked')),
 actor_subject text NOT NULL, payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(org_id,project_id,decision_id),
 FOREIGN KEY(org_id,project_id,proposal_id) REFERENCES public.aip_budget_policy_window_proposal,
 CHECK(org_id='org-org' AND project_id='dev-project')
);
CREATE UNIQUE INDEX policy_window_initial_decision_v1
 ON public.aip_budget_policy_window_decision(org_id,project_id,proposal_id)
 WHERE decision IN('approved','rejected');
CREATE UNIQUE INDEX policy_window_revocation_v1
 ON public.aip_budget_policy_window_decision(org_id,project_id,proposal_id) WHERE decision='revoked';
CREATE TABLE public.aip_budget_policy_window_receipt (
 org_id text NOT NULL, project_id text NOT NULL, receipt_id text NOT NULL,
 actor_subject text NOT NULL, operation text NOT NULL CHECK(operation IN('propose','decide','revoke','consume')),
 idempotency_key text NOT NULL, request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
 proposal_id text NOT NULL, decision_id text,
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 transaction_id bigint NOT NULL DEFAULT txid_current(),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(org_id,project_id,receipt_id),
 UNIQUE(org_id,project_id,actor_subject,operation,idempotency_key),
 FOREIGN KEY(org_id,project_id,proposal_id) REFERENCES public.aip_budget_policy_window_proposal,
 FOREIGN KEY(org_id,project_id,decision_id) REFERENCES public.aip_budget_policy_window_decision,
 CHECK(org_id='org-org' AND project_id='dev-project')
);
CREATE UNIQUE INDEX policy_window_consume_once_v1
 ON public.aip_budget_policy_window_receipt(org_id,project_id,proposal_id) WHERE operation='consume';
CREATE UNIQUE INDEX policy_window_consume_transaction_v1
 ON public.aip_budget_policy_window_receipt(transaction_id) WHERE operation='consume';
CREATE TABLE public.aip_budget_policy_window_binding (
 org_id text NOT NULL, project_id text NOT NULL, binding_id text NOT NULL,
 binding_hash text NOT NULL CHECK(binding_hash ~ '^[0-9a-f]{64}$'),
 proposal_id text NOT NULL, decision_id text NOT NULL, receipt_id text NOT NULL,
 policy_ref jsonb NOT NULL CHECK(jsonb_typeof(policy_ref)='object'),
 price_ref jsonb NOT NULL CHECK(jsonb_typeof(price_ref)='object'),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 transaction_id bigint NOT NULL DEFAULT txid_current(),
 PRIMARY KEY(org_id,project_id,binding_id),
 UNIQUE(org_id,project_id,proposal_id), UNIQUE(org_id,project_id,policy_ref),
 UNIQUE(org_id,project_id,price_ref),
 FOREIGN KEY(org_id,project_id,proposal_id) REFERENCES public.aip_budget_policy_window_proposal,
 FOREIGN KEY(org_id,project_id,decision_id) REFERENCES public.aip_budget_policy_window_decision,
 FOREIGN KEY(org_id,project_id,receipt_id) REFERENCES public.aip_budget_policy_window_receipt
  DEFERRABLE INITIALLY DEFERRED,
 CHECK(org_id='org-org' AND project_id='dev-project')
);
CREATE TABLE public.aip_budget_policy_window_fence (
 org_id text NOT NULL, project_id text NOT NULL, proposal_id text NOT NULL,
 version bigint NOT NULL DEFAULT 1 CHECK(version>=1), revoked boolean NOT NULL DEFAULT false,
 modified_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(org_id,project_id,proposal_id),
 FOREIGN KEY(org_id,project_id,proposal_id) REFERENCES public.aip_budget_policy_window_proposal,
 CHECK(org_id='org-org' AND project_id='dev-project')
);

CREATE FUNCTION public.aip_policy_window_command_v1(c jsonb, op_name text)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE allowed text[]; identities text[]; hashes text[]; field text; ref jsonb; expected text;
 start_at timestamptz; end_at timestamptz;
BEGIN
 IF op_name='propose' THEN
  allowed:=ARRAY['parentCostProposalId','parentCostProposalHash','parentCostDecisionId',
   'parentConsumptionReceiptId','expectedBudgetRef','expectedBudgetHeadVersion',
   'expectedProviderRef','expectedProviderModelId','effectiveFrom','effectiveUntil'];
  identities:=ARRAY['parentCostProposalId','parentCostDecisionId','parentConsumptionReceiptId','expectedProviderModelId'];
  hashes:=ARRAY['parentCostProposalHash'];
 ELSIF op_name='decide' THEN
  allowed:=ARRAY['proposalId','proposalHash','targetPairHash','decision'];
  identities:=ARRAY['proposalId'];hashes:=ARRAY['proposalHash','targetPairHash'];
 ELSIF op_name='revoke' THEN
  allowed:=ARRAY['proposalId','proposalHash','originalDecisionId','originalDecisionHash','reason'];
  identities:=ARRAY['proposalId','originalDecisionId','reason'];hashes:=ARRAY['proposalHash','originalDecisionHash'];
 ELSIF op_name='consume' THEN
  allowed:=ARRAY['proposalId','proposalHash','decisionId','decisionHash','targetPairHash'];
  identities:=ARRAY['proposalId','decisionId'];hashes:=ARRAY['proposalHash','decisionHash','targetPairHash'];
 ELSE RAISE EXCEPTION 'POLICY_WINDOW_OPERATION_REQUIRED' USING ERRCODE='22023'; END IF;
 IF (jsonb_typeof(c)='object' AND octet_length(c::text)<=16384
  AND c-(allowed||ARRAY['schemaVersion','orgId','projectId','idempotencyKey'])='{}'::jsonb
  AND c ?& (allowed||ARRAY['schemaVersion','orgId','projectId','idempotencyKey'])
  AND jsonb_typeof(c->'schemaVersion')='number' AND c->>'schemaVersion'='1'
  AND c->>'orgId'='org-org' AND c->>'projectId'='dev-project'
  AND jsonb_typeof(c->'idempotencyKey')='string'
  AND c->>'idempotencyKey' ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$') IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_EXACT_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 FOREACH field IN ARRAY identities LOOP
  IF (jsonb_typeof(c->field)='string' AND length(c->>field) BETWEEN 1 AND
    CASE WHEN field='reason' THEN 500 WHEN field='expectedProviderModelId' THEN 240 ELSE 200 END
    AND c->>field=btrim(c->>field) AND c->>field !~ '[[:cntrl:]]') IS NOT TRUE THEN
   RAISE EXCEPTION 'POLICY_WINDOW_CANONICAL_IDENTITY_REQUIRED' USING ERRCODE='22023'; END IF;
 END LOOP;
 FOREACH field IN ARRAY hashes LOOP
  IF (jsonb_typeof(c->field)='string' AND length(c->>field)=64 AND c->>field ~ '^[0-9a-f]{64}$') IS NOT TRUE THEN
   RAISE EXCEPTION 'POLICY_WINDOW_EXACT_HASH_REQUIRED' USING ERRCODE='22023'; END IF;
 END LOOP;
 IF op_name='decide' AND (jsonb_typeof(c->'decision')='string'
   AND c->>'decision' IN('approved','rejected')) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_EXPLICIT_DECISION_REQUIRED' USING ERRCODE='22023'; END IF;
 IF op_name='propose' THEN
  FOREACH field IN ARRAY ARRAY['expectedBudgetRef','expectedProviderRef'] LOOP
   ref:=c->field;expected:=CASE WHEN field='expectedBudgetRef' THEN 'BudgetRevision' ELSE 'ProviderInstanceRevision' END;
   IF (jsonb_typeof(ref)='object' AND ref-ARRAY['assetType','assetId','revision','contentHash']='{}'::jsonb
      AND ref ?& ARRAY['assetType','assetId','revision','contentHash']
      AND ref->>'assetType'=expected AND jsonb_typeof(ref->'assetId')='string'
      AND length(ref->>'assetId') BETWEEN 1 AND 200 AND ref->>'assetId'=btrim(ref->>'assetId')
      AND ref->>'assetId' !~ '[[:cntrl:]]' AND jsonb_typeof(ref->'revision')='number'
      AND ref->>'revision' ~ '^[1-9][0-9]{0,15}$'
      AND (ref->>'revision')::bigint<=9007199254740991
      AND jsonb_typeof(ref->'contentHash')='string' AND length(ref->>'contentHash')=64
      AND ref->>'contentHash' ~ '^[0-9a-f]{64}$') IS NOT TRUE THEN
    RAISE EXCEPTION 'POLICY_WINDOW_EXACT_REFERENCE_REQUIRED' USING ERRCODE='22023'; END IF;
  END LOOP;
  IF (jsonb_typeof(c->'expectedBudgetHeadVersion')='number'
     AND c->>'expectedBudgetHeadVersion' ~ '^[1-9][0-9]{0,15}$'
     AND (c->>'expectedBudgetHeadVersion')::bigint<=9007199254740991) IS NOT TRUE THEN
   RAISE EXCEPTION 'POLICY_WINDOW_EXACT_HEAD_REQUIRED' USING ERRCODE='22023'; END IF;
  FOREACH field IN ARRAY ARRAY['effectiveFrom','effectiveUntil'] LOOP
   IF (jsonb_typeof(c->field)='string' AND c->>field ~
     '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$') IS NOT TRUE THEN
    RAISE EXCEPTION 'POLICY_WINDOW_CANONICAL_UTC_REQUIRED' USING ERRCODE='22023'; END IF;
   IF c->>field IS DISTINCT FROM to_char((c->>field)::timestamptz AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"') THEN
    RAISE EXCEPTION 'POLICY_WINDOW_CANONICAL_UTC_REQUIRED' USING ERRCODE='22023'; END IF;
  END LOOP;
  start_at:=(c->>'effectiveFrom')::timestamptz;end_at:=(c->>'effectiveUntil')::timestamptz;
  IF end_at<=start_at THEN RAISE EXCEPTION 'POLICY_WINDOW_POSITIVE_WINDOW_REQUIRED' USING ERRCODE='22023'; END IF;
 END IF;
 RETURN c;
END $$;

CREATE FUNCTION public.aip_policy_window_parent_v1(c jsonb, lock_current boolean)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE p public.aip_budget_cost_proposal%ROWTYPE;d public.aip_budget_cost_decision%ROWTYPE;
 r public.aip_budget_receipt%ROWTYPE;b public.aip_budget_revision%ROWTYPE;
 v public.aip_provider_instance_revision%ROWTYPE;bh public.aip_budget_head%ROWTYPE;
 vh bigint;f public.aip_budget_cost_runtime_fence%ROWTYPE;t jsonb;tenant jsonb;
 parent_ref jsonb;provider_ref jsonb;digest text;expected jsonb;members text[];now_at timestamptz;
BEGIN
 PERFORM public.aip_policy_window_command_v1(c,'propose');
 IF (session_user,current_user) NOT IN(
   ('aos_budget_renewal_maker_call','aos_budget_renewal_proposal_owner'),
   ('aos_budget_renewal_issuer_call','aos_budget_renewal_issuer_owner'),
   ('aos_budget_consumer_call','aos_budget_consumer_owner')) THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PARENT_PURPOSE_REQUIRED' USING ERRCODE='42501'; END IF;
 IF lock_current THEN
  PERFORM pg_advisory_xact_lock(hashtextextended('budget-cost-review:org-org:dev-project:'||(c->>'parentCostProposalId'),0));
 END IF;
 SELECT * INTO STRICT p FROM public.aip_budget_cost_proposal WHERE org_id='org-org'
  AND project_id='dev-project' AND proposal_id=c->>'parentCostProposalId';
 tenant:=jsonb_build_object('orgId','org-org','projectId','dev-project');t:=p.payload->'target';
 IF (p.proposal_hash=c->>'parentCostProposalHash' AND p.payload->'tenant'=tenant
   AND p.status='proposed' AND p.source_verification='pending' AND NOT p.activation_eligible
   AND p.proposal_hash=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.budget-cost-proposal/v1','proposal',p.payload))
   AND p.maker_subject=p.payload->>'makerSubject' AND p.checker_subject=p.payload->>'checkerSubject'
   AND p.maker_subject<>p.checker_subject AND p.budget_id=t->>'budgetId'
   AND p.payload->'basis'->>'kind'='development_risk_proposal'
   AND t->>'environment'='development' AND t->>'currency'='CNY'
   AND t->'hardStop'='true'::jsonb AND t->>'unknownUsageBehavior'='block') IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PARENT_PROPOSAL_DRIFT' USING ERRCODE='23514'; END IF;
 members:=ARRAY[p.maker_subject,p.checker_subject,'postgres-service:aos_budget_renewal_maker_call',
  '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'];
 IF lock_current THEN
  PERFORM subject FROM public.meta_membership WHERE org_id='org-org' AND project_id='dev-project'
   AND subject=ANY(members) ORDER BY subject FOR SHARE;
 END IF;
 IF (SELECT count(DISTINCT subject) FROM public.meta_membership WHERE org_id='org-org'
  AND project_id='dev-project' AND subject=ANY(members) AND lower(role) IN('owner','admin'))
  IS DISTINCT FROM (SELECT count(DISTINCT subject) FROM unnest(members) AS subject) THEN
  RAISE EXCEPTION 'POLICY_WINDOW_CURRENT_MEMBERS_REQUIRED' USING ERRCODE='42501'; END IF;
 SELECT * INTO STRICT d FROM public.aip_budget_cost_decision WHERE org_id='org-org'
  AND project_id='dev-project' AND decision_id=c->>'parentCostDecisionId' AND proposal_id=p.proposal_id;
 IF (d.decision='approved' AND d.proposal_hash=p.proposal_hash AND d.actor_subject=p.checker_subject
  AND d.source_ref=p.payload->'basis'->'provider') IS NOT TRUE
  OR EXISTS(SELECT 1 FROM public.aip_budget_cost_revocation WHERE org_id='org-org'
   AND project_id='dev-project' AND decision_id=d.decision_id) THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PARENT_APPROVAL_REQUIRED' USING ERRCODE='42501'; END IF;
 SELECT * INTO STRICT r FROM public.aip_budget_receipt WHERE org_id='org-org'
  AND project_id='dev-project' AND operation='budget_revision.activate_cost' AND idempotency_key=p.proposal_id;
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.budget-cost-consume/v1',
  'tenant',tenant,'proposalId',p.proposal_id,'proposalHash',p.proposal_hash,'decisionId',d.decision_id));
 expected:=jsonb_build_object('resourceType','BudgetRevision','resourceId',t->>'budgetId',
  'revision',t->'revision','contentHash',public.aip_budget_cost_hash_a0v_126(t),
  'proposalId',p.proposal_id,'proposalHash',p.proposal_hash,'decisionId',d.decision_id,
  'receiptId','budget-cost-consume-'||digest);
 IF (r.receipt_id=c->>'parentConsumptionReceiptId' AND r.receipt_id=expected->>'receiptId'
  AND r.result_ref=expected AND r.request_hash=digest AND r.created_by=p.maker_subject) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PARENT_CONSUMPTION_REQUIRED' USING ERRCODE='23514'; END IF;
 IF lock_current THEN
  SELECT * INTO STRICT bh FROM public.aip_budget_head WHERE org_id='org-org' AND project_id='dev-project'
   AND budget_id=p.budget_id FOR SHARE;
 ELSE
  SELECT * INTO STRICT bh FROM public.aip_budget_head WHERE org_id='org-org' AND project_id='dev-project' AND budget_id=p.budget_id;
 END IF;
 SELECT * INTO STRICT b FROM public.aip_budget_revision WHERE org_id=bh.org_id AND project_id=bh.project_id
  AND budget_id=bh.budget_id AND revision=bh.current_revision;
 parent_ref:=jsonb_build_object('assetType','BudgetRevision','assetId',b.budget_id,'revision',b.revision,'contentHash',b.content_hash);
 IF (parent_ref=c->'expectedBudgetRef' AND bh.version=(c->>'expectedBudgetHeadVersion')::bigint
   AND bh.version=(p.payload->>'expectedHeadVersion')::bigint+1
   AND b.revision=(t->>'revision')::bigint AND b.lifecycle='active'
   AND b.content_hash=expected->>'contentHash' AND b.payload->'tenant'=tenant
   AND b.payload->>'contentHash'=b.content_hash AND b.payload-ARRAY['tenant','contentHash','createdBy','createdAt']=t
   AND b.environment=t->>'environment' AND b.currency=t->>'currency' AND b.hard_stop
   AND b.unknown_usage_behavior='block' AND b.owner=t->>'owner'
   AND b.daily_limit_minor=(t->>'dailyLimitMinor')::bigint AND b.monthly_limit_minor=(t->>'monthlyLimitMinor')::bigint
   AND b.alert_threshold_pct=(t->>'alertThresholdPct')::integer AND b.over_budget_approver=t->>'overBudgetApprover'
   AND b.effective_from=(t->>'effectiveFrom')::timestamptz AND b.effective_until=(t->>'effectiveUntil')::timestamptz
   AND b.created_by=b.payload->>'createdBy' AND b.created_at=(b.payload->>'createdAt')::timestamptz) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PARENT_BUDGET_DRIFT' USING ERRCODE='23514'; END IF;
 SELECT * INTO STRICT f FROM public.aip_budget_cost_runtime_fence WHERE org_id='org-org' AND project_id='dev-project'
  AND budget_id=b.budget_id AND revision=b.revision;
 IF f.decision_id IS DISTINCT FROM d.decision_id THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PARENT_FENCE_DRIFT' USING ERRCODE='23514'; END IF;
 provider_ref:=p.payload->'basis'->'provider';
 IF (provider_ref=c->'expectedProviderRef' AND p.payload->'basis'->>'providerModelId'=c->>'expectedProviderModelId') IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PARENT_PROVIDER_SCOPE' USING ERRCODE='23514'; END IF;
 IF lock_current THEN
  SELECT current_revision INTO STRICT vh FROM public.aip_provider_instance_head WHERE org_id='org-org'
   AND project_id='dev-project' AND provider_instance_id=provider_ref->>'assetId' FOR SHARE;
 ELSE
  SELECT current_revision INTO STRICT vh FROM public.aip_provider_instance_head WHERE org_id='org-org'
   AND project_id='dev-project' AND provider_instance_id=provider_ref->>'assetId';
 END IF;
 SELECT * INTO STRICT v FROM public.aip_provider_instance_revision WHERE org_id='org-org' AND project_id='dev-project'
  AND provider_instance_id=provider_ref->>'assetId' AND revision=vh;
 IF (provider_ref=jsonb_build_object('assetType','ProviderInstanceRevision','assetId',v.provider_instance_id,
    'revision',v.revision,'contentHash',v.content_hash) AND v.lifecycle='active'
   AND v.payload->'tenant'=tenant AND v.payload->>'lifecycle'='active'
   AND v.payload->>'providerInstanceId'=v.provider_instance_id AND v.payload->>'revision'=v.revision::text
   AND v.payload->>'contentHash'=v.content_hash AND v.payload->>'createdBy'=v.created_by
   AND (v.payload->>'createdAt')::timestamptz=v.created_at
   AND v.content_hash=public.aip_budget_cost_hash_a0v_126(v.payload-ARRAY['tenant','revision','contentHash','createdBy','createdAt'])) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PARENT_PROVIDER_DRIFT' USING ERRCODE='23514'; END IF;
 now_at:=clock_timestamp();
 IF (b.effective_from<=now_at AND now_at<b.effective_until
   AND b.effective_from<=(c->>'effectiveFrom')::timestamptz
   AND (c->>'effectiveUntil')::timestamptz<b.effective_until AND now_at<(c->>'effectiveUntil')::timestamptz) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PARENT_WINDOW_REQUIRED' USING ERRCODE='23514'; END IF;
 -- Original decision expiry governed its already-proven consumption, not the
 -- lifetime of that consumed risk grant. Current revoke/head/window still bind.
 IF session_user='aos_budget_consumer_call' THEN
  IF public.aip_budget_consumption_fact_a0v_128('org-org','dev-project',p.proposal_id,d.decision_id,
    p.maker_subject,p.proposal_hash)->>'status' IS DISTINCT FROM 'observed' THEN
   RAISE EXCEPTION 'POLICY_WINDOW_ORIGINAL_OWNER_PROOF_REQUIRED' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN jsonb_build_object('costProposalId',p.proposal_id,'costProposalHash',p.proposal_hash,
  'costDecisionId',d.decision_id,'consumptionReceiptId',r.receipt_id,'budgetRef',parent_ref,
  'budgetHeadVersion',bh.version,'providerRef',provider_ref,'providerModelId',c->'expectedProviderModelId',
  'owner',b.owner,'budgetWindow',jsonb_build_object('effectiveFrom',t->'effectiveFrom','effectiveUntil',t->'effectiveUntil'),
  'risk',(p.payload->'basis')-ARRAY['kind','provider','providerModelId'],
  'makerSubject',p.maker_subject,'checkerSubject',p.checker_subject);
END $$;

CREATE FUNCTION public.aip_policy_window_relation_shape_v1(p_oid oid)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT jsonb_build_object('name',c.relname,'owner',pg_get_userbyid(c.relowner),
  'rls',c.relrowsecurity,'forceRls',c.relforcerowsecurity,'acl',c.relacl::text,
  'columns',(SELECT jsonb_agg(jsonb_build_object('name',a.attname,'acl',a.attacl::text) ORDER BY a.attnum)
   FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped),
  'policies',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',p.polname,'roles',to_jsonb(p.polroles),
   'permissive',p.polpermissive,'command',p.polcmd,'using',pg_get_expr(p.polqual,p.polrelid),
   'check',pg_get_expr(p.polwithcheck,p.polrelid)) ORDER BY p.polname)
   FROM pg_policy p WHERE p.polrelid=c.oid),'[]'::jsonb),
  'triggers',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',t.tgname,'enabled',t.tgenabled,
    'definition',pg_get_triggerdef(t.oid)) ORDER BY t.tgname)
   FROM pg_trigger t WHERE t.tgrelid=c.oid AND NOT t.tgisinternal),'[]'::jsonb),
  'indexes',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',ic.relname,
    'definition',pg_get_indexdef(i.indexrelid),'valid',i.indisvalid,'ready',i.indisready)
    ORDER BY ic.relname) FROM pg_index i JOIN pg_class ic ON ic.oid=i.indexrelid
    WHERE i.indrelid=c.oid),'[]'::jsonb),
  'constraints',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',co.conname,
    'type',co.contype,'deferrable',co.condeferrable,'deferred',co.condeferred,
    'definition',pg_get_constraintdef(co.oid)) ORDER BY co.conname)
    FROM pg_constraint co WHERE co.conrelid=c.oid),'[]'::jsonb))
 FROM pg_class c WHERE c.oid=p_oid AND c.relnamespace='public'::regnamespace
$$;

CREATE FUNCTION public.aip_policy_window_expected_v1(source jsonb, approval_slot text)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE c jsonb:=source->'request';parent jsonb:=source->'parent';ident text:=source->>'ident';
 tenant jsonb:=jsonb_build_object('orgId','org-org','projectId','dev-project');
 from_at timestamptz;until_at timestamptz;from_text text;until_text text;auth jsonb;policy jsonb;price jsonb;pair jsonb;
BEGIN
 PERFORM public.aip_policy_window_command_v1(c,'propose');
 IF (ident ~ '^[0-9a-f]{64}$' AND approval_slot='window-approval-'||ident
  AND jsonb_typeof(parent)='object') IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_OWNER_SOURCE_REQUIRED' USING ERRCODE='23514'; END IF;
 from_at:=(c->>'effectiveFrom')::timestamptz;until_at:=(c->>'effectiveUntil')::timestamptz;
 -- Command wire is fixed-six UTC. Persisted assets must instead retain the
 -- established Pydantic asset JSON format, which omits a zero fraction.
 from_text:=to_char(from_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS')||
  CASE WHEN date_trunc('second',from_at)=from_at THEN 'Z' ELSE '.'||to_char(from_at AT TIME ZONE 'UTC','US')||'Z' END;
 until_text:=to_char(until_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS')||
  CASE WHEN date_trunc('second',until_at)=until_at THEN 'Z' ELSE '.'||to_char(until_at AT TIME ZONE 'UTC','US')||'Z' END;
 auth:=jsonb_build_object('tenant',tenant,'provider',parent->'providerRef',
  'providerModelId',parent->'providerModelId','approvalRef',approval_slot,'environment','development',
  'effectiveFrom',from_text,'effectiveUntil',until_text);
 policy:=jsonb_build_object('policyId','window-policy-'||ident,'revision',1,
  'environment','development','effectiveFrom',from_text,'effectiveUntil',until_text,
  'owner',parent->'owner','approvalRef',approval_slot,'lifecycle','active',
  'developmentCostAuthorization',auth,'budgetRevisionRef',parent->'budgetRef',
  'currency','CNY','hardStop',true,'unknownUsageBehavior','block','unknownPriceBehavior','block',
  'allowZeroPrice',false,'zeroPriceApprovalRef',NULL);
 price:=jsonb_build_object('priceSnapshotId','window-price-'||ident,'currency','CNY',
  'inputTokenPrice',NULL,'outputTokenPrice',NULL,'cachedTokenPrice',NULL,'tokenUnit',1000,
  'effectiveFrom',from_text,'effectiveUntil',until_text,'lifecycle','active','developmentCostAuthorization',auth);
 pair:=jsonb_build_object('policy',policy,'price',price);
 RETURN jsonb_build_object('targets',pair,'targetPairHash',public.aip_budget_cost_hash_a0v_126(
  jsonb_build_object('domain','aos.budget-policy-window.targets/v1','targets',pair)));
END $$;

CREATE FUNCTION public.aip_policy_window_history_v1(c jsonb,op_name text,actor text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE r public.aip_budget_policy_window_receipt%ROWTYPE;p public.aip_budget_policy_window_proposal%ROWTYPE;
 d public.aip_budget_policy_window_decision%ROWTYPE;digest text;ident text;
BEGIN
 PERFORM public.aip_policy_window_command_v1(c,op_name);
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
  'domain','aos.budget-policy-window.'||op_name||'/v1','command',c-'idempotencyKey'));
 SELECT * INTO r FROM public.aip_budget_policy_window_receipt WHERE org_id='org-org' AND project_id='dev-project'
  AND actor_subject=actor AND operation=op_name AND idempotency_key=c->>'idempotencyKey';
 IF NOT FOUND THEN RETURN NULL; END IF;
 ident:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.policy-window-receipt-id/v1',
  'operation',op_name,'actor',actor,'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
  'key',c->>'idempotencyKey'));
 SELECT * INTO STRICT p FROM public.aip_budget_policy_window_proposal WHERE org_id=r.org_id
  AND project_id=r.project_id AND proposal_id=r.proposal_id;
 PERFORM public.aip_policy_window_proposal_fact_v1(p.proposal_id,p.proposal_hash,false);
 IF (r.request_hash=digest AND r.receipt_id='window-'||op_name||'-'||ident
  AND p.proposal_hash=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
   'domain','aos.budget-policy-window.proposal/v1','proposal',p.payload))
  AND r.payload->>'proposalId'=p.proposal_id AND r.payload->>'proposalHash'=p.proposal_hash
  AND r.payload->>'requestHash'=digest AND r.payload->'activationEligible'='false'::jsonb
  AND r.payload->'command'=c) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_RECEIPT_CONFLICT' USING ERRCODE='23514'; END IF;
 IF op_name='propose' THEN
  IF (p.payload->'request'=c AND p.maker_subject=actor AND r.payload->'proposal'=p.payload) IS NOT TRUE THEN
   RAISE EXCEPTION 'POLICY_WINDOW_PROPOSAL_HISTORY_DRIFT' USING ERRCODE='23514'; END IF;
 ELSE
  SELECT * INTO STRICT d FROM public.aip_budget_policy_window_decision WHERE org_id=r.org_id
   AND project_id=r.project_id AND decision_id=r.decision_id AND proposal_id=r.proposal_id;
  IF (p.proposal_id=c->>'proposalId' AND p.proposal_hash=c->>'proposalHash'
   AND d.decision_hash=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
    'domain','aos.budget-policy-window.decision/v1','decision',d.payload))
   AND r.payload->>'decisionId'=d.decision_id AND r.payload->>'decisionHash'=d.decision_hash) IS NOT TRUE THEN
   RAISE EXCEPTION 'POLICY_WINDOW_DECISION_HISTORY_DRIFT' USING ERRCODE='23514'; END IF;
  IF op_name IN('decide','revoke') AND (d.actor_subject=actor AND d.payload->'command'=c) IS NOT TRUE THEN
   RAISE EXCEPTION 'POLICY_WINDOW_CHECKER_HISTORY_DRIFT' USING ERRCODE='23514'; END IF;
  IF op_name='consume' AND (d.decision='approved' AND d.decision_id=c->>'decisionId'
    AND d.decision_hash=c->>'decisionHash' AND p.payload->>'targetPairHash'=c->>'targetPairHash') IS NOT TRUE THEN
   RAISE EXCEPTION 'POLICY_WINDOW_CONSUME_HISTORY_DRIFT' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN r.payload;
END $$;

CREATE FUNCTION public.aip_policy_window_proposal_fact_v1(pid text,expected_hash text,check_current boolean)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE p public.aip_budget_policy_window_proposal%ROWTYPE;e jsonb;ident text;parent jsonb;
 f public.aip_budget_policy_window_fence%ROWTYPE;
BEGIN
 SELECT * INTO STRICT p FROM public.aip_budget_policy_window_proposal WHERE org_id='org-org'
  AND project_id='dev-project' AND proposal_id=pid;
 ident:=replace(pid,'window-proposal-','');
 e:=public.aip_policy_window_expected_v1(jsonb_build_object('request',p.payload->'request',
  'parent',p.payload->'parent','ident',ident),p.payload->>'approvalSlot');
 IF (p.proposal_hash=expected_hash AND p.proposal_hash=public.aip_budget_cost_hash_a0v_126(
    jsonb_build_object('domain','aos.budget-policy-window.proposal/v1','proposal',p.payload))
   AND p.maker_subject='postgres-service:aos_budget_renewal_maker_call'
   AND p.checker_subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
   AND p.payload->>'makerSubject'=p.maker_subject AND p.payload->>'checkerSubject'=p.checker_subject
   AND p.payload->'tenant'=jsonb_build_object('orgId','org-org','projectId','dev-project')
   AND p.payload->>'operationFamily'='budget-policy-window/v1' AND p.payload->'schemaVersion'='1'::jsonb
   AND p.payload->'targets'=e->'targets' AND p.payload->'targetPairHash'=e->'targetPairHash'
   AND p.payload->>'requestHash'=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
    'domain','aos.budget-policy-window.propose/v1','command',(p.payload->'request')-'idempotencyKey'))
   AND p.created_at=(p.payload->>'createdAt')::timestamptz AND p.expires_at=(p.payload->>'expiresAt')::timestamptz
   AND p.expires_at=least(p.created_at+interval '30 minutes',
    (p.payload->'request'->>'effectiveUntil')::timestamptz,
    (p.payload->'parent'->'budgetWindow'->>'effectiveUntil')::timestamptz)) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PROPOSAL_FACT_DRIFT' USING ERRCODE='23514'; END IF;
 IF check_current THEN
  parent:=public.aip_policy_window_parent_v1(p.payload->'request',true);
  IF parent IS DISTINCT FROM p.payload->'parent' OR clock_timestamp()<p.created_at OR clock_timestamp()>=p.expires_at THEN
   RAISE EXCEPTION 'POLICY_WINDOW_CURRENT_PARENT_OR_DEADLINE_REQUIRED' USING ERRCODE='23514'; END IF;
  SELECT * INTO STRICT f FROM public.aip_budget_policy_window_fence WHERE org_id=p.org_id
   AND project_id=p.project_id AND proposal_id=pid FOR UPDATE;
  IF f.revoked THEN RAISE EXCEPTION 'POLICY_WINDOW_REVOKED' USING ERRCODE='42501'; END IF;
 END IF;
 RETURN p.payload;
END $$;

CREATE FUNCTION public.aip_policy_window_propose_v1(c jsonb)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE actor text:='postgres-service:aos_budget_renewal_maker_call';checker text:='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657';
 digest text;ident text;pid text;slot text;p jsonb;parent jsonb;targets jsonb;prior jsonb;result jsonb;
 now_at timestamptz;deadline timestamptz;rid text;
BEGIN
 PERFORM public.aip_policy_window_profile_v1('propose');
 PERFORM public.aip_policy_window_command_v1(c,'propose');
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
  'domain','aos.budget-policy-window.propose/v1','command',c-'idempotencyKey'));
 ident:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.window-proposal-id/v1',
  'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),'maker',actor,'key',c->>'idempotencyKey'));
 pid:='window-proposal-'||ident;slot:='window-approval-'||ident;
 PERFORM pg_advisory_xact_lock(hashtextextended('budget-cost-review:org-org:dev-project:'||(c->>'parentCostProposalId'),0));
 PERFORM pg_advisory_xact_lock(hashtextextended('budget-policy-window:org-org:dev-project:'||pid,0));
 prior:=public.aip_policy_window_history_v1(c,'propose',actor);
 IF prior IS NOT NULL THEN RETURN prior; END IF;
 parent:=public.aip_policy_window_parent_v1(c,true);
 targets:=public.aip_policy_window_expected_v1(jsonb_build_object('request',c,'parent',parent,'ident',ident),slot);
 now_at:=clock_timestamp();deadline:=least(now_at+interval '30 minutes',(c->>'effectiveUntil')::timestamptz,
  (parent->'budgetWindow'->>'effectiveUntil')::timestamptz);
 p:=jsonb_build_object('schemaVersion',1,'operationFamily','budget-policy-window/v1',
  'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
  'makerSubject',actor,'checkerSubject',checker,'request',c,'requestHash',digest,'parent',parent,
  'approvalSlot',slot,'targets',targets->'targets','targetPairHash',targets->'targetPairHash',
  'createdAt',to_char(now_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
  'expiresAt',to_char(deadline AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'));
 INSERT INTO public.aip_budget_policy_window_proposal(org_id,project_id,proposal_id,proposal_hash,
  maker_subject,checker_subject,payload,created_at,expires_at)
 VALUES('org-org','dev-project',pid,public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
  'domain','aos.budget-policy-window.proposal/v1','proposal',p)),actor,checker,p,now_at,deadline);
 INSERT INTO public.aip_budget_policy_window_fence(org_id,project_id,proposal_id)
 VALUES('org-org','dev-project',pid);
 rid:='window-propose-'||public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.policy-window-receipt-id/v1',
  'operation','propose','actor',actor,'tenant',p->'tenant','key',c->>'idempotencyKey'));
 result:=jsonb_build_object('status','prepared','operation','propose','command',c,'requestHash',digest,
  'proposalId',pid,'proposalHash',public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
  'domain','aos.budget-policy-window.proposal/v1','proposal',p)),
  'proposal',p,'targetPairHash',p->'targetPairHash','receiptId',rid,'activationEligible',false);
 INSERT INTO public.aip_budget_policy_window_receipt(org_id,project_id,receipt_id,actor_subject,
  operation,idempotency_key,request_hash,proposal_id,payload)
 VALUES('org-org','dev-project',rid,actor,'propose',c->>'idempotencyKey',digest,pid,result);
 IF clock_timestamp()>=deadline THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PROPOSAL_EXPIRED' USING ERRCODE='23514'; END IF;
 RETURN result;
END $$;

CREATE FUNCTION public.aip_policy_window_profile_v1(op_name text)
RETURNS void LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE expected_login text;expected_owner text;role_row record;seal jsonb;item jsonb;actual jsonb;
 is_inquiry boolean:=left(op_name,10)='reconcile_';operation text:=replace(op_name,'reconcile_','');
BEGIN
 expected_login:=CASE operation WHEN 'propose' THEN 'aos_budget_renewal_maker_call'
   WHEN 'decide' THEN 'aos_budget_renewal_issuer_call' WHEN 'revoke' THEN 'aos_budget_renewal_issuer_call'
   WHEN 'consume' THEN 'aos_budget_consumer_call' END;
 expected_owner:=CASE WHEN is_inquiry OR operation='consume' THEN 'aos_budget_consumer_owner'
   WHEN operation='propose' THEN 'aos_budget_renewal_proposal_owner' ELSE 'aos_budget_renewal_issuer_owner' END;
 IF (expected_login IS NOT NULL AND session_user=expected_login AND current_user=expected_owner
  AND current_setting('aos.org_id',true)='org-org' AND current_setting('aos.project_id',true)='dev-project'
  AND current_setting('transaction_isolation')='read committed'
  AND current_setting('transaction_read_only')=CASE WHEN is_inquiry THEN 'on' ELSE 'off' END
  AND current_schemas(true)<@ARRAY['pg_catalog','public']::name[]) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_ACTUAL_PURPOSE_REQUIRED' USING ERRCODE='42501'; END IF;
 FOR role_row IN SELECT * FROM pg_roles WHERE rolname IN(expected_login,expected_owner) LOOP
  IF role_row.rolsuper OR role_row.rolbypassrls OR role_row.rolinherit OR role_row.rolcreatedb
     OR role_row.rolcreaterole OR role_row.rolreplication
     OR role_row.rolcanlogin IS DISTINCT FROM (role_row.rolname=expected_login)
     OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=role_row.oid OR member=role_row.oid)
     OR has_schema_privilege(role_row.oid,'public','CREATE') THEN
   RAISE EXCEPTION 'POLICY_WINDOW_ROLE_DRIFT' USING ERRCODE='42501'; END IF;
 END LOOP;
 IF NOT is_inquiry AND operation IN('propose','decide','revoke') THEN
  PERFORM public.aip_renewal_profile_a0v_162(operation);
 END IF;
 seal:=obj_description('public.aip_budget_policy_window_proposal'::regclass,'pg_class')::jsonb;
 IF (seal->>'schema'='aos-policy-window-native-seal/v1'
     AND jsonb_array_length(seal->'functions')=22 AND jsonb_array_length(seal->'relations')=19
     AND (SELECT count(DISTINCT value->>'signature') FROM jsonb_array_elements(seal->'functions'))=22
     AND (SELECT count(DISTINCT value->>'name') FROM jsonb_array_elements(seal->'relations'))=19) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_SCHEMA_SEAL_REQUIRED' USING ERRCODE='42501'; END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(seal->'functions') LOOP
  IF item->>'signature' NOT IN(
   'public.aip_policy_window_command_v1(jsonb,text)',
   'public.aip_policy_window_relation_shape_v1(oid)',
   'public.aip_policy_window_profile_v1(text)',
   'public.aip_policy_window_parent_v1(jsonb,boolean)',
   'public.aip_policy_window_expected_v1(jsonb,text)',
   'public.aip_policy_window_propose_v1(jsonb)',
   'public.aip_policy_window_history_v1(jsonb,text,text)',
   'public.aip_policy_window_proposal_fact_v1(text,text,boolean)',
   'public.aip_policy_window_decide_v1(jsonb,text)',
   'public.aip_policy_window_revoke_v1(jsonb,text)',
   'public.aip_policy_window_consume_v1(jsonb)',
   'public.aip_policy_window_reconcile_v1(jsonb,text,text)',
   'public.aip_policy_window_guard_journal_v1()',
   'public.aip_policy_window_guard_fence_v1()',
   'public.aip_policy_window_complete_consume_v1()',
   'public.aip_budget_cost_hash_a0v_126(jsonb)',
   'public.canonical_asset_registry_jsonb(jsonb)',
   'public.guard_aip4_append_only()',
   'public.aip_budget_consumption_fact_a0v_128(text,text,text,text,text,text)',
   'public.aip_budget_cost_actor_a0v_127(text,text,text,text,text)',
   'public.aip_cost_configuration_write_guard_a0v_128()',
   'public.aip_renewal_profile_a0v_162(text)') THEN
   RAISE EXCEPTION 'POLICY_WINDOW_FUNCTION_SET_DRIFT' USING ERRCODE='42501'; END IF;
  SELECT jsonb_build_object('signature',item->>'signature','owner',pg_get_userbyid(p.proowner),
   'definer',p.prosecdef,'config',to_jsonb(p.proconfig),'acl',p.proacl::text,
   'bodySha256',encode(public.digest(convert_to(pg_get_functiondef(p.oid),'UTF8'),'sha256'),'hex'))
   INTO actual FROM pg_proc p WHERE p.oid=to_regprocedure(item->>'signature');
  IF actual IS DISTINCT FROM item THEN RAISE EXCEPTION 'POLICY_WINDOW_FUNCTION_SEAL_DRIFT' USING ERRCODE='42501'; END IF;
 END LOOP;
 FOR item IN SELECT value FROM jsonb_array_elements(seal->'relations') LOOP
  IF item->>'name' NOT IN('aip_budget_policy_window_proposal','aip_budget_policy_window_decision',
    'aip_budget_policy_window_receipt','aip_budget_policy_window_binding','aip_budget_policy_window_fence',
    'aip_budget_cost_proposal','aip_budget_cost_decision','aip_budget_cost_revocation',
    'aip_budget_receipt','aip_budget_cost_runtime_fence','aip_budget_head','aip_budget_revision',
    'aip_provider_instance_head','aip_provider_instance_revision','meta_membership',
    'aip_model_governance_policy_head','aip_model_governance_policy_revision',
    'aip_model_price_snapshot_head','aip_model_price_snapshot_revision') THEN
   RAISE EXCEPTION 'POLICY_WINDOW_RELATION_SET_DRIFT' USING ERRCODE='42501'; END IF;
  actual:=public.aip_policy_window_relation_shape_v1(to_regclass('public.'||quote_ident(item->>'name')));
  IF actual IS DISTINCT FROM item THEN RAISE EXCEPTION 'POLICY_WINDOW_RELATION_SEAL_DRIFT' USING ERRCODE='42501'; END IF;
 END LOOP;
END $$;

CREATE FUNCTION public.aip_policy_window_decide_v1(c jsonb,actor text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE p jsonb;locator jsonb;prior jsonb;d jsonb;dh text;digest text;rid text;result jsonb;now_at timestamptz;
BEGIN
 PERFORM public.aip_policy_window_profile_v1('decide');
 PERFORM public.aip_policy_window_command_v1(c,'decide');
 IF actor IS DISTINCT FROM '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657' THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PROTECTED_CHECKER_REQUIRED' USING ERRCODE='42501'; END IF;
 SELECT payload INTO STRICT locator FROM public.aip_budget_policy_window_proposal WHERE org_id='org-org'
  AND project_id='dev-project' AND proposal_id=c->>'proposalId';
 PERFORM pg_advisory_xact_lock(hashtextextended('budget-cost-review:org-org:dev-project:'||
  (locator->'request'->>'parentCostProposalId'),0));
 PERFORM pg_advisory_xact_lock(hashtextextended('budget-policy-window:org-org:dev-project:'||(c->>'proposalId'),0));
 prior:=public.aip_policy_window_history_v1(c,'decide',actor);
 IF prior IS NOT NULL THEN RETURN prior; END IF;
 p:=public.aip_policy_window_proposal_fact_v1(c->>'proposalId',c->>'proposalHash',true);
 IF p->>'targetPairHash' IS DISTINCT FROM c->>'targetPairHash' THEN
  RAISE EXCEPTION 'POLICY_WINDOW_EXACT_TARGET_PAIR_REQUIRED' USING ERRCODE='23514'; END IF;
 IF EXISTS(SELECT 1 FROM public.aip_budget_policy_window_decision WHERE org_id='org-org'
   AND project_id='dev-project' AND proposal_id=c->>'proposalId') THEN
  RAISE EXCEPTION 'POLICY_WINDOW_ALREADY_DECIDED' USING ERRCODE='23514'; END IF;
 now_at:=clock_timestamp();
 d:=jsonb_build_object('operation','decide','command',c,'actorSubject',actor,
  'proposalId',c->'proposalId','proposalHash',c->'proposalHash','targetPairHash',c->'targetPairHash',
  'decisionId',p->'approvalSlot','decision',c->'decision',
  'createdAt',to_char(now_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'));
 dh:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.budget-policy-window.decision/v1','decision',d));
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
  'domain','aos.budget-policy-window.decide/v1','command',c-'idempotencyKey'));
 rid:='window-decide-'||public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.policy-window-receipt-id/v1',
  'operation','decide','actor',actor,'tenant',p->'tenant','key',c->>'idempotencyKey'));
 INSERT INTO public.aip_budget_policy_window_decision(org_id,project_id,proposal_id,decision_id,
  decision_hash,decision,actor_subject,payload,created_at)
 VALUES('org-org','dev-project',c->>'proposalId',p->>'approvalSlot',dh,c->>'decision',actor,d,now_at);
 result:=jsonb_build_object('status','observed','operation','decide','command',c,'requestHash',digest,
  'proposalId',c->'proposalId','proposalHash',c->'proposalHash','decisionId',p->'approvalSlot',
  'decisionHash',dh,'decision',c->'decision','receiptId',rid,'activationEligible',false);
 INSERT INTO public.aip_budget_policy_window_receipt(org_id,project_id,receipt_id,actor_subject,
  operation,idempotency_key,request_hash,proposal_id,decision_id,payload)
 VALUES('org-org','dev-project',rid,actor,'decide',c->>'idempotencyKey',digest,c->>'proposalId',p->>'approvalSlot',result);
 IF clock_timestamp()>=(p->>'expiresAt')::timestamptz THEN
  RAISE EXCEPTION 'POLICY_WINDOW_DECISION_EXPIRED' USING ERRCODE='23514'; END IF;
 RETURN result;
END $$;

CREATE FUNCTION public.aip_policy_window_revoke_v1(c jsonb,actor text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE p jsonb;locator jsonb;prior jsonb;original public.aip_budget_policy_window_decision%ROWTYPE;
 f public.aip_budget_policy_window_fence%ROWTYPE;d jsonb;dh text;digest text;rid text;result jsonb;now_at timestamptz;
BEGIN
 PERFORM public.aip_policy_window_profile_v1('revoke');
 PERFORM public.aip_policy_window_command_v1(c,'revoke');
 IF actor IS DISTINCT FROM '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657' THEN
  RAISE EXCEPTION 'POLICY_WINDOW_PROTECTED_CHECKER_REQUIRED' USING ERRCODE='42501'; END IF;
 SELECT payload INTO STRICT locator FROM public.aip_budget_policy_window_proposal WHERE org_id='org-org'
  AND project_id='dev-project' AND proposal_id=c->>'proposalId';
 PERFORM pg_advisory_xact_lock(hashtextextended('budget-cost-review:org-org:dev-project:'||
  (locator->'request'->>'parentCostProposalId'),0));
 PERFORM pg_advisory_xact_lock(hashtextextended('budget-policy-window:org-org:dev-project:'||(c->>'proposalId'),0));
 prior:=public.aip_policy_window_history_v1(c,'revoke',actor);
 IF prior IS NOT NULL THEN RETURN prior; END IF;
 p:=public.aip_policy_window_proposal_fact_v1(c->>'proposalId',c->>'proposalHash',false);
 PERFORM subject FROM public.meta_membership WHERE org_id='org-org' AND project_id='dev-project'
  AND subject=actor FOR SHARE;
 IF NOT EXISTS(SELECT 1 FROM public.meta_membership WHERE org_id='org-org' AND project_id='dev-project'
  AND subject=actor AND lower(role) IN('owner','admin')) THEN
  RAISE EXCEPTION 'POLICY_WINDOW_CURRENT_CHECKER_REQUIRED' USING ERRCODE='42501'; END IF;
 SELECT * INTO STRICT original FROM public.aip_budget_policy_window_decision WHERE org_id='org-org'
  AND project_id='dev-project' AND proposal_id=c->>'proposalId' AND decision_id=c->>'originalDecisionId';
 IF (original.decision='approved' AND original.decision_id=p->>'approvalSlot' AND original.actor_subject=actor
   AND original.decision_hash=c->>'originalDecisionHash'
   AND original.decision_hash=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
    'domain','aos.budget-policy-window.decision/v1','decision',original.payload))
   AND original.payload->>'proposalHash'=c->>'proposalHash'
   AND original.payload->>'targetPairHash'=p->>'targetPairHash') IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_ORIGINAL_APPROVAL_REQUIRED' USING ERRCODE='23514'; END IF;
 SELECT * INTO STRICT f FROM public.aip_budget_policy_window_fence WHERE org_id='org-org'
  AND project_id='dev-project' AND proposal_id=c->>'proposalId' FOR UPDATE;
 IF f.revoked THEN RAISE EXCEPTION 'POLICY_WINDOW_ALREADY_REVOKED' USING ERRCODE='23514'; END IF;
 now_at:=clock_timestamp();
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
  'domain','aos.budget-policy-window.revoke/v1','command',c-'idempotencyKey'));
 rid:='window-revoke-'||public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.policy-window-receipt-id/v1',
  'operation','revoke','actor',actor,'tenant',p->'tenant','key',c->>'idempotencyKey'));
 d:=jsonb_build_object('operation','revoke','command',c,'actorSubject',actor,'proposalId',c->'proposalId',
  'proposalHash',c->'proposalHash','targetPairHash',p->'targetPairHash','decisionId',rid,'decision','revoked',
  'createdAt',to_char(now_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'));
 dh:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.budget-policy-window.decision/v1','decision',d));
 INSERT INTO public.aip_budget_policy_window_decision(org_id,project_id,proposal_id,decision_id,
  decision_hash,decision,actor_subject,payload,created_at)
 VALUES('org-org','dev-project',c->>'proposalId',rid,dh,'revoked',actor,d,now_at);
 UPDATE public.aip_budget_policy_window_fence SET version=version+1,revoked=true,
  modified_at=greatest(modified_at,now_at) WHERE org_id='org-org' AND project_id='dev-project'
  AND proposal_id=c->>'proposalId';
 result:=jsonb_build_object('status','observed','operation','revoke','command',c,'requestHash',digest,
  'proposalId',c->'proposalId','proposalHash',c->'proposalHash','decisionId',rid,
  'decisionHash',dh,'decision','revoked','receiptId',rid,'activationEligible',false);
 INSERT INTO public.aip_budget_policy_window_receipt(org_id,project_id,receipt_id,actor_subject,
  operation,idempotency_key,request_hash,proposal_id,decision_id,payload)
 VALUES('org-org','dev-project',rid,actor,'revoke',c->>'idempotencyKey',digest,c->>'proposalId',rid,result);
 RETURN result;
END $$;

CREATE FUNCTION public.aip_policy_window_consume_v1(c jsonb)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE p jsonb;locator jsonb;prior jsonb;d public.aip_budget_policy_window_decision%ROWTYPE;
 actor text:='postgres-service:aos_budget_renewal_maker_call';digest text;rid text;bid text;bh text;
 policy jsonb;price jsonb;policy_hash text;price_hash text;policy_ref jsonb;price_ref jsonb;
 binding jsonb;result jsonb;now_at timestamptz;stamp text;
BEGIN
 PERFORM public.aip_policy_window_profile_v1('consume');
 PERFORM public.aip_policy_window_command_v1(c,'consume');
 SELECT payload INTO STRICT locator FROM public.aip_budget_policy_window_proposal WHERE org_id='org-org'
  AND project_id='dev-project' AND proposal_id=c->>'proposalId';
 PERFORM pg_advisory_xact_lock(hashtextextended('budget-cost-review:org-org:dev-project:'||
  (locator->'request'->>'parentCostProposalId'),0));
 PERFORM pg_advisory_xact_lock(hashtextextended('budget-policy-window:org-org:dev-project:'||(c->>'proposalId'),0));
 prior:=public.aip_policy_window_history_v1(c,'consume',actor);
 IF prior IS NOT NULL THEN RETURN prior; END IF;
 p:=public.aip_policy_window_proposal_fact_v1(c->>'proposalId',c->>'proposalHash',true);
 IF EXISTS(SELECT 1 FROM public.aip_budget_policy_window_receipt WHERE org_id='org-org'
  AND project_id='dev-project' AND proposal_id=c->>'proposalId' AND operation='consume') THEN
  RAISE EXCEPTION 'POLICY_WINDOW_ALREADY_CONSUMED_USE_ORIGINAL_KEY' USING ERRCODE='23514'; END IF;
 SELECT * INTO STRICT d FROM public.aip_budget_policy_window_decision WHERE org_id='org-org'
  AND project_id='dev-project' AND proposal_id=c->>'proposalId' AND decision_id=c->>'decisionId';
 IF (d.decision='approved' AND d.decision_id=p->>'approvalSlot' AND d.decision_hash=c->>'decisionHash'
  AND d.actor_subject=p->>'checkerSubject' AND d.decision_hash=public.aip_budget_cost_hash_a0v_126(
   jsonb_build_object('domain','aos.budget-policy-window.decision/v1','decision',d.payload))
  AND d.payload->>'proposalHash'=c->>'proposalHash'
  AND d.payload->>'targetPairHash'=c->>'targetPairHash' AND c->>'targetPairHash'=p->>'targetPairHash'
  AND d.created_at=(d.payload->>'createdAt')::timestamptz
  AND d.created_at>=(p->>'createdAt')::timestamptz AND d.created_at<(p->>'expiresAt')::timestamptz) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_EXACT_APPROVAL_REQUIRED' USING ERRCODE='23514'; END IF;
 IF EXISTS(SELECT 1 FROM public.aip_budget_policy_window_decision WHERE org_id='org-org'
   AND project_id='dev-project' AND proposal_id=c->>'proposalId' AND decision='revoked') THEN
  RAISE EXCEPTION 'POLICY_WINDOW_REVOKED' USING ERRCODE='42501'; END IF;
 now_at:=clock_timestamp();stamp:=to_char(now_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"');
 IF now_at<(p->'request'->>'effectiveFrom')::timestamptz
  OR now_at>=(p->>'expiresAt')::timestamptz THEN
  RAISE EXCEPTION 'POLICY_WINDOW_CURRENT_WINDOW_REQUIRED' USING ERRCODE='23514'; END IF;
 policy:=p->'targets'->'policy';price:=p->'targets'->'price';
 policy_hash:=public.aip_budget_cost_hash_a0v_126(policy);price_hash:=public.aip_budget_cost_hash_a0v_126(price);
 policy_ref:=jsonb_build_object('assetType','BudgetPolicyRevision','assetId',policy->'policyId',
  'revision',1,'contentHash',policy_hash);
 price_ref:=jsonb_build_object('assetType','ModelPriceSnapshotRevision','assetId',price->'priceSnapshotId',
  'revision',1,'contentHash',price_hash);
 policy:=policy||jsonb_build_object('tenant',p->'tenant','contentHash',policy_hash,'createdBy',actor,'createdAt',stamp);
 price:=price||jsonb_build_object('tenant',p->'tenant','revision',1,'contentHash',price_hash,'createdBy',actor,'createdAt',stamp);
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
  'domain','aos.budget-policy-window.consume/v1','command',c-'idempotencyKey'));
 rid:='window-consume-'||public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.policy-window-receipt-id/v1',
  'operation','consume','actor',actor,'tenant',p->'tenant','key',c->>'idempotencyKey'));
 bid:='window-binding-'||public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.policy-window-binding-id/v1',
  'tenant',p->'tenant','proposalId',c->'proposalId','decisionId',d.decision_id,'targetPairHash',p->'targetPairHash'));
 binding:=jsonb_build_object('bindingId',bid,'tenant',p->'tenant','parent',p->'parent',
  'proposalId',c->'proposalId','proposalHash',c->'proposalHash','decisionId',d.decision_id,'decisionHash',d.decision_hash,
  'targetPairHash',p->'targetPairHash','policyRef',policy_ref,'priceRef',price_ref,'receiptId',rid);
 bh:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.budget-policy-window.binding/v1','binding',binding));
 INSERT INTO public.aip_model_price_snapshot_head(org_id,project_id,model_price_snapshot_id,current_revision,version)
 VALUES('org-org','dev-project',price->>'priceSnapshotId',1,1);
 INSERT INTO public.aip_model_price_snapshot_revision(org_id,project_id,model_price_snapshot_id,revision,
  content_hash,lifecycle,payload,created_by,created_at)
 VALUES('org-org','dev-project',price->>'priceSnapshotId',1,price_hash,'active',price,actor,now_at);
 INSERT INTO public.aip_model_governance_policy_head(org_id,project_id,policy_kind,policy_id,current_revision,version)
 VALUES('org-org','dev-project','budget',policy->>'policyId',1,1);
 INSERT INTO public.aip_model_governance_policy_revision(org_id,project_id,policy_kind,policy_id,revision,
  content_hash,lifecycle,effective_from,effective_until,payload,created_by,created_at)
 VALUES('org-org','dev-project','budget',policy->>'policyId',1,policy_hash,'active',
  (policy->>'effectiveFrom')::timestamptz,(policy->>'effectiveUntil')::timestamptz,policy,actor,now_at);
 INSERT INTO public.aip_budget_policy_window_binding(org_id,project_id,binding_id,binding_hash,
  proposal_id,decision_id,receipt_id,policy_ref,price_ref,payload)
 VALUES('org-org','dev-project',bid,bh,c->>'proposalId',d.decision_id,rid,policy_ref,price_ref,binding);
 UPDATE public.aip_budget_policy_window_fence SET version=version+1,modified_at=greatest(modified_at,now_at)
 WHERE org_id='org-org' AND project_id='dev-project' AND proposal_id=c->>'proposalId';
 result:=jsonb_build_object('status','observed','operation','consume','command',c,'requestHash',digest,
  'proposalId',c->'proposalId','proposalHash',c->'proposalHash','decisionId',d.decision_id,'decisionHash',d.decision_hash,
  'targetPairHash',p->'targetPairHash','budgetRef',p->'parent'->'budgetRef','policyRef',policy_ref,
  'priceRef',price_ref,'bindingId',bid,'bindingHash',bh,'receiptId',rid,'activationEligible',false);
 INSERT INTO public.aip_budget_policy_window_receipt(org_id,project_id,receipt_id,actor_subject,
  operation,idempotency_key,request_hash,proposal_id,decision_id,payload)
 VALUES('org-org','dev-project',rid,actor,'consume',c->>'idempotencyKey',digest,c->>'proposalId',d.decision_id,result);
 IF clock_timestamp()>=(p->>'expiresAt')::timestamptz THEN
  RAISE EXCEPTION 'POLICY_WINDOW_CONSUMPTION_EXPIRED' USING ERRCODE='23514'; END IF;
 RETURN result;
END $$;

CREATE FUNCTION public.aip_policy_window_reconcile_v1(c jsonb,op_name text,actor text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE result jsonb;expected_actor text;
BEGIN
 PERFORM public.aip_policy_window_profile_v1('reconcile_'||op_name);
 PERFORM public.aip_policy_window_command_v1(c,op_name);
 expected_actor:=CASE WHEN op_name IN('decide','revoke') THEN '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
  ELSE 'postgres-service:aos_budget_renewal_maker_call' END;
 IF actor IS DISTINCT FROM expected_actor THEN
  RAISE EXCEPTION 'POLICY_WINDOW_ORIGINAL_ACTOR_REQUIRED' USING ERRCODE='42501'; END IF;
 result:=public.aip_policy_window_history_v1(c,op_name,actor);
 IF result IS NULL THEN RETURN jsonb_build_object('status','unresolved','activationEligible',false); END IF;
 RETURN jsonb_build_object('status','observed','receipt',result,'activationEligible',false);
END $$;

CREATE FUNCTION public.aip_policy_window_guard_journal_v1()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE op_name text;p jsonb;d public.aip_budget_policy_window_decision%ROWTYPE;
BEGIN
 IF TG_OP<>'INSERT' OR (NEW.org_id,NEW.project_id) IS DISTINCT FROM ('org-org','dev-project') THEN
  RAISE EXCEPTION 'POLICY_WINDOW_INSERT_SCOPE_REQUIRED' USING ERRCODE='42501'; END IF;
 IF TG_TABLE_NAME='aip_budget_policy_window_proposal' THEN
  PERFORM public.aip_policy_window_profile_v1('propose');
  IF (NEW.maker_subject=NEW.payload->>'makerSubject' AND NEW.checker_subject=NEW.payload->>'checkerSubject'
    AND NEW.maker_subject='postgres-service:aos_budget_renewal_maker_call'
    AND NEW.checker_subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
    AND NEW.proposal_hash=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
     'domain','aos.budget-policy-window.proposal/v1','proposal',NEW.payload))
    AND NEW.created_at=(NEW.payload->>'createdAt')::timestamptz
    AND NEW.expires_at=(NEW.payload->>'expiresAt')::timestamptz) IS NOT TRUE THEN
   RAISE EXCEPTION 'POLICY_WINDOW_PROPOSAL_INSERT_DRIFT' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='aip_budget_policy_window_decision' THEN
  op_name:=CASE WHEN NEW.decision='revoked' THEN 'revoke' ELSE 'decide' END;
  PERFORM public.aip_policy_window_profile_v1(op_name);
  p:=public.aip_policy_window_proposal_fact_v1(NEW.proposal_id,NEW.payload->>'proposalHash',false);
  IF (NEW.actor_subject=p->>'checkerSubject' AND NEW.actor_subject=NEW.payload->>'actorSubject'
    AND NEW.decision=NEW.payload->>'decision' AND NEW.decision_id=NEW.payload->>'decisionId'
    AND NEW.payload->>'operation'=op_name AND NEW.payload->>'targetPairHash'=p->>'targetPairHash'
    AND NEW.created_at=(NEW.payload->>'createdAt')::timestamptz
    AND NEW.decision_hash=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
      'domain','aos.budget-policy-window.decision/v1','decision',NEW.payload))) IS NOT TRUE THEN
   RAISE EXCEPTION 'POLICY_WINDOW_DECISION_INSERT_DRIFT' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='aip_budget_policy_window_binding' THEN
  PERFORM public.aip_policy_window_profile_v1('consume');
  IF (NEW.binding_id=NEW.payload->>'bindingId' AND NEW.proposal_id=NEW.payload->>'proposalId'
    AND NEW.decision_id=NEW.payload->>'decisionId' AND NEW.receipt_id=NEW.payload->>'receiptId'
    AND NEW.policy_ref=NEW.payload->'policyRef' AND NEW.price_ref=NEW.payload->'priceRef'
    AND NEW.transaction_id=txid_current()
    AND NEW.binding_hash=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
     'domain','aos.budget-policy-window.binding/v1','binding',NEW.payload))) IS NOT TRUE THEN
   RAISE EXCEPTION 'POLICY_WINDOW_BINDING_INSERT_DRIFT' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='aip_budget_policy_window_receipt' THEN
  op_name:=NEW.operation;PERFORM public.aip_policy_window_profile_v1(op_name);
  PERFORM public.aip_policy_window_command_v1(NEW.payload->'command',op_name);
  p:=public.aip_policy_window_proposal_fact_v1(NEW.proposal_id,NEW.payload->>'proposalHash',false);
  IF (NEW.payload->>'operation'=op_name AND NEW.payload->>'proposalId'=NEW.proposal_id
    AND NEW.payload->'activationEligible'='false'::jsonb
    AND NEW.actor_subject=CASE WHEN op_name IN('decide','revoke') THEN p->>'checkerSubject' ELSE p->>'makerSubject' END
    AND NEW.idempotency_key=NEW.payload->'command'->>'idempotencyKey'
    AND NEW.transaction_id=txid_current() AND NEW.payload->>'receiptId'=NEW.receipt_id
    AND NEW.request_hash=NEW.payload->>'requestHash'
    AND NEW.request_hash=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
     'domain','aos.budget-policy-window.'||op_name||'/v1','command',(NEW.payload->'command')-'idempotencyKey'))) IS NOT TRUE THEN
   RAISE EXCEPTION 'POLICY_WINDOW_RECEIPT_INSERT_DRIFT' USING ERRCODE='23514'; END IF;
  IF op_name<>'propose' THEN
   SELECT * INTO STRICT d FROM public.aip_budget_policy_window_decision WHERE org_id=NEW.org_id
    AND project_id=NEW.project_id AND proposal_id=NEW.proposal_id AND decision_id=NEW.decision_id;
   IF (d.decision_id=NEW.payload->>'decisionId' AND d.decision_hash=NEW.payload->>'decisionHash') IS NOT TRUE THEN
    RAISE EXCEPTION 'POLICY_WINDOW_RECEIPT_DECISION_DRIFT' USING ERRCODE='23514'; END IF;
  END IF;
 ELSE RAISE EXCEPTION 'POLICY_WINDOW_UNEXPECTED_JOURNAL' USING ERRCODE='42501'; END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION public.aip_policy_window_guard_fence_v1()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP='INSERT' THEN
  PERFORM public.aip_policy_window_profile_v1('propose');
  IF NEW.version<>1 OR NEW.revoked THEN
   RAISE EXCEPTION 'POLICY_WINDOW_INITIAL_FENCE_REQUIRED' USING ERRCODE='23514'; END IF;
 ELSIF TG_OP='UPDATE' THEN
  IF session_user='aos_budget_renewal_issuer_call' THEN
   PERFORM public.aip_policy_window_profile_v1('revoke');
   IF OLD.revoked OR NOT NEW.revoked OR NOT EXISTS(SELECT 1 FROM public.aip_budget_policy_window_decision
    WHERE org_id=OLD.org_id AND project_id=OLD.project_id AND proposal_id=OLD.proposal_id AND decision='revoked') THEN
    RAISE EXCEPTION 'POLICY_WINDOW_REVOCATION_FENCE_REQUIRED' USING ERRCODE='23514'; END IF;
  ELSE
   PERFORM public.aip_policy_window_profile_v1('consume');
   IF OLD.revoked OR NEW.revoked THEN RAISE EXCEPTION 'POLICY_WINDOW_REVOKED' USING ERRCODE='42501'; END IF;
  END IF;
  IF (NEW.org_id,NEW.project_id,NEW.proposal_id) IS DISTINCT FROM (OLD.org_id,OLD.project_id,OLD.proposal_id)
    OR NEW.version<>OLD.version+1 OR NEW.modified_at<OLD.modified_at THEN
   RAISE EXCEPTION 'POLICY_WINDOW_FENCE_DRIFT' USING ERRCODE='23514'; END IF;
 ELSE RAISE EXCEPTION 'POLICY_WINDOW_FENCE_HISTORY_REQUIRED' USING ERRCODE='42501'; END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION public.aip_policy_window_complete_consume_v1()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE pid text;p jsonb;r public.aip_budget_policy_window_receipt%ROWTYPE;
 b public.aip_budget_policy_window_binding%ROWTYPE;d public.aip_budget_policy_window_decision%ROWTYPE;
 policy jsonb;price jsonb;policy_hash text;price_hash text;expected_binding jsonb;stamp text;f record;
BEGIN
 IF TG_TABLE_NAME='aip_budget_policy_window_receipt' THEN
  IF NEW.operation<>'consume' THEN RETURN NEW; END IF;pid:=NEW.proposal_id;
 ELSIF TG_TABLE_NAME='aip_budget_policy_window_binding' THEN pid:=NEW.proposal_id;
 ELSIF TG_TABLE_NAME='aip_model_price_snapshot_revision' THEN
  IF NEW.model_price_snapshot_id NOT LIKE 'window-price-%' THEN RETURN NEW; END IF;
  SELECT proposal_id INTO STRICT pid FROM public.aip_budget_policy_window_binding WHERE org_id=NEW.org_id
   AND project_id=NEW.project_id AND price_ref->>'assetId'=NEW.model_price_snapshot_id
   AND price_ref->>'revision'=NEW.revision::text;
 ELSIF TG_TABLE_NAME='aip_model_governance_policy_revision' THEN
  IF NEW.policy_kind<>'budget' OR NEW.policy_id NOT LIKE 'window-policy-%' THEN RETURN NEW; END IF;
  SELECT proposal_id INTO STRICT pid FROM public.aip_budget_policy_window_binding WHERE org_id=NEW.org_id
   AND project_id=NEW.project_id AND policy_ref->>'assetId'=NEW.policy_id
   AND policy_ref->>'revision'=NEW.revision::text;
 ELSE RAISE EXCEPTION 'POLICY_WINDOW_COMPLETENESS_RELATION_REQUIRED' USING ERRCODE='23514'; END IF;
 PERFORM public.aip_policy_window_profile_v1('consume');
 SELECT * INTO STRICT r FROM public.aip_budget_policy_window_receipt WHERE org_id='org-org'
  AND project_id='dev-project' AND proposal_id=pid AND operation='consume';
 p:=public.aip_policy_window_proposal_fact_v1(pid,r.payload->>'proposalHash',false);
 SELECT * INTO STRICT b FROM public.aip_budget_policy_window_binding WHERE org_id=r.org_id
  AND project_id=r.project_id AND proposal_id=pid AND receipt_id=r.receipt_id;
 SELECT * INTO STRICT d FROM public.aip_budget_policy_window_decision WHERE org_id=r.org_id
  AND project_id=r.project_id AND proposal_id=pid AND decision_id=r.decision_id;
 policy_hash:=public.aip_budget_cost_hash_a0v_126(p->'targets'->'policy');
 price_hash:=public.aip_budget_cost_hash_a0v_126(p->'targets'->'price');
 expected_binding:=jsonb_build_object('bindingId',b.binding_id,'tenant',p->'tenant','parent',p->'parent',
  'proposalId',pid,'proposalHash',r.payload->'proposalHash','decisionId',d.decision_id,'decisionHash',d.decision_hash,
  'targetPairHash',p->'targetPairHash','policyRef',jsonb_build_object('assetType','BudgetPolicyRevision',
    'assetId',p->'targets'->'policy'->'policyId','revision',1,'contentHash',policy_hash),
  'priceRef',jsonb_build_object('assetType','ModelPriceSnapshotRevision',
    'assetId',p->'targets'->'price'->'priceSnapshotId','revision',1,'contentHash',price_hash),'receiptId',r.receipt_id);
 IF (r.transaction_id=txid_current() AND b.transaction_id=txid_current() AND b.payload=expected_binding
   AND b.binding_hash=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
    'domain','aos.budget-policy-window.binding/v1','binding',expected_binding))
   AND r.payload->>'bindingId'=b.binding_id AND r.payload->>'bindingHash'=b.binding_hash
   AND r.payload->'policyRef'=b.policy_ref AND r.payload->'priceRef'=b.price_ref
   AND r.payload->'budgetRef'=p->'parent'->'budgetRef' AND r.payload->>'targetPairHash'=p->>'targetPairHash'
   AND d.decision='approved' AND d.decision_id=p->>'approvalSlot' AND d.actor_subject=p->>'checkerSubject'
   AND d.payload->>'proposalHash'=r.payload->>'proposalHash'
   AND d.payload->>'targetPairHash'=p->>'targetPairHash'
   AND d.decision_hash=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
    'domain','aos.budget-policy-window.decision/v1','decision',d.payload))
   AND clock_timestamp()<(p->>'expiresAt')::timestamptz) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_ATOMIC_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
 SELECT * INTO STRICT f FROM public.aip_budget_policy_window_fence WHERE org_id=r.org_id
  AND project_id=r.project_id AND proposal_id=pid;
 IF f.revoked OR f.version<>2 THEN RAISE EXCEPTION 'POLICY_WINDOW_ATOMIC_FENCE_REQUIRED' USING ERRCODE='23514'; END IF;
 SELECT payload INTO STRICT price FROM public.aip_model_price_snapshot_revision WHERE org_id=r.org_id
  AND project_id=r.project_id AND model_price_snapshot_id=b.price_ref->>'assetId'
  AND revision=1 AND content_hash=price_hash AND lifecycle='active';
 SELECT payload INTO STRICT policy FROM public.aip_model_governance_policy_revision WHERE org_id=r.org_id
  AND project_id=r.project_id AND policy_kind='budget' AND policy_id=b.policy_ref->>'assetId'
  AND revision=1 AND content_hash=policy_hash AND lifecycle='active';
 stamp:=price->>'createdAt';
 IF (price=(p->'targets'->'price')||jsonb_build_object('tenant',p->'tenant','revision',1,
     'contentHash',price_hash,'createdBy',p->'makerSubject','createdAt',stamp)
   AND policy=(p->'targets'->'policy')||jsonb_build_object('tenant',p->'tenant',
     'contentHash',policy_hash,'createdBy',p->'makerSubject','createdAt',stamp)
   AND EXISTS(SELECT 1 FROM public.aip_model_price_snapshot_head WHERE org_id=r.org_id
    AND project_id=r.project_id AND model_price_snapshot_id=b.price_ref->>'assetId' AND current_revision=1 AND version=1)
   AND EXISTS(SELECT 1 FROM public.aip_model_governance_policy_head WHERE org_id=r.org_id
    AND project_id=r.project_id AND policy_kind='budget' AND policy_id=b.policy_ref->>'assetId'
    AND current_revision=1 AND version=1)) IS NOT TRUE THEN
  RAISE EXCEPTION 'POLICY_WINDOW_ATOMIC_PAIR_REQUIRED' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
