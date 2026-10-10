CREATE FUNCTION public.prepare_shared_parent_initial_intents(
          p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,
          p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_manifest_hash text,
          p_certificates bytea,p_pending_hash text,p_obligation_hash text,p_suite_raw bytea,p_input_raw bytea,
          p_target_intent uuid,p_judge_intent uuid) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $intents$
          DECLARE obligation aos_shared_parent_physical_private.initial_target_obligation%ROWTYPE; prior_target aos_shared_parent_physical_private.target_intent%ROWTYPE;
            prior_judge aos_shared_parent_physical_private.judge_dependency%ROWTYPE; fact jsonb; value jsonb; pending jsonb; original jsonb; after_facts jsonb;
            target_body jsonb; target_hash text; judge_body jsonb; judge_hash text; native_case jsonb;
            p_request text:=p_tr; p_hash text:=p_th;
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_INTENT_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            IF p_target_intent IS NULL OR p_judge_intent IS NULL OR p_target_intent=p_judge_intent THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_DISTINCT_INTENT_IDS_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT * INTO obligation FROM aos_shared_parent_physical_private.initial_target_obligation WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR obligation.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR obligation.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR obligation.pending_hash IS DISTINCT FROM p_pending_hash
              OR obligation.content_hash IS DISTINCT FROM p_obligation_hash
              OR obligation.target_hold IS DISTINCT FROM p_target
              OR obligation.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(obligation.body),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_INTENT_NATIVE_OBLIGATION_REQUIRED' USING ERRCODE='23514'; END IF;
            fact:=public.capacity_occupation_eval_case_fact(p_raw,p_source,p_target,p_tr,p_th,p_suite_raw,obligation.case_id);
            IF p_input_raw IS NULL OR octet_length(p_input_raw)=0 OR octet_length(p_input_raw)>1048576
              OR encode(sha256(p_input_raw),'hex') IS DISTINCT FROM fact->>'inputHash' THEN
              RAISE EXCEPTION 'CAPACITY_CASE_INPUT_BYTES_REQUIRED' USING ERRCODE='23514'; END IF;
            value:=convert_from(p_input_raw,'UTF8')::jsonb;
            target_body:=jsonb_build_object(
              'schemaVersion','aos.shared-parent-target-intent/v1','intentId',p_target_intent,'planId',p_plan,
              'pendingOriginHash',p_pending_hash,'obligationHash',p_obligation_hash,
              'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
              'requestId',p_request,'requestHash',p_hash,'requestMaker',fact->>'requestMaker',
              'approvalChecker',fact->>'approvalChecker','approvalSnapshot',fact->'approvalSnapshot',
              'proposalId',fact->>'proposalId','proposalHash',fact->>'proposalHash',
              'originalIdempotencyKey',fact->>'requestIdempotencyKey','application',fact->'application',
              'parentHold',p_target,'caseId',obligation.case_id,'inputRef',fact->'inputRef',
              'inputHash',fact->>'inputHash','inputValue',value,'purpose','target','attempt',1,
              'callerLogin',session_user,'callerXid',pg_current_xact_id()::text,'callerPid',pg_backend_pid(),
              'state','pending_full_admission','executionAllowed',false);
            target_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(target_body),'UTF8')),'hex');
            INSERT INTO aos_shared_parent_physical_private.target_intent(intent_id,plan_id,org_id,project_id,request_id,case_id,attempt,body,content_hash,caller_xid,caller_pid)
              VALUES(p_target_intent,p_plan,'org-org','dev-project',p_tr,obligation.case_id,1,target_body,target_hash,
                pg_current_xact_id(),pg_backend_pid()) ON CONFLICT DO NOTHING;
            SELECT * INTO prior_target FROM aos_shared_parent_physical_private.target_intent WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR prior_target.intent_id IS DISTINCT FROM p_target_intent
              OR prior_target.body IS DISTINCT FROM target_body OR prior_target.content_hash IS DISTINCT FROM target_hash
              OR prior_target.caller_xid IS DISTINCT FROM pg_current_xact_id() OR prior_target.caller_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_TARGET_INTENT_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            pending:=public.read_shared_parent_pending_origin(
              p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates,p_pending_hash);
            original:=pending#>'{immutable,origin,immutable,originalRisk,originalFacts}';native_case:=original->'cases'->0;
            IF fact->'application' IS DISTINCT FROM original->'target'->'application'
              OR fact->>'inputHash' IS DISTINCT FROM native_case->'inputArtifact'->>'contentHash'
              OR obligation.case_id IS DISTINCT FROM native_case->>'caseId'
              OR original#>>'{judge,application,ruleFacts,rule,inputProtocol}' IS DISTINCT FROM 'aos.model-eval-judge-input/v1' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_INTENT_ORIGINAL_PAIR_REQUIRED' USING ERRCODE='23514'; END IF;
            judge_body:=jsonb_build_object('schemaVersion','aos.shared-parent-judge-dependency/v1',
              'intentId',p_judge_intent,'planId',p_plan,'pendingOriginHash',p_pending_hash,
              'tenant',target_body->'tenant','requestId',p_jr,'requestHash',p_jh,
              'parentHold',p_judge,'caseId',obligation.case_id,'application',original#>'{judge,application}',
              'targetIntentId',p_target_intent,'targetIntentHash',target_hash,
              'inputDependency',jsonb_build_object('protocol','aos.model-eval-judge-input/v1',
                'state','awaiting_target_result','targetIntentId',p_target_intent,
                'targetIntentHash',target_hash,'expectedArtifact',native_case->'expectedArtifact'),
              'purpose','judge','attempt',1,'callerLogin',session_user,'callerXid',pg_current_xact_id()::text,
              'callerPid',pg_backend_pid(),'state','awaiting_target_result','executionAllowed',false);
            judge_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(judge_body),'UTF8')),'hex');
            INSERT INTO aos_shared_parent_physical_private.judge_dependency(intent_id,plan_id,org_id,project_id,target_intent_id,target_intent_hash,
              request_id,case_id,attempt,body,content_hash,caller_xid,caller_pid)
              VALUES(p_judge_intent,p_plan,'org-org','dev-project',p_target_intent,target_hash,p_jr,obligation.case_id,1,
                judge_body,judge_hash,pg_current_xact_id(),pg_backend_pid()) ON CONFLICT DO NOTHING;
            SELECT * INTO prior_judge FROM aos_shared_parent_physical_private.judge_dependency WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR prior_judge.intent_id IS DISTINCT FROM p_judge_intent
              OR prior_judge.body IS DISTINCT FROM judge_body OR prior_judge.content_hash IS DISTINCT FROM judge_hash
              OR prior_judge.caller_xid IS DISTINCT FROM pg_current_xact_id() OR prior_judge.caller_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_JUDGE_DEPENDENCY_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            after_facts:=public.read_shared_parent_admission_original_facts(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh);
            IF after_facts IS DISTINCT FROM original OR EXISTS(SELECT 1 FROM jsonb_array_elements(pending#>'{immutable,certificates}') envelope
                WHERE clock_timestamp()<(envelope#>>'{certificate,validFrom}')::timestamptz
                   OR clock_timestamp()>=(envelope#>>'{certificate,validUntil}')::timestamptz) THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_INTENT_CURRENT_AFTER_WAITS_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'targetIntent',target_body,'targetIntentHash',target_hash,
              'judgeDependency',judge_body,'judgeDependencyHash',judge_hash,'executionAllowed',false);
          END $intents$
