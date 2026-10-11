
          DECLARE receipt aos_shared_parent_physical_private.complete_receipt_v2%ROWTYPE;sealed jsonb;current_members jsonb;
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
              RAISE EXCEPTION 'SHARED_ADMISSION_FINAL_PHYSICAL_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO receipt FROM aos_shared_parent_physical_private.complete_receipt_v2 WHERE plan_id=p_plan FOR SHARE;
            sealed:=receipt.body->'physicalFacts';
            IF receipt.plan_id IS NULL OR receipt.org_id IS DISTINCT FROM 'org-org'
              OR receipt.project_id IS DISTINCT FROM 'dev-project'
              OR receipt.caller_xid IS DISTINCT FROM p_xid OR receipt.caller_pid IS DISTINCT FROM p_pid
              OR receipt.content_hash IS DISTINCT FROM p_receipt_hash
              OR receipt.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(receipt.body),'UTF8')),'hex')
              OR receipt.body->>'schemaVersion' IS DISTINCT FROM 'aos.shared-parent-complete-receipt-preparation/v2'
              OR receipt.body->>'planId' IS DISTINCT FROM p_plan::text
              OR receipt.body#>>'{tenant,orgId}' IS DISTINCT FROM 'org-org'
              OR receipt.body#>>'{tenant,projectId}' IS DISTINCT FROM 'dev-project'
              OR receipt.body->>'callerLogin' IS DISTINCT FROM session_user
              OR receipt.body->>'callerXid' IS DISTINCT FROM p_xid::text
              OR receipt.body->>'callerPid' IS DISTINCT FROM p_pid::text
              OR receipt.body->>'state' IS DISTINCT FROM 'awaiting_complete_native_end'
              OR receipt.body->'executionAllowed' IS DISTINCT FROM 'false'::jsonb
              OR receipt.body->'windowExpiryReleasesRisk' IS DISTINCT FROM 'false'::jsonb
              OR receipt.body->'unknownCommitRetainsRisk' IS DISTINCT FROM 'true'::jsonb
              OR jsonb_typeof(sealed) IS DISTINCT FROM 'object'
              OR sealed->>'planId' IS DISTINCT FROM p_plan::text
              OR sealed->>'callerXid' IS DISTINCT FROM p_xid::text
              OR sealed->>'callerPid' IS DISTINCT FROM p_pid::text
              OR sealed->>'physicalAccountId' IS DISTINCT FROM receipt.physical_account_id::text
              OR sealed->>'initialCallAuthorityHash' IS DISTINCT FROM receipt.material_hash
              OR sealed->>'obligationHash' IS DISTINCT FROM receipt.body#>>'{nodes,initialTargetObligation}'
              OR sealed->'executionAllowed' IS DISTINCT FROM 'false'::jsonb
              OR jsonb_typeof(sealed->'unresolvedMembers') IS DISTINCT FROM 'array'
              OR jsonb_typeof(sealed->'accountMapping') IS DISTINCT FROM 'object'
              OR receipt.body->>'physicalFactsHash' IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(sealed),'UTF8')),'hex')
              OR sealed->>'unresolvedSetHash' IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(sealed->'unresolvedMembers'),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_FINAL_PHYSICAL_RECEIPT_REQUIRED' USING ERRCODE='23514'; END IF;
            IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(sealed->'unresolvedMembers') member
              WHERE member->>'kind'='initialTarget' AND member->>'id'=p_plan::text
                AND member#>>'{nativeRow,content_hash}'=sealed->>'obligationHash') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_FINAL_PHYSICAL_SELF_REQUIRED' USING ERRCODE='23514'; END IF;
            current_members:=public.read_shared_parent_unresolved_members(receipt.physical_account_id);
            IF current_members->'accountMapping' IS DISTINCT FROM sealed->'accountMapping'
              OR current_members->'accountVersion' IS DISTINCT FROM sealed->'accountVersion'
              OR current_members->'unresolvedMembers' IS DISTINCT FROM sealed->'unresolvedMembers'
              OR current_members->'unresolvedSetHash' IS DISTINCT FROM sealed->'unresolvedSetHash'
              OR current_members->'unresolvedRequests' IS DISTINCT FROM sealed->'unresolvedRequests'
              OR current_members->'unresolvedTokenUpperBound' IS DISTINCT FROM sealed->'unresolvedTokenUpperBound' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_FINAL_PHYSICAL_CHANGED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'receiptHash',receipt.content_hash,
              'physicalFactsHash',receipt.body->>'physicalFactsHash','unresolvedSetHash',sealed->>'unresolvedSetHash',
              'physicalComparisonMatched',true,'executionAllowed',false);
          END 