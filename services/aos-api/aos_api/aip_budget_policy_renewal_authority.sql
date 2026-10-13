-- Closed authority foundation. Operation functions and the renewed publication
-- guard are added only with the full native three-actor implementation.
-- Callers remain NOLOGIN; this file does not authorize deployment or approval.
CREATE TABLE public.aip_budget_policy_renewal_proposal (
 org_id text NOT NULL,project_id text NOT NULL,proposal_id text NOT NULL,
 proposal_hash text NOT NULL CHECK(proposal_hash ~ '^[0-9a-f]{64}$'),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(org_id,project_id,proposal_id),
 CHECK(org_id='org-org' AND project_id='dev-project')
);
CREATE TABLE public.aip_budget_policy_renewal_decision (
 org_id text NOT NULL,project_id text NOT NULL,proposal_id text NOT NULL,
 decision_id text NOT NULL,decision_hash text NOT NULL CHECK(decision_hash ~ '^[0-9a-f]{64}$'),
 decision text NOT NULL CHECK(decision IN('approved','rejected','revoked')),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(org_id,project_id,decision_id),
 FOREIGN KEY(org_id,project_id,proposal_id)
 REFERENCES public.aip_budget_policy_renewal_proposal(org_id,project_id,proposal_id),
 CHECK(org_id='org-org' AND project_id='dev-project')
);
CREATE UNIQUE INDEX aip_renewal_initial_decision_a0v162
 ON public.aip_budget_policy_renewal_decision(org_id,project_id,proposal_id)
 WHERE decision IN('approved','rejected');
CREATE UNIQUE INDEX aip_renewal_revocation_a0v162
 ON public.aip_budget_policy_renewal_decision(org_id,project_id,proposal_id)
 WHERE decision='revoked';
CREATE TABLE public.aip_budget_policy_renewal_receipt (
 org_id text NOT NULL,project_id text NOT NULL,operation text NOT NULL
 CHECK(operation IN('propose','decide','revoke','consume')),
 idempotency_key text NOT NULL,receipt_id text NOT NULL,proposal_id text NOT NULL,
 decision_id text,request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 transaction_id bigint NOT NULL DEFAULT txid_current(),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(org_id,project_id,receipt_id),
 UNIQUE(org_id,project_id,operation,idempotency_key),
 FOREIGN KEY(org_id,project_id,proposal_id)
 REFERENCES public.aip_budget_policy_renewal_proposal(org_id,project_id,proposal_id),
 CHECK(org_id='org-org' AND project_id='dev-project')
);
CREATE UNIQUE INDEX aip_renewal_consumed_once_a0v162
 ON public.aip_budget_policy_renewal_receipt(org_id,project_id,proposal_id) WHERE operation='consume';
CREATE UNIQUE INDEX aip_renewal_single_request_tx_a0v162
 ON public.aip_budget_policy_renewal_receipt(transaction_id) WHERE operation='consume';

CREATE FUNCTION public.aip_renewal_relation_shape_a0v_162(p_oid oid)
RETURNS jsonb LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT jsonb_build_object('name',c.relname,'owner',pg_get_userbyid(c.relowner),
  'rls',c.relrowsecurity,'forceRls',c.relforcerowsecurity,'acl',c.relacl::text,
  'columns',(SELECT jsonb_agg(jsonb_build_object('name',a.attname,'acl',a.attacl::text)
      ORDER BY a.attnum) FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped),
  'policies',COALESCE((SELECT jsonb_agg(jsonb_build_object('name',p.polname,
      'permissive',p.polpermissive,'roles',to_jsonb(p.polroles),'command',p.polcmd,
      'using',pg_get_expr(p.polqual,p.polrelid),'check',pg_get_expr(p.polwithcheck,p.polrelid))
      ORDER BY p.polname) FROM pg_policy p WHERE p.polrelid=c.oid),'[]'::jsonb))
 FROM pg_class c WHERE c.oid=p_oid AND c.relnamespace='public'::regnamespace
$$;

CREATE FUNCTION public.aip_renewal_profile_a0v_162(p_purpose text)
RETURNS void LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE caller text; expected_owner text; r record; manifest jsonb; item jsonb;
        actual jsonb; fid oid; relation oid;
        journal text;
BEGIN
 IF p_purpose IN('propose','reconcile_propose') THEN
   caller:='aos_budget_renewal_maker_call';
   expected_owner:=CASE WHEN p_purpose='propose' THEN 'aos_budget_renewal_proposal_owner'
                      ELSE 'aos_budget_renewal_publish_owner' END;
   IF (p_purpose='propose' AND current_setting('transaction_read_only')<>'off')
      OR (p_purpose='reconcile_propose' AND current_setting('transaction_read_only')<>'on') THEN
     RAISE EXCEPTION 'RENEWAL_TRANSACTION_MODE_REQUIRED' USING ERRCODE='42501'; END IF;
 ELSIF p_purpose IN('consume','reconcile_consume') THEN
   caller:='aos_budget_renewal_consumer_call';expected_owner:='aos_budget_renewal_publish_owner';
   IF (p_purpose='consume' AND current_setting('transaction_read_only')<>'off')
      OR (p_purpose='reconcile_consume' AND current_setting('transaction_read_only')<>'on') THEN
     RAISE EXCEPTION 'RENEWAL_TRANSACTION_MODE_REQUIRED' USING ERRCODE='42501'; END IF;
 ELSIF p_purpose IN('decide','revoke','issuer_observe','reconcile_decide','reconcile_revoke') THEN
   caller:='aos_budget_renewal_issuer_call';expected_owner:='aos_budget_renewal_issuer_owner';
   IF p_purpose IN('reconcile_decide','reconcile_revoke') THEN
     expected_owner:='aos_budget_renewal_publish_owner';
     IF current_setting('transaction_read_only')<>'on' THEN
       RAISE EXCEPTION 'RENEWAL_TRANSACTION_MODE_REQUIRED' USING ERRCODE='42501'; END IF;
   ELSIF p_purpose IN('decide','revoke') AND current_setting('transaction_read_only')<>'off' THEN
     RAISE EXCEPTION 'RENEWAL_TRANSACTION_MODE_REQUIRED' USING ERRCODE='42501'; END IF;
 ELSE
   RAISE EXCEPTION 'RENEWAL_OPERATION_NOT_IMPLEMENTED' USING ERRCODE='42501';
 END IF;
 IF (session_user=caller AND current_user=expected_owner
    AND current_setting('aos.org_id',true)='org-org'
    AND current_setting('aos.project_id',true)='dev-project'
    AND current_setting('transaction_isolation')='read committed'
    AND current_schemas(true)<@ARRAY['pg_catalog','public']::name[]) IS NOT TRUE THEN
   RAISE EXCEPTION 'RENEWAL_ACTUAL_SESSION_REQUIRED' USING ERRCODE='42501';
 END IF;
 FOR r IN SELECT * FROM pg_roles WHERE rolname IN(
   'aos_budget_renewal_maker_call','aos_budget_renewal_issuer_call','aos_budget_renewal_consumer_call',
   'aos_budget_renewal_proposal_owner','aos_budget_renewal_issuer_owner','aos_budget_renewal_publish_owner') LOOP
   IF r.rolsuper OR r.rolbypassrls OR r.rolinherit OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication
      OR (r.rolname LIKE '%_owner' AND r.rolcanlogin)
      OR (r.rolname=caller AND NOT r.rolcanlogin)
      OR EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid OR roleid=r.oid)
      OR has_schema_privilege(r.oid,'public','CREATE') THEN
     RAISE EXCEPTION 'RENEWAL_ROLE_PROFILE_DRIFT' USING ERRCODE='42501';
   END IF;
 END LOOP;
 IF (SELECT count(*) FROM pg_roles WHERE rolname LIKE 'aos_budget_renewal_%'
     AND rolname IN('aos_budget_renewal_maker_call','aos_budget_renewal_issuer_call',
       'aos_budget_renewal_consumer_call','aos_budget_renewal_proposal_owner',
       'aos_budget_renewal_issuer_owner','aos_budget_renewal_publish_owner'))<>6 THEN
   RAISE EXCEPTION 'RENEWAL_ROLE_PROFILE_DRIFT' USING ERRCODE='42501';
 END IF;
 FOREACH journal IN ARRAY ARRAY['aip_budget_policy_renewal_proposal',
   'aip_budget_policy_renewal_decision','aip_budget_policy_renewal_receipt'] LOOP
   IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid=to_regclass('public.'||journal)
     AND tgname='renewal_immutable_update' AND tgenabled='O' AND tgtype=27
     AND tgfoid='public.guard_aip4_append_only()'::regprocedure)
     OR NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid=to_regclass('public.'||journal)
     AND tgname='renewal_immutable_truncate' AND tgenabled='O' AND tgtype=34
     AND tgfoid='public.guard_aip4_append_only()'::regprocedure) THEN
     RAISE EXCEPTION 'RENEWAL_IMMUTABLE_TRIGGER_DRIFT' USING ERRCODE='42501'; END IF;
 END LOOP;
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='public.aip_budget_policy_renewal_receipt'::regclass
   AND tgname='renewal_consume_complete' AND tgenabled='O' AND tgtype=5
   AND tgdeferrable AND tginitdeferred AND tgconstraint<>0
   AND tgfoid='public.aip_renewal_complete_receipt_a0v_162()'::regprocedure) THEN
   RAISE EXCEPTION 'RENEWAL_COMPLETENESS_TRIGGER_DRIFT' USING ERRCODE='42501'; END IF;
 manifest:=obj_description('public.aip_budget_policy_renewal_proposal'::regclass,'pg_class')::jsonb;
 IF (manifest->>'schema'='aos-renewal-schema-seal/v1'
     AND jsonb_array_length(manifest->'functions')=22
     AND jsonb_array_length(manifest->'relations')=10) IS NOT TRUE THEN
   RAISE EXCEPTION 'RENEWAL_SCHEMA_SEAL_REQUIRED' USING ERRCODE='42501';
 END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(manifest->'functions') LOOP
   IF item->>'signature' NOT IN(
     'public.aip_renewal_relation_shape_a0v_162(oid)',
     'public.aip_renewal_profile_a0v_162(text)',
     'public.aip_renewal_checker_member_a0v_162()',
     'public.aip_renewal_source_a0v_162(jsonb,text)',
     'public.aip_renewal_proposal_command_a0v_162(jsonb)',
     'public.aip_renewal_propose_a0v_162(jsonb)',
     'public.aip_renewal_reconcile_a0v_162(jsonb,text,text)',
     'public.aip_renewal_issuer_command_a0v_162(jsonb,text)',
     'public.aip_renewal_issuer_fact_a0v_162(jsonb,text,boolean)',
     'public.aip_renewal_issuer_write_a0v_162(jsonb,text,text)',
     'public.aip_renewal_decide_a0v_162(jsonb,text)',
     'public.aip_renewal_revoke_a0v_162(jsonb,text)',
     'public.aip_renewal_consume_command_a0v_162(jsonb)',
     'public.aip_renewal_consume_fact_a0v_162(jsonb,boolean)',
     'public.aip_renewal_consume_history_a0v_162(jsonb)',
     'public.aip_renewal_assert_insert_a0v_162(text,text,text,bigint,text,jsonb,text,timestamp with time zone,timestamp with time zone,timestamp with time zone)',
     'public.aip_renewal_complete_receipt_a0v_162()',
     'public.aip_renewal_consume_a0v_162(jsonb)',
     'public.aip_budget_cost_hash_a0v_126(jsonb)',
     'public.canonical_asset_registry_jsonb(jsonb)',
     'public.guard_aip4_append_only()',
     'public.aip_cost_configuration_write_guard_a0v_128()') THEN
     RAISE EXCEPTION 'RENEWAL_SCHEMA_SEAL_REQUIRED' USING ERRCODE='42501'; END IF;
   fid:=to_regprocedure(item->>'signature');
   SELECT jsonb_build_object('signature',item->>'signature','owner',pg_get_userbyid(p.proowner),
     'definer',p.prosecdef,'config',to_jsonb(p.proconfig),'acl',p.proacl::text,
     'bodySha256',encode(public.digest(convert_to(pg_get_functiondef(p.oid),'UTF8'),'sha256'),'hex'))
     INTO actual FROM pg_proc p WHERE p.oid=fid;
   IF actual IS DISTINCT FROM item THEN
     RAISE EXCEPTION 'RENEWAL_FUNCTION_PROFILE_DRIFT' USING ERRCODE='42501'; END IF;
 END LOOP;
 FOR item IN SELECT value FROM jsonb_array_elements(manifest->'relations') LOOP
   relation:=to_regclass('public.'||quote_ident(item->>'name'));
   IF item->>'name' NOT IN('aip_budget_policy_renewal_proposal','aip_budget_policy_renewal_decision',
     'aip_budget_policy_renewal_receipt','aip_model_governance_policy_head',
     'aip_model_governance_policy_revision','aip_budget_head','aip_budget_revision',
     'aip_provider_instance_head','aip_provider_instance_revision','meta_membership')
     OR public.aip_renewal_relation_shape_a0v_162(relation) IS DISTINCT FROM item
     OR has_table_privilege(caller,relation,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
     OR EXISTS(SELECT 1 FROM pg_attribute a WHERE a.attrelid=relation AND a.attnum>0 AND NOT a.attisdropped
         AND has_column_privilege(caller,relation,a.attnum,'SELECT,INSERT,UPDATE,REFERENCES')) THEN
     RAISE EXCEPTION 'RENEWAL_RELATION_PROFILE_DRIFT' USING ERRCODE='42501'; END IF;
 END LOOP;
END $$;

CREATE FUNCTION public.aip_renewal_proposal_command_a0v_162(c jsonb)
RETURNS void LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF (jsonb_typeof(c)='object' AND c-ARRAY['schemaVersion','orgId','projectId','idempotencyKey',
   'sourcePolicyId','expectedSourceRevision','expectedHeadVersion','expectedSourceHash',
   'effectiveFrom','effectiveUntil']='{}'::jsonb
   AND c->>'schemaVersion'='1' AND jsonb_typeof(c->'schemaVersion')='number'
   AND c->>'orgId'='org-org' AND c->>'projectId'='dev-project'
   AND jsonb_typeof(c->'idempotencyKey')='string' AND c->>'idempotencyKey' ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$'
   AND jsonb_typeof(c->'sourcePolicyId')='string' AND c->>'sourcePolicyId' ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$'
   AND jsonb_typeof(c->'expectedSourceRevision')='number'
   AND jsonb_typeof(c->'expectedHeadVersion')='number'
   AND c->>'expectedSourceRevision' ~ '^[1-9][0-9]{0,15}$'
   AND c->>'expectedHeadVersion' ~ '^[1-9][0-9]{0,15}$'
   AND (c->>'expectedSourceRevision')::bigint<9007199254740991
   AND (c->>'expectedHeadVersion')::bigint<=9007199254740991
   AND jsonb_typeof(c->'expectedSourceHash')='string' AND c->>'expectedSourceHash' ~ '^[0-9a-f]{64}$'
   AND jsonb_typeof(c->'effectiveFrom')='string' AND c->>'effectiveFrom' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})$'
   AND jsonb_typeof(c->'effectiveUntil')='string' AND c->>'effectiveUntil' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})$') IS NOT TRUE THEN
   RAISE EXCEPTION 'RENEWAL_EXACT_PROPOSAL_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
END $$;

CREATE FUNCTION public.aip_renewal_source_a0v_162(c jsonb,slot text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE h public.aip_model_governance_policy_head%ROWTYPE;
 s public.aip_model_governance_policy_revision%ROWTYPE;
 b public.aip_budget_revision%ROWTYPE;v public.aip_provider_instance_revision%ROWTYPE;
 bh bigint;vh bigint;auth jsonb;body jsonb;t jsonb;now_at timestamptz;
 from_at timestamptz;until_at timestamptz;tenant jsonb;contract jsonb;
BEGIN
 PERFORM public.aip_renewal_proposal_command_a0v_162(c);
 tenant:=jsonb_build_object('orgId','org-org','projectId','dev-project');
 from_at:=(c->>'effectiveFrom')::timestamptz;until_at:=(c->>'effectiveUntil')::timestamptz;
 SELECT * INTO STRICT h FROM public.aip_model_governance_policy_head
   WHERE org_id='org-org' AND project_id='dev-project' AND policy_kind='budget'
     AND policy_id=c->>'sourcePolicyId' FOR SHARE;
 SELECT * INTO STRICT s FROM public.aip_model_governance_policy_revision
   WHERE org_id=h.org_id AND project_id=h.project_id AND policy_kind='budget'
     AND policy_id=h.policy_id AND revision=h.current_revision;
 body:=s.payload-ARRAY['tenant','contentHash','createdBy','createdAt'];auth:=body->'developmentCostAuthorization';
 IF (h.current_revision=(c->>'expectedSourceRevision')::bigint
   AND h.version=(c->>'expectedHeadVersion')::bigint AND s.content_hash=c->>'expectedSourceHash'
   AND s.lifecycle='active' AND s.payload->>'lifecycle'='active'
   AND s.payload->>'policyId'=s.policy_id AND s.payload->>'revision'=s.revision::text
   AND s.payload->'tenant'=tenant AND s.payload->>'contentHash'=s.content_hash
   AND s.content_hash=public.aip_budget_cost_hash_a0v_126(body)
   AND (s.payload->>'effectiveFrom')::timestamptz=s.effective_from
   AND (s.payload->>'effectiveUntil')::timestamptz=s.effective_until
   AND s.payload->>'createdBy'=s.created_by AND (s.payload->>'createdAt')::timestamptz=s.created_at
   AND body->>'environment'='development' AND body->>'currency'='CNY'
   AND body->'hardStop'='true'::jsonb AND body->>'unknownUsageBehavior'='block'
   AND body->>'unknownPriceBehavior'='block' AND body->'allowZeroPrice'='false'::jsonb
   AND body->'zeroPriceApprovalRef'='null'::jsonb AND jsonb_typeof(auth)='object'
   AND auth->'tenant'=tenant AND auth->>'environment'='development'
   AND auth->>'approvalRef'=body->>'approvalRef' AND slot<>body->>'approvalRef'
   AND length(auth->>'providerModelId') BETWEEN 1 AND 240
   AND (auth->>'effectiveFrom')::timestamptz<=s.effective_from
   AND (auth->>'effectiveUntil')::timestamptz>=s.effective_until
   AND from_at>=s.effective_until AND until_at>from_at) IS NOT TRUE THEN
   RAISE EXCEPTION 'RENEWAL_CURRENT_POLICY_OR_WINDOW_REQUIRED' USING ERRCODE='23514'; END IF;
 SELECT current_revision INTO STRICT bh FROM public.aip_budget_head
   WHERE org_id='org-org' AND project_id='dev-project'
     AND budget_id=body->'budgetRevisionRef'->>'assetId' FOR SHARE;
 SELECT * INTO STRICT b FROM public.aip_budget_revision WHERE org_id='org-org'
   AND project_id='dev-project' AND budget_id=body->'budgetRevisionRef'->>'assetId' AND revision=bh;
 SELECT current_revision INTO STRICT vh FROM public.aip_provider_instance_head
   WHERE org_id='org-org' AND project_id='dev-project'
     AND provider_instance_id=auth->'provider'->>'assetId' FOR SHARE;
 SELECT * INTO STRICT v FROM public.aip_provider_instance_revision WHERE org_id='org-org'
   AND project_id='dev-project' AND provider_instance_id=auth->'provider'->>'assetId' AND revision=vh;
 now_at:=clock_timestamp();
 IF (body->'budgetRevisionRef'=jsonb_build_object('assetType','BudgetRevision',
   'assetId',b.budget_id,'revision',b.revision,'contentHash',b.content_hash)
   AND b.lifecycle='active' AND b.payload->>'lifecycle'='active'
   AND b.payload->'tenant'=tenant AND b.payload->>'budgetId'=b.budget_id
   AND b.payload->>'revision'=b.revision::text AND b.payload->>'contentHash'=b.content_hash
   AND b.content_hash=public.aip_budget_cost_hash_a0v_126(b.payload-ARRAY['tenant','contentHash','createdBy','createdAt'])
   AND b.payload->>'environment'='development' AND b.payload->>'currency'='CNY'
   AND b.payload->'hardStop'='true'::jsonb AND b.payload->>'unknownUsageBehavior'='block'
   AND b.environment=b.payload->>'environment' AND b.currency=b.payload->>'currency'
   AND b.payload->>'dailyLimitMinor'=b.daily_limit_minor::text
   AND b.payload->>'monthlyLimitMinor'=b.monthly_limit_minor::text
   AND b.payload->>'alertThresholdPct'=b.alert_threshold_pct::text
   AND b.hard_stop AND b.unknown_usage_behavior='block'
   AND b.payload->>'owner'=b.owner AND b.payload->>'overBudgetApprover'=b.over_budget_approver
   AND b.payload->>'createdBy'=b.created_by AND (b.payload->>'createdAt')::timestamptz=b.created_at
   AND (b.payload->>'effectiveFrom')::timestamptz=b.effective_from
   AND (b.payload->>'effectiveUntil')::timestamptz=b.effective_until
   AND b.effective_from<=now_at AND now_at<b.effective_until
   AND from_at>=b.effective_from AND until_at<=b.effective_until AND now_at<until_at
   AND auth->'provider'=jsonb_build_object('assetType','ProviderInstanceRevision',
      'assetId',v.provider_instance_id,'revision',v.revision,'contentHash',v.content_hash)
   AND v.lifecycle='active' AND v.payload->>'lifecycle'='active'
   AND v.payload->'tenant'=tenant AND v.payload->>'providerInstanceId'=v.provider_instance_id
   AND v.payload->>'revision'=v.revision::text AND v.payload->>'contentHash'=v.content_hash
   AND v.payload->>'createdBy'=v.created_by AND (v.payload->>'createdAt')::timestamptz=v.created_at
   AND v.content_hash=public.aip_budget_cost_hash_a0v_126(v.payload-ARRAY['tenant','revision','contentHash','createdBy','createdAt'])) IS NOT TRUE THEN
   RAISE EXCEPTION 'RENEWAL_CURRENT_BUDGET_PROVIDER_REQUIRED' USING ERRCODE='23514'; END IF;
 PERFORM subject FROM public.meta_membership WHERE org_id='org-org' AND project_id='dev-project'
   AND subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657' FOR SHARE;
 IF NOT EXISTS(SELECT 1 FROM public.meta_membership WHERE org_id='org-org' AND project_id='dev-project'
   AND subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657' AND lower(role) IN('owner','admin')) THEN
   RAISE EXCEPTION 'RENEWAL_CURRENT_CHECKER_REQUIRED' USING ERRCODE='42501'; END IF;
 t:=body||jsonb_build_object('revision',s.revision+1,'effectiveFrom',c->'effectiveFrom',
   'effectiveUntil',c->'effectiveUntil','approvalRef',slot,'lifecycle','active',
   'developmentCostAuthorization',auth||jsonb_build_object('effectiveFrom',c->'effectiveFrom',
     'effectiveUntil',c->'effectiveUntil','approvalRef',slot));
 contract:=jsonb_build_object('schemaVersion',1,'tenant',tenant,'sourcePolicy',s.payload,
   'targetPolicy',t||jsonb_build_object('lifecycle','draft'),'expectedHeadVersion',h.version,
   'makerSubject','postgres-service:aos_budget_renewal_maker_call',
   'checkerSubject','6f31cfdc-a26c-4f1f-ad6b-95a8559cc657');
 RETURN jsonb_build_object('schemaVersion',1,'tenant',tenant,
   'makerSubject',contract->'makerSubject','checkerSubject',contract->'checkerSubject',
   'sourceRef',jsonb_build_object('assetType','BudgetPolicyRevision','assetId',s.policy_id,
     'revision',s.revision,'contentHash',s.content_hash),'sourceHeadVersion',h.version,
   'budgetRef',body->'budgetRevisionRef','providerRef',auth->'provider',
   'sourcePolicy',s.payload,'sourceBudget',b.payload,'sourceProvider',v.payload,
   'targetDraft',t||jsonb_build_object('lifecycle','draft'),'targetActive',t,
   'approvalSlot',slot,'contract',contract,'contractHash',public.aip_budget_cost_hash_a0v_126(
     jsonb_build_object('domain','aos.budget-policy-renewal-proposal/v1','proposal',contract)));
END $$;

CREATE FUNCTION public.aip_renewal_propose_a0v_162(c jsonb)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE digest text;ident text;pid text;slot text;p jsonb;result jsonb;
        prior public.aip_budget_policy_renewal_receipt%ROWTYPE;
BEGIN
 PERFORM public.aip_renewal_profile_a0v_162('propose');
 PERFORM public.aip_renewal_proposal_command_a0v_162(c);
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
   'domain','aos.budget-policy-renewal.propose/v1','command',c-'idempotencyKey'));
 ident:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.renewal-proposal-id/v1',
   'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
   'maker',session_user,'key',c->>'idempotencyKey'));
 pid:='renewal-proposal-'||ident;slot:='renewal-approval-'||ident;
 PERFORM pg_advisory_xact_lock(hashtextextended('budget-policy-renewal:org-org:dev-project:'||pid,0));
 SELECT * INTO prior FROM public.aip_budget_policy_renewal_receipt WHERE org_id='org-org'
   AND project_id='dev-project' AND operation='propose' AND idempotency_key=c->>'idempotencyKey';
 IF FOUND THEN
   IF prior.request_hash IS DISTINCT FROM digest
      OR prior.receipt_id IS DISTINCT FROM 'renewal-propose-'||ident
      OR prior.proposal_id IS DISTINCT FROM pid
      OR prior.payload->>'proposalId' IS DISTINCT FROM pid
      OR prior.payload->>'operation' IS DISTINCT FROM 'propose'
      OR prior.payload->>'requestHash' IS DISTINCT FROM digest
      OR prior.payload->'activationEligible' IS DISTINCT FROM 'false'::jsonb
      OR NOT EXISTS(SELECT 1 FROM public.aip_budget_policy_renewal_proposal pp
        WHERE pp.org_id='org-org' AND pp.project_id='dev-project' AND pp.proposal_id=pid
          AND pp.proposal_hash=public.aip_budget_cost_hash_a0v_126(pp.payload)
          AND prior.payload->'proposal'=pp.payload AND prior.payload->>'proposalHash'=pp.proposal_hash) THEN
     RAISE EXCEPTION 'RENEWAL_IDEMPOTENCY_CONFLICT' USING ERRCODE='23514'; END IF;
   RETURN prior.payload;
 END IF;
 p:=public.aip_renewal_source_a0v_162(c,slot);
 p:=p||jsonb_build_object('request',c,'requestHash',digest);
 INSERT INTO public.aip_budget_policy_renewal_proposal(org_id,project_id,proposal_id,proposal_hash,payload)
   VALUES('org-org','dev-project',pid,public.aip_budget_cost_hash_a0v_126(p),p);
 result:=jsonb_build_object('status','prepared','operation','propose','requestHash',digest,
   'proposalId',pid,'proposalHash',public.aip_budget_cost_hash_a0v_126(p),
   'targetActiveHash',public.aip_budget_cost_hash_a0v_126(p->'targetActive'),
   'targetDraft',p->'targetDraft','proposal',p,'activationEligible',false);
 INSERT INTO public.aip_budget_policy_renewal_receipt(org_id,project_id,operation,idempotency_key,
   receipt_id,proposal_id,request_hash,payload)
   VALUES('org-org','dev-project','propose',c->>'idempotencyKey','renewal-propose-'||ident,pid,digest,result);
 IF (p->'targetActive'->>'effectiveUntil')::timestamptz<=clock_timestamp() THEN
   RAISE EXCEPTION 'RENEWAL_PROPOSAL_EXPIRED_BEFORE_COMMIT' USING ERRCODE='23514'; END IF;
 RETURN result;
END $$;

CREATE FUNCTION public.aip_renewal_reconcile_a0v_162(c jsonb,operation text,actor text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE digest text;r public.aip_budget_policy_renewal_receipt%ROWTYPE;
        p public.aip_budget_policy_renewal_proposal%ROWTYPE;
        ident text;
        d public.aip_budget_policy_renewal_decision%ROWTYPE;
BEGIN
 IF operation='consume' THEN
   IF actor IS NOT NULL THEN RAISE EXCEPTION 'RENEWAL_CONSUMER_ACTOR_DERIVED' USING ERRCODE='42501'; END IF;
   PERFORM public.aip_renewal_profile_a0v_162('reconcile_consume');
   RETURN public.aip_renewal_consume_history_a0v_162(c);
 END IF;
 IF operation IN('decide','revoke') THEN
   PERFORM public.aip_renewal_profile_a0v_162('reconcile_'||operation);
   PERFORM public.aip_renewal_issuer_command_a0v_162(c,operation);
   IF actor IS DISTINCT FROM '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657' THEN
     RAISE EXCEPTION 'RENEWAL_PROTECTED_CHECKER_REQUIRED' USING ERRCODE='42501'; END IF;
   digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain',
     'aos.budget-policy-renewal.'||operation||'/v1','command',c-'idempotencyKey'));
   ident:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.renewal-issuer-receipt-id/v1',
     'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
     'operation',operation,'actor',actor,'key',c->>'idempotencyKey'));
   SELECT * INTO r FROM public.aip_budget_policy_renewal_receipt rr WHERE rr.org_id='org-org'
     AND rr.project_id='dev-project' AND rr.operation=aip_renewal_reconcile_a0v_162.operation
     AND rr.idempotency_key=c->>'idempotencyKey';
   IF NOT FOUND THEN RETURN jsonb_build_object('status','unresolved','operation',operation,
     'requestHash',digest,'activationEligible',false); END IF;
   SELECT * INTO STRICT p FROM public.aip_budget_policy_renewal_proposal WHERE org_id='org-org'
     AND project_id='dev-project' AND proposal_id=r.proposal_id;
   SELECT * INTO STRICT d FROM public.aip_budget_policy_renewal_decision WHERE org_id='org-org'
     AND project_id='dev-project' AND decision_id=r.decision_id AND proposal_id=p.proposal_id;
   IF (r.request_hash=digest AND r.receipt_id='renewal-'||operation||'-'||ident
     AND p.proposal_id=c->>'proposalId' AND p.proposal_hash=c->>'proposalHash'
     AND p.proposal_hash=public.aip_budget_cost_hash_a0v_126(p.payload)
     AND p.payload->>'checkerSubject'=actor
     AND d.decision_hash=public.aip_budget_cost_hash_a0v_126(d.payload)
     AND d.payload->'command'=c AND d.payload->>'actorSubject'=actor
     AND d.payload->>'proposalHash'=p.proposal_hash
     AND d.payload->>'issuerReceiptId'=r.receipt_id
     AND d.payload->>'targetActiveHash'=public.aip_budget_cost_hash_a0v_126(p.payload->'targetActive')
     AND r.payload->'decisionPayload'=d.payload AND r.payload->>'decisionHash'=d.decision_hash
     AND r.payload->'activationEligible'='false'::jsonb
     AND ((operation='decide' AND d.decision=c->>'decision')
       OR (operation='revoke' AND d.decision='revoked'
          AND d.payload->>'originalDecisionId'=c->>'decisionId'
          AND d.payload->>'originalDecisionHash'=c->>'decisionHash'))) IS NOT TRUE THEN
     RETURN jsonb_build_object('status','conflict','operation',operation,'requestHash',digest,
       'activationEligible',false); END IF;
   RETURN r.payload||jsonb_build_object('status','observed');
 END IF;
 IF operation IS DISTINCT FROM 'propose' OR actor IS NOT NULL THEN
   RAISE EXCEPTION 'RENEWAL_OPERATION_NOT_IMPLEMENTED' USING ERRCODE='42501'; END IF;
 PERFORM public.aip_renewal_profile_a0v_162('reconcile_propose');
 PERFORM public.aip_renewal_proposal_command_a0v_162(c);
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
   'domain','aos.budget-policy-renewal.propose/v1','command',c-'idempotencyKey'));
 ident:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.renewal-proposal-id/v1',
   'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
   'maker',session_user,'key',c->>'idempotencyKey'));
 SELECT * INTO r FROM public.aip_budget_policy_renewal_receipt rr WHERE rr.org_id='org-org'
   AND rr.project_id='dev-project' AND rr.operation='propose' AND rr.idempotency_key=c->>'idempotencyKey';
 IF NOT FOUND THEN RETURN jsonb_build_object('status','unresolved','operation','propose',
   'requestHash',digest,'activationEligible',false); END IF;
 SELECT * INTO STRICT p FROM public.aip_budget_policy_renewal_proposal WHERE org_id='org-org'
   AND project_id='dev-project' AND proposal_id=r.proposal_id;
 IF (r.request_hash=digest AND r.receipt_id='renewal-propose-'||ident
   AND p.proposal_id='renewal-proposal-'||ident
   AND p.payload->'request'=c AND p.payload->>'requestHash'=digest
   AND p.payload->>'makerSubject'='postgres-service:aos_budget_renewal_maker_call'
   AND p.proposal_hash=public.aip_budget_cost_hash_a0v_126(p.payload)
   AND r.payload->'proposal'=p.payload AND r.payload->>'proposalId'=p.proposal_id
   AND r.payload->>'proposalHash'=p.proposal_hash
   AND r.payload->'targetDraft'=p.payload->'targetDraft'
   AND r.payload->>'targetActiveHash'=public.aip_budget_cost_hash_a0v_126(p.payload->'targetActive')
   AND r.payload->>'status'='prepared' AND r.payload->'activationEligible'='false'::jsonb) IS NOT TRUE THEN
   RETURN jsonb_build_object('status','conflict','operation','propose','requestHash',digest,
     'activationEligible',false);
 END IF;
 RETURN r.payload||jsonb_build_object('status','observed');
END $$;

CREATE FUNCTION public.aip_renewal_checker_member_a0v_162()
RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 PERFORM public.aip_renewal_profile_a0v_162('issuer_observe');
 RETURN EXISTS(SELECT 1 FROM public.meta_membership
    WHERE org_id='org-org' AND project_id='dev-project'
      AND subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657' AND lower(role) IN('owner','admin'));
END $$;

CREATE FUNCTION public.aip_renewal_issuer_command_a0v_162(c jsonb,op_name text)
RETURNS void LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF (jsonb_typeof(c)='object' AND c->>'schemaVersion'='1'
   AND jsonb_typeof(c->'schemaVersion')='number'
   AND c->>'orgId'='org-org' AND c->>'projectId'='dev-project'
   AND jsonb_typeof(c->'idempotencyKey')='string'
   AND c->>'idempotencyKey' ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$'
   AND jsonb_typeof(c->'proposalId')='string'
   AND c->>'proposalId' ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$'
   AND jsonb_typeof(c->'proposalHash')='string' AND c->>'proposalHash' ~ '^[0-9a-f]{64}$') IS NOT TRUE THEN
   RAISE EXCEPTION 'RENEWAL_EXACT_ISSUER_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 IF op_name='decide' THEN
   IF (c-ARRAY['schemaVersion','orgId','projectId','idempotencyKey','proposalId','proposalHash',
      'targetActiveHash','decision']='{}'::jsonb AND jsonb_typeof(c->'targetActiveHash')='string'
      AND c->>'targetActiveHash' ~ '^[0-9a-f]{64}$' AND c->>'decision' IN('approved','rejected')) IS NOT TRUE THEN
     RAISE EXCEPTION 'RENEWAL_EXACT_ISSUER_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 ELSIF op_name='revoke' THEN
   IF (c-ARRAY['schemaVersion','orgId','projectId','idempotencyKey','proposalId','proposalHash',
      'decisionId','decisionHash','reasonCode']='{}'::jsonb AND jsonb_typeof(c->'decisionId')='string'
      AND c->>'decisionId' ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$'
      AND jsonb_typeof(c->'decisionHash')='string' AND c->>'decisionHash' ~ '^[0-9a-f]{64}$'
      AND c->>'reasonCode' IN('approval_withdrawn','scope_changed','dependency_changed')) IS NOT TRUE THEN
     RAISE EXCEPTION 'RENEWAL_EXACT_ISSUER_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
 ELSE
   RAISE EXCEPTION 'RENEWAL_EXACT_ISSUER_OPERATION_REQUIRED' USING ERRCODE='22023';
 END IF;
END $$;

CREATE FUNCTION public.aip_renewal_issuer_fact_a0v_162(c jsonb,actor text,check_current boolean)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE p public.aip_budget_policy_renewal_proposal%ROWTYPE;current_fact jsonb;
BEGIN
 SELECT * INTO STRICT p FROM public.aip_budget_policy_renewal_proposal
   WHERE org_id='org-org' AND project_id='dev-project' AND proposal_id=c->>'proposalId' FOR SHARE;
 PERFORM decision_id FROM public.aip_budget_policy_renewal_decision
   WHERE org_id='org-org' AND project_id='dev-project' AND proposal_id=p.proposal_id
   ORDER BY decision_id FOR SHARE;
 IF (actor='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
   AND p.payload->>'checkerSubject'=actor
   AND p.payload->>'makerSubject'='postgres-service:aos_budget_renewal_maker_call'
   AND p.proposal_hash=c->>'proposalHash' AND p.proposal_hash=public.aip_budget_cost_hash_a0v_126(p.payload)
   AND p.payload->'targetActive'=p.payload->'targetDraft'||jsonb_build_object('lifecycle','active')
   AND p.payload->'targetActive'->>'approvalRef'=p.payload->>'approvalSlot') IS NOT TRUE THEN
   RAISE EXCEPTION 'RENEWAL_PROTECTED_CHECKER_AND_PROPOSAL_REQUIRED' USING ERRCODE='42501'; END IF;
 IF check_current THEN
   current_fact:=public.aip_renewal_source_a0v_162(p.payload->'request',p.payload->>'approvalSlot');
   IF current_fact IS DISTINCT FROM p.payload-ARRAY['request','requestHash'] THEN
     RAISE EXCEPTION 'RENEWAL_CURRENT_PROPOSAL_FACT_DRIFT' USING ERRCODE='23514'; END IF;
 ELSE
   -- Withdrawing an unsafe approval must remain possible after dependency drift.
   PERFORM subject FROM public.meta_membership WHERE org_id='org-org' AND project_id='dev-project'
     AND subject=actor FOR SHARE;
   IF NOT EXISTS(SELECT 1 FROM public.meta_membership WHERE org_id='org-org' AND project_id='dev-project'
     AND subject=actor AND lower(role) IN('owner','admin')) THEN
     RAISE EXCEPTION 'RENEWAL_CURRENT_CHECKER_REQUIRED' USING ERRCODE='42501'; END IF;
 END IF;
 RETURN p.payload;
END $$;

CREATE FUNCTION public.aip_renewal_issuer_write_a0v_162(c jsonb,actor text,op_name text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE p jsonb;d jsonb;digest text;ident text;did text;outcome text;result jsonb;
        prior public.aip_budget_policy_renewal_receipt%ROWTYPE;
        original public.aip_budget_policy_renewal_decision%ROWTYPE;
        prior_decision public.aip_budget_policy_renewal_decision%ROWTYPE;
BEGIN
 PERFORM public.aip_renewal_profile_a0v_162(op_name);
 PERFORM public.aip_renewal_issuer_command_a0v_162(c,op_name);
 IF actor IS DISTINCT FROM '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657' THEN
   RAISE EXCEPTION 'RENEWAL_PROTECTED_CHECKER_REQUIRED' USING ERRCODE='42501'; END IF;
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
   'domain','aos.budget-policy-renewal.'||op_name||'/v1','command',c-'idempotencyKey'));
 ident:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.renewal-issuer-receipt-id/v1',
   'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
   'operation',op_name,'actor',actor,'key',c->>'idempotencyKey'));
 PERFORM pg_advisory_xact_lock(hashtextextended('budget-policy-renewal:org-org:dev-project:'||(c->>'proposalId'),0));
 SELECT * INTO prior FROM public.aip_budget_policy_renewal_receipt rr WHERE rr.org_id='org-org'
   AND rr.project_id='dev-project' AND rr.operation=op_name AND rr.idempotency_key=c->>'idempotencyKey';
 IF FOUND THEN
   SELECT * INTO STRICT prior_decision FROM public.aip_budget_policy_renewal_decision
     WHERE org_id='org-org' AND project_id='dev-project' AND decision_id=prior.decision_id;
   IF (prior.request_hash=digest AND prior.receipt_id='renewal-'||op_name||'-'||ident
     AND prior.proposal_id=c->>'proposalId' AND prior.payload->>'actorSubject'=actor
     AND prior_decision.decision_hash=public.aip_budget_cost_hash_a0v_126(prior_decision.payload)
     AND prior.payload->'decisionPayload'=prior_decision.payload
     AND prior.payload->>'decisionHash'=prior_decision.decision_hash
     AND prior_decision.payload->'command'=c AND prior_decision.payload->>'actorSubject'=actor) IS NOT TRUE THEN
     RAISE EXCEPTION 'RENEWAL_IDEMPOTENCY_CONFLICT' USING ERRCODE='23514'; END IF;
   RETURN prior.payload;
 END IF;
 p:=public.aip_renewal_issuer_fact_a0v_162(c,actor,op_name='decide');
 IF op_name='decide' THEN
   IF c->>'targetActiveHash' IS DISTINCT FROM public.aip_budget_cost_hash_a0v_126(p->'targetActive') THEN
     RAISE EXCEPTION 'RENEWAL_EXACT_TARGET_REQUIRED' USING ERRCODE='23514'; END IF;
   IF EXISTS(SELECT 1 FROM public.aip_budget_policy_renewal_decision WHERE org_id='org-org'
     AND project_id='dev-project' AND proposal_id=c->>'proposalId') THEN
     RAISE EXCEPTION 'RENEWAL_ALREADY_DECIDED' USING ERRCODE='23514'; END IF;
   did:=p->>'approvalSlot';outcome:=c->>'decision';
 ELSE
   SELECT * INTO STRICT original FROM public.aip_budget_policy_renewal_decision
     WHERE org_id='org-org' AND project_id='dev-project' AND proposal_id=c->>'proposalId'
       AND decision_id=c->>'decisionId' FOR SHARE;
   IF (original.decision='approved' AND original.decision_id=p->>'approvalSlot'
     AND original.decision_hash=c->>'decisionHash'
     AND original.decision_hash=public.aip_budget_cost_hash_a0v_126(original.payload)
     AND original.payload->>'actorSubject'=actor
     AND original.payload->>'proposalHash'=c->>'proposalHash'
     AND original.payload->>'targetActiveHash'=public.aip_budget_cost_hash_a0v_126(p->'targetActive')
     AND EXISTS(SELECT 1 FROM public.aip_budget_policy_renewal_receipt rr
       WHERE rr.org_id='org-org' AND rr.project_id='dev-project' AND rr.operation='decide'
         AND rr.proposal_id=c->>'proposalId' AND rr.decision_id=original.decision_id
         AND rr.receipt_id=original.payload->>'issuerReceiptId'
         AND rr.payload->>'actorSubject'=actor
         AND rr.payload->>'decisionHash'=original.decision_hash
         AND rr.payload->'decisionPayload'=original.payload)) IS NOT TRUE THEN
     RAISE EXCEPTION 'RENEWAL_ORIGINAL_APPROVED_DECISION_REQUIRED' USING ERRCODE='42501'; END IF;
   IF EXISTS(SELECT 1 FROM public.aip_budget_policy_renewal_decision WHERE org_id='org-org'
     AND project_id='dev-project' AND proposal_id=c->>'proposalId' AND decision='revoked') THEN
     RAISE EXCEPTION 'RENEWAL_ALREADY_REVOKED' USING ERRCODE='23514'; END IF;
   did:='renewal-revocation-'||ident;outcome:='revoked';
 END IF;
 d:=jsonb_build_object('proposalId',c->'proposalId','proposalHash',c->'proposalHash',
   'targetActiveHash',public.aip_budget_cost_hash_a0v_126(p->'targetActive'),'actorSubject',actor,
   'decision',outcome,'command',c,'issuerReceiptId','renewal-'||op_name||'-'||ident,
   'expiresAt',p->'targetActive'->'effectiveUntil');
 IF op_name='revoke' THEN
   d:=d||jsonb_build_object('originalDecisionId',c->'decisionId','originalDecisionHash',c->'decisionHash',
                           'reasonCode',c->'reasonCode');
 END IF;
 INSERT INTO public.aip_budget_policy_renewal_decision(org_id,project_id,proposal_id,
   decision_id,decision_hash,decision,payload) VALUES('org-org','dev-project',c->>'proposalId',
   did,public.aip_budget_cost_hash_a0v_126(d),outcome,d);
 result:=jsonb_build_object('status',CASE WHEN op_name='decide' THEN 'decided' ELSE 'revoked' END,
   'operation',op_name,'requestHash',digest,'proposalId',c->'proposalId','proposalHash',c->'proposalHash',
   'decisionId',did,'decisionHash',public.aip_budget_cost_hash_a0v_126(d),'decisionPayload',d,
   'targetActiveHash',d->'targetActiveHash','actorSubject',actor,'activationEligible',false);
 INSERT INTO public.aip_budget_policy_renewal_receipt(org_id,project_id,operation,idempotency_key,
   receipt_id,proposal_id,decision_id,request_hash,payload) VALUES('org-org','dev-project',op_name,
   c->>'idempotencyKey','renewal-'||op_name||'-'||ident,c->>'proposalId',did,digest,result);
 IF op_name='decide' AND (d->>'expiresAt')::timestamptz<=clock_timestamp() THEN
   RAISE EXCEPTION 'RENEWAL_DECISION_EXPIRED_BEFORE_COMMIT' USING ERRCODE='23514'; END IF;
 RETURN result;
END $$;

CREATE FUNCTION public.aip_renewal_decide_a0v_162(c jsonb,actor text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN RETURN public.aip_renewal_issuer_write_a0v_162(c,actor,'decide'); END $$;
CREATE FUNCTION public.aip_renewal_revoke_a0v_162(c jsonb,actor text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN RETURN public.aip_renewal_issuer_write_a0v_162(c,actor,'revoke'); END $$;

CREATE FUNCTION public.aip_renewal_consume_command_a0v_162(c jsonb)
RETURNS void LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF (jsonb_typeof(c)='object' AND c-ARRAY['schemaVersion','orgId','projectId','idempotencyKey',
     'proposalId','proposalHash','decisionId','decisionHash']='{}'::jsonb
   AND c->>'schemaVersion'='1' AND jsonb_typeof(c->'schemaVersion')='number'
   AND c->>'orgId'='org-org' AND c->>'projectId'='dev-project'
   AND jsonb_typeof(c->'idempotencyKey')='string'
   AND c->>'idempotencyKey' ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$'
   AND jsonb_typeof(c->'proposalId')='string' AND c->>'proposalId' ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$'
   AND jsonb_typeof(c->'decisionId')='string' AND c->>'decisionId' ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$'
   AND jsonb_typeof(c->'proposalHash')='string' AND c->>'proposalHash' ~ '^[0-9a-f]{64}$'
   AND jsonb_typeof(c->'decisionHash')='string' AND c->>'decisionHash' ~ '^[0-9a-f]{64}$') IS NOT TRUE THEN
   RAISE EXCEPTION 'RENEWAL_EXACT_CONSUMER_COMMAND_REQUIRED' USING ERRCODE='22023'; END IF;
END $$;

CREATE FUNCTION public.aip_renewal_consume_fact_a0v_162(c jsonb,check_current boolean)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE p public.aip_budget_policy_renewal_proposal%ROWTYPE;
 d public.aip_budget_policy_renewal_decision%ROWTYPE;
 r public.aip_budget_policy_renewal_receipt%ROWTYPE;current_fact jsonb;
BEGIN
 PERFORM public.aip_renewal_consume_command_a0v_162(c);
 IF check_current THEN
   SELECT * INTO STRICT p FROM public.aip_budget_policy_renewal_proposal WHERE org_id='org-org'
     AND project_id='dev-project' AND proposal_id=c->>'proposalId' FOR SHARE;
   PERFORM decision_id FROM public.aip_budget_policy_renewal_decision WHERE org_id='org-org'
     AND project_id='dev-project' AND proposal_id=p.proposal_id ORDER BY decision_id FOR SHARE;
 ELSE
   SELECT * INTO STRICT p FROM public.aip_budget_policy_renewal_proposal WHERE org_id='org-org'
     AND project_id='dev-project' AND proposal_id=c->>'proposalId';
 END IF;
 SELECT * INTO STRICT d FROM public.aip_budget_policy_renewal_decision WHERE org_id='org-org'
   AND project_id='dev-project' AND proposal_id=p.proposal_id AND decision_id=c->>'decisionId';
 SELECT * INTO STRICT r FROM public.aip_budget_policy_renewal_receipt WHERE org_id='org-org'
   AND project_id='dev-project' AND operation='decide' AND proposal_id=p.proposal_id AND decision_id=d.decision_id;
 IF (p.proposal_hash=c->>'proposalHash' AND p.proposal_hash=public.aip_budget_cost_hash_a0v_126(p.payload)
   AND p.payload->>'makerSubject'='postgres-service:aos_budget_renewal_maker_call'
   AND p.payload->>'checkerSubject'='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
   AND d.decision='approved' AND d.decision_id=p.payload->>'approvalSlot'
   AND d.decision_hash=c->>'decisionHash' AND d.decision_hash=public.aip_budget_cost_hash_a0v_126(d.payload)
   AND d.payload->>'decision'='approved' AND d.payload->>'proposalId'=p.proposal_id
   AND d.payload->>'proposalHash'=p.proposal_hash AND d.payload->>'actorSubject'=p.payload->>'checkerSubject'
   AND d.payload->>'targetActiveHash'=public.aip_budget_cost_hash_a0v_126(p.payload->'targetActive')
   AND r.receipt_id=d.payload->>'issuerReceiptId' AND r.payload->'decisionPayload'=d.payload
   AND r.payload->>'decisionHash'=d.decision_hash AND r.payload->>'actorSubject'=p.payload->>'checkerSubject'
   AND r.payload->>'targetActiveHash'=d.payload->>'targetActiveHash') IS NOT TRUE THEN
   RAISE EXCEPTION 'RENEWAL_EXACT_APPROVAL_AND_ISSUER_RECEIPT_REQUIRED' USING ERRCODE='42501'; END IF;
 IF check_current THEN
   IF EXISTS(SELECT 1 FROM public.aip_budget_policy_renewal_decision WHERE org_id='org-org'
     AND project_id='dev-project' AND proposal_id=p.proposal_id AND decision_id<>d.decision_id) THEN
     RAISE EXCEPTION 'RENEWAL_REVOKED_OR_AMBIGUOUS_DECISION' USING ERRCODE='42501'; END IF;
   PERFORM policy_id FROM public.aip_model_governance_policy_head WHERE org_id='org-org'
     AND project_id='dev-project' AND policy_kind='budget' AND policy_id=p.payload->'sourceRef'->>'assetId' FOR UPDATE;
   current_fact:=public.aip_renewal_source_a0v_162(p.payload->'request',p.payload->>'approvalSlot');
   IF current_fact IS DISTINCT FROM p.payload-ARRAY['request','requestHash'] THEN
     RAISE EXCEPTION 'RENEWAL_CURRENT_PROPOSAL_FACT_DRIFT' USING ERRCODE='23514'; END IF;
   IF ((p.payload->'targetActive'->>'effectiveFrom')::timestamptz<=clock_timestamp()
     AND clock_timestamp()<(p.payload->'targetActive'->>'effectiveUntil')::timestamptz
     AND clock_timestamp()<(d.payload->>'expiresAt')::timestamptz) IS NOT TRUE THEN
     RAISE EXCEPTION 'RENEWAL_CURRENT_APPROVAL_WINDOW_REQUIRED' USING ERRCODE='42501'; END IF;
 END IF;
 RETURN jsonb_build_object('proposal',p.payload,'decision',d.payload,
   'decisionId',d.decision_id,'decisionHash',d.decision_hash);
END $$;

CREATE FUNCTION public.aip_renewal_consume_history_a0v_162(c jsonb)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE digest text;ident text;r public.aip_budget_policy_renewal_receipt%ROWTYPE;
 v public.aip_model_governance_policy_revision%ROWTYPE;f jsonb;policy jsonb;
BEGIN
 PERFORM public.aip_renewal_consume_command_a0v_162(c);
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
   'domain','aos.budget-policy-renewal.consume/v1','command',c-'idempotencyKey'));
 ident:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.renewal-consume-id/v1',
   'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
   'consumer',session_user,'key',c->>'idempotencyKey'));
 SELECT * INTO r FROM public.aip_budget_policy_renewal_receipt WHERE org_id='org-org'
   AND project_id='dev-project' AND operation='consume' AND idempotency_key=c->>'idempotencyKey';
 IF NOT FOUND THEN RETURN jsonb_build_object('status','unresolved','operation','consume',
   'requestHash',digest,'activationEligible',false); END IF;
 IF r.request_hash IS DISTINCT FROM digest OR r.proposal_id IS DISTINCT FROM c->>'proposalId'
   OR r.decision_id IS DISTINCT FROM c->>'decisionId' OR r.receipt_id IS DISTINCT FROM 'renewal-consume-'||ident
   OR r.payload->'command' IS DISTINCT FROM c THEN
   RETURN jsonb_build_object('status','conflict','operation','consume','requestHash',digest,'activationEligible',false); END IF;
 f:=public.aip_renewal_consume_fact_a0v_162(c,false);policy:=r.payload->'policy';
 SELECT * INTO STRICT v FROM public.aip_model_governance_policy_revision WHERE org_id='org-org'
   AND project_id='dev-project' AND policy_kind='budget' AND policy_id=r.payload->'ref'->>'assetId'
   AND revision=(r.payload->'ref'->>'revision')::bigint;
 IF (v.lifecycle='active' AND v.payload=policy
   AND v.content_hash=public.aip_budget_cost_hash_a0v_126(f->'proposal'->'targetActive')
   AND policy-ARRAY['tenant','contentHash','createdBy','createdAt']=f->'proposal'->'targetActive'
   AND policy->>'contentHash'=v.content_hash AND policy->'tenant'=f->'proposal'->'tenant'
   AND r.payload->>'actorSubject'='postgres-service:aos_budget_renewal_consumer_call'
   AND v.created_by=r.payload->>'actorSubject' AND policy->>'createdBy'=v.created_by
   AND (policy->>'createdAt')::timestamptz=v.created_at
   AND r.payload->'ref'=jsonb_build_object('assetType','BudgetPolicyRevision','assetId',v.policy_id,
     'revision',v.revision,'contentHash',v.content_hash)
   AND r.payload->>'decisionHash'=f->>'decisionHash'
   AND r.payload->'activationEligible'='false'::jsonb) IS NOT TRUE THEN
   RETURN jsonb_build_object('status','conflict','operation','consume','requestHash',digest,'activationEligible',false); END IF;
 RETURN r.payload;
END $$;

CREATE FUNCTION public.aip_renewal_assert_insert_a0v_162(
 p_org text,p_project text,p_policy text,p_revision bigint,p_hash text,p_body jsonb,
 p_actor text,p_created_at timestamptz,p_from timestamptz,p_until timestamptz)
RETURNS void LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE r public.aip_budget_policy_renewal_receipt%ROWTYPE;f jsonb;
BEGIN
 PERFORM public.aip_renewal_profile_a0v_162('consume');
 SELECT * INTO STRICT r FROM public.aip_budget_policy_renewal_receipt WHERE org_id=p_org
   AND project_id=p_project AND operation='consume' AND transaction_id=txid_current();
 f:=public.aip_renewal_consume_fact_a0v_162(r.payload->'command',true);
 IF (p_org='org-org' AND p_project='dev-project' AND r.payload->'policy'=p_body
   AND p_body-ARRAY['tenant','contentHash','createdBy','createdAt']=f->'proposal'->'targetActive'
   AND p_hash=public.aip_budget_cost_hash_a0v_126(f->'proposal'->'targetActive')
   AND p_body->>'contentHash'=p_hash AND p_body->>'policyId'=p_policy
   AND p_body->>'revision'=p_revision::text
   AND p_actor='postgres-service:aos_budget_renewal_consumer_call' AND p_body->>'createdBy'=p_actor
   AND (p_body->>'createdAt')::timestamptz=p_created_at
   AND (p_body->>'effectiveFrom')::timestamptz=p_from AND (p_body->>'effectiveUntil')::timestamptz=p_until
   AND r.payload->'ref'=jsonb_build_object('assetType','BudgetPolicyRevision','assetId',p_policy,
     'revision',p_revision,'contentHash',p_hash)) IS NOT TRUE THEN
   RAISE EXCEPTION 'RENEWAL_EXACT_INSERT_AND_SAME_TX_RECEIPT_REQUIRED' USING ERRCODE='23514'; END IF;
END $$;

CREATE OR REPLACE FUNCTION public.aip_cost_configuration_write_guard_a0v_128()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE protected boolean;
BEGIN
 IF TG_TABLE_NAME='aip_model_governance_policy_receipt' THEN
   protected:=NEW.operation='budget_cost.configure';
 ELSE
   protected:=NEW.lifecycle='active' AND NEW.payload ? 'developmentCostAuthorization'
     AND NEW.payload->'developmentCostAuthorization'<>'null'::jsonb;
 END IF;
 IF session_user='aos_budget_renewal_consumer_call' AND current_user='aos_budget_renewal_publish_owner' THEN
   IF TG_TABLE_SCHEMA<>'public' OR TG_TABLE_NAME<>'aip_model_governance_policy_revision' THEN
     RAISE EXCEPTION 'RENEWAL_BUDGET_POLICY_ONLY' USING ERRCODE='42501'; END IF;
   IF NEW.policy_kind IS DISTINCT FROM 'budget' OR NEW.lifecycle IS DISTINCT FROM 'active' OR protected IS NOT TRUE THEN
     RAISE EXCEPTION 'RENEWAL_BUDGET_POLICY_ONLY' USING ERRCODE='42501'; END IF;
   PERFORM public.aip_renewal_assert_insert_a0v_162(NEW.org_id,NEW.project_id,NEW.policy_id,
     NEW.revision,NEW.content_hash,NEW.payload,NEW.created_by,NEW.created_at,NEW.effective_from,NEW.effective_until);
 ELSIF protected AND (session_user<>'aos_budget_consumer_call' OR current_user<>'aos_budget_consumer_owner') THEN
   RAISE EXCEPTION 'COST_CONFIGURATION_CONSUMER_REQUIRED' USING ERRCODE='42501';
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION public.aip_renewal_complete_receipt_a0v_162()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE v public.aip_model_governance_policy_revision%ROWTYPE;
 h public.aip_model_governance_policy_head%ROWTYPE;f jsonb;
BEGIN
 IF NEW.operation<>'consume' THEN RETURN NULL; END IF;
 PERFORM public.aip_renewal_profile_a0v_162('consume');
 f:=public.aip_renewal_consume_fact_a0v_162(NEW.payload->'command',false);
 SELECT * INTO STRICT v FROM public.aip_model_governance_policy_revision WHERE org_id=NEW.org_id
   AND project_id=NEW.project_id AND policy_kind='budget' AND policy_id=NEW.payload->'ref'->>'assetId'
   AND revision=(NEW.payload->'ref'->>'revision')::bigint;
 SELECT * INTO STRICT h FROM public.aip_model_governance_policy_head WHERE org_id=NEW.org_id
   AND project_id=NEW.project_id AND policy_kind='budget' AND policy_id=v.policy_id;
 IF (NEW.transaction_id=txid_current() AND v.payload=NEW.payload->'policy'
   AND v.content_hash=NEW.payload->'ref'->>'contentHash' AND v.lifecycle='active'
   AND h.current_revision=v.revision AND h.version=(NEW.payload->>'headVersionAfter')::bigint
   AND v.effective_from<=clock_timestamp() AND clock_timestamp()<v.effective_until
   AND clock_timestamp()<(f->'decision'->>'expiresAt')::timestamptz
   AND NOT EXISTS(SELECT 1 FROM public.aip_budget_policy_renewal_decision WHERE org_id=NEW.org_id
     AND project_id=NEW.project_id AND proposal_id=NEW.proposal_id AND decision='revoked')
   AND EXISTS(SELECT 1 FROM public.meta_membership WHERE org_id=NEW.org_id AND project_id=NEW.project_id
     AND subject='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657' AND lower(role) IN('admin','owner'))) IS NOT TRUE THEN
   RAISE EXCEPTION 'RENEWAL_INCOMPLETE_OR_EXPIRED_PUBLICATION' USING ERRCODE='23514'; END IF;
 RETURN NULL;
END $$;

CREATE FUNCTION public.aip_renewal_consume_a0v_162(c jsonb)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE digest text;ident text;f jsonb;p jsonb;t jsonb;policy jsonb;result jsonb;prior jsonb;
 stamp timestamptz;ref jsonb;updated_count bigint;
BEGIN
 PERFORM public.aip_renewal_profile_a0v_162('consume');
 PERFORM public.aip_renewal_consume_command_a0v_162(c);
 PERFORM pg_advisory_xact_lock(hashtextextended('budget-policy-renewal:org-org:dev-project:'||(c->>'proposalId'),0));
 prior:=public.aip_renewal_consume_history_a0v_162(c);
 IF prior->>'status'='observed' THEN RETURN prior; END IF;
 IF prior->>'status' IS DISTINCT FROM 'unresolved' THEN
   RAISE EXCEPTION 'RENEWAL_CONSUME_RECEIPT_CONFLICT' USING ERRCODE='23514'; END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid='public.aip_model_governance_policy_revision'::regclass
   AND tgname='cost_configuration_write_guard' AND tgenabled='O'
   AND tgfoid='public.aip_cost_configuration_write_guard_a0v_128()'::regprocedure) THEN
   RAISE EXCEPTION 'RENEWAL_ORIGINAL_INSERT_GUARD_REQUIRED' USING ERRCODE='42501'; END IF;
 f:=public.aip_renewal_consume_fact_a0v_162(c,true);p:=f->'proposal';t:=p->'targetActive';
 digest:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object(
   'domain','aos.budget-policy-renewal.consume/v1','command',c-'idempotencyKey'));
 ident:=public.aip_budget_cost_hash_a0v_126(jsonb_build_object('domain','aos.renewal-consume-id/v1',
   'tenant',p->'tenant','consumer',session_user,'key',c->>'idempotencyKey'));
 stamp:=clock_timestamp();
 policy:=t||jsonb_build_object('tenant',p->'tenant','contentHash',public.aip_budget_cost_hash_a0v_126(t),
   'createdBy','postgres-service:aos_budget_renewal_consumer_call',
   'createdAt',to_char(stamp AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'));
 ref:=jsonb_build_object('assetType','BudgetPolicyRevision','assetId',t->'policyId',
   'revision',t->'revision','contentHash',policy->'contentHash');
 result:=jsonb_build_object('status','observed','operation','consume','requestHash',digest,
   'proposalId',c->'proposalId','proposalHash',c->'proposalHash','decisionId',c->'decisionId',
   'decisionHash',c->'decisionHash','command',c,'policy',policy,'ref',ref,
   'actorSubject','postgres-service:aos_budget_renewal_consumer_call',
   'headVersionBefore',p->'sourceHeadVersion','headVersionAfter',(p->>'sourceHeadVersion')::bigint+1,
   'activationEligible',false);
 INSERT INTO public.aip_budget_policy_renewal_receipt(org_id,project_id,operation,idempotency_key,
   receipt_id,proposal_id,decision_id,request_hash,payload) VALUES('org-org','dev-project','consume',
   c->>'idempotencyKey','renewal-consume-'||ident,c->>'proposalId',c->>'decisionId',digest,result);
 INSERT INTO public.aip_model_governance_policy_revision(org_id,project_id,policy_kind,policy_id,
   revision,content_hash,lifecycle,effective_from,effective_until,payload,created_by,created_at)
   VALUES('org-org','dev-project','budget',t->>'policyId',(t->>'revision')::bigint,policy->>'contentHash',
     'active',(t->>'effectiveFrom')::timestamptz,(t->>'effectiveUntil')::timestamptz,policy,
     policy->>'createdBy',stamp);
 UPDATE public.aip_model_governance_policy_head SET current_revision=(t->>'revision')::bigint,
   version=version+1,updated_at=stamp WHERE org_id='org-org' AND project_id='dev-project'
   AND policy_kind='budget' AND policy_id=t->>'policyId'
   AND current_revision=(p->'sourceRef'->>'revision')::bigint AND version=(p->>'sourceHeadVersion')::bigint;
 GET DIAGNOSTICS updated_count=ROW_COUNT;
 IF updated_count<>1 THEN RAISE EXCEPTION 'RENEWAL_HEAD_CAS_FAILED' USING ERRCODE='23514'; END IF;
 IF stamp>=(t->>'effectiveUntil')::timestamptz THEN
   RAISE EXCEPTION 'RENEWAL_PUBLICATION_EXPIRED' USING ERRCODE='23514'; END IF;
 RETURN result;
END $$;
