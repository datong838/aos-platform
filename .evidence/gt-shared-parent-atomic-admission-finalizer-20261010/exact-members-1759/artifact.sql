CREATE FUNCTION public.read_shared_parent_unresolved_members(p_account uuid)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $members$
          DECLARE account_row aos_physical_capacity_occupation_private.account_guard%ROWTYPE;
            members jsonb; total_requests bigint; total_tokens numeric; invalid_members bigint;
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_EXACT_MEMBER_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO account_row FROM aos_physical_capacity_occupation_private.account_guard
              WHERE physical_account_id=p_account AND org_id='org-org' AND project_id='dev-project' FOR SHARE;
            IF NOT FOUND THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_EXACT_MEMBER_ACCOUNT_REQUIRED' USING ERRCODE='23514'; END IF;
            WITH native_members AS (
              SELECT 'legacyDebit'::text AS kind,d.debit_id::text AS member_id,
                to_jsonb(d) AS native_row,d.immutable AS original_body,d.content_hash,
                d.token_units AS tokens,d.org_id,d.project_id
              FROM aos_physical_capacity_occupation_private.prepared_parent_debit d WHERE d.physical_account_id=p_account
              UNION ALL
              SELECT 'initialTarget',d.plan_id::text,to_jsonb(d),d.body,d.content_hash,
                d.token_upper_bound,d.org_id,d.project_id
              FROM aos_shared_parent_physical_private.initial_target_obligation d WHERE d.physical_account_id=p_account
            )
            SELECT coalesce(jsonb_agg(jsonb_build_object('kind',kind,'id',member_id,'nativeRow',native_row)
                ORDER BY kind COLLATE "C",member_id COLLATE "C"),'[]'::jsonb),
              count(*),coalesce(sum(tokens),0),
              count(*) FILTER(WHERE org_id IS DISTINCT FROM 'org-org' OR project_id IS DISTINCT FROM 'dev-project'
                OR tokens IS NULL OR tokens<=0 OR content_hash IS DISTINCT FROM
                  'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(original_body),'UTF8')),'hex'))
              INTO members,total_requests,total_tokens,invalid_members FROM native_members;
            IF invalid_members<>0 THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_EXACT_MEMBER_HASH_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('physicalAccountId',p_account,'accountVersion',account_row.version,
              'accountMapping',to_jsonb(account_row),'unresolvedMembers',members,
              'unresolvedSetHash','sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(members),'UTF8')),'hex'),
              'unresolvedRequests',total_requests,'unresolvedTokenUpperBound',total_tokens,'executionAllowed',false);
          END $members$;

ALTER FUNCTION public.read_shared_parent_unresolved_members(uuid) OWNER TO aos_physical_capacity_occupation_owner;

REVOKE ALL ON FUNCTION public.read_shared_parent_unresolved_members(uuid) FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer;

CREATE FUNCTION public.read_shared_parent_receipt_origin(p_plan uuid,p_pending_hash text,p_xid xid8,p_pid integer)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $retained$
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
          END $retained$;

ALTER FUNCTION public.read_shared_parent_receipt_origin(uuid,text,xid8,integer) OWNER TO aos_model_eval_issuer_owner;

REVOKE ALL ON FUNCTION public.read_shared_parent_receipt_origin(uuid,text,xid8,integer) FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer;

GRANT EXECUTE ON FUNCTION public.read_shared_parent_receipt_origin(uuid,text,xid8,integer) TO aos_physical_capacity_occupation_owner;

CREATE TABLE aos_shared_parent_physical_private.complete_receipt_v2(
          plan_id uuid PRIMARY KEY REFERENCES aos_shared_parent_physical_private.initial_target_obligation(plan_id),
          org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
          material_hash text NOT NULL CHECK(material_hash ~ '^sha256:[0-9a-f]{64}$'),
          physical_account_id uuid NOT NULL,body jsonb NOT NULL,
          content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          caller_xid xid8 NOT NULL,caller_pid integer NOT NULL CHECK(caller_pid>0));

ALTER TABLE aos_shared_parent_physical_private.complete_receipt_v2 OWNER TO aos_physical_capacity_occupation_owner;

REVOKE ALL ON aos_shared_parent_physical_private.complete_receipt_v2 FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer;

ALTER TABLE aos_shared_parent_physical_private.complete_receipt_v2 ENABLE ROW LEVEL SECURITY;

ALTER TABLE aos_shared_parent_physical_private.complete_receipt_v2 FORCE ROW LEVEL SECURITY;

CREATE POLICY exact_scope ON aos_shared_parent_physical_private.complete_receipt_v2 TO aos_physical_capacity_occupation_owner
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true));

CREATE FUNCTION aos_shared_parent_physical_private.bind_complete_receipt_v2() RETURNS trigger LANGUAGE plpgsql
          SET search_path=pg_catalog AS $receipt_binding$
          DECLARE obligation aos_shared_parent_physical_private.initial_target_obligation%ROWTYPE;
            target_row aos_shared_parent_physical_private.target_intent%ROWTYPE;judge_row aos_shared_parent_physical_private.judge_dependency%ROWTYPE;
            material aos_shared_parent_physical_private.initial_call_authority%ROWTYPE;window_row aos_shared_parent_physical_private.initial_window_obligation%ROWTYPE;
            risk_row aos_shared_parent_physical_private.complete_parent_risk%ROWTYPE;node record;count_nodes integer:=0;
            hashes jsonb:='{}'::jsonb;pending jsonb;facts jsonb;intents jsonb;live jsonb;member_set jsonb;
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
              OR NEW.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR NEW.caller_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO obligation FROM aos_shared_parent_physical_private.initial_target_obligation WHERE plan_id=NEW.plan_id FOR SHARE;
            SELECT * INTO target_row FROM aos_shared_parent_physical_private.target_intent WHERE plan_id=NEW.plan_id FOR SHARE;
            SELECT * INTO judge_row FROM aos_shared_parent_physical_private.judge_dependency WHERE plan_id=NEW.plan_id FOR SHARE;
            SELECT * INTO material FROM aos_shared_parent_physical_private.initial_call_authority WHERE plan_id=NEW.plan_id FOR SHARE;
            SELECT * INTO window_row FROM aos_shared_parent_physical_private.initial_window_obligation WHERE plan_id=NEW.plan_id FOR SHARE;
            SELECT * INTO risk_row FROM aos_shared_parent_physical_private.complete_parent_risk WHERE plan_id=NEW.plan_id FOR SHARE;
            FOR node IN SELECT 'initialTargetObligation' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id FROM aos_shared_parent_physical_private.initial_target_obligation WHERE plan_id=NEW.plan_id
              UNION ALL SELECT 'targetIntent' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id FROM aos_shared_parent_physical_private.target_intent WHERE plan_id=NEW.plan_id
              UNION ALL SELECT 'judgeDependency' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id FROM aos_shared_parent_physical_private.judge_dependency WHERE plan_id=NEW.plan_id
              UNION ALL SELECT 'initialCallAuthority' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id FROM aos_shared_parent_physical_private.initial_call_authority WHERE plan_id=NEW.plan_id
              UNION ALL SELECT 'initialWindowObligation' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id FROM aos_shared_parent_physical_private.initial_window_obligation WHERE plan_id=NEW.plan_id
              UNION ALL SELECT 'completeParentRisk' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id FROM aos_shared_parent_physical_private.complete_parent_risk WHERE plan_id=NEW.plan_id LOOP
              IF node.caller_xid IS DISTINCT FROM NEW.caller_xid OR node.caller_pid IS DISTINCT FROM NEW.caller_pid
                OR node.org_id IS DISTINCT FROM NEW.org_id OR node.project_id IS DISTINCT FROM NEW.project_id
                OR node.body->>'planId' IS DISTINCT FROM NEW.plan_id::text
                OR node.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                  public.canonical_asset_registry_jsonb(node.body),'UTF8')),'hex') THEN
                RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_NODE_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
              hashes:=hashes||jsonb_build_object(node.name,node.content_hash);count_nodes:=count_nodes+1;
            END LOOP;
            IF count_nodes<>6 OR material.content_hash IS DISTINCT FROM NEW.material_hash
              OR window_row.material_hash IS DISTINCT FROM material.content_hash
              OR window_row.physical_account_id IS DISTINCT FROM obligation.physical_account_id
              OR risk_row.physical_account_id IS DISTINCT FROM obligation.physical_account_id
              OR risk_row.pending_hash IS DISTINCT FROM obligation.pending_hash
              OR material.target_id IS DISTINCT FROM target_row.intent_id
              OR material.target_hash IS DISTINCT FROM target_row.content_hash
              OR material.judge_id IS DISTINCT FROM judge_row.intent_id
              OR material.judge_hash IS DISTINCT FROM judge_row.content_hash THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_COMPLETE_NODES_REQUIRED' USING ERRCODE='23514'; END IF;
            pending:=public.read_shared_parent_receipt_origin(NEW.plan_id,obligation.pending_hash,NEW.caller_xid,NEW.caller_pid);
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
            intents:=public.verify_shared_parent_final_call_authority(NEW.plan_id,material.content_hash,NEW.caller_xid,NEW.caller_pid);
            IF intents->>'targetIntentHash' IS DISTINCT FROM target_row.content_hash
              OR intents->>'judgeDependencyHash' IS DISTINCT FROM judge_row.content_hash
              OR intents->>'initialCallAuthorityHash' IS DISTINCT FROM material.content_hash THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_CURRENT_INTENTS_REQUIRED' USING ERRCODE='23514'; END IF;
            -- This original account update/capacity check occurs before native drain.
            live:=public.read_shared_parent_live_physical_facts(NEW.plan_id,window_row.content_hash,NEW.caller_xid,NEW.caller_pid);
            hashes:=hashes||jsonb_build_object('pendingOrigin',pending->>'contentHash',
              'endAuthority',pending->>'authorityMaterialHash');
            member_set:=public.read_shared_parent_unresolved_members(obligation.physical_account_id);
            IF member_set->>'accountVersion' IS DISTINCT FROM live#>>'{facts,accountVersion}'
              OR member_set->>'unresolvedRequests' IS DISTINCT FROM live#>>'{facts,unresolvedRequests}'
              OR member_set->>'unresolvedTokenUpperBound' IS DISTINCT FROM live#>>'{facts,unresolvedTokenUpperBound}' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_MEMBER_TOTALS_CHANGED' USING ERRCODE='23514'; END IF;
            live:=jsonb_set(live,'{facts}',(live->'facts')||jsonb_build_object(
              'accountMapping',member_set->'accountMapping','unresolvedMembers',member_set->'unresolvedMembers',
              'unresolvedSetHash',member_set->'unresolvedSetHash'));
            live:=jsonb_set(live,'{contentHash}',to_jsonb('sha256:'||encode(sha256(convert_to(
              public.canonical_asset_registry_jsonb(live->'facts'),'UTF8')),'hex')));
            NEW.physical_account_id:=obligation.physical_account_id;
            NEW.body:=jsonb_build_object('schemaVersion','aos.shared-parent-complete-receipt-preparation/v2',
              'planId',NEW.plan_id,'tenant',jsonb_build_object('orgId',NEW.org_id,'projectId',NEW.project_id),
              'nodes',hashes,'originalRiskHash',risk_row.body->>'originalRiskHash',
              'sourcePacketHash',material.body->>'sourcePacketHash','physicalFacts',live->'facts',
              'physicalFactsHash',live->>'contentHash','callerLogin',session_user,
              'callerXid',NEW.caller_xid::text,'callerPid',NEW.caller_pid,
              'state','awaiting_complete_native_end','preparedAt',clock_timestamp(),
              'windowExpiryReleasesRisk',false,'unknownCommitRetainsRisk',true,'executionAllowed',false);
            NEW.content_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(NEW.body),'UTF8')),'hex');
            RETURN NEW;
          END $receipt_binding$;

ALTER FUNCTION aos_shared_parent_physical_private.bind_complete_receipt_v2() OWNER TO aos_physical_capacity_occupation_owner;

REVOKE ALL ON FUNCTION aos_shared_parent_physical_private.bind_complete_receipt_v2() FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer;

CREATE TRIGGER exact_complete_receipt BEFORE INSERT ON aos_shared_parent_physical_private.complete_receipt_v2 FOR EACH ROW EXECUTE FUNCTION aos_shared_parent_physical_private.bind_complete_receipt_v2();

CREATE TRIGGER immutable_complete_receipt BEFORE UPDATE OR DELETE ON aos_shared_parent_physical_private.complete_receipt_v2 FOR EACH ROW EXECUTE FUNCTION aos_shared_parent_physical_private.immutable_obligation();

CREATE TRIGGER no_truncate_complete_receipt BEFORE TRUNCATE ON aos_shared_parent_physical_private.complete_receipt_v2 FOR EACH STATEMENT EXECUTE FUNCTION aos_shared_parent_physical_private.immutable_obligation();

CREATE CONSTRAINT TRIGGER require_complete_receipt_end AFTER INSERT ON aos_shared_parent_physical_private.complete_receipt_v2
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION aos_shared_parent_physical_private.require_complete_obligation();

CREATE FUNCTION public.stage_shared_parent_complete_receipt_v2(p_plan uuid,p_material_hash text,p_xid xid8,p_pid integer)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $receipt_stage$
          DECLARE previous aos_shared_parent_physical_private.complete_receipt_v2%ROWTYPE;pending jsonb;
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
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO previous FROM aos_shared_parent_physical_private.complete_receipt_v2 WHERE plan_id=p_plan FOR SHARE;
            IF FOUND THEN RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_ALREADY_STAGED' USING ERRCODE='23514'; END IF;
            INSERT INTO aos_shared_parent_physical_private.complete_receipt_v2(plan_id,org_id,project_id,material_hash,caller_xid,caller_pid)
              VALUES(p_plan,'org-org','dev-project',p_material_hash,p_xid,p_pid) RETURNING * INTO previous;
            -- Revalidate original signed authority after all insertion/uniqueness/FK waits.
            pending:=public.read_shared_parent_receipt_origin(p_plan,previous.body#>>'{nodes,pendingOrigin}',p_xid,p_pid);
            IF pending->>'authorityMaterialHash' IS DISTINCT FROM previous.body#>>'{nodes,endAuthority}'
              OR pending->>'sourcePacketHash' IS DISTINCT FROM previous.body->>'sourcePacketHash'
              OR pending#>>'{immutable,origin,immutable,originalRiskHash}' IS DISTINCT FROM previous.body->>'originalRiskHash' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_POSTWAIT_ORIGIN_CHANGED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'immutable',previous.body,'contentHash',previous.content_hash,
              'persisted',true,'executionAllowed',false,'state','awaiting_complete_native_end');
          END $receipt_stage$;

ALTER FUNCTION public.stage_shared_parent_complete_receipt_v2(uuid,text,xid8,integer) OWNER TO aos_physical_capacity_occupation_owner;

REVOKE ALL ON FUNCTION public.stage_shared_parent_complete_receipt_v2(uuid,text,xid8,integer) FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer;
