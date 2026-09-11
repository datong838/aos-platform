"""Read-only, scoped source checks for a later transactional draft receiver."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef, DecisionSummaryRevision, InsightRevision, MethodRevision
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.tenant_scope import TenantScope


def require_current_revision(conn: Any, scope: TenantScope, ref: AnalystExactRef):
    """Resolve only allowlisted current revisions, holding the head until commit."""
    kinds = {
        "DecisionSummaryRevision": ("decision", "decision_id", DecisionSummaryRevision),
        "InsightRevision": ("insight", "insight_id", InsightRevision),
        "MethodRevision": ("method", "method_id", MethodRevision),
    }
    if ref.resource_type not in kinds:
        raise ValueError("unsupported analyst source kind")
    table, identity, model = kinds[ref.resource_type]
    row = conn.execute(
        f"""SELECT revision.payload,revision.content_hash
        FROM ecommerce_analyst_{table}_head head
        JOIN ecommerce_analyst_{table}_revision revision
          ON revision.org_id=head.org_id AND revision.project_id=head.project_id
         AND revision.{identity}=head.{identity} AND revision.revision=head.current_revision
        WHERE head.org_id=%s AND head.project_id=%s AND head.{identity}=%s
          AND head.current_revision=%s FOR SHARE OF head""",
        (*scope.key, ref.resource_id, ref.revision),
    ).fetchone()
    if row is None or row["content_hash"] != ref.content_hash:
        raise ValueError("current analyst exact source unavailable")
    item = model.model_validate(row["payload"])
    if ((item.tenant.org_id, item.tenant.project_id) != scope.key
            or getattr(item, identity) != ref.resource_id or item.revision != ref.revision
            or item.content_hash != ref.content_hash
            or canonical_hash(item.model_dump(mode="json", by_alias=True, exclude={"content_hash"})) != ref.content_hash):
        raise ValueError("analyst source payload authority mismatch")
    return item


def require_growth_plan_sources(conn: Any, scope: TenantScope, ref: AnalystExactRef, *,
                                markings: list[str], now: datetime,
                                max_source_age: timedelta) -> DecisionSummaryRevision:
    """Validate current sources in the caller's transaction without writing.

    This is a snapshot check. Approval and execution must revalidate evidence;
    reading cannot prevent a subsequent revocation from being committed.
    """
    if (now.utcoffset() is None or max_source_age <= timedelta(0)
            or not markings or any(not isinstance(value, str) or not value.strip() for value in markings)):
        raise ValueError("explicit source lifetime, clock and markings required")
    if ref.resource_type != "DecisionSummaryRevision":
        raise ValueError("growth plan source must be a DecisionSummaryRevision")
    decision = require_current_revision(conn, scope, ref)
    insight = require_current_revision(conn, scope, decision.insight_ref)
    if insight.cutoff_at > now or now - insight.cutoff_at > max_source_age:
        raise ValueError("insight source cutoff is stale or future")
    # No fallback connection is used: every production read receives conn.
    store = AipProductionContractStore()
    refs = { (source.resource_id, source.revision, source.content_hash): source
             for source in [*decision.evidence_refs, *insight.evidence_refs] }
    for source in refs.values():
        bundle = store.get_evidence_bundle(scope, source.resource_id, source.revision,
                                           conn=conn, markings=markings)
        if ((bundle.tenant.org_id, bundle.tenant.project_id) != scope.key
                or bundle.content_hash != source.content_hash or bundle.lifecycle != "frozen"
                or bundle.coverage != "complete" or bundle.freshness != "fresh"
                or bundle.revoked or not bundle.item_refs
                or bundle.cutoff_at.utcoffset() is None or bundle.cutoff_at > now
                or now - bundle.cutoff_at > max_source_age):
            raise ValueError("evidence bundle is unavailable for current planning")
        brief = store.get_brief(scope, bundle.brief_ref.resource_id, conn=conn)
        if (brief.revision != bundle.brief_ref.revision or brief.content_hash != bundle.brief_ref.content_hash
                or brief.lifecycle != "frozen"):
            raise ValueError("evidence bundle brief is no longer current")
        for evidence in bundle.item_refs:
            if evidence.resource_type != "Evidence" or evidence.revision != 1:
                raise ValueError("unsupported evidence reference")
            row = conn.execute(
                """SELECT evidence.content_hash,evidence.freshness_at,evidence.payload,
                     EXISTS(SELECT 1 FROM public.aip_evidence_revoke_event revoked
                      WHERE revoked.org_id=evidence.org_id AND revoked.project_id=evidence.project_id
                        AND revoked.evidence_id=evidence.evidence_id AND revoked.revision=1
                        AND revoked.content_hash=evidence.content_hash) AS revoked
                FROM public.aip_evidence evidence
                WHERE evidence.org_id=%s AND evidence.project_id=%s AND evidence.evidence_id=%s""",
                (*scope.key, evidence.resource_id),
            ).fetchone()
            if row is None or row["content_hash"] != evidence.content_hash or row["revoked"]:
                raise ValueError("underlying evidence unavailable or revoked")
            fresh = row["freshness_at"]
            if (fresh is None or fresh.utcoffset() is None or fresh > now
                    or fresh < bundle.cutoff_at or now - fresh > max_source_age):
                raise ValueError("underlying evidence freshness is unavailable")
            payload = row["payload"]
            if not isinstance(payload, dict):
                raise ValueError("underlying evidence payload unavailable")
            required = payload.get("marking", ["public"])
            if (not isinstance(required, list) or not all(isinstance(value, str) and value.strip() for value in required)
                    or not set(required or ["public"]).issubset(set(markings))):
                raise ValueError("underlying evidence marking is not allowed")
    return decision
