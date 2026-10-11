
          DECLARE obligation aos_shared_parent_physical_private.initial_target_obligation%ROWTYPE;
            target_row aos_shared_parent_physical_private.target_intent%ROWTYPE;judge_row aos_shared_parent_physical_private.judge_dependency%ROWTYPE;
            material aos_shared_parent_physical_private.initial_call_authority%ROWTYPE;window_row aos_shared_parent_physical_private.initial_window_obligation%ROWTYPE;
            risk_row aos_shared_parent_physical_private.complete_parent_risk%ROWTYPE;node record;count_nodes integer:=0;
            hashes jsonb:='{}'::jsonb;pending jsonb;facts jsonb;intents jsonb;live jsonb;member_set jsonb;
            receipt aos_shared_parent_physical_private.complete_receipt_v2%ROWTYPE;physical_match jsonb;
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project' OR p_xid IS DISTINCT FROM pg_current_xact_id()
              OR p_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_COMPLETE_END_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO receipt FROM aos_shared_parent_physical_private.complete_receipt_v2 WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR receipt.caller_xid IS DISTINCT FROM p_xid OR receipt.caller_pid IS DISTINCT FROM p_pid
              OR receipt.org_id IS DISTINCT FROM 'org-org' OR receipt.project_id IS DISTINCT FROM 'dev-project'
              OR receipt.content_hash IS DISTINCT FROM p_receipt_hash
              OR receipt.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(receipt.body),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_COMPLETE_END_RECEIPT_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT * INTO obligation FROM aos_shared_parent_physical_private.initial_target_obligation WHERE plan_id=receipt.plan_id FOR SHARE;
            SELECT * INTO target_row FROM aos_shared_parent_physical_private.target_intent WHERE plan_id=receipt.plan_id FOR SHARE;
            SELECT * INTO judge_row FROM aos_shared_parent_physical_private.judge_dependency WHERE plan_id=receipt.plan_id FOR SHARE;
            SELECT * INTO material FROM aos_shared_parent_physical_private.initial_call_authority WHERE plan_id=receipt.plan_id FOR SHARE;
            SELECT * INTO window_row FROM aos_shared_parent_physical_private.initial_window_obligation WHERE plan_id=receipt.plan_id FOR SHARE;
            SELECT * INTO risk_row FROM aos_shared_parent_physical_private.complete_parent_risk WHERE plan_id=receipt.plan_id FOR SHARE;
            FOR node IN SELECT 'initialTargetObligation' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id FROM aos_shared_parent_physical_private.initial_target_obligation WHERE plan_id=receipt.plan_id
              UNION ALL SELECT 'targetIntent' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id FROM aos_shared_parent_physical_private.target_intent WHERE plan_id=receipt.plan_id
              UNION ALL SELECT 'judgeDependency' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id FROM aos_shared_parent_physical_private.judge_dependency WHERE plan_id=receipt.plan_id
              UNION ALL SELECT 'initialCallAuthority' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id FROM aos_shared_parent_physical_private.initial_call_authority WHERE plan_id=receipt.plan_id
              UNION ALL SELECT 'initialWindowObligation' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id FROM aos_shared_parent_physical_private.initial_window_obligation WHERE plan_id=receipt.plan_id
              UNION ALL SELECT 'completeParentRisk' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id FROM aos_shared_parent_physical_private.complete_parent_risk WHERE plan_id=receipt.plan_id LOOP
              IF node.caller_xid IS DISTINCT FROM receipt.caller_xid OR node.caller_pid IS DISTINCT FROM receipt.caller_pid
                OR node.org_id IS DISTINCT FROM receipt.org_id OR node.project_id IS DISTINCT FROM receipt.project_id
                OR node.body->>'planId' IS DISTINCT FROM receipt.plan_id::text
                OR node.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                  public.canonical_asset_registry_jsonb(node.body),'UTF8')),'hex') THEN
                RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_NODE_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
              hashes:=hashes||jsonb_build_object(node.name,node.content_hash);count_nodes:=count_nodes+1;
            END LOOP;
            IF count_nodes<>6 OR material.content_hash IS DISTINCT FROM receipt.material_hash
              OR window_row.material_hash IS DISTINCT FROM material.content_hash
              OR window_row.physical_account_id IS DISTINCT FROM obligation.physical_account_id
              OR risk_row.physical_account_id IS DISTINCT FROM obligation.physical_account_id
              OR risk_row.pending_hash IS DISTINCT FROM obligation.pending_hash
              OR material.target_id IS DISTINCT FROM target_row.intent_id
              OR material.target_hash IS DISTINCT FROM target_row.content_hash
              OR material.judge_id IS DISTINCT FROM judge_row.intent_id
              OR material.judge_hash IS DISTINCT FROM judge_row.content_hash THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_COMPLETE_NODES_REQUIRED' USING ERRCODE='23514'; END IF;
            pending:=public.read_shared_parent_receipt_origin(receipt.plan_id,obligation.pending_hash,receipt.caller_xid,receipt.caller_pid);
            facts:=pending#>'{immutable,origin,immutable,originalRisk,originalFacts}';
            IF pending->>'sourcePacketHash' IS DISTINCT FROM material.body->>'sourcePacketHash'
              OR pending->>'sourcePacketHash' IS DISTINCT FROM 'sha256:'||encode(sha256(material.source_raw),'hex')
              OR risk_row.body->'originalRisk' IS DISTINCT FROM pending#>'{immutable,origin,immutable,originalRisk}'
              OR risk_row.body->>'originalRiskHash' IS DISTINCT FROM pending#>>'{immutable,origin,immutable,originalRiskHash}'
              OR risk_row.body->>'authorityMaterialHash' IS DISTINCT FROM pending->>'authorityMaterialHash'
              OR risk_row.target_hold::text IS DISTINCT FROM facts#>>'{target,reservationId}'
              OR risk_row.judge_hold::text IS DISTINCT FROM facts#>>'{judge,reservationId}'
              OR risk_row.target_request IS DISTINCT FROM facts#>>'{target,requestId}'
              OR risk_row.judge_request IS DISTINCT FROM facts#>>'{judge,requestId}'
              OR obligation.physical_account_id::text IS DISTINCT FROM facts#>>'{target,physicalAccountId}'
              OR obligation.physical_account_id::text IS DISTINCT FROM facts#>>'{judge,physicalAccountId}' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_ORIGINAL_RISK_REQUIRED' USING ERRCODE='23514'; END IF;
            intents:=public.verify_shared_parent_final_call_authority(receipt.plan_id,material.content_hash,receipt.caller_xid,receipt.caller_pid);
            IF intents->>'targetIntentHash' IS DISTINCT FROM target_row.content_hash
              OR intents->>'judgeDependencyHash' IS DISTINCT FROM judge_row.content_hash
              OR intents->>'initialCallAuthorityHash' IS DISTINCT FROM material.content_hash THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_CURRENT_INTENTS_REQUIRED' USING ERRCODE='23514'; END IF;
            hashes:=hashes||jsonb_build_object('pendingOrigin',pending->>'contentHash',
              'endAuthority',pending->>'authorityMaterialHash');
            IF hashes IS DISTINCT FROM receipt.body->'nodes'
              OR receipt.body->>'originalRiskHash' IS DISTINCT FROM risk_row.body->>'originalRiskHash'
              OR receipt.body->>'sourcePacketHash' IS DISTINCT FROM material.body->>'sourcePacketHash'
              OR receipt.physical_account_id IS DISTINCT FROM obligation.physical_account_id THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_COMPLETE_END_NODES_CHANGED' USING ERRCODE='23514'; END IF;
            physical_match:=public.verify_shared_parent_final_physical(p_plan,p_receipt_hash,p_xid,p_pid);
            IF physical_match->'physicalComparisonMatched' IS DISTINCT FROM 'true'::jsonb THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_COMPLETE_END_PHYSICAL_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'receiptHash',receipt.content_hash,
              'nodes',hashes,'originalRiskHash',receipt.body->>'originalRiskHash',
              'sourcePacketHash',receipt.body->>'sourcePacketHash','physicalComparison',physical_match,
              'factsReadAt',clock_timestamp(),'nativeEndRequired',true,
              'durableDeadlineEstablished',false,'executionAllowed',false);
          END 