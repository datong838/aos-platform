CREATE FUNCTION public.verify_shared_parent_final_call_authority(p_plan uuid,p_material_hash text,p_xid xid8,p_pid integer)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $call_read$
          DECLARE target_row aos_shared_parent_physical_private.target_intent%ROWTYPE; judge_row aos_shared_parent_physical_private.judge_dependency%ROWTYPE;
            obligation aos_shared_parent_physical_private.initial_target_obligation%ROWTYPE; body jsonb; packet jsonb; material aos_shared_parent_physical_private.initial_call_authority%ROWTYPE; p_raw bytea;p_suite_raw bytea;p_input_raw bytea;
            pending jsonb; facts jsonb; verified jsonb; certificates bytea;
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project' OR p_xid IS DISTINCT FROM pg_current_xact_id() OR p_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CALL_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO material FROM aos_shared_parent_physical_private.initial_call_authority WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR material.content_hash IS DISTINCT FROM p_material_hash
              OR material.caller_xid IS DISTINCT FROM p_xid OR material.caller_pid IS DISTINCT FROM p_pid THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CALL_MATERIAL_REQUIRED' USING ERRCODE='23514'; END IF;
            p_raw:=material.source_raw;p_suite_raw:=material.suite_raw;p_input_raw:=material.input_raw;
            IF p_raw IS NULL OR octet_length(p_raw) NOT BETWEEN 2 AND 1048576 THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RETAINED_PACKET_REQUIRED' USING ERRCODE='23514'; END IF;
            packet:=convert_from(p_raw,'UTF8')::jsonb;
            IF jsonb_typeof(packet) IS DISTINCT FROM 'object'
              OR jsonb_typeof(packet->'authentication') IS DISTINCT FROM 'object' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RETAINED_PACKET_REQUIRED' USING ERRCODE='23514'; END IF;
            IF convert_to(public.canonical_asset_registry_jsonb(packet),'UTF8') IS DISTINCT FROM p_raw
              OR (SELECT count(*) FROM jsonb_object_keys(packet))<>4
              OR packet-ARRAY['protocol','tenant','sourceRef','authentication'] IS DISTINCT FROM '{}'::jsonb
              OR packet->>'protocol' IS DISTINCT FROM 'aos-provider-capacity-source-consumption/v1'
              OR packet->'tenant' IS DISTINCT FROM jsonb_build_object('orgId','org-org','projectId','dev-project')
              OR (SELECT count(*) FROM jsonb_object_keys(packet->'authentication'))<>4
              OR (packet->'authentication')-ARRAY['consumerSubject','oidcIssuer','oidcAudience','authenticationExpiresAt'] IS DISTINCT FROM '{}'::jsonb THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RETAINED_PACKET_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT * INTO target_row FROM aos_shared_parent_physical_private.target_intent WHERE plan_id=p_plan FOR SHARE;
            SELECT * INTO judge_row FROM aos_shared_parent_physical_private.judge_dependency WHERE plan_id=p_plan FOR SHARE;
            SELECT * INTO obligation FROM aos_shared_parent_physical_private.initial_target_obligation WHERE plan_id=p_plan FOR SHARE;
            IF target_row.plan_id IS NULL OR judge_row.plan_id IS NULL OR obligation.plan_id IS NULL
              OR target_row.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR judge_row.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR obligation.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR target_row.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR judge_row.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR obligation.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR judge_row.target_intent_id IS DISTINCT FROM target_row.intent_id
              OR judge_row.target_intent_hash IS DISTINCT FROM target_row.content_hash
              OR target_row.body->>'obligationHash' IS DISTINCT FROM obligation.content_hash
              OR target_row.body->>'pendingOriginHash' IS DISTINCT FROM obligation.pending_hash
              OR judge_row.body->>'pendingOriginHash' IS DISTINCT FROM obligation.pending_hash
              OR target_row.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(target_row.body),'UTF8')),'hex')
              OR judge_row.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(judge_row.body),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CALL_NATIVE_NODES_REQUIRED' USING ERRCODE='23514'; END IF;
            IF p_suite_raw IS NULL OR octet_length(p_suite_raw) NOT BETWEEN 1 AND 1048576
              OR p_input_raw IS NULL OR octet_length(p_input_raw) NOT BETWEEN 1 AND 1048576
              OR encode(sha256(p_input_raw),'hex') IS DISTINCT FROM target_row.body->>'inputHash'
              OR convert_from(p_input_raw,'UTF8')::jsonb IS DISTINCT FROM target_row.body->'inputValue' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CALL_BYTES_REQUIRED' USING ERRCODE='23514'; END IF;
            body:=jsonb_build_object('schemaVersion','aos.shared-parent-initial-call-authority/v1',
              'planId',p_plan,'pendingOriginHash',obligation.pending_hash,'obligationHash',obligation.content_hash,
              'targetIntentId',target_row.intent_id,'targetIntentHash',target_row.content_hash,
              'judgeDependencyId',judge_row.intent_id,'judgeDependencyHash',judge_row.content_hash,
              'sourcePacketHash','sha256:'||encode(sha256(p_raw),'hex'),
              'suiteBytesHash','sha256:'||encode(sha256(p_suite_raw),'hex'),
              'inputBytesHash','sha256:'||encode(sha256(p_input_raw),'hex'),
              'callerLogin',session_user,'callerXid',pg_current_xact_id()::text,'callerPid',pg_backend_pid(),
              'executionAllowed',false);
            IF body IS DISTINCT FROM material.body
              OR p_material_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CALL_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
            pending:=public.read_shared_parent_retained_origin(p_plan,obligation.pending_hash,p_xid,p_pid);
            facts:=pending#>'{immutable,origin,immutable,originalRisk,originalFacts}';
            certificates:=convert_to(public.canonical_asset_registry_jsonb(pending#>'{immutable,certificates}'),'UTF8');
            verified:=public.verify_shared_parent_final_intents(p_raw,facts#>'{target,sourceRef}',
              (facts#>>'{target,reservationId}')::uuid,facts#>>'{target,requestId}',facts#>>'{target,requestHash}',
              (facts#>>'{judge,reservationId}')::uuid,facts#>>'{judge,requestId}',facts#>>'{judge,requestHash}',
              p_plan,pending#>'{immutable,origin,immutable,manifest}',pending#>>'{immutable,origin,immutable,manifestHash}',
              certificates,obligation.pending_hash,obligation.content_hash,p_suite_raw,p_input_raw,target_row.intent_id,judge_row.intent_id);
            IF verified->'targetIntent' IS DISTINCT FROM target_row.body
              OR verified->>'targetIntentHash' IS DISTINCT FROM target_row.content_hash
              OR verified->'judgeDependency' IS DISTINCT FROM judge_row.body
              OR verified->>'judgeDependencyHash' IS DISTINCT FROM judge_row.content_hash THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CALL_CURRENTNESS_CHANGED' USING ERRCODE='23514'; END IF;
            RETURN verified||jsonb_build_object('initialCallAuthorityHash',material.content_hash);
          END $call_read$

ALTER FUNCTION public.verify_shared_parent_final_call_authority(uuid,text,xid8,integer) OWNER TO aos_physical_capacity_occupation_owner

REVOKE ALL ON FUNCTION public.verify_shared_parent_final_call_authority(uuid,text,xid8,integer) FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer
