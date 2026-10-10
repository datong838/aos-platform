CREATE FUNCTION public.read_shared_parent_live_physical_facts(
          p_plan uuid,p_window_hash text,p_xid xid8,p_pid integer) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $live$
          DECLARE window_row aos_shared_parent_physical_private.initial_window_obligation%ROWTYPE;
            material aos_shared_parent_physical_private.initial_call_authority%ROWTYPE; obligation aos_shared_parent_physical_private.initial_target_obligation%ROWTYPE;
            packet jsonb; guard_doc jsonb; fact jsonb; body jsonb; guard_version bigint;
            used_requests bigint; used_tokens numeric; total_requests bigint; total_tokens numeric;
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
              RAISE EXCEPTION 'SHARED_ADMISSION_LIVE_PHYSICAL_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO window_row FROM aos_shared_parent_physical_private.initial_window_obligation WHERE plan_id=p_plan FOR SHARE;
            SELECT * INTO material FROM aos_shared_parent_physical_private.initial_call_authority WHERE plan_id=p_plan FOR SHARE;
            SELECT * INTO obligation FROM aos_shared_parent_physical_private.initial_target_obligation WHERE plan_id=p_plan FOR SHARE;
            IF window_row.plan_id IS NULL OR material.plan_id IS NULL OR obligation.plan_id IS NULL
              OR window_row.content_hash IS DISTINCT FROM p_window_hash
              OR window_row.material_hash IS DISTINCT FROM material.content_hash
              OR window_row.physical_account_id IS DISTINCT FROM obligation.physical_account_id
              OR window_row.caller_xid IS DISTINCT FROM p_xid OR window_row.caller_pid IS DISTINCT FROM p_pid
              OR material.caller_xid IS DISTINCT FROM p_xid OR material.caller_pid IS DISTINCT FROM p_pid
              OR obligation.caller_xid IS DISTINCT FROM p_xid OR obligation.caller_pid IS DISTINCT FROM p_pid
              OR material.body->>'sourcePacketHash' IS DISTINCT FROM 'sha256:'||encode(sha256(material.source_raw),'hex')
              OR material.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(material.body),'UTF8')),'hex')
              OR window_row.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(window_row.body),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_LIVE_PHYSICAL_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
            packet:=convert_from(material.source_raw,'UTF8')::jsonb;
            guard_doc:=public.prepare_capacity_occupation_account_guard(material.source_raw,packet->'sourceRef');
            -- Fresh original Source verification follows the actual account UPDATE wait.
            fact:=public.capacity_occupation_source_fact(material.source_raw,packet->'sourceRef');
            SELECT version INTO guard_version FROM aos_physical_capacity_occupation_private.account_guard
              WHERE physical_account_id=obligation.physical_account_id AND org_id='org-org' AND project_id='dev-project'
                FOR UPDATE;
            -- The original guard just UPDATEd and still holds this account lock.
            -- A savepoint writes a subtransaction xmin, while its xid is the top xid.
            IF NOT FOUND OR fact->>'physicalAccountId' IS DISTINCT FROM obligation.physical_account_id::text
              OR guard_doc->>'physicalAccountId' IS DISTINCT FROM obligation.physical_account_id::text
              OR guard_doc->>'xid' IS DISTINCT FROM p_xid::text
              OR (guard_doc->>'pid')::integer IS DISTINCT FROM p_pid
              OR (guard_doc->>'version')::bigint IS DISTINCT FROM guard_version THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_LIVE_PHYSICAL_GUARD_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT count(*),coalesce(sum(token_units),0) INTO total_requests,total_tokens FROM (
              SELECT token_units FROM aos_physical_capacity_occupation_private.prepared_parent_debit WHERE physical_account_id=obligation.physical_account_id
              UNION ALL SELECT token_upper_bound FROM aos_shared_parent_physical_private.initial_target_obligation WHERE physical_account_id=obligation.physical_account_id
            ) native_unresolved;
            used_requests:=total_requests-1;used_tokens:=total_tokens-obligation.token_upper_bound;
            IF used_requests<0 OR used_tokens<0 THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_LIVE_PHYSICAL_COUNTS_REQUIRED' USING ERRCODE='23514'; END IF;
            fact:=fact||jsonb_build_object('tokenUpperBound',obligation.token_upper_bound);
            IF used_requests>=(fact->>'maxConcurrency')::bigint
                OR used_tokens+(fact->>'tokenUpperBound')::bigint>(fact->'tokenLimit'->>'maxTokens')::numeric THEN
                RAISE EXCEPTION 'CAPACITY_PHYSICAL_CAPACITY_EXCEEDED' USING ERRCODE='23514'; END IF;
            body:=jsonb_build_object('schemaVersion','aos.shared-parent-live-physical-facts/v1',
              'planId',p_plan,'windowSnapshotHash',p_window_hash,'initialCallAuthorityHash',material.content_hash,
              'obligationHash',obligation.content_hash,'physicalAccountId',obligation.physical_account_id,
              'accountVersion',guard_version,'sourceRef',packet->'sourceRef','maxConcurrency',fact->'maxConcurrency',
              'sourceTokenLimit',fact->'tokenLimit','unresolvedRequests',total_requests,'unresolvedTokenUpperBound',total_tokens,
              'observedAt',clock_timestamp(),'callerXid',p_xid::text,'callerPid',p_pid,
              'windowExpiryReleasesRisk',false,'executionAllowed',false);
            RETURN jsonb_build_object('facts',body,'contentHash','sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex'),
              'executionAllowed',false);
          END $live$
