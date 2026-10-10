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
