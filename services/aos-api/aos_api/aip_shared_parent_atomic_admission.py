"""Original-fact entry for the complete versioned shared-parent admission.

Explicit SQL artifact only. The versioned risk ledger, certificates, trusted
end channel and native full admission matrix remain required before admission
can be exposed. Necessary facts are never execution permission.
"""
from aos_api.aip_physical_capacity_occupation_authority import OWNER, PLAN_FACT
from aos_api import aip_shared_parent_certificate_prepare as _certificate
from aos_api import aip_physical_capacity_occupation_authority as _physical
import re

FUNCTION = 'public.read_shared_parent_admission_original_facts(bytea,jsonb,uuid,text,text,uuid,text,text)'


FINAL_CALL = 'public.verify_shared_parent_final_call_authority(uuid,text,xid8,integer)'


def shared_parent_final_call_validation_statements():
    """Retain original material verification, using the fixed Intent comparison.

    This explicit closed artifact removes the reachable Intent producer only.
    Source delegates still require semantic closure and the complete native
    Receipt/end protocol before any admission can be exposed.
    """
    signature = READ_INITIAL_CALL.split('(')[0]
    definitions = [sql for sql in shared_parent_initial_call_authority_statements()
                   if sql.startswith('CREATE FUNCTION ' + signature + '(')]
    if len(definitions) != 1:
        raise ValueError('SHARED_ADMISSION_FINAL_CALL_DEFINITION_REQUIRED')
    body = definitions[0]
    producer = INITIAL_INTENT.split('(')[0]
    boundary = 'verified:=' + producer + '('
    if body.count(boundary) != 1 or body.count(producer) != 1:
        raise ValueError('SHARED_ADMISSION_FINAL_CALL_COMPARISON_BOUNDARY_REQUIRED')
    body = body.replace(boundary, 'verified:=' + FINAL_INTENT.split('(')[0] + '(', 1)
    if re.search(r'\b(?:INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b', body, re.I):
        raise ValueError('SHARED_ADMISSION_FINAL_CALL_DIRECT_WRITER_FORBIDDEN')
    body = body.replace('CREATE FUNCTION ' + signature + '(',
                        'CREATE FUNCTION ' + FINAL_CALL.split('(')[0] + '(', 1)
    return (body,
            f'ALTER FUNCTION {FINAL_CALL} OWNER TO {OWNER}',
            f'REVOKE ALL ON FUNCTION {FINAL_CALL} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer')


FINAL_INTENT = 'public.verify_shared_parent_final_intents(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text,bytea,text,text,bytea,bytea,uuid,uuid)'


def shared_parent_final_intent_validation_statements():
    """Compare persisted intents with original authority without direct DML.

    Preserve the original producer exactly. Exact write fragments are removed
    only in this closed comparison artifact; generator drift fails closed.
    Nested delegates, physical facts and the full Receipt/native end protocol
    must still be accepted before this can be used by a complete finalizer.
    """
    signature = INITIAL_INTENT.split('(')[0]
    definitions = [sql for sql in shared_parent_initial_intent_statements()
                   if sql.startswith('CREATE FUNCTION ' + signature + '(')]
    if len(definitions) != 1:
        raise ValueError('SHARED_ADMISSION_FINAL_INTENT_DEFINITION_REQUIRED')
    body = definitions[0]
    target = PHYSICAL_SCHEMA + '.target_intent'
    judge = PHYSICAL_SCHEMA + '.judge_dependency'
    writes = (
        f'''            INSERT INTO {target}(intent_id,plan_id,org_id,project_id,request_id,case_id,attempt,body,content_hash,caller_xid,caller_pid)
              VALUES(p_target_intent,p_plan,'org-org','dev-project',p_tr,obligation.case_id,1,target_body,target_hash,
                pg_current_xact_id(),pg_backend_pid()) ON CONFLICT DO NOTHING;
''',
        f'''            INSERT INTO {judge}(intent_id,plan_id,org_id,project_id,target_intent_id,target_intent_hash,
              request_id,case_id,attempt,body,content_hash,caller_xid,caller_pid)
              VALUES(p_judge_intent,p_plan,'org-org','dev-project',p_target_intent,target_hash,p_jr,obligation.case_id,1,
                judge_body,judge_hash,pg_current_xact_id(),pg_backend_pid()) ON CONFLICT DO NOTHING;
''',
    )
    for fragment in writes:
        if body.count(fragment) != 1:
            raise ValueError('SHARED_ADMISSION_FINAL_INTENT_WRITE_BOUNDARY_REQUIRED')
        body = body.replace(fragment, '', 1)
    if re.search(r'\b(?:INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b', body, re.I):
        raise ValueError('SHARED_ADMISSION_FINAL_INTENT_DIRECT_WRITER_FORBIDDEN')
    body = body.replace('CREATE FUNCTION ' + signature + '(',
                        'CREATE FUNCTION ' + FINAL_INTENT.split('(')[0] + '(', 1)
    return (body,
            f'ALTER FUNCTION {FINAL_INTENT} OWNER TO {OWNER}',
            f'REVOKE ALL ON FUNCTION {FINAL_INTENT} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer')


def shared_parent_admission_description_validation_sql():
    """Reuse original complete manifest checks after trusted versioned origin.

    Caller-supplied JSON and legacy prepared rows are not an admission origin.
    The complete version must establish current native facts/risk/Source and
    caller context before using this fragment or creating a receipt.
    """
    return _physical.shared_parent_description_validation_sql()


def shared_parent_admission_certificate_validation_sql():
    """Reuse both original native certificate checks without new trust rules.

    This fragment requires original validated doc/items/caller variables and
    the original issuer delegate's verification privilege. It neither builds
    a description nor authenticates that origin by itself. The complete new
    admission must still bind those inputs before any ledger/receipt write.
    """
    return (_certificate.shared_parent_native_verifier_requirement_sql()
            + _certificate.shared_parent_certificate_claim_sql())


def shared_parent_admission_certificate_lock_sql():
    """Original complete-set and Root locks, before post-wait verification.

    Only the new admission lane separates these phases. The published
    preparation producer and its full validation fragment remain unchanged.
    """
    original = _certificate.shared_parent_certificate_claim_sql()
    boundary = '            -- Validate every signature and complete original claim before any certificate insert.\n'
    locks, marker, validation = original.partition(boundary)
    if (not marker or boundary in validation or 'FOR SHARE OF e' not in locks
            or 'SHARED_CERTIFICATE_COMPLETE_SET_REQUIRED' not in locks
            or 'SHARED_CERTIFICATE_PREPUBLISHED_ROOT_REQUIRED' not in locks
            or 'verify_model_shared_parent_certificate_signature' not in validation):
        raise ValueError('SHARED_CERTIFICATE_LOCK_PHASE_BOUNDARY_REQUIRED')
    return locks


def shared_parent_original_fact_statements():
    """Reuse original Source and independent Target/Judge hold validation.

    Only the existing physical owner can call this entry internally. Runtime
    callers receive no direct execute grant. No legacy preparation row is
    created or finalized, and none of its seven denial guards is changed.
    """
    return (
        f'''CREATE FUNCTION {FUNCTION.split('(')[0]}(
          p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,
          p_judge uuid,p_jr text,p_jh text) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $facts$
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_ORIGINAL_FACT_CALLER_REQUIRED' USING ERRCODE='42501';
            END IF;
            RETURN {PLAN_FACT.split('(')[0]}(
              p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh);
          END $facts$''',
        f'ALTER FUNCTION {FUNCTION} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
    )


ORIGIN = 'public.build_shared_parent_admission_origin(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text)'
CERTIFICATE_SET = 'public.validate_shared_parent_admission_certificate_set(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text,bytea)'
ADMISSION_SCHEMA = 'aos_shared_parent_admission_private'
PERSIST = 'public.persist_shared_parent_admission_origin(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text,bytea)'
END_CHANNEL = ADMISSION_SCHEMA + '.require_complete_admission(uuid,text,xid8,integer)'


def shared_parent_admission_origin_statements():
    """Build trusted native facts/description for the complete versioned lane.

    No old preparation rows, caller-supplied facts, admission Receipt or ledger
    writes. Certificates and full physical/end-channel protocol remain needed.
    Explicit artifact only; no automatic installation or runtime execute grant.
    """
    return (
        f'''CREATE FUNCTION {ORIGIN.split('(')[0]}(
          p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,
          p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_hash text) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $origin$
          DECLARE facts jsonb; after_facts jsonb; item jsonb; legs jsonb:='[]'; body jsonb; digest text;
            risk {_physical.SCHEMA}.prepared_plan_risk%ROWTYPE;
            leg jsonb; parent jsonb; fact jsonb; source_doc jsonb; original_case jsonb; purpose text; idx integer:=0;
          BEGIN
            facts:={FUNCTION.split('(')[0]}(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh);
            IF p_plan IS NULL THEN RAISE EXCEPTION 'CAPACITY_PLAN_ID_REQUIRED' USING ERRCODE='23514'; END IF;
            source_doc:=public.capacity_occupation_source_fact(p_raw,p_source);
{_physical.shared_parent_original_risk_body_sql()}            risk.immutable:=body; risk.content_hash:=digest;
            risk.target_request:=p_tr; risk.judge_request:=p_jr;
{shared_parent_admission_description_validation_sql()}            body:=jsonb_build_object(
              'schemaVersion','aos.shared-parent-admission-origin/v1','planId',p_plan,
              'tenant',risk.immutable->'tenant','originalRisk',risk.immutable,
              'originalRiskHash',risk.content_hash,'manifest',p_manifest,'manifestHash',p_hash,
              'callerLogin',session_user,'callerXid',pg_current_xact_id()::text,'callerPid',pg_backend_pid(),
              'state','awaiting_full_admission','executionAllowed',false);
            digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
            after_facts:={FUNCTION.split('(')[0]}(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh);
            IF after_facts IS DISTINCT FROM facts THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_ORIGIN_FACT_CHANGED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'immutable',body,'contentHash',digest,'executionAllowed',false);
          END $origin$''',
        f'ALTER FUNCTION {ORIGIN} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {ORIGIN} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
    )


def shared_parent_admission_certificate_set_statements():
    """Closed original-Issuer verification against newly derived native origin.

    Explicit artifact; prerequisite original verifier/Root installation remains
    separate. No certificate, risk, Intent or Receipt rows are written. This
    verification result cannot authorize execution or a full admission COMMIT.
    """
    issuer = _certificate.ISSUER_OWNER
    origin_call = (f'{ORIGIN.split("(")[0]}('
                   'p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash)')
    return (
        f'GRANT EXECUTE ON FUNCTION {ORIGIN} TO {issuer}',
        f'''CREATE FUNCTION {CERTIFICATE_SET.split('(')[0]}(
          p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,
          p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_manifest_hash text,p_certificates bytea)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $set$
          DECLARE doc jsonb; plan jsonb; items jsonb; envelope jsonb; claim jsonb; leg jsonb; app jsonb;
            root record; head record; candidate jsonb; p_hash text;
            expected integer; actual integer; distinct_legs integer; start_at timestamptz; end_at timestamptz;
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
              OR p_certificates IS NULL OR octet_length(p_certificates) NOT BETWEEN 2 AND 1048576 THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CERTIFICATE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            items:=convert_from(p_certificates,'UTF8')::jsonb;
            IF jsonb_typeof(items) IS DISTINCT FROM 'array'
              OR convert_to(public.canonical_asset_registry_jsonb(items),'UTF8') IS DISTINCT FROM p_certificates THEN
              RAISE EXCEPTION 'SHARED_CERTIFICATE_CANONICAL_SET_REQUIRED' USING ERRCODE='23514'; END IF;
            doc:={origin_call};p_hash:=doc->>'contentHash';
{_certificate.shared_parent_native_verifier_requirement_sql()}{shared_parent_admission_certificate_lock_sql()}            IF {origin_call} IS DISTINCT FROM doc THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CERTIFICATE_ORIGIN_CHANGED' USING ERRCODE='23514'; END IF;
{shared_parent_admission_certificate_validation_sql()}            RETURN jsonb_build_object('origin',doc,'certificateCount',actual,
              'executionAllowed',false,'rootProvenanceVerified',false,'state','awaiting_full_admission');
          END $set$''',
        f'ALTER FUNCTION {CERTIFICATE_SET} OWNER TO {issuer}',
        f'REVOKE ALL ON FUNCTION {CERTIFICATE_SET} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
    )


def shared_parent_admission_storage_statements():
    """Closed immutable native origin storage, pending the complete end channel.

    Neither storage nor certificates allocate physical capacity or authorize
    execution. Until the complete native end-channel artifact exists, a queued
    origin cannot COMMIT. No original preparation guard is replaced.
    """
    s = ADMISSION_SCHEMA
    issuer = _certificate.ISSUER_OWNER
    table = s + '.pending_origin'
    denied = f'PUBLIC,aos_runtime,aos_provider_capacity_issuer,{OWNER}'
    return (
        f'CREATE SCHEMA {s} AUTHORIZATION {issuer}',
        f'REVOKE ALL ON SCHEMA {s} FROM {denied}',
        f'''CREATE TABLE {table}(
          plan_id uuid PRIMARY KEY,org_id text NOT NULL CHECK(org_id='org-org'),
          project_id text NOT NULL CHECK(project_id='dev-project'),
          physical_account_id uuid NOT NULL,target_hold uuid NOT NULL,judge_hold uuid NOT NULL,
          caller_xid xid8 NOT NULL,caller_pid integer NOT NULL CHECK(caller_pid>0),
          body jsonb NOT NULL,content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          CHECK(target_hold<>judge_hold))''',
        f'ALTER TABLE {table} OWNER TO {issuer}',
        f'REVOKE ALL ON {table} FROM {denied}',
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {table} TO {issuer}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'''CREATE FUNCTION {s}.check_pending_origin() RETURNS trigger
          LANGUAGE plpgsql SET search_path=pg_catalog AS $binding$
          DECLARE origin jsonb; facts jsonb;
          BEGIN
            origin:=NEW.body#>'{{origin,immutable}}';facts:=origin#>'{{originalRisk,originalFacts}}';
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'
              OR NEW.body->>'schemaVersion' IS DISTINCT FROM 'aos.shared-parent-pending-origin/v1'
              OR NEW.body->>'state' IS DISTINCT FROM 'awaiting_full_admission'
              OR NEW.body->'executionAllowed' IS DISTINCT FROM 'false'::jsonb
              OR NEW.body#>>'{{origin,planId}}' IS DISTINCT FROM NEW.plan_id::text
              OR origin->>'schemaVersion' IS DISTINCT FROM 'aos.shared-parent-admission-origin/v1'
              OR origin->>'callerLogin' IS DISTINCT FROM session_user
              OR origin->>'callerXid' IS DISTINCT FROM pg_current_xact_id()::text
              OR origin->>'callerPid' IS DISTINCT FROM pg_backend_pid()::text
              OR NEW.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR NEW.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR origin#>>'{{tenant,orgId}}' IS DISTINCT FROM NEW.org_id
              OR origin#>>'{{tenant,projectId}}' IS DISTINCT FROM NEW.project_id
              OR facts#>>'{{target,physicalAccountId}}' IS DISTINCT FROM NEW.physical_account_id::text
              OR facts#>>'{{judge,physicalAccountId}}' IS DISTINCT FROM NEW.physical_account_id::text
              OR facts#>>'{{target,reservationId}}' IS DISTINCT FROM NEW.target_hold::text
              OR facts#>>'{{judge,reservationId}}' IS DISTINCT FROM NEW.judge_hold::text
              OR NEW.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(NEW.body),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_PENDING_ORIGIN_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN NEW;
          END $binding$''',
        f'ALTER FUNCTION {s}.check_pending_origin() OWNER TO {issuer}',
        f'REVOKE ALL ON FUNCTION {s}.check_pending_origin() FROM {denied}',
        f'''CREATE FUNCTION {s}.immutable_pending_origin() RETURNS trigger
          LANGUAGE plpgsql SET search_path=pg_catalog AS $immutable$
          BEGIN RAISE EXCEPTION 'SHARED_ADMISSION_PENDING_ORIGIN_IMMUTABLE' USING ERRCODE='42501'; END $immutable$''',
        f'ALTER FUNCTION {s}.immutable_pending_origin() OWNER TO {issuer}',
        f'REVOKE ALL ON FUNCTION {s}.immutable_pending_origin() FROM {denied}',
        f'''CREATE FUNCTION {s}.require_pending_completion() RETURNS trigger
          LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $end$
          BEGIN
            IF NEW.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR NEW.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR NOT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_language l ON l.oid=p.prolang
                WHERE p.oid=to_regprocedure('{END_CHANNEL}')
                  AND pg_get_userbyid(p.proowner)='{OWNER}' AND p.prosecdef
                  AND p.proconfig=ARRAY['search_path=pg_catalog'] AND l.lanname='plpgsql'
                  AND p.prorettype='void'::regtype
                  AND NOT has_function_privilege('aos_runtime',p.oid,'EXECUTE')
                  AND NOT has_function_privilege('aos_provider_capacity_issuer',p.oid,'EXECUTE')) THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_COMPLETE_END_CHANNEL_REQUIRED' USING ERRCODE='23514'; END IF;
            PERFORM {s}.require_complete_admission(NEW.plan_id,NEW.content_hash,NEW.caller_xid,NEW.caller_pid);
            RETURN NEW;
          END $end$''',
        f'ALTER FUNCTION {s}.require_pending_completion() OWNER TO {issuer}',
        f'REVOKE ALL ON FUNCTION {s}.require_pending_completion() FROM {denied}',
        f'CREATE TRIGGER bind_pending_origin BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.check_pending_origin()',
        f'CREATE TRIGGER immutable_pending_origin BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.immutable_pending_origin()',
        f'CREATE TRIGGER no_truncate_pending_origin BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {s}.immutable_pending_origin()',
        f'''CREATE CONSTRAINT TRIGGER require_complete_admission_end AFTER INSERT ON {table}
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.require_pending_completion()''',
        f'''CREATE FUNCTION {PERSIST.split('(')[0]}(
          p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,
          p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_manifest_hash text,p_certificates bytea)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $persist$
          DECLARE verified jsonb; origin jsonb; facts jsonb; body jsonb; digest text; previous {table}%ROWTYPE;
          BEGIN
            verified:={CERTIFICATE_SET.split('(')[0]}(
              p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates);
            origin:=verified->'origin';facts:=origin#>'{{immutable,originalRisk,originalFacts}}';
            body:=jsonb_build_object('schemaVersion','aos.shared-parent-pending-origin/v1',
              'origin',origin,'certificates',convert_from(p_certificates,'UTF8')::jsonb,
              'certificateSetHash','sha256:'||encode(sha256(p_certificates),'hex'),
              'state','awaiting_full_admission','executionAllowed',false);
            digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
            INSERT INTO {table}(plan_id,org_id,project_id,physical_account_id,target_hold,judge_hold,
              caller_xid,caller_pid,body,content_hash)
              VALUES(p_plan,'org-org','dev-project',(facts#>>'{{target,physicalAccountId}}')::uuid,
                (facts#>>'{{target,reservationId}}')::uuid,(facts#>>'{{judge,reservationId}}')::uuid,
                pg_current_xact_id(),pg_backend_pid(),body,digest) ON CONFLICT DO NOTHING;
            SELECT * INTO previous FROM {table} WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR previous.body IS DISTINCT FROM body OR previous.content_hash IS DISTINCT FROM digest
              OR previous.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR previous.caller_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_PENDING_ORIGIN_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            -- INSERT uniqueness and row locks may wait. Revalidate the complete
            -- native origin and all signatures after those waits, before return.
            IF {CERTIFICATE_SET.split('(')[0]}(
              p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates)
                IS DISTINCT FROM verified THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_PENDING_ORIGIN_CURRENTNESS_CHANGED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'immutable',body,'contentHash',digest,
              'persisted',true,'executionAllowed',false,'state','awaiting_full_admission');
          END $persist$''',
        f'ALTER FUNCTION {PERSIST} OWNER TO {issuer}',
        f'REVOKE ALL ON FUNCTION {PERSIST} FROM {denied}',
    )


READ_PENDING = 'public.read_shared_parent_pending_origin(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text,bytea,text)'


def shared_parent_pending_origin_lookup_statements():
    """Fixed native handoff to the physical owner, without table access.

    Raw authority inputs are reverified after row waits. This lookup neither
    creates missing origins nor allocates capacity, issues receipts or admits
    execution. The complete ledger/end channel remains a separate requirement.
    """
    issuer = _certificate.ISSUER_OWNER
    table = ADMISSION_SCHEMA + '.pending_origin'
    return (
        f'''CREATE FUNCTION {READ_PENDING.split('(')[0]}(
          p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,
          p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_manifest_hash text,
          p_certificates bytea,p_pending_hash text) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $lookup$
          DECLARE verified jsonb; previous {table}%ROWTYPE; facts jsonb;
          BEGIN
            IF {_end_authority_native_context_sql()}
              OR p_certificates IS NULL OR octet_length(p_certificates) NOT BETWEEN 2 AND 1048576 THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CERTIFICATE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO previous FROM {table} WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR previous.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR previous.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR previous.content_hash IS DISTINCT FROM p_pending_hash
              OR previous.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(previous.body),'UTF8')),'hex')
              OR previous.org_id IS DISTINCT FROM 'org-org'
              OR previous.project_id IS DISTINCT FROM 'dev-project'
              OR previous.target_hold IS DISTINCT FROM p_target
              OR previous.judge_hold IS DISTINCT FROM p_judge
              OR previous.body->>'schemaVersion' IS DISTINCT FROM 'aos.shared-parent-pending-origin/v1'
              OR previous.body->'certificates' IS DISTINCT FROM convert_from(p_certificates,'UTF8')::jsonb
              OR previous.body->>'certificateSetHash' IS DISTINCT FROM 'sha256:'||encode(sha256(p_certificates),'hex')
              OR previous.body->>'state' IS DISTINCT FROM 'awaiting_full_admission'
              OR previous.body->'executionAllowed' IS DISTINCT FROM 'false'::jsonb THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_PENDING_ORIGIN_EXACT_HANDOFF_REQUIRED' USING ERRCODE='23514'; END IF;
            -- No effects precede this full post-lock original verification.
            verified:={CERTIFICATE_SET.split('(')[0]}(
              p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates);
            facts:=verified#>'{{origin,immutable,originalRisk,originalFacts}}';
            IF previous.physical_account_id::text IS DISTINCT FROM facts#>>'{{target,physicalAccountId}}'
              OR previous.physical_account_id::text IS DISTINCT FROM facts#>>'{{judge,physicalAccountId}}'
              OR previous.body->'origin' IS DISTINCT FROM verified->'origin' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_PENDING_ORIGIN_CURRENTNESS_CHANGED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',previous.plan_id,'immutable',previous.body,
              'contentHash',previous.content_hash,'persisted',true,
              'executionAllowed',false,'state','awaiting_full_admission');
          END $lookup$''',
        f'ALTER FUNCTION {READ_PENDING} OWNER TO {issuer}',
        f'REVOKE ALL ON FUNCTION {READ_PENDING} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
        f'GRANT EXECUTE ON FUNCTION {READ_PENDING} TO {OWNER}',
    )


PHYSICAL_SCHEMA = 'aos_shared_parent_physical_private'
INITIAL_OBLIGATION = 'public.prepare_shared_parent_initial_target_obligation(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text,bytea,text)'
PHYSICAL_END = 'public.require_complete_shared_parent_admission(uuid,text,xid8,integer)'


def shared_parent_physical_obligation_statements():
    """First Target obligation; legacy/new totals under original account lock.

    No dispatch, monetary debit, release or complete admission. Missing native
    complete finalizer rejects COMMIT; formal cutover remains independently
    required even when this isolated internal component is installed.
    """
    s = PHYSICAL_SCHEMA
    table = s + '.initial_target_obligation'
    denied = 'PUBLIC,aos_runtime,aos_provider_capacity_issuer'
    return (
        f'CREATE SCHEMA {s} AUTHORIZATION {OWNER}',
        f'REVOKE ALL ON SCHEMA {s} FROM {denied}',
        f'''CREATE TABLE {table}(
          plan_id uuid PRIMARY KEY,org_id text NOT NULL CHECK(org_id='org-org'),
          project_id text NOT NULL CHECK(project_id='dev-project'),
          physical_account_id uuid NOT NULL REFERENCES {_physical.SCHEMA}.account_guard(physical_account_id),
          target_hold uuid NOT NULL,case_id text NOT NULL CHECK(length(case_id)>0),
          token_upper_bound bigint NOT NULL CHECK(token_upper_bound>0),
          pending_hash text NOT NULL CHECK(pending_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          caller_xid xid8 NOT NULL,caller_pid integer NOT NULL CHECK(caller_pid>0),
          body jsonb NOT NULL,content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{{64}}$'))''',
        f'ALTER TABLE {table} OWNER TO {OWNER}',
        f'REVOKE ALL ON {table} FROM {denied}',
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {table} TO {OWNER}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'''CREATE FUNCTION {s}.immutable_obligation() RETURNS trigger LANGUAGE plpgsql
          SET search_path=pg_catalog AS $immutable$
          BEGIN RAISE EXCEPTION 'SHARED_ADMISSION_OBLIGATION_IMMUTABLE' USING ERRCODE='42501'; END $immutable$''',
        f'ALTER FUNCTION {s}.immutable_obligation() OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {s}.immutable_obligation() FROM {denied}',
        f'CREATE TRIGGER immutable_obligation BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.immutable_obligation()',
        f'CREATE TRIGGER no_truncate_obligation BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {s}.immutable_obligation()',
        f'''CREATE FUNCTION {s}.require_complete_obligation() RETURNS trigger LANGUAGE plpgsql
          SECURITY DEFINER SET search_path=pg_catalog AS $end$
          BEGIN
            IF NEW.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR NEW.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR NOT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_language l ON l.oid=p.prolang
                WHERE p.oid=to_regprocedure('{PHYSICAL_END}') AND pg_get_userbyid(p.proowner)='{OWNER}'
                  AND p.prosecdef AND p.proconfig=ARRAY['search_path=pg_catalog'] AND l.lanname='plpgsql'
                  AND p.prorettype='void'::regtype
                  AND NOT has_function_privilege('aos_runtime',p.oid,'EXECUTE')
                  AND NOT has_function_privilege('aos_provider_capacity_issuer',p.oid,'EXECUTE')) THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_COMPLETE_END_CHANNEL_REQUIRED' USING ERRCODE='23514'; END IF;
            PERFORM {PHYSICAL_END.split('(')[0]}(NEW.plan_id,NEW.content_hash,NEW.caller_xid,NEW.caller_pid);
            RETURN NEW;
          END $end$''',
        f'ALTER FUNCTION {s}.require_complete_obligation() OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {s}.require_complete_obligation() FROM {denied}',
        f'''CREATE CONSTRAINT TRIGGER require_complete_obligation_end AFTER INSERT ON {table}
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.require_complete_obligation()''',
        f'''CREATE FUNCTION {INITIAL_OBLIGATION.split('(')[0]}(
          p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,
          p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_manifest_hash text,
          p_certificates bytea,p_pending_hash text) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $obligation$
          DECLARE pending jsonb; fact jsonb; body jsonb; digest text; account jsonb;
            case_id text; used_requests bigint; used_tokens numeric; previous {table}%ROWTYPE;
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_OBLIGATION_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            account:={_physical.GUARD.split('(')[0]}(p_raw,p_source);
            pending:={READ_PENDING.split('(')[0]}(
              p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates,p_pending_hash);
            fact:=pending#>'{{immutable,origin,immutable,originalRisk,originalFacts,target}}';
            case_id:=pending#>>'{{immutable,origin,immutable,originalRisk,originalFacts,cases,0,caseId}}';
            IF case_id IS NULL OR account->>'physicalAccountId' IS DISTINCT FROM fact->>'physicalAccountId' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_OBLIGATION_NATIVE_ACCOUNT_REQUIRED' USING ERRCODE='23514'; END IF;
            body:=jsonb_build_object('schemaVersion','aos.shared-parent-initial-target-obligation/v1',
              'planId',p_plan,'pendingOriginHash',p_pending_hash,'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
              'physicalAccountId',fact->>'physicalAccountId','targetHold',p_target,'caseId',case_id,
              'tokenUpperBound',fact->'tokenUpperBound','callerLogin',session_user,
              'callerXid',pg_current_xact_id()::text,'callerPid',pg_backend_pid(),
              'state','pending_full_admission','executionAllowed',false);
            digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
            SELECT * INTO previous FROM {table} WHERE plan_id=p_plan FOR SHARE;
            IF FOUND THEN
              IF previous.body IS DISTINCT FROM body OR previous.content_hash IS DISTINCT FROM digest
                OR previous.caller_xid IS DISTINCT FROM pg_current_xact_id() OR previous.caller_pid IS DISTINCT FROM pg_backend_pid() THEN
                RAISE EXCEPTION 'SHARED_ADMISSION_OBLIGATION_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            ELSE
              SELECT count(*),coalesce(sum(token_units),0) INTO used_requests,used_tokens
                FROM {_physical.SCHEMA}.prepared_parent_debit WHERE physical_account_id=(fact->>'physicalAccountId')::uuid;
              SELECT used_requests+count(*),used_tokens+coalesce(sum(token_upper_bound),0) INTO used_requests,used_tokens
                FROM {table} WHERE physical_account_id=(fact->>'physicalAccountId')::uuid;
              {_physical._physical_call_capacity_guard_sql('target')}
              INSERT INTO {table}(plan_id,org_id,project_id,physical_account_id,target_hold,case_id,token_upper_bound,
                pending_hash,caller_xid,caller_pid,body,content_hash)
                VALUES(p_plan,'org-org','dev-project',(fact->>'physicalAccountId')::uuid,p_target,case_id,
                  (fact->>'tokenUpperBound')::bigint,p_pending_hash,pg_current_xact_id(),pg_backend_pid(),body,digest);
            END IF;
            IF {READ_PENDING.split('(')[0]}(
              p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates,p_pending_hash)
                IS DISTINCT FROM pending THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_OBLIGATION_CURRENTNESS_CHANGED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'immutable',body,'contentHash',digest,'executionAllowed',false);
          END $obligation$''',
        f'ALTER FUNCTION {INITIAL_OBLIGATION} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {INITIAL_OBLIGATION} FROM {denied}',
    )


INITIAL_INTENT = 'public.prepare_shared_parent_initial_intents(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text,bytea,text,text,bytea,bytea,uuid,uuid)'


def shared_parent_initial_intent_statements():
    """Unique first Target intent and nonexecuting Judge result dependency.

    Original native CASE_FACT and input/approval kernels remain authoritative.
    Full ending, legacy cutover and actual-result consumers remain required.
    """
    s = PHYSICAL_SCHEMA
    target = s + '.target_intent'
    judge = s + '.judge_dependency'
    denied = 'PUBLIC,aos_runtime,aos_provider_capacity_issuer'
    statements = [
        f'''CREATE TABLE {target}(
          intent_id uuid PRIMARY KEY,plan_id uuid NOT NULL UNIQUE REFERENCES {s}.initial_target_obligation(plan_id),
          org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
          request_id text NOT NULL,case_id text NOT NULL,attempt integer NOT NULL CHECK(attempt=1),
          body jsonb NOT NULL,content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          caller_xid xid8 NOT NULL,caller_pid integer NOT NULL CHECK(caller_pid>0),
          UNIQUE(org_id,project_id,request_id,case_id,attempt),UNIQUE(intent_id,content_hash))''',
        f'''CREATE TABLE {judge}(
          intent_id uuid PRIMARY KEY,plan_id uuid NOT NULL UNIQUE REFERENCES {target}(plan_id),
          org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
          target_intent_id uuid NOT NULL UNIQUE,target_intent_hash text NOT NULL,
          request_id text NOT NULL,case_id text NOT NULL,attempt integer NOT NULL CHECK(attempt=1),
          body jsonb NOT NULL,content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          caller_xid xid8 NOT NULL,caller_pid integer NOT NULL CHECK(caller_pid>0),
          UNIQUE(org_id,project_id,request_id,case_id,attempt),
          FOREIGN KEY(target_intent_id,target_intent_hash) REFERENCES {target}(intent_id,content_hash))''',
    ]
    for table in (target, judge):
        statements.extend((
            f'ALTER TABLE {table} OWNER TO {OWNER}',
            f'REVOKE ALL ON {table} FROM {denied}',
            f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
            f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
            f'''CREATE POLICY exact_scope ON {table} TO {OWNER}
              USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
              WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
            f'CREATE TRIGGER immutable_intent BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.immutable_obligation()',
            f'CREATE TRIGGER no_truncate_intent BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {s}.immutable_obligation()',
            f'''CREATE CONSTRAINT TRIGGER require_complete_intent_end AFTER INSERT ON {table}
              DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.require_complete_obligation()''',
        ))
    statements.extend((
        f'''CREATE FUNCTION {INITIAL_INTENT.split('(')[0]}(
          p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,
          p_judge uuid,p_jr text,p_jh text,p_plan uuid,p_manifest jsonb,p_manifest_hash text,
          p_certificates bytea,p_pending_hash text,p_obligation_hash text,p_suite_raw bytea,p_input_raw bytea,
          p_target_intent uuid,p_judge_intent uuid) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $intents$
          DECLARE obligation {s}.initial_target_obligation%ROWTYPE; prior_target {target}%ROWTYPE;
            prior_judge {judge}%ROWTYPE; fact jsonb; value jsonb; pending jsonb; original jsonb; after_facts jsonb;
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
            SELECT * INTO obligation FROM {s}.initial_target_obligation WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR obligation.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR obligation.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR obligation.pending_hash IS DISTINCT FROM p_pending_hash
              OR obligation.content_hash IS DISTINCT FROM p_obligation_hash
              OR obligation.target_hold IS DISTINCT FROM p_target
              OR obligation.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(obligation.body),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_INTENT_NATIVE_OBLIGATION_REQUIRED' USING ERRCODE='23514'; END IF;
            fact:={_physical.CASE_FACT.split('(')[0]}(p_raw,p_source,p_target,p_tr,p_th,p_suite_raw,obligation.case_id);
{_physical.occupation_input_bytes_validation_sql()}            target_body:=jsonb_build_object(
              'schemaVersion','aos.shared-parent-target-intent/v1','intentId',p_target_intent,'planId',p_plan,
              'pendingOriginHash',p_pending_hash,'obligationHash',p_obligation_hash,
              'tenant',jsonb_build_object('orgId','org-org','projectId','dev-project'),
{_physical.occupation_target_authority_fields_sql()}              'parentHold',p_target,'caseId',obligation.case_id,'inputRef',fact->'inputRef',
              'inputHash',fact->>'inputHash','inputValue',value,'purpose','target','attempt',1,
              'callerLogin',session_user,'callerXid',pg_current_xact_id()::text,'callerPid',pg_backend_pid(),
              'state','pending_full_admission','executionAllowed',false);
            target_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(target_body),'UTF8')),'hex');
            INSERT INTO {target}(intent_id,plan_id,org_id,project_id,request_id,case_id,attempt,body,content_hash,caller_xid,caller_pid)
              VALUES(p_target_intent,p_plan,'org-org','dev-project',p_tr,obligation.case_id,1,target_body,target_hash,
                pg_current_xact_id(),pg_backend_pid()) ON CONFLICT DO NOTHING;
            SELECT * INTO prior_target FROM {target} WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR prior_target.intent_id IS DISTINCT FROM p_target_intent
              OR prior_target.body IS DISTINCT FROM target_body OR prior_target.content_hash IS DISTINCT FROM target_hash
              OR prior_target.caller_xid IS DISTINCT FROM pg_current_xact_id() OR prior_target.caller_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_TARGET_INTENT_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            pending:={READ_PENDING.split('(')[0]}(
              p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates,p_pending_hash);
            original:=pending#>'{{immutable,origin,immutable,originalRisk,originalFacts}}';native_case:=original->'cases'->0;
            IF fact->'application' IS DISTINCT FROM original->'target'->'application'
              OR fact->>'inputHash' IS DISTINCT FROM native_case->'inputArtifact'->>'contentHash'
              OR obligation.case_id IS DISTINCT FROM native_case->>'caseId'
              OR original#>>'{{judge,application,ruleFacts,rule,inputProtocol}}' IS DISTINCT FROM 'aos.model-eval-judge-input/v1' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_INTENT_ORIGINAL_PAIR_REQUIRED' USING ERRCODE='23514'; END IF;
            judge_body:=jsonb_build_object('schemaVersion','aos.shared-parent-judge-dependency/v1',
              'intentId',p_judge_intent,'planId',p_plan,'pendingOriginHash',p_pending_hash,
              'tenant',target_body->'tenant','requestId',p_jr,'requestHash',p_jh,
              'parentHold',p_judge,'caseId',obligation.case_id,'application',original#>'{{judge,application}}',
              'targetIntentId',p_target_intent,'targetIntentHash',target_hash,
              'inputDependency',jsonb_build_object('protocol','aos.model-eval-judge-input/v1',
                'state','awaiting_target_result','targetIntentId',p_target_intent,
                'targetIntentHash',target_hash,'expectedArtifact',native_case->'expectedArtifact'),
              'purpose','judge','attempt',1,'callerLogin',session_user,'callerXid',pg_current_xact_id()::text,
              'callerPid',pg_backend_pid(),'state','awaiting_target_result','executionAllowed',false);
            judge_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(judge_body),'UTF8')),'hex');
            INSERT INTO {judge}(intent_id,plan_id,org_id,project_id,target_intent_id,target_intent_hash,
              request_id,case_id,attempt,body,content_hash,caller_xid,caller_pid)
              VALUES(p_judge_intent,p_plan,'org-org','dev-project',p_target_intent,target_hash,p_jr,obligation.case_id,1,
                judge_body,judge_hash,pg_current_xact_id(),pg_backend_pid()) ON CONFLICT DO NOTHING;
            SELECT * INTO prior_judge FROM {judge} WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR prior_judge.intent_id IS DISTINCT FROM p_judge_intent
              OR prior_judge.body IS DISTINCT FROM judge_body OR prior_judge.content_hash IS DISTINCT FROM judge_hash
              OR prior_judge.caller_xid IS DISTINCT FROM pg_current_xact_id() OR prior_judge.caller_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_JUDGE_DEPENDENCY_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            after_facts:={FUNCTION.split('(')[0]}(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh);
            IF after_facts IS DISTINCT FROM original OR EXISTS(SELECT 1 FROM jsonb_array_elements(pending#>'{{immutable,certificates}}') envelope
                WHERE clock_timestamp()<(envelope#>>'{{certificate,validFrom}}')::timestamptz
                   OR clock_timestamp()>=(envelope#>>'{{certificate,validUntil}}')::timestamptz) THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_INTENT_CURRENT_AFTER_WAITS_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'targetIntent',target_body,'targetIntentHash',target_hash,
              'judgeDependency',judge_body,'judgeDependencyHash',judge_hash,'executionAllowed',false);
          END $intents$''',
        f'ALTER FUNCTION {INITIAL_INTENT} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {INITIAL_INTENT} FROM {denied}',
    ))
    return tuple(statements)


STAGE_AUTHORITY = 'public.stage_shared_parent_end_authority(bytea,jsonb,uuid,text,text,uuid,text,text,uuid,jsonb,text,bytea,text)'
READ_RETAINED = 'public.read_shared_parent_retained_origin(uuid,text,xid8,integer)'


def _end_authority_native_context_sql():
    return """session_user<>'aos_provider_capacity_occupation'
              OR current_setting('role',true) IS DISTINCT FROM 'aos_runtime'
              OR current_setting('transaction_isolation') IS DISTINCT FROM 'serializable'
              OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
              OR current_setting('TimeZone') IS DISTINCT FROM 'UTC'
              OR current_setting('session_replication_role') IS DISTINCT FROM 'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project'"""


def _retained_source_packet_validation_sql():
    """Closed original consumer-claims packet; no bearer token is retained."""
    return """            IF p_raw IS NULL OR octet_length(p_raw) NOT BETWEEN 2 AND 1048576 THEN
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
"""


def _end_authority_body_sql():
    """Derive bindings from the previously native-verified pending origin."""
    return """            facts:=pending#>'{immutable,origin,immutable,originalRisk,originalFacts}';
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
"""


def shared_parent_end_authority_statements():
    """Retain native Source revalidation inputs for the future full ending.

    Closed explicit artifact. No bearer, new authentication, runtime grant or
    complete ending is created. Immutable material has the same deferred
    complete-ending requirement and cannot be independently committed.
    """
    s = ADMISSION_SCHEMA
    table = s + '.end_authority'
    issuer = _certificate.ISSUER_OWNER
    denied = f'PUBLIC,aos_runtime,aos_provider_capacity_issuer,{OWNER}'
    return (
        f'''CREATE TABLE {table}(
          plan_id uuid PRIMARY KEY REFERENCES {s}.pending_origin(plan_id),
          org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
          pending_hash text NOT NULL CHECK(pending_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          source_raw bytea NOT NULL CHECK(octet_length(source_raw) BETWEEN 2 AND 1048576),
          body jsonb NOT NULL,content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          caller_xid xid8 NOT NULL,caller_pid integer NOT NULL CHECK(caller_pid>0))''',
        f'ALTER TABLE {table} OWNER TO {issuer}',
        f'REVOKE ALL ON {table} FROM {denied}',
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {table} TO {issuer}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'''CREATE FUNCTION {s}.check_end_authority() RETURNS trigger
          LANGUAGE plpgsql SET search_path=pg_catalog AS $retained_binding$
          DECLARE original {s}.pending_origin%ROWTYPE; pending jsonb; facts jsonb; body jsonb;
            packet jsonb; p_raw bytea:=NEW.source_raw;
          BEGIN
            IF {_end_authority_native_context_sql()} THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_AUTHORITY_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
{_retained_source_packet_validation_sql()}            SELECT * INTO original FROM {s}.pending_origin WHERE plan_id=NEW.plan_id FOR SHARE;
            IF NOT FOUND OR original.content_hash IS DISTINCT FROM NEW.pending_hash
              OR original.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR original.caller_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_AUTHORITY_PENDING_REQUIRED' USING ERRCODE='23514'; END IF;
            pending:=jsonb_build_object('planId',original.plan_id,'immutable',original.body,'contentHash',original.content_hash);
{_end_authority_body_sql()}            IF NEW.body IS DISTINCT FROM body
              OR NEW.org_id IS DISTINCT FROM original.org_id OR NEW.project_id IS DISTINCT FROM original.project_id
              OR NEW.caller_xid IS DISTINCT FROM original.caller_xid OR NEW.caller_pid IS DISTINCT FROM original.caller_pid
              OR packet->'sourceRef' IS DISTINCT FROM body->'sourceRef'
              OR facts#>'{{judge,sourceRef}}' IS DISTINCT FROM body->'sourceRef'
              OR NEW.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_AUTHORITY_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN NEW;
          END $retained_binding$''',
        f'ALTER FUNCTION {s}.check_end_authority() OWNER TO {issuer}',
        f'REVOKE ALL ON FUNCTION {s}.check_end_authority() FROM {denied}',
        f'CREATE TRIGGER exact_authority BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.check_end_authority()',
        f'CREATE TRIGGER immutable_authority BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.immutable_pending_origin()',
        f'CREATE TRIGGER no_truncate_authority BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {s}.immutable_pending_origin()',
        f'''CREATE CONSTRAINT TRIGGER require_complete_authority_end AFTER INSERT ON {table}
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.require_pending_completion()''',
        f'''CREATE FUNCTION {STAGE_AUTHORITY.split('(')[0]}(
          p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,p_judge uuid,p_jr text,p_jh text,
          p_plan uuid,p_manifest jsonb,p_manifest_hash text,p_certificates bytea,p_pending_hash text)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $retain$
          DECLARE pending jsonb; facts jsonb; body jsonb; packet jsonb; digest text; previous {table}%ROWTYPE;
          BEGIN
            IF {_end_authority_native_context_sql()} THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_AUTHORITY_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
{_retained_source_packet_validation_sql()}            pending:={READ_PENDING.split('(')[0]}(
              p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates,p_pending_hash);
{_end_authority_body_sql()}            digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
            INSERT INTO {table}(plan_id,org_id,project_id,pending_hash,source_raw,body,content_hash,caller_xid,caller_pid)
              VALUES(p_plan,'org-org','dev-project',p_pending_hash,p_raw,body,digest,pg_current_xact_id(),pg_backend_pid())
              ON CONFLICT DO NOTHING;
            SELECT * INTO previous FROM {table} WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR previous.pending_hash IS DISTINCT FROM p_pending_hash
              OR previous.source_raw IS DISTINCT FROM p_raw OR previous.body IS DISTINCT FROM body
              OR previous.content_hash IS DISTINCT FROM digest OR previous.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR previous.caller_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_AUTHORITY_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            IF {READ_PENDING.split('(')[0]}(
              p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates,p_pending_hash)
                IS DISTINCT FROM pending THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_AUTHORITY_CURRENTNESS_CHANGED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'immutable',body,'contentHash',digest,'executionAllowed',false);
          END $retain$''',
        f'ALTER FUNCTION {STAGE_AUTHORITY} OWNER TO {issuer}',
        f'REVOKE ALL ON FUNCTION {STAGE_AUTHORITY} FROM {denied}',
        f'''CREATE FUNCTION {READ_RETAINED.split('(')[0]}(p_plan uuid,p_pending_hash text,p_xid xid8,p_pid integer)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $retained$
          DECLARE material {table}%ROWTYPE; original {s}.pending_origin%ROWTYPE;
            pending jsonb; facts jsonb; body jsonb; packet jsonb; p_raw bytea; verified jsonb; certificates bytea;
          BEGIN
            IF {_end_authority_native_context_sql()}
              OR p_xid IS DISTINCT FROM pg_current_xact_id() OR p_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RETAINED_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO material FROM {table} WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR material.pending_hash IS DISTINCT FROM p_pending_hash
              OR material.caller_xid IS DISTINCT FROM p_xid OR material.caller_pid IS DISTINCT FROM p_pid THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RETAINED_AUTHORITY_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT * INTO original FROM {s}.pending_origin WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR original.content_hash IS DISTINCT FROM p_pending_hash
              OR original.caller_xid IS DISTINCT FROM p_xid OR original.caller_pid IS DISTINCT FROM p_pid THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RETAINED_PENDING_REQUIRED' USING ERRCODE='23514'; END IF;
            p_raw:=material.source_raw;
{_retained_source_packet_validation_sql()}            pending:=jsonb_build_object('planId',original.plan_id,'immutable',original.body,'contentHash',original.content_hash);
{_end_authority_body_sql()}            IF body IS DISTINCT FROM material.body
              OR material.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex')
              OR packet->'sourceRef' IS DISTINCT FROM body->'sourceRef' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RETAINED_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
            certificates:=convert_to(public.canonical_asset_registry_jsonb(original.body->'certificates'),'UTF8');
            verified:={READ_PENDING.split('(')[0]}(p_raw,body->'sourceRef',
              (body->>'targetHold')::uuid,body->>'targetRequestId',body->>'targetRequestHash',
              (body->>'judgeHold')::uuid,body->>'judgeRequestId',body->>'judgeRequestHash',p_plan,
              original.body#>'{{origin,immutable,manifest}}',body->>'manifestHash',certificates,p_pending_hash);
            RETURN verified||jsonb_build_object('authorityMaterialHash',material.content_hash);
          END $retained$''',
        f'ALTER FUNCTION {READ_RETAINED} OWNER TO {issuer}',
        f'REVOKE ALL ON FUNCTION {READ_RETAINED} FROM {denied}',
        f'GRANT EXECUTE ON FUNCTION {READ_RETAINED} TO {OWNER}',
    )

STAGE_INITIAL_CALL = INITIAL_INTENT.replace('prepare_shared_parent_initial_intents', 'stage_shared_parent_initial_call_authority')
READ_INITIAL_CALL = 'public.read_shared_parent_initial_call_authority(uuid,text,xid8,integer)'


def _initial_call_material_binding_sql():
    """Native immutable node identity, bytes and caller; never caller JSON facts."""
    s = PHYSICAL_SCHEMA
    return f"""            SELECT * INTO target_row FROM {s}.target_intent WHERE plan_id=p_plan FOR SHARE;
            SELECT * INTO judge_row FROM {s}.judge_dependency WHERE plan_id=p_plan FOR SHARE;
            SELECT * INTO obligation FROM {s}.initial_target_obligation WHERE plan_id=p_plan FOR SHARE;
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
"""


def shared_parent_initial_call_authority_statements():
    """Explicit closed original-byte handoff; complete end gate remains required."""
    s = PHYSICAL_SCHEMA
    table = s + '.initial_call_authority'
    denied = 'PUBLIC,aos_runtime,aos_provider_capacity_issuer'
    declarations = f'''target_row {s}.target_intent%ROWTYPE; judge_row {s}.judge_dependency%ROWTYPE;
            obligation {s}.initial_target_obligation%ROWTYPE; body jsonb; packet jsonb;'''
    context = _end_authority_native_context_sql()
    packet = _retained_source_packet_validation_sql()
    binding = _initial_call_material_binding_sql()
    return (
        f'''CREATE TABLE {table}(
          plan_id uuid PRIMARY KEY REFERENCES {s}.initial_target_obligation(plan_id),
          org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
          target_id uuid NOT NULL,target_hash text NOT NULL,judge_id uuid NOT NULL,judge_hash text NOT NULL,
          source_raw bytea NOT NULL,suite_raw bytea NOT NULL,input_raw bytea NOT NULL,
          body jsonb NOT NULL,content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          caller_xid xid8 NOT NULL,caller_pid integer NOT NULL CHECK(caller_pid>0),
          FOREIGN KEY(target_id,target_hash) REFERENCES {s}.target_intent(intent_id,content_hash),
          FOREIGN KEY(judge_id) REFERENCES {s}.judge_dependency(intent_id))''',
        f'ALTER TABLE {table} OWNER TO {OWNER}',
        f'REVOKE ALL ON {table} FROM {denied}',
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {table} TO {OWNER}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'''CREATE FUNCTION {s}.bind_initial_call_authority() RETURNS trigger LANGUAGE plpgsql
          SET search_path=pg_catalog AS $call_binding$
          DECLARE {declarations} p_plan uuid:=NEW.plan_id; p_raw bytea:=NEW.source_raw;
            p_suite_raw bytea:=NEW.suite_raw;p_input_raw bytea:=NEW.input_raw;
          BEGIN
            IF {context} THEN RAISE EXCEPTION 'SHARED_ADMISSION_CALL_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
{packet}{binding}            IF NEW.body IS DISTINCT FROM body
              OR NEW.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex')
              OR NEW.target_id IS DISTINCT FROM target_row.intent_id OR NEW.target_hash IS DISTINCT FROM target_row.content_hash
              OR NEW.judge_id IS DISTINCT FROM judge_row.intent_id OR NEW.judge_hash IS DISTINCT FROM judge_row.content_hash
              OR NEW.caller_xid IS DISTINCT FROM pg_current_xact_id() OR NEW.caller_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CALL_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN NEW;
          END $call_binding$''',
        f'ALTER FUNCTION {s}.bind_initial_call_authority() OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {s}.bind_initial_call_authority() FROM {denied}',
        f'CREATE TRIGGER exact_initial_call BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.bind_initial_call_authority()',
        f'CREATE TRIGGER immutable_initial_call BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.immutable_obligation()',
        f'CREATE TRIGGER no_truncate_initial_call BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {s}.immutable_obligation()',
        f'''CREATE CONSTRAINT TRIGGER require_complete_call_end AFTER INSERT ON {table}
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.require_complete_obligation()''',
        f'''CREATE FUNCTION {STAGE_INITIAL_CALL.split('(')[0]}(
          p_raw bytea,p_source jsonb,p_target uuid,p_tr text,p_th text,p_judge uuid,p_jr text,p_jh text,
          p_plan uuid,p_manifest jsonb,p_manifest_hash text,p_certificates bytea,p_pending_hash text,p_obligation_hash text,
          p_suite_raw bytea,p_input_raw bytea,p_target_intent uuid,p_judge_intent uuid) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $call_stage$
          DECLARE {declarations} verified jsonb; pending jsonb; previous {table}%ROWTYPE; digest text;
          BEGIN
            IF {context} THEN RAISE EXCEPTION 'SHARED_ADMISSION_CALL_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
{packet}            verified:={INITIAL_INTENT.split('(')[0]}(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,
              p_plan,p_manifest,p_manifest_hash,p_certificates,p_pending_hash,p_obligation_hash,p_suite_raw,p_input_raw,p_target_intent,p_judge_intent);
            pending:={READ_RETAINED.split('(')[0]}(p_plan,p_pending_hash,pg_current_xact_id(),pg_backend_pid());
{binding}            digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
            INSERT INTO {table}(plan_id,org_id,project_id,target_id,target_hash,judge_id,judge_hash,
              source_raw,suite_raw,input_raw,body,content_hash,caller_xid,caller_pid)
              VALUES(p_plan,'org-org','dev-project',target_row.intent_id,target_row.content_hash,judge_row.intent_id,judge_row.content_hash,
                p_raw,p_suite_raw,p_input_raw,body,digest,pg_current_xact_id(),pg_backend_pid()) ON CONFLICT DO NOTHING;
            SELECT * INTO previous FROM {table} WHERE plan_id=p_plan FOR SHARE;
            IF previous.body IS DISTINCT FROM body OR previous.content_hash IS DISTINCT FROM digest
              OR previous.source_raw IS DISTINCT FROM p_raw OR previous.suite_raw IS DISTINCT FROM p_suite_raw
              OR previous.input_raw IS DISTINCT FROM p_input_raw THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CALL_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            IF {INITIAL_INTENT.split('(')[0]}(p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,
              p_plan,p_manifest,p_manifest_hash,p_certificates,p_pending_hash,p_obligation_hash,p_suite_raw,p_input_raw,p_target_intent,p_judge_intent)
              IS DISTINCT FROM verified THEN RAISE EXCEPTION 'SHARED_ADMISSION_CALL_CURRENTNESS_CHANGED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'immutable',body,'contentHash',digest,'executionAllowed',false);
          END $call_stage$''',
        f'ALTER FUNCTION {STAGE_INITIAL_CALL} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {STAGE_INITIAL_CALL} FROM {denied}',
        f'''CREATE FUNCTION {READ_INITIAL_CALL.split('(')[0]}(p_plan uuid,p_material_hash text,p_xid xid8,p_pid integer)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $call_read$
          DECLARE {declarations} material {table}%ROWTYPE; p_raw bytea;p_suite_raw bytea;p_input_raw bytea;
            pending jsonb; facts jsonb; verified jsonb; certificates bytea;
          BEGIN
            IF {context} OR p_xid IS DISTINCT FROM pg_current_xact_id() OR p_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CALL_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO material FROM {table} WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR material.content_hash IS DISTINCT FROM p_material_hash
              OR material.caller_xid IS DISTINCT FROM p_xid OR material.caller_pid IS DISTINCT FROM p_pid THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CALL_MATERIAL_REQUIRED' USING ERRCODE='23514'; END IF;
            p_raw:=material.source_raw;p_suite_raw:=material.suite_raw;p_input_raw:=material.input_raw;
{packet}{binding}            IF body IS DISTINCT FROM material.body
              OR p_material_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CALL_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
            pending:={READ_RETAINED.split('(')[0]}(p_plan,obligation.pending_hash,p_xid,p_pid);
            facts:=pending#>'{{immutable,origin,immutable,originalRisk,originalFacts}}';
            certificates:=convert_to(public.canonical_asset_registry_jsonb(pending#>'{{immutable,certificates}}'),'UTF8');
            verified:={INITIAL_INTENT.split('(')[0]}(p_raw,facts#>'{{target,sourceRef}}',
              (facts#>>'{{target,reservationId}}')::uuid,facts#>>'{{target,requestId}}',facts#>>'{{target,requestHash}}',
              (facts#>>'{{judge,reservationId}}')::uuid,facts#>>'{{judge,requestId}}',facts#>>'{{judge,requestHash}}',
              p_plan,pending#>'{{immutable,origin,immutable,manifest}}',pending#>>'{{immutable,origin,immutable,manifestHash}}',
              certificates,obligation.pending_hash,obligation.content_hash,p_suite_raw,p_input_raw,target_row.intent_id,judge_row.intent_id);
            IF verified->'targetIntent' IS DISTINCT FROM target_row.body
              OR verified->>'targetIntentHash' IS DISTINCT FROM target_row.content_hash
              OR verified->'judgeDependency' IS DISTINCT FROM judge_row.body
              OR verified->>'judgeDependencyHash' IS DISTINCT FROM judge_row.content_hash THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_CALL_CURRENTNESS_CHANGED' USING ERRCODE='23514'; END IF;
            RETURN verified||jsonb_build_object('initialCallAuthorityHash',material.content_hash);
          END $call_read$''',
        f'ALTER FUNCTION {READ_INITIAL_CALL} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {READ_INITIAL_CALL} FROM {denied}',
    )

STAGE_INITIAL_WINDOW = 'public.stage_shared_parent_initial_window_obligation(uuid,text,xid8,integer)'


def shared_parent_initial_window_obligation_statements():
    """Native window identity and conservative unresolved-risk union only.

    No obligation is released on time, window or Source revision changes.
    Actual settlement, full ending and execution remain separate requirements.
    """
    s = PHYSICAL_SCHEMA
    table = s + '.initial_window_obligation'
    denied = 'PUBLIC,aos_runtime,aos_provider_capacity_issuer'
    return (
        f'''CREATE TABLE {table}(
          plan_id uuid PRIMARY KEY REFERENCES {s}.initial_target_obligation(plan_id),
          org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
          material_hash text NOT NULL CHECK(material_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          physical_account_id uuid NOT NULL REFERENCES {_physical.SCHEMA}.account_guard(physical_account_id),
          caller_xid xid8 NOT NULL,caller_pid integer NOT NULL CHECK(caller_pid>0),
          body jsonb NOT NULL,content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{{64}}$'))''',
        f'ALTER TABLE {table} OWNER TO {OWNER}',
        f'REVOKE ALL ON {table} FROM {denied}',
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {table} TO {OWNER}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'''CREATE FUNCTION {s}.bind_initial_window() RETURNS trigger LANGUAGE plpgsql
          SET search_path=pg_catalog AS $window_binding$
          DECLARE material {s}.initial_call_authority%ROWTYPE; obligation {s}.initial_target_obligation%ROWTYPE;
            fact jsonb; packet jsonb; limit_body jsonb; body jsonb; guard_version bigint;
            used_requests bigint; used_tokens numeric; total_requests bigint; total_tokens numeric;
            now_at timestamptz; anchor_at timestamptz; window_seconds integer; window_index numeric;
          BEGIN
            IF {_end_authority_native_context_sql()} THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_WINDOW_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO material FROM {s}.initial_call_authority WHERE plan_id=NEW.plan_id FOR SHARE;
            SELECT * INTO obligation FROM {s}.initial_target_obligation WHERE plan_id=NEW.plan_id FOR SHARE;
            IF material.plan_id IS NULL OR obligation.plan_id IS NULL
              OR material.content_hash IS DISTINCT FROM NEW.material_hash
              OR material.caller_xid IS DISTINCT FROM pg_current_xact_id() OR material.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR obligation.caller_xid IS DISTINCT FROM pg_current_xact_id() OR obligation.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR NEW.caller_xid IS DISTINCT FROM pg_current_xact_id() OR NEW.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR NEW.physical_account_id IS DISTINCT FROM obligation.physical_account_id THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_WINDOW_NATIVE_MATERIAL_REQUIRED' USING ERRCODE='23514'; END IF;
            packet:=convert_from(material.source_raw,'UTF8')::jsonb;
            fact:={_physical.SOURCE_FACT.split('(')[0]}(material.source_raw,packet->'sourceRef');
            IF fact->>'physicalAccountId' IS DISTINCT FROM obligation.physical_account_id::text THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_WINDOW_NATIVE_ACCOUNT_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT version INTO guard_version FROM {_physical.SCHEMA}.account_guard
              WHERE physical_account_id=obligation.physical_account_id AND org_id='org-org' AND project_id='dev-project'
                AND xmin::text::numeric=mod(pg_current_xact_id()::text::numeric,4294967296) FOR UPDATE;
            IF NOT FOUND THEN RAISE EXCEPTION 'SHARED_ADMISSION_WINDOW_NATIVE_GUARD_REQUIRED' USING ERRCODE='23514'; END IF;
            limit_body:=fact->'tokenLimit';
            IF limit_body->>'mode' NOT IN ('inflight_upper_bound','fixed_window_rate')
              OR limit_body->>'mode' IS NULL OR limit_body->>'unit' IS DISTINCT FROM 'token'
              OR (limit_body->>'maxTokens')::numeric IS NULL OR (limit_body->>'maxTokens')::numeric<=0 THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_WINDOW_NATIVE_LIMIT_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT count(*),coalesce(sum(token_units),0) INTO total_requests,total_tokens FROM (
              SELECT token_units FROM {_physical.SCHEMA}.prepared_parent_debit WHERE physical_account_id=obligation.physical_account_id
              UNION ALL SELECT token_upper_bound FROM {s}.initial_target_obligation WHERE physical_account_id=obligation.physical_account_id
            ) native_unresolved;
            -- Current initial obligation is already present exactly once.
            used_requests:=total_requests-1;used_tokens:=total_tokens-obligation.token_upper_bound;
            IF used_requests<0 OR used_tokens<0 THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_WINDOW_NATIVE_COUNTS_REQUIRED' USING ERRCODE='23514'; END IF;
            fact:=fact||jsonb_build_object('tokenUpperBound',obligation.token_upper_bound);
            {_physical._physical_call_capacity_guard_sql('target')}
            now_at:=clock_timestamp();
            IF limit_body->>'mode'='fixed_window_rate' THEN
              window_seconds:=(limit_body->>'windowSeconds')::integer;
              anchor_at:=(limit_body->>'windowAnchor')::timestamptz;
              IF window_seconds IS NULL OR window_seconds NOT BETWEEN 1 AND 86400 OR anchor_at IS NULL THEN
                RAISE EXCEPTION 'SHARED_ADMISSION_WINDOW_NATIVE_LIMIT_REQUIRED' USING ERRCODE='23514'; END IF;
              window_index:=floor(extract(epoch FROM now_at-anchor_at)/window_seconds);
            END IF;
            body:=jsonb_build_object('schemaVersion','aos.shared-parent-initial-window-obligation/v1',
              'planId',NEW.plan_id,'initialCallAuthorityHash',material.content_hash,
              'obligationHash',obligation.content_hash,'physicalAccountId',obligation.physical_account_id,
              'sourceRef',packet->'sourceRef','sourceTokenLimit',limit_body,'accountVersion',guard_version,
              'observedAt',now_at,'windowIndex',window_index,'windowAnchor',anchor_at,'windowSeconds',window_seconds,
              'unresolvedRequests',total_requests,'unresolvedTokenUpperBound',total_tokens,
              'countingBasis','legacy_prepared_plus_new_initial_unreleased','windowExpiryReleasesRisk',false,
              'callerLogin',session_user,'callerXid',pg_current_xact_id()::text,'callerPid',pg_backend_pid(),
              'state','prepared_window_only','executionAllowed',false);
            NEW.body:=body;NEW.content_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
            RETURN NEW;
          END $window_binding$''',
        f'ALTER FUNCTION {s}.bind_initial_window() OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {s}.bind_initial_window() FROM {denied}',
        f'CREATE TRIGGER bind_initial_window BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.bind_initial_window()',
        f'CREATE TRIGGER immutable_initial_window BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.immutable_obligation()',
        f'CREATE TRIGGER no_truncate_initial_window BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {s}.immutable_obligation()',
        f'''CREATE CONSTRAINT TRIGGER require_complete_window_end AFTER INSERT ON {table}
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.require_complete_obligation()''',
        f'''CREATE FUNCTION {STAGE_INITIAL_WINDOW.split('(')[0]}(p_plan uuid,p_material_hash text,p_xid xid8,p_pid integer)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $window_stage$
          DECLARE material {s}.initial_call_authority%ROWTYPE; previous {table}%ROWTYPE;
            packet jsonb; guard_doc jsonb; call_doc jsonb;
          BEGIN
            IF {_end_authority_native_context_sql()} OR p_xid IS DISTINCT FROM pg_current_xact_id() OR p_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_WINDOW_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO material FROM {s}.initial_call_authority WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR material.content_hash IS DISTINCT FROM p_material_hash
              OR material.caller_xid IS DISTINCT FROM p_xid OR material.caller_pid IS DISTINCT FROM p_pid THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_WINDOW_NATIVE_MATERIAL_REQUIRED' USING ERRCODE='23514'; END IF;
            packet:=convert_from(material.source_raw,'UTF8')::jsonb;
            guard_doc:={_physical.GUARD.split('(')[0]}(material.source_raw,packet->'sourceRef');
            call_doc:={READ_INITIAL_CALL.split('(')[0]}(p_plan,p_material_hash,p_xid,p_pid);
            SELECT * INTO previous FROM {table} WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND THEN
              INSERT INTO {table}(plan_id,org_id,project_id,material_hash,physical_account_id,caller_xid,caller_pid,body,content_hash)
                VALUES(p_plan,'org-org','dev-project',p_material_hash,(guard_doc->>'physicalAccountId')::uuid,p_xid,p_pid,'{{}}'::jsonb,'sha256:'||repeat('0',64))
                RETURNING * INTO previous;
            END IF;
            IF previous.material_hash IS DISTINCT FROM p_material_hash OR previous.caller_xid IS DISTINCT FROM p_xid
              OR previous.caller_pid IS DISTINCT FROM p_pid OR previous.physical_account_id::text IS DISTINCT FROM guard_doc->>'physicalAccountId'
              OR previous.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(previous.body),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_WINDOW_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'immutable',previous.body,'contentHash',previous.content_hash,
              'initialCall',call_doc,'executionAllowed',false);
          END $window_stage$''',
        f'ALTER FUNCTION {STAGE_INITIAL_WINDOW} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {STAGE_INITIAL_WINDOW} FROM {denied}',
    )

READ_LIVE_PHYSICAL = 'public.read_shared_parent_live_physical_facts(uuid,text,xid8,integer)'

READ_UNRESOLVED_MEMBERS = 'public.read_shared_parent_unresolved_members(uuid)'

FINAL_PHYSICAL = 'public.verify_shared_parent_final_physical(uuid,text,xid8,integer)'


def shared_parent_final_physical_comparison_statements():
    """Compare sealed v2 physical facts without updating the native account.

    This necessary component does not establish Source currentness, engine
    drain completion, final clock, callback closure or execution permission.
    """
    s = PHYSICAL_SCHEMA
    return (
        f'''CREATE FUNCTION {FINAL_PHYSICAL.split('(')[0]}(
          p_plan uuid,p_receipt_hash text,p_xid xid8,p_pid integer) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $physical_compare$
          DECLARE receipt {s}.complete_receipt_v2%ROWTYPE;sealed jsonb;current_members jsonb;
          BEGIN
            IF {_end_authority_native_context_sql()} OR p_xid IS DISTINCT FROM pg_current_xact_id()
              OR p_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_FINAL_PHYSICAL_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO receipt FROM {s}.complete_receipt_v2 WHERE plan_id=p_plan FOR SHARE;
            sealed:=receipt.body->'physicalFacts';
            IF receipt.plan_id IS NULL OR receipt.org_id IS DISTINCT FROM 'org-org'
              OR receipt.project_id IS DISTINCT FROM 'dev-project'
              OR receipt.caller_xid IS DISTINCT FROM p_xid OR receipt.caller_pid IS DISTINCT FROM p_pid
              OR receipt.content_hash IS DISTINCT FROM p_receipt_hash
              OR receipt.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(receipt.body),'UTF8')),'hex')
              OR receipt.body->>'schemaVersion' IS DISTINCT FROM 'aos.shared-parent-complete-receipt-preparation/v2'
              OR receipt.body->>'planId' IS DISTINCT FROM p_plan::text
              OR receipt.body#>>'{{tenant,orgId}}' IS DISTINCT FROM 'org-org'
              OR receipt.body#>>'{{tenant,projectId}}' IS DISTINCT FROM 'dev-project'
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
              OR sealed->>'obligationHash' IS DISTINCT FROM receipt.body#>>'{{nodes,initialTargetObligation}}'
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
                AND member#>>'{{nativeRow,content_hash}}'=sealed->>'obligationHash') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_FINAL_PHYSICAL_SELF_REQUIRED' USING ERRCODE='23514'; END IF;
            current_members:={READ_UNRESOLVED_MEMBERS.split('(')[0]}(receipt.physical_account_id);
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
          END $physical_compare$''',
        f'ALTER FUNCTION {FINAL_PHYSICAL} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {FINAL_PHYSICAL} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
    )


def shared_parent_unresolved_member_statements():
    """Derive exact native membership; no Source or admission permission."""
    s = PHYSICAL_SCHEMA
    return (
        f'''CREATE FUNCTION {READ_UNRESOLVED_MEMBERS.split('(')[0]}(p_account uuid)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $members$
          DECLARE account_row {_physical.SCHEMA}.account_guard%ROWTYPE;
            members jsonb; total_requests bigint; total_tokens numeric; invalid_members bigint;
          BEGIN
            IF {_end_authority_native_context_sql()} THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_EXACT_MEMBER_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO account_row FROM {_physical.SCHEMA}.account_guard
              WHERE physical_account_id=p_account AND org_id='org-org' AND project_id='dev-project' FOR SHARE;
            IF NOT FOUND THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_EXACT_MEMBER_ACCOUNT_REQUIRED' USING ERRCODE='23514'; END IF;
            WITH native_members AS (
              SELECT 'legacyDebit'::text AS kind,d.debit_id::text AS member_id,
                to_jsonb(d) AS native_row,d.immutable AS original_body,d.content_hash,
                d.token_units AS tokens,d.org_id,d.project_id
              FROM {_physical.SCHEMA}.prepared_parent_debit d WHERE d.physical_account_id=p_account
              UNION ALL
              SELECT 'initialTarget',d.plan_id::text,to_jsonb(d),d.body,d.content_hash,
                d.token_upper_bound,d.org_id,d.project_id
              FROM {s}.initial_target_obligation d WHERE d.physical_account_id=p_account
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
          END $members$''',
        f'ALTER FUNCTION {READ_UNRESOLVED_MEMBERS} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {READ_UNRESOLVED_MEMBERS} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
    )


def shared_parent_exact_receipt_statements():
    """Explicit v2 preparation, preserving every original v1 artifact.

    A sealed member set is necessary for later pure comparison. Neither this
    package nor the membership reader supplies the full native ending.
    """
    statements = list(shared_parent_complete_receipt_statements())
    boundary = "            NEW.physical_account_id:=obligation.physical_account_id;"
    candidates = [i for i, sql in enumerate(statements)
                  if sql.startswith('CREATE FUNCTION ' + PHYSICAL_SCHEMA + '.bind_complete_receipt()')]
    if len(candidates) != 1 or statements[candidates[0]].count(boundary) != 1:
        raise ValueError('SHARED_ADMISSION_EXACT_RECEIPT_BINDING_BOUNDARY_REQUIRED')
    index = candidates[0]
    declaration = "pending jsonb;facts jsonb;intents jsonb;live jsonb;"
    if statements[index].count(declaration) != 1:
        raise ValueError('SHARED_ADMISSION_EXACT_RECEIPT_DECLARATION_REQUIRED')
    statements[index] = statements[index].replace(declaration, declaration + "member_set jsonb;", 1)
    addition = f'''            member_set:={READ_UNRESOLVED_MEMBERS.split('(')[0]}(obligation.physical_account_id);
            IF member_set->>'accountVersion' IS DISTINCT FROM live#>>'{{facts,accountVersion}}'
              OR member_set->>'unresolvedRequests' IS DISTINCT FROM live#>>'{{facts,unresolvedRequests}}'
              OR member_set->>'unresolvedTokenUpperBound' IS DISTINCT FROM live#>>'{{facts,unresolvedTokenUpperBound}}' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_MEMBER_TOTALS_CHANGED' USING ERRCODE='23514'; END IF;
            live:=jsonb_set(live,'{{facts}}',(live->'facts')||jsonb_build_object(
              'accountMapping',member_set->'accountMapping','unresolvedMembers',member_set->'unresolvedMembers',
              'unresolvedSetHash',member_set->'unresolvedSetHash'));
            live:=jsonb_set(live,'{{contentHash}}',to_jsonb('sha256:'||encode(sha256(convert_to(
              public.canonical_asset_registry_jsonb(live->'facts'),'UTF8')),'hex')));
'''
    statements[index] = statements[index].replace(boundary, addition + boundary, 1)
    replacements = (
        ('stage_shared_parent_complete_receipt', 'stage_shared_parent_complete_receipt_v2'),
        ('bind_complete_receipt', 'bind_complete_receipt_v2'),
        (PHYSICAL_SCHEMA + '.complete_receipt', PHYSICAL_SCHEMA + '.complete_receipt_v2'),
        ('aos.shared-parent-complete-receipt-preparation/v1', 'aos.shared-parent-complete-receipt-preparation/v2'),
    )
    for before, after in replacements:
        statements = [sql.replace(before, after) for sql in statements]
    # Both v1/v2 reuse the original closed Issuer origin delegate. Install the
    # chosen complete package once; this is not an automatic upgrade migration.
    return (*shared_parent_unresolved_member_statements(), *statements)


def shared_parent_live_physical_fact_statements():
    """Current original Source and old/new totals under an account write lock.

    This is one required ending fact, never a complete admission decision.
    The complete ending must still verify every node and all original authority.
    """
    s = PHYSICAL_SCHEMA
    return (
        f'''CREATE FUNCTION {READ_LIVE_PHYSICAL.split('(')[0]}(
          p_plan uuid,p_window_hash text,p_xid xid8,p_pid integer) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $live$
          DECLARE window_row {s}.initial_window_obligation%ROWTYPE;
            material {s}.initial_call_authority%ROWTYPE; obligation {s}.initial_target_obligation%ROWTYPE;
            packet jsonb; guard_doc jsonb; fact jsonb; body jsonb; guard_version bigint;
            used_requests bigint; used_tokens numeric; total_requests bigint; total_tokens numeric;
          BEGIN
            IF {_end_authority_native_context_sql()} OR p_xid IS DISTINCT FROM pg_current_xact_id()
              OR p_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_LIVE_PHYSICAL_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO window_row FROM {s}.initial_window_obligation WHERE plan_id=p_plan FOR SHARE;
            SELECT * INTO material FROM {s}.initial_call_authority WHERE plan_id=p_plan FOR SHARE;
            SELECT * INTO obligation FROM {s}.initial_target_obligation WHERE plan_id=p_plan FOR SHARE;
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
            guard_doc:={_physical.GUARD.split('(')[0]}(material.source_raw,packet->'sourceRef');
            -- Fresh original Source verification follows the actual account UPDATE wait.
            fact:={_physical.SOURCE_FACT.split('(')[0]}(material.source_raw,packet->'sourceRef');
            SELECT version INTO guard_version FROM {_physical.SCHEMA}.account_guard
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
              SELECT token_units FROM {_physical.SCHEMA}.prepared_parent_debit WHERE physical_account_id=obligation.physical_account_id
              UNION ALL SELECT token_upper_bound FROM {s}.initial_target_obligation WHERE physical_account_id=obligation.physical_account_id
            ) native_unresolved;
            used_requests:=total_requests-1;used_tokens:=total_tokens-obligation.token_upper_bound;
            IF used_requests<0 OR used_tokens<0 THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_LIVE_PHYSICAL_COUNTS_REQUIRED' USING ERRCODE='23514'; END IF;
            fact:=fact||jsonb_build_object('tokenUpperBound',obligation.token_upper_bound);
            {_physical._physical_call_capacity_guard_sql('target')}
            body:=jsonb_build_object('schemaVersion','aos.shared-parent-live-physical-facts/v1',
              'planId',p_plan,'windowSnapshotHash',p_window_hash,'initialCallAuthorityHash',material.content_hash,
              'obligationHash',obligation.content_hash,'physicalAccountId',obligation.physical_account_id,
              'accountVersion',guard_version,'sourceRef',packet->'sourceRef','maxConcurrency',fact->'maxConcurrency',
              'sourceTokenLimit',fact->'tokenLimit','unresolvedRequests',total_requests,'unresolvedTokenUpperBound',total_tokens,
              'observedAt',clock_timestamp(),'callerXid',p_xid::text,'callerPid',p_pid,
              'windowExpiryReleasesRisk',false,'executionAllowed',false);
            RETURN jsonb_build_object('facts',body,'contentHash','sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex'),
              'executionAllowed',false);
          END $live$''',
        f'ALTER FUNCTION {READ_LIVE_PHYSICAL} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {READ_LIVE_PHYSICAL} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
    )


STAGE_PARENT_RISK = 'public.stage_shared_parent_complete_risk(uuid,text,xid8,integer)'

STAGE_COMPLETE_RECEIPT = 'public.stage_shared_parent_complete_receipt(uuid,text,xid8,integer)'
READ_RECEIPT_ORIGIN = 'public.read_shared_parent_receipt_origin(uuid,text,xid8,integer)'


def shared_parent_receipt_origin_statements():
    """Expose only the original verified packet hash, retaining every check."""
    signature = READ_RETAINED.split('(')[0]
    definitions = [sql for sql in shared_parent_end_authority_statements()
                   if sql.startswith('CREATE FUNCTION ' + signature + '(')]
    if len(definitions) != 1:
        raise ValueError('SHARED_ADMISSION_RECEIPT_ORIGIN_DEFINITION_REQUIRED')
    body = definitions[0]
    boundary = "RETURN verified||jsonb_build_object('authorityMaterialHash',material.content_hash);"
    if body.count(boundary) != 1:
        raise ValueError('SHARED_ADMISSION_RECEIPT_ORIGIN_RETURN_BOUNDARY_REQUIRED')
    body = body.replace(boundary,
        "RETURN verified||jsonb_build_object('authorityMaterialHash',material.content_hash,"
        "'sourcePacketHash',body->>'sourcePacketHash');", 1)
    if re.search(r'\b(?:INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b', body, re.I):
        raise ValueError('SHARED_ADMISSION_RECEIPT_ORIGIN_DIRECT_WRITER_FORBIDDEN')
    body = body.replace('CREATE FUNCTION ' + signature + '(',
                        'CREATE FUNCTION ' + READ_RECEIPT_ORIGIN.split('(')[0] + '(', 1)
    return (body,
            f'ALTER FUNCTION {READ_RECEIPT_ORIGIN} OWNER TO {_certificate.ISSUER_OWNER}',
            f'REVOKE ALL ON FUNCTION {READ_RECEIPT_ORIGIN} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
            f'GRANT EXECUTE ON FUNCTION {READ_RECEIPT_ORIGIN} TO {OWNER}')


def shared_parent_complete_receipt_statements():
    """Derive all eight node bindings before drain; never admit execution.

    The current live account version is derived natively, not taken from the
    historical window. The immutable preparation retains risk on unknown
    outcomes and still requires the complete native end/COMMIT protocol.
    """
    s = PHYSICAL_SCHEMA
    table = s + '.complete_receipt'
    denied = 'PUBLIC,aos_runtime,aos_provider_capacity_issuer'
    nodes = (('initialTargetObligation', 'initial_target_obligation'),
             ('targetIntent', 'target_intent'), ('judgeDependency', 'judge_dependency'),
             ('initialCallAuthority', 'initial_call_authority'),
             ('initialWindowObligation', 'initial_window_obligation'),
             ('completeParentRisk', 'complete_parent_risk'))
    scan = '\n              UNION ALL '.join(
        f"SELECT '{name}' AS name,body,content_hash,caller_xid,caller_pid,org_id,project_id "
        f"FROM {s}.{relation} WHERE plan_id=NEW.plan_id" for name, relation in nodes)
    return (
        *shared_parent_receipt_origin_statements(),
        f'''CREATE TABLE {table}(
          plan_id uuid PRIMARY KEY REFERENCES {s}.initial_target_obligation(plan_id),
          org_id text NOT NULL CHECK(org_id='org-org'),project_id text NOT NULL CHECK(project_id='dev-project'),
          material_hash text NOT NULL CHECK(material_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          physical_account_id uuid NOT NULL,body jsonb NOT NULL,
          content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          caller_xid xid8 NOT NULL,caller_pid integer NOT NULL CHECK(caller_pid>0))''',
        f'ALTER TABLE {table} OWNER TO {OWNER}',
        f'REVOKE ALL ON {table} FROM {denied}',
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {table} TO {OWNER}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'''CREATE FUNCTION {s}.bind_complete_receipt() RETURNS trigger LANGUAGE plpgsql
          SET search_path=pg_catalog AS $receipt_binding$
          DECLARE obligation {s}.initial_target_obligation%ROWTYPE;
            target_row {s}.target_intent%ROWTYPE;judge_row {s}.judge_dependency%ROWTYPE;
            material {s}.initial_call_authority%ROWTYPE;window_row {s}.initial_window_obligation%ROWTYPE;
            risk_row {s}.complete_parent_risk%ROWTYPE;node record;count_nodes integer:=0;
            hashes jsonb:='{{}}'::jsonb;pending jsonb;facts jsonb;intents jsonb;live jsonb;
          BEGIN
            IF {_end_authority_native_context_sql()}
              OR NEW.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR NEW.caller_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO obligation FROM {s}.initial_target_obligation WHERE plan_id=NEW.plan_id FOR SHARE;
            SELECT * INTO target_row FROM {s}.target_intent WHERE plan_id=NEW.plan_id FOR SHARE;
            SELECT * INTO judge_row FROM {s}.judge_dependency WHERE plan_id=NEW.plan_id FOR SHARE;
            SELECT * INTO material FROM {s}.initial_call_authority WHERE plan_id=NEW.plan_id FOR SHARE;
            SELECT * INTO window_row FROM {s}.initial_window_obligation WHERE plan_id=NEW.plan_id FOR SHARE;
            SELECT * INTO risk_row FROM {s}.complete_parent_risk WHERE plan_id=NEW.plan_id FOR SHARE;
            FOR node IN {scan} LOOP
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
            pending:={READ_RECEIPT_ORIGIN.split('(')[0]}(NEW.plan_id,obligation.pending_hash,NEW.caller_xid,NEW.caller_pid);
            facts:=pending#>'{{immutable,origin,immutable,originalRisk,originalFacts}}';
            IF pending->>'sourcePacketHash' IS DISTINCT FROM material.body->>'sourcePacketHash'
              OR pending->>'sourcePacketHash' IS DISTINCT FROM 'sha256:'||encode(sha256(material.source_raw),'hex')
              OR risk_row.body->'originalRisk' IS DISTINCT FROM pending#>'{{immutable,origin,immutable,originalRisk}}'
              OR risk_row.body->>'originalRiskHash' IS DISTINCT FROM pending#>>'{{immutable,origin,immutable,originalRiskHash}}'
              OR risk_row.body->>'authorityMaterialHash' IS DISTINCT FROM pending->>'authorityMaterialHash'
              OR risk_row.target_hold::text IS DISTINCT FROM facts#>>'{{target,reservationId}}'
              OR risk_row.judge_hold::text IS DISTINCT FROM facts#>>'{{judge,reservationId}}'
              OR risk_row.target_request IS DISTINCT FROM facts#>>'{{target,requestId}}'
              OR risk_row.judge_request IS DISTINCT FROM facts#>>'{{judge,requestId}}'
              OR obligation.physical_account_id::text IS DISTINCT FROM facts#>>'{{target,physicalAccountId}}'
              OR obligation.physical_account_id::text IS DISTINCT FROM facts#>>'{{judge,physicalAccountId}}' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_ORIGINAL_RISK_REQUIRED' USING ERRCODE='23514'; END IF;
            intents:={FINAL_CALL.split('(')[0]}(NEW.plan_id,material.content_hash,NEW.caller_xid,NEW.caller_pid);
            IF intents->>'targetIntentHash' IS DISTINCT FROM target_row.content_hash
              OR intents->>'judgeDependencyHash' IS DISTINCT FROM judge_row.content_hash
              OR intents->>'initialCallAuthorityHash' IS DISTINCT FROM material.content_hash THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_CURRENT_INTENTS_REQUIRED' USING ERRCODE='23514'; END IF;
            -- This original account update/capacity check occurs before native drain.
            live:={READ_LIVE_PHYSICAL.split('(')[0]}(NEW.plan_id,window_row.content_hash,NEW.caller_xid,NEW.caller_pid);
            hashes:=hashes||jsonb_build_object('pendingOrigin',pending->>'contentHash',
              'endAuthority',pending->>'authorityMaterialHash');
            NEW.physical_account_id:=obligation.physical_account_id;
            NEW.body:=jsonb_build_object('schemaVersion','aos.shared-parent-complete-receipt-preparation/v1',
              'planId',NEW.plan_id,'tenant',jsonb_build_object('orgId',NEW.org_id,'projectId',NEW.project_id),
              'nodes',hashes,'originalRiskHash',risk_row.body->>'originalRiskHash',
              'sourcePacketHash',material.body->>'sourcePacketHash','physicalFacts',live->'facts',
              'physicalFactsHash',live->>'contentHash','callerLogin',session_user,
              'callerXid',NEW.caller_xid::text,'callerPid',NEW.caller_pid,
              'state','awaiting_complete_native_end','preparedAt',clock_timestamp(),
              'windowExpiryReleasesRisk',false,'unknownCommitRetainsRisk',true,'executionAllowed',false);
            NEW.content_hash:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(NEW.body),'UTF8')),'hex');
            RETURN NEW;
          END $receipt_binding$''',
        f'ALTER FUNCTION {s}.bind_complete_receipt() OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {s}.bind_complete_receipt() FROM {denied}',
        f'CREATE TRIGGER exact_complete_receipt BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.bind_complete_receipt()',
        f'CREATE TRIGGER immutable_complete_receipt BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.immutable_obligation()',
        f'CREATE TRIGGER no_truncate_complete_receipt BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {s}.immutable_obligation()',
        f'''CREATE CONSTRAINT TRIGGER require_complete_receipt_end AFTER INSERT ON {table}
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.require_complete_obligation()''',
        f'''CREATE FUNCTION {STAGE_COMPLETE_RECEIPT.split('(')[0]}(p_plan uuid,p_material_hash text,p_xid xid8,p_pid integer)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $receipt_stage$
          DECLARE previous {table}%ROWTYPE;pending jsonb;
          BEGIN
            IF {_end_authority_native_context_sql()} OR p_xid IS DISTINCT FROM pg_current_xact_id()
              OR p_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO previous FROM {table} WHERE plan_id=p_plan FOR SHARE;
            IF FOUND THEN RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_ALREADY_STAGED' USING ERRCODE='23514'; END IF;
            INSERT INTO {table}(plan_id,org_id,project_id,material_hash,caller_xid,caller_pid)
              VALUES(p_plan,'org-org','dev-project',p_material_hash,p_xid,p_pid) RETURNING * INTO previous;
            -- Revalidate original signed authority after all insertion/uniqueness/FK waits.
            pending:={READ_RECEIPT_ORIGIN.split('(')[0]}(p_plan,previous.body#>>'{{nodes,pendingOrigin}}',p_xid,p_pid);
            IF pending->>'authorityMaterialHash' IS DISTINCT FROM previous.body#>>'{{nodes,endAuthority}}'
              OR pending->>'sourcePacketHash' IS DISTINCT FROM previous.body->>'sourcePacketHash'
              OR pending#>>'{{immutable,origin,immutable,originalRiskHash}}' IS DISTINCT FROM previous.body->>'originalRiskHash' THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RECEIPT_POSTWAIT_ORIGIN_CHANGED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'immutable',previous.body,'contentHash',previous.content_hash,
              'persisted',true,'executionAllowed',false,'state','awaiting_complete_native_end');
          END $receipt_stage$''',
        f'ALTER FUNCTION {STAGE_COMPLETE_RECEIPT} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {STAGE_COMPLETE_RECEIPT} FROM {denied}',
    )


def shared_parent_complete_parent_risk_statements():
    """Persist the complete original two-parent risk, without charging it again.

    Current originals come only from the fixed retained-origin delegate. This
    pending ledger cannot finalize or upgrade a legacy prepared risk; the full
    admission end channel and independently authorized cutover remain required.
    """
    s = PHYSICAL_SCHEMA
    table = s + '.complete_parent_risk'
    denied = 'PUBLIC,aos_runtime,aos_provider_capacity_issuer'
    body_sql = """body:=jsonb_build_object('schemaVersion','aos.shared-parent-complete-risk/v1',
              'planId',p_plan,'pendingOriginHash',p_pending_hash,
              'authorityMaterialHash',pending->>'authorityMaterialHash',
              'originalRiskHash',pending#>>'{immutable,origin,immutable,originalRiskHash}',
              'originalRisk',pending#>'{immutable,origin,immutable,originalRisk}',
              'state','awaiting_full_admission','windowExpiryReleasesRisk',false,'executionAllowed',false);"""
    return (
        f'''CREATE TABLE {table}(
          plan_id uuid PRIMARY KEY,org_id text NOT NULL CHECK(org_id='org-org'),
          project_id text NOT NULL CHECK(project_id='dev-project'),
          target_request text NOT NULL,judge_request text NOT NULL,
          target_hold uuid NOT NULL,judge_hold uuid NOT NULL,
          physical_account_id uuid NOT NULL,pending_hash text NOT NULL,
          body jsonb NOT NULL,content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          caller_xid xid8 NOT NULL,caller_pid integer NOT NULL CHECK(caller_pid>0),
          UNIQUE(org_id,project_id,target_request,judge_request))''',
        f'ALTER TABLE {table} OWNER TO {OWNER}',
        f'REVOKE ALL ON {table} FROM {denied}',
        f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
        f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
        f'''CREATE POLICY exact_scope ON {table} TO {OWNER}
          USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
          WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))''',
        f'''CREATE FUNCTION {s}.bind_complete_parent_risk() RETURNS trigger LANGUAGE plpgsql
          SET search_path=pg_catalog AS $risk_binding$
          DECLARE risk jsonb:=NEW.body->'originalRisk'; facts jsonb:=risk->'originalFacts';
          BEGIN
            IF {_end_authority_native_context_sql()} THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RISK_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            IF NEW.body->>'schemaVersion' IS DISTINCT FROM 'aos.shared-parent-complete-risk/v1'
              OR NEW.body->>'planId' IS DISTINCT FROM NEW.plan_id::text
              OR NEW.body->>'pendingOriginHash' IS DISTINCT FROM NEW.pending_hash
              OR NEW.body->>'state' IS DISTINCT FROM 'awaiting_full_admission'
              OR NEW.body->'windowExpiryReleasesRisk' IS DISTINCT FROM 'false'::jsonb
              OR NEW.body->'executionAllowed' IS DISTINCT FROM 'false'::jsonb
              OR risk->>'schemaVersion' IS DISTINCT FROM 'aos.capacity-complete-plan-risk/v1'
              OR risk->>'planId' IS DISTINCT FROM NEW.plan_id::text
              OR risk->>'state' IS DISTINCT FROM 'prepared_risk_only'
              OR risk->'executionAllowed' IS DISTINCT FROM 'false'::jsonb
              OR risk->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',NEW.org_id,'projectId',NEW.project_id)
              OR risk->>'callerLogin' IS DISTINCT FROM session_user
              OR risk->>'callerXid' IS DISTINCT FROM NEW.caller_xid::text
              OR (risk->>'callerPid')::integer IS DISTINCT FROM NEW.caller_pid
              OR NEW.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR NEW.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR facts#>>'{{target,requestId}}' IS DISTINCT FROM NEW.target_request
              OR facts#>>'{{judge,requestId}}' IS DISTINCT FROM NEW.judge_request
              OR facts#>>'{{target,reservationId}}' IS DISTINCT FROM NEW.target_hold::text
              OR facts#>>'{{judge,reservationId}}' IS DISTINCT FROM NEW.judge_hold::text
              OR facts#>>'{{target,physicalAccountId}}' IS DISTINCT FROM NEW.physical_account_id::text
              OR facts#>>'{{judge,physicalAccountId}}' IS DISTINCT FROM NEW.physical_account_id::text
              OR NEW.body->>'originalRiskHash' IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(risk),'UTF8')),'hex')
              OR NEW.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(NEW.body),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RISK_BINDING_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN NEW;
          END $risk_binding$''',
        f'ALTER FUNCTION {s}.bind_complete_parent_risk() OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {s}.bind_complete_parent_risk() FROM {denied}',
        f'CREATE TRIGGER exact_complete_risk BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.bind_complete_parent_risk()',
        f'CREATE TRIGGER immutable_complete_risk BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {s}.immutable_obligation()',
        f'CREATE TRIGGER no_truncate_complete_risk BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {s}.immutable_obligation()',
        f'''CREATE CONSTRAINT TRIGGER require_complete_risk_end AFTER INSERT ON {table}
          DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {s}.require_complete_obligation()''',
        f'''CREATE FUNCTION {STAGE_PARENT_RISK.split('(')[0]}(p_plan uuid,p_pending_hash text,p_xid xid8,p_pid integer)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $risk_stage$
          DECLARE pending jsonb; facts jsonb; body jsonb; digest text; old_plan uuid;
            previous {table}%ROWTYPE;
          BEGIN
            IF {_end_authority_native_context_sql()} OR p_xid IS DISTINCT FROM pg_current_xact_id()
              OR p_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RISK_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            pending:={READ_RETAINED.split('(')[0]}(p_plan,p_pending_hash,p_xid,p_pid);
            facts:=pending#>'{{immutable,origin,immutable,originalRisk,originalFacts}}';
            SELECT plan_id INTO old_plan FROM {_physical.SCHEMA}.prepared_plan_risk
              WHERE org_id='org-org' AND project_id='dev-project'
                AND target_request=facts#>>'{{target,requestId}}'
                AND judge_request=facts#>>'{{judge,requestId}}' FOR SHARE;
            IF FOUND THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_LEGACY_RISK_PAIR_REQUIRES_CUTOVER' USING ERRCODE='23514'; END IF;
            {body_sql}
            digest:='sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8')),'hex');
            INSERT INTO {table}(plan_id,org_id,project_id,target_request,judge_request,target_hold,judge_hold,
              physical_account_id,pending_hash,body,content_hash,caller_xid,caller_pid)
              VALUES(p_plan,'org-org','dev-project',facts#>>'{{target,requestId}}',facts#>>'{{judge,requestId}}',
                (facts#>>'{{target,reservationId}}')::uuid,(facts#>>'{{judge,reservationId}}')::uuid,
                (facts#>>'{{target,physicalAccountId}}')::uuid,p_pending_hash,body,digest,p_xid,p_pid) ON CONFLICT DO NOTHING;
            SELECT * INTO previous FROM {table} WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR previous.body IS DISTINCT FROM body OR previous.content_hash IS DISTINCT FROM digest
              OR previous.pending_hash IS DISTINCT FROM p_pending_hash
              OR previous.caller_xid IS DISTINCT FROM p_xid OR previous.caller_pid IS DISTINCT FROM p_pid THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RISK_REPLAY_CONFLICT' USING ERRCODE='23514'; END IF;
            -- All possible ledger/legacy locks and uniqueness waits precede this full verification.
            IF {READ_RETAINED.split('(')[0]}(p_plan,p_pending_hash,p_xid,p_pid) IS DISTINCT FROM pending THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_RISK_CURRENTNESS_CHANGED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'immutable',body,'contentHash',digest,'executionAllowed',false);
          END $risk_stage$''',
        f'ALTER FUNCTION {STAGE_PARENT_RISK} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {STAGE_PARENT_RISK} FROM {denied}',
    )


COMPLETE_END_FACTS = 'public.read_shared_parent_complete_end_facts(uuid,text,xid8,integer)'


def shared_parent_complete_end_fact_statements():
    """Collect the original eight-node end facts without admitting execution.

    Reuse the exact v2 Receipt binding kernel, retaining all original Source,
    certificate, parent-risk and Intent checks. Physical state is compared,
    never produced here. Native drain/lifecycle, final deadline and durable
    confirmation still belong to the complete ending protocol.
    """
    schema = PHYSICAL_SCHEMA
    name = schema + '.bind_complete_receipt_v2()'
    definitions = [statement for statement in shared_parent_exact_receipt_statements()
                   if statement.startswith('CREATE FUNCTION ' + name)]
    if len(definitions) != 1:
        raise ValueError('SHARED_ADMISSION_COMPLETE_END_BINDER_REQUIRED')
    original = definitions[0]
    begin = '            SELECT * INTO obligation FROM '
    end = '            NEW.physical_account_id:=obligation.physical_account_id;'
    physical = f'''            -- This original account update/capacity check occurs before native drain.
            live:={READ_LIVE_PHYSICAL.split('(')[0]}(NEW.plan_id,window_row.content_hash,NEW.caller_xid,NEW.caller_pid);
'''
    origin_hashes = '''            hashes:=hashes||jsonb_build_object('pendingOrigin',pending->>'contentHash',
              'endAuthority',pending->>'authorityMaterialHash');
'''
    if any(original.count(marker) != 1 for marker in (begin, end, physical, origin_hashes)):
        raise ValueError('SHARED_ADMISSION_COMPLETE_END_BINDING_BOUNDARY_REQUIRED')
    declaration_start = '          DECLARE obligation '
    declaration_end = '          BEGIN\n'
    if original.count(declaration_start) != 1 or original.count(declaration_end) != 1:
        raise ValueError('SHARED_ADMISSION_COMPLETE_END_DECLARATION_REQUIRED')
    declarations = original[original.index(declaration_start):original.index(declaration_end)]
    kernel = original[original.index(begin):original.index(physical)] + origin_hashes
    if original.index(physical) >= original.index(end):
        raise ValueError('SHARED_ADMISSION_COMPLETE_END_PHYSICAL_BOUNDARY_REQUIRED')
    if re.search(r'\b(?:INSERT|UPDATE|DELETE|MERGE|TRUNCATE)\b', kernel, re.I):
        raise ValueError('SHARED_ADMISSION_COMPLETE_END_DIRECT_WRITER_FORBIDDEN')
    if READ_LIVE_PHYSICAL.split('(')[0] in kernel:
        raise ValueError('SHARED_ADMISSION_COMPLETE_END_PHYSICAL_PRODUCER_FORBIDDEN')
    kernel = kernel.replace('NEW.', 'receipt.')
    signature = COMPLETE_END_FACTS.split('(')[0]
    return (
        f'''CREATE FUNCTION {signature}(p_plan uuid,p_receipt_hash text,p_xid xid8,p_pid integer)
          RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER PARALLEL UNSAFE SET search_path=pg_catalog AS $end_facts$
{declarations}            receipt {schema}.complete_receipt_v2%ROWTYPE;physical_match jsonb;
          BEGIN
            IF {_end_authority_native_context_sql()} OR p_xid IS DISTINCT FROM pg_current_xact_id()
              OR p_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_COMPLETE_END_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO receipt FROM {schema}.complete_receipt_v2 WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR receipt.caller_xid IS DISTINCT FROM p_xid OR receipt.caller_pid IS DISTINCT FROM p_pid
              OR receipt.org_id IS DISTINCT FROM 'org-org' OR receipt.project_id IS DISTINCT FROM 'dev-project'
              OR receipt.content_hash IS DISTINCT FROM p_receipt_hash
              OR receipt.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(receipt.body),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_COMPLETE_END_RECEIPT_REQUIRED' USING ERRCODE='23514'; END IF;
{kernel}            IF hashes IS DISTINCT FROM receipt.body->'nodes'
              OR receipt.body->>'originalRiskHash' IS DISTINCT FROM risk_row.body->>'originalRiskHash'
              OR receipt.body->>'sourcePacketHash' IS DISTINCT FROM material.body->>'sourcePacketHash'
              OR receipt.physical_account_id IS DISTINCT FROM obligation.physical_account_id THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_COMPLETE_END_NODES_CHANGED' USING ERRCODE='23514'; END IF;
            physical_match:={FINAL_PHYSICAL.split('(')[0]}(p_plan,p_receipt_hash,p_xid,p_pid);
            IF physical_match->'physicalComparisonMatched' IS DISTINCT FROM 'true'::jsonb THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_COMPLETE_END_PHYSICAL_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'receiptHash',receipt.content_hash,
              'nodes',hashes,'originalRiskHash',receipt.body->>'originalRiskHash',
              'sourcePacketHash',receipt.body->>'sourcePacketHash','physicalComparison',physical_match,
              'factsReadAt',clock_timestamp(),'nativeEndRequired',true,
              'durableDeadlineEstablished',false,'executionAllowed',false);
          END $end_facts$''',
        f'ALTER FUNCTION {COMPLETE_END_FACTS} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {COMPLETE_END_FACTS} FROM PUBLIC,aos_runtime,aos_provider_capacity_issuer',
    )
