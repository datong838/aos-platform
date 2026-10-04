"""Original canonical build evidence; no Owner, license or start authority."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from aos_api.aip_production_contracts import BuildEvidenceBundleRequest, ExactRevisionRef
from aos_api.tenant_scope import TenantScope


class BuildProvenanceUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class VerifiedBuildProvenance:
    source: ExactRevisionRef
    request_hash: str
    required_fact_ids: tuple[str, ...]
    authorization: str = 'BUILD_PROVENANCE_ONLY_NO_START'


def _require_scope(conn: Any, scope: TenantScope) -> None:
    if type(scope) is not TenantScope or conn.info.transaction_status != TransactionStatus.INTRANS:
        raise BuildProvenanceUnavailable('BUILD_PROVENANCE_CALLER_TRANSACTION_REQUIRED')
    row=conn.execute("SELECT current_setting('aos.org_id',true) AS org,"
        "current_setting('aos.project_id',true) AS project").fetchone()
    if row is None or (row['org'],row['project']) != scope.key:
        raise BuildProvenanceUnavailable('BUILD_PROVENANCE_SCOPE_MISMATCH')


def append_build_provenance(conn: Any, scope: TenantScope, bundle_id: str, key: str,
                            request_payload: dict[str, Any], authority_payload: dict[str, Any]) -> bool:
    """Keep generic pre-migration build compatibility; never retrofit a replay."""
    from aos_api.aip_production_contract_store import canonical_hash
    _require_scope(conn,scope)
    if conn.execute("SELECT to_regclass('public.aip_evidence_bundle_build_provenance') AS table_name").fetchone()['table_name'] is None:
        return False
    conn.execute("""INSERT INTO public.aip_evidence_bundle_build_provenance
        (org_id,project_id,bundle_id,revision,content_hash,idempotency_key,
         request_hash,request_payload,authority_payload)
        VALUES(%s,%s,%s,1,%s,%s,%s,%s,%s)""",
        (*scope.key,bundle_id,canonical_hash(authority_payload),key,
         canonical_hash(request_payload),Jsonb(request_payload),Jsonb(authority_payload)))
    return True


def _utc(value: datetime) -> datetime:
    # Legacy build accepts naive cutoff and interprets it as UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def read_build_provenance(conn: Any, scope: TenantScope, ref: ExactRevisionRef) -> VerifiedBuildProvenance:
    from aos_api.aip_production_contract_store import canonical_hash
    _require_scope(conn,scope)
    if not isinstance(ref,ExactRevisionRef) or ref.resource_type != 'EvidenceBundleRevision':
        raise BuildProvenanceUnavailable('BUILD_PROVENANCE_EXACT_REF_REQUIRED')
    if conn.execute("SELECT to_regclass('public.aip_evidence_bundle_build_provenance') AS table_name").fetchone()['table_name'] is None:
        raise BuildProvenanceUnavailable('BUILD_PROVENANCE_SCHEMA_UNAVAILABLE')
    args=(*scope.key,ref.resource_id,ref.revision,ref.content_hash)
    provenance=conn.execute("""SELECT * FROM public.aip_evidence_bundle_build_provenance
        WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s AND content_hash=%s""",args).fetchone()
    if provenance is None:
        raise BuildProvenanceUnavailable('BUILD_PROVENANCE_MISSING')
    evidence=conn.execute("""SELECT * FROM public.aip_evidence_bundle_revision
        WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s AND content_hash=%s""",args).fetchone()
    if evidence is None or evidence['lifecycle'] != 'frozen':
        raise BuildProvenanceUnavailable('BUILD_PROVENANCE_EXACT_FROZEN_MISSING')
    payload=provenance['request_payload']
    try:
        body=BuildEvidenceBundleRequest.model_validate(payload)
    except ValidationError as exc:
        raise BuildProvenanceUnavailable('BUILD_PROVENANCE_INPUT_INVALID') from exc
    if canonical_hash(body.model_dump(mode='json',by_alias=True)) != canonical_hash(payload):
        raise BuildProvenanceUnavailable('BUILD_PROVENANCE_INPUT_NOT_CANONICAL')
    if canonical_hash(payload) != provenance['request_hash']:
        raise BuildProvenanceUnavailable('BUILD_PROVENANCE_REQUEST_HASH_MISMATCH')
    fields={'briefRef':'brief_ref','subjectRefs':'subject_refs','itemRefs':'item_refs',
            'marking':'marking','licenseSummary':'license_summary'}
    if any(payload[key] != evidence[column] for key,column in fields.items()) or _utc(body.cutoff_at) != _utc(evidence['cutoff_at']):
        raise BuildProvenanceUnavailable('BUILD_PROVENANCE_SOURCE_FIELDS_MISMATCH')
    expected={**payload,**{key:evidence[key] for key in ('coverage','missing','conflicts','uncertainties','freshness')}}
    if canonical_hash(expected) != ref.content_hash or canonical_hash(provenance['authority_payload']) != ref.content_hash:
        raise BuildProvenanceUnavailable('BUILD_PROVENANCE_AUTHORITY_HASH_MISMATCH')
    receipt=conn.execute("""SELECT request_hash,result_ref FROM public.aip_production_contract_receipt
        WHERE org_id=%s AND project_id=%s AND operation='evidence_bundle.build' AND idempotency_key=%s""",
        (*scope.key,provenance['idempotency_key'])).fetchone()
    result={'resourceType':'EvidenceBundleRevision','resourceId':ref.resource_id,
            'revision':ref.revision,'contentHash':ref.content_hash}
    if receipt is None or receipt['request_hash'] != provenance['request_hash'] or receipt['result_ref'] != result:
        raise BuildProvenanceUnavailable('BUILD_PROVENANCE_RECEIPT_MISMATCH')
    return VerifiedBuildProvenance(ref,provenance['request_hash'],tuple(body.required_fact_ids))
