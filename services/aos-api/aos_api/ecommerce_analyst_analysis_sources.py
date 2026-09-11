"""Read complete, authorized evidence material within the caller's transaction.

The returned body is sensitive input, not a Provider dispatch grant. Do not log
it or place it in generic task metadata. Later dispatch must enforce its own
current model, data, egress and budget authority.
"""
import json
from datetime import timedelta

from pydantic import Field

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_production_contracts import ResolveEvidenceDisclosureRequest, DisclosureLevel, DisclosurePurpose
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef


class AnalysisEvidenceGrant(AipContractModel):
    decision_id: str = Field(min_length=1, max_length=200)
    request: ResolveEvidenceDisclosureRequest


class AnalysisBundleSourceRequest(AipContractModel):
    bundle_ref: AnalystExactRef
    grants: list[AnalysisEvidenceGrant] = Field(min_length=1, max_length=100)


def _ref_key(ref):
    return ref.resource_type, ref.resource_id, ref.revision, ref.content_hash


def read_analysis_bundle(*, conn, scope, task_id, actor, request: AnalysisBundleSourceRequest,
                         markings, now, max_source_age: timedelta, max_bytes: int) -> dict:
    if (conn is None or not task_id.strip() or not actor.strip() or now.utcoffset() is None
            or max_source_age <= timedelta(0) or type(max_bytes) is not int or max_bytes < 1
            or not markings or any(not isinstance(x, str) or not x.strip() for x in markings)):
        raise ValueError("explicit transaction, task, actor, source lifetime, markings and byte limit required")
    ref = request.bundle_ref
    if ref.resource_type != "EvidenceBundleRevision":
        raise ValueError("analysis source must reference an exact evidence bundle")
    owner = AipProductionContractStore()
    bundle = owner.get_evidence_bundle(scope, ref.resource_id, ref.revision, conn=conn, markings=markings)
    if ((bundle.tenant.org_id, bundle.tenant.project_id) != scope.key
            or (bundle.bundle_id, bundle.revision, bundle.content_hash) != (ref.resource_id, ref.revision, ref.content_hash)
            or bundle.lifecycle != "frozen" or bundle.coverage != "complete" or bundle.freshness != "fresh"
            or bundle.revoked or not 1 <= len(bundle.item_refs) <= 100
            or bundle.cutoff_at.utcoffset() is None or bundle.cutoff_at > now
            or now - bundle.cutoff_at > max_source_age or bundle.brief_ref.resource_type != "TaskBriefRevision"):
        raise ValueError("current complete analysis evidence bundle required")
    brief = owner.get_brief(scope, bundle.brief_ref.resource_id, conn=conn)
    if ((brief.tenant.org_id, brief.tenant.project_id) != scope.key or brief.task_id != task_id
            or (brief.brief_id, brief.revision, brief.content_hash) != (bundle.brief_ref.resource_id, bundle.brief_ref.revision, bundle.brief_ref.content_hash)
            or brief.lifecycle != "frozen"):
        raise ValueError("analysis bundle must belong to the current frozen task brief")
    wanted = [_ref_key(item) for item in bundle.item_refs]
    if len(set(wanted)) != len(wanted) or any(item.resource_type != "Evidence" or item.revision != 1 for item in bundle.item_refs):
        raise ValueError("analysis bundle evidence inventory is invalid")
    grants = {}
    for grant in request.grants:
        body = grant.request
        key = _ref_key(body.evidence_ref)
        if (key in grants or body.task_id != task_id or body.purpose != DisclosurePurpose.SOURCE
                or body.requested_level != DisclosureLevel.L3):
            raise ValueError("analysis source grants must be unique original same-task source requests")
        grants[key] = grant
    if set(grants) != set(wanted):
        raise ValueError("analysis requires a disclosure grant for every exact bundle item")
    material = {"bundleRef": ref.model_dump(mode="json", by_alias=True), "cutoffAt": bundle.cutoff_at.isoformat(), "items": []}
    for key in wanted:
        grant = grants[key]
        item = owner.read_disclosed_evidence_source(conn, scope, actor, grant.decision_id, grant.request, markings=markings)
        material["items"].append(item)
        if len(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")) > max_bytes:
            raise ValueError("complete analysis material exceeds the explicit byte limit")
    return material
