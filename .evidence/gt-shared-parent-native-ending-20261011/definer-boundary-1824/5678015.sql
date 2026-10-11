
          DECLARE material aos_shared_parent_admission_private.end_authority%ROWTYPE; original aos_shared_parent_admission_private.pending_origin%ROWTYPE;
            pending jsonb; facts jsonb; body jsonb; packet jsonb; p_raw bytea; verified jsonb; certificates bytea;
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
              OR p_xid IS DISTINCT FROM pg_current_xact_id() OR p_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RETAINED_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO material FROM aos_shared_parent_admission_private.end_authority WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR material.pending_hash IS DISTINCT FROM p_pending_hash
              OR material.caller_xid IS DISTINCT FROM p_xid OR material.caller_pid IS DISTINCT FROM p_pid THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RETAINED_AUTHORITY_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT * INTO original FROM aos_shared_parent_admission_private.pending_origin WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR original.content_hash IS DISTINCT FROM p_pending_hash
              OR original.caller_xid IS DISTINCT FROM p_xid OR original.caller_pid IS DISTINCT FROM p_pid THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RETAINED_PENDING_REQUIRED' USING ERRCODE='23514'; END IF;
            p_raw:=material.source_raw;
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
            pending:=jsonb_build_object('planId',original.plan_id,'immutable',original.body,'contentHash',original.content_hash);
            facts:=pending#>'{immutable,origin,immutable,originalRisk,originalFacts}';
            body:=jsonb_build_object('schemaVersion','aos.shared-parent-end-authority/v1',
              'planId',pending->'planId','pendingOriginHash',pending->>'contentHash',
              'sourcePacketHash','sha256:'||encode(sha256(p_raw),'hex'),
              'sourceRef',facts#>'{target,sourceRef}',
              'targetHold',facts#>'{target,reservationId}','targetRequestId',facts#>'{target,requestId}',
              'targetRequestHash',facts#>'{target,requestHash}',
              'judgeHold',facts#>'{judge,reservationId}','judgeRequestId',facts#>'{judge,requestId}',
              'judgeRequestHash',facts#>'{judge,requestHash}',
              'manifestHash',pending#>'{immutable,origin,immutable,manifestHash}',
              'callerLogin',session_user,'callerXid',pg_current_xact_id()::text,'callerPid',pg_backend_pid(),
              'state','awaiting_full_admission','executionAllowed',false);
            IF body IS DISTINCT FROM material.body
              OR material.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex')
              OR packet->'sourceRef' IS DISTINCT FROM body->'sourceRef' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RETAINED_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
            certificates:=convert_to(public.canonical_asset_registry_jsonb(original.body->'certificates'),'UTF8');
            verified:=public.read_shared_parent_pending_origin(p_raw,body->'sourceRef',
              (body->>'targetHold')::uuid,body->>'targetRequestId',body->>'targetRequestHash',
              (body->>'judgeHold')::uuid,body->>'judgeRequestId',body->>'judgeRequestHash',p_plan,
              original.body#>'{origin,immutable,manifest}',body->>'manifestHash',certificates,p_pending_hash);
            RETURN verified||jsonb_build_object('authorityMaterialHash',material.content_hash,'sourcePacketHash',body->>'sourcePacketHash');
          END 