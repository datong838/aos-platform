"""Original-fact entry for the complete versioned shared-parent admission.

Explicit SQL artifact only. The versioned risk ledger, certificates, trusted
end channel and native full admission matrix remain required before admission
can be exposed. Necessary facts are never execution permission.
"""
from aos_api.aip_physical_capacity_occupation_authority import OWNER, PLAN_FACT
from aos_api import aip_shared_parent_certificate_prepare as _certificate
from aos_api import aip_physical_capacity_occupation_authority as _physical

FUNCTION = 'public.read_shared_parent_admission_original_facts(bytea,jsonb,uuid,text,text,uuid,text,text)'


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
{shared_parent_admission_certificate_validation_sql()}            IF {origin_call} IS DISTINCT FROM doc THEN
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
            verified:={CERTIFICATE_SET.split('(')[0]}(
              p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates);
            facts:=verified#>'{{origin,immutable,originalRisk,originalFacts}}';
            SELECT * INTO previous FROM {table} WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR previous.caller_xid IS DISTINCT FROM pg_current_xact_id()
              OR previous.caller_pid IS DISTINCT FROM pg_backend_pid()
              OR previous.content_hash IS DISTINCT FROM p_pending_hash
              OR previous.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(
                public.canonical_asset_registry_jsonb(previous.body),'UTF8')),'hex')
              OR previous.org_id IS DISTINCT FROM 'org-org'
              OR previous.project_id IS DISTINCT FROM 'dev-project'
              OR previous.physical_account_id::text IS DISTINCT FROM facts#>>'{{target,physicalAccountId}}'
              OR previous.physical_account_id::text IS DISTINCT FROM facts#>>'{{judge,physicalAccountId}}'
              OR previous.target_hold IS DISTINCT FROM p_target
              OR previous.judge_hold IS DISTINCT FROM p_judge
              OR previous.body->>'schemaVersion' IS DISTINCT FROM 'aos.shared-parent-pending-origin/v1'
              OR previous.body->'origin' IS DISTINCT FROM verified->'origin'
              OR previous.body->'certificates' IS DISTINCT FROM convert_from(p_certificates,'UTF8')::jsonb
              OR previous.body->>'certificateSetHash' IS DISTINCT FROM 'sha256:'||encode(sha256(p_certificates),'hex')
              OR previous.body->>'state' IS DISTINCT FROM 'awaiting_full_admission'
              OR previous.body->'executionAllowed' IS DISTINCT FROM 'false'::jsonb THEN
              RAISE EXCEPTION 'SHARED_ADMISSION_PENDING_ORIGIN_EXACT_HANDOFF_REQUIRED' USING ERRCODE='23514'; END IF;
            IF {CERTIFICATE_SET.split('(')[0]}(
              p_raw,p_source,p_target,p_tr,p_th,p_judge,p_jr,p_jh,p_plan,p_manifest,p_manifest_hash,p_certificates)
                IS DISTINCT FROM verified THEN
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
