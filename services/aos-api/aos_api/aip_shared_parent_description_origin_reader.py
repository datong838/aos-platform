"""Same native caller description read only; no issuer or execution authority."""
import re
from uuid import UUID

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aos_api.aip_physical_capacity_occupation_authority import OWNER, SCHEMA
from aos_api.aip_physical_capacity_occupation_contracts import SharedParentRiskDescriptionPreparation
from aos_api.aip_model_eval_execution_contracts import ModelEvalTargetJudgeSharedRiskManifest
from aos_api.aip_model_eval_execution_owner import ModelEvalExecutionOwner, ModelEvalOwnerRejected
from aos_api.aip_provider_capacity_occupation_source import consume_capacity_source_for_occupation
from aos_api.aip_provider_capacity_source_consumer import _consumption_packet
from aos_api.tenant_scope import TenantScope

FUNCTION = 'public.read_capacity_shared_risk_description_origin(bytea,jsonb,uuid,text)'


def shared_description_origin_statements():
    """Explicit isolated installation; no direct table grants or mutations."""
    return (
        f'''CREATE FUNCTION {FUNCTION.split('(')[0]}(
          p_raw bytea,p_source jsonb,p_plan uuid,p_hash text) RETURNS jsonb
          LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $origin$
          DECLARE risk {SCHEMA}.prepared_plan_risk%ROWTYPE;
            doc {SCHEMA}.prepared_shared_risk_description%ROWTYPE; facts jsonb; again jsonb;
          BEGIN
            IF session_user<>'aos_provider_capacity_occupation'
              OR current_setting('transaction_isolation')<>'serializable'
              OR current_setting('transaction_read_only')<>'off'
              OR current_setting('TimeZone')<>'UTC'
              OR current_setting('session_replication_role')<>'origin'
              OR current_setting('aos.org_id',true) IS DISTINCT FROM 'org-org'
              OR current_setting('aos.project_id',true) IS DISTINCT FROM 'dev-project' THEN
              RAISE EXCEPTION 'SHARED_DESCRIPTION_NATIVE_CALLER_REQUIRED' USING ERRCODE='42501'; END IF;
            SELECT * INTO risk FROM {SCHEMA}.prepared_plan_risk WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR risk.org_id<>'org-org' OR risk.project_id<>'dev-project'
              OR risk.origin_xid IS DISTINCT FROM pg_current_xact_id()
              OR risk.origin_pid IS DISTINCT FROM pg_backend_pid() THEN
              RAISE EXCEPTION 'SHARED_DESCRIPTION_RISK_ORIGIN_REQUIRED' USING ERRCODE='23514'; END IF;
            SELECT * INTO doc FROM {SCHEMA}.prepared_shared_risk_description WHERE plan_id=p_plan FOR SHARE;
            IF NOT FOUND OR doc.org_id IS DISTINCT FROM risk.org_id OR doc.project_id IS DISTINCT FROM risk.project_id
              OR doc.origin_xid IS DISTINCT FROM risk.origin_xid OR doc.origin_pid IS DISTINCT FROM risk.origin_pid
              OR doc.content_hash IS DISTINCT FROM p_hash
              OR doc.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(doc.immutable),'UTF8')),'hex')
              OR risk.content_hash IS DISTINCT FROM 'sha256:'||encode(sha256(convert_to(public.canonical_asset_registry_jsonb(risk.immutable),'UTF8')),'hex')
              OR doc.immutable->>'originalRiskHash' IS DISTINCT FROM risk.content_hash
              OR doc.immutable->>'planId' IS DISTINCT FROM p_plan::text
              OR doc.immutable->'tenant' IS DISTINCT FROM risk.immutable->'tenant'
              OR doc.immutable->>'callerLogin' IS DISTINCT FROM session_user
              OR doc.immutable->>'callerXid' IS DISTINCT FROM pg_current_xact_id()::text
              OR doc.immutable->>'callerPid' IS DISTINCT FROM pg_backend_pid()::text
              OR doc.immutable->>'manifestHash' IS DISTINCT FROM encode(sha256(convert_to(public.canonical_asset_registry_jsonb(doc.immutable->'manifest'),'UTF8')),'hex') THEN
              RAISE EXCEPTION 'SHARED_DESCRIPTION_ORIGINAL_ROW_REQUIRED' USING ERRCODE='23514'; END IF;
            facts:=public.capacity_occupation_plan_risk_fact(p_raw,p_source,
              (risk.immutable->'originalFacts'->'target'->>'reservationId')::uuid,risk.target_request,
              risk.immutable->'originalFacts'->'target'->>'requestHash',
              (risk.immutable->'originalFacts'->'judge'->>'reservationId')::uuid,risk.judge_request,
              risk.immutable->'originalFacts'->'judge'->>'requestHash');
            IF facts IS DISTINCT FROM risk.immutable->'originalFacts'
              OR doc.immutable->'manifest'->'judgeRequest' IS DISTINCT FROM facts->'judge'->'application' THEN
              RAISE EXCEPTION 'SHARED_DESCRIPTION_CURRENT_FACT_REQUIRED' USING ERRCODE='23514'; END IF;
            again:=public.capacity_occupation_plan_risk_fact(p_raw,p_source,
              (facts->'target'->>'reservationId')::uuid,risk.target_request,facts->'target'->>'requestHash',
              (facts->'judge'->>'reservationId')::uuid,risk.judge_request,facts->'judge'->>'requestHash');
            IF again IS DISTINCT FROM facts THEN
              RAISE EXCEPTION 'SHARED_DESCRIPTION_FINAL_FACT_REQUIRED' USING ERRCODE='23514'; END IF;
            RETURN jsonb_build_object('planId',p_plan,'immutable',doc.immutable,'contentHash',doc.content_hash,'executionAllowed',false);
          END $origin$''',
        f'ALTER FUNCTION {FUNCTION} OWNER TO {OWNER}',
        f'REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC',
        f'GRANT EXECUTE ON FUNCTION {FUNCTION} TO aos_runtime',
    )


def read_shared_parent_description_origin(conn, scope, source_command, manifest, *,
        expected_content_hash, release_policy, artifact_bytes):
    """Read original uncommittable preparation, never create or authenticate calls."""
    try:
        if (type(conn) is not psycopg.Connection or conn.info.transaction_status != TransactionStatus.INTRANS
                or type(scope) is not TenantScope or scope.key != ('org-org','dev-project')
                or type(expected_content_hash) is not str
                or re.fullmatch(r'sha256:[0-9a-f]{64}',expected_content_hash) is None):
            raise ValueError('exact native origin reader arguments required')
        plan = ModelEvalTargetJudgeSharedRiskManifest.model_validate(manifest)
        packet = _consumption_packet(source_command)
        source = consume_capacity_source_for_occupation(conn,source_command)
        owner = ModelEvalExecutionOwner()
        owner.validate_original_target_judge_shared_risk_manifest(conn,scope,plan,
            release_policy=release_policy,artifact_bytes=artifact_bytes)
        with conn.cursor(row_factory=dict_row) as cur:
            row = cur.execute('SELECT public.read_capacity_shared_risk_description_origin(%s,%s::jsonb,%s::uuid,%s) AS fact',
                (packet,Jsonb(source_command.source_ref.model_dump(mode='json',by_alias=True)),UUID(plan.execution_id),expected_content_hash)).fetchone()
        description = SharedParentRiskDescriptionPreparation.model_validate(row['fact'])
        if description.content_hash != expected_content_hash or description.immutable.manifest != plan:
            raise ValueError('exact original full description required')
        owner.validate_original_target_judge_shared_risk_manifest(conn,scope,plan,
            release_policy=release_policy,artifact_bytes=artifact_bytes)
        final_source = consume_capacity_source_for_occupation(conn,source_command)
        with conn.cursor(row_factory=dict_row) as cur:
            current = cur.execute("""SELECT clock_timestamp() AS now,pg_current_xact_id()::text AS xid,
              pg_backend_pid() AS pid,session_user AS login,current_user AS role,
              current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project,
              current_setting('transaction_isolation') AS isolation,current_setting('transaction_read_only') AS readonly,
              current_setting('TimeZone') AS timezone,current_setting('session_replication_role') AS replication""").fetchone()
        if (source != final_source or packet != _consumption_packet(source_command)
                or not source.valid_from <= current['now'] < source.valid_until
                or (current['xid'],current['pid'],current['login'],current['role'],current['org'],current['project'],
                    current['isolation'],current['readonly'],current['timezone'],current['replication']) !=
                   (description.immutable.caller_xid,description.immutable.caller_pid,
                    'aos_provider_capacity_occupation','aos_runtime',*scope.key,'serializable','off','UTC','origin')):
            raise ValueError('current native original caller required after waits')
        return description
    except Exception:
        raise ModelEvalOwnerRejected('SHARED_DESCRIPTION_NATIVE_ORIGIN_REQUIRED') from None
