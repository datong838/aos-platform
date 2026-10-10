"""Original-fact entry for the complete versioned shared-parent admission.

Explicit SQL artifact only. The versioned risk ledger, certificates, trusted
end channel and native full admission matrix remain required before admission
can be exposed. Necessary facts are never execution permission.
"""
from aos_api.aip_physical_capacity_occupation_authority import OWNER, PLAN_FACT

FUNCTION = 'public.read_shared_parent_admission_original_facts(bytea,jsonb,uuid,text,text,uuid,text,text)'


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
