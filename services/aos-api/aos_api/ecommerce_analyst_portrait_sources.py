"""Exact D01 authority metadata; this is not metric observation readiness.

Values and raw source disclosure must be validated separately before generation.
Every read uses the caller's transaction. Later dispatch must revalidate current
authority; a metric revision can be appended after this snapshot.
"""
from contextlib import contextmanager
from datetime import datetime

from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import CreateEvalContractRequest
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_analyst_growth_plan_sources import require_current_revision


def read_portrait_authorities(*, conn, scope, method_ref: AnalystExactRef,
                             metric_refs: list[AnalystExactRef], eval_ref: AnalystExactRef, now: datetime):
    if (conn is None or method_ref.resource_type != "MethodRevision"
            or eval_ref.resource_type != "EvalContractRevision"
            or not isinstance(metric_refs, list) or not 1 <= len(metric_refs) <= 100
            or any(ref.resource_type != "MetricDefinitionRevision" for ref in metric_refs)
            or len({ref.resource_id for ref in metric_refs}) != len(metric_refs)
            or not isinstance(now, datetime) or now.utcoffset() is None):
        raise ValueError("exact current method, unique metric definitions and eval contract required")

    @contextmanager
    def bound(requested_scope):
        if requested_scope != scope:
            raise ValueError("portrait authority transaction scope mismatch")
        yield conn

    method = require_current_revision(conn, scope, method_ref)
    metrics = []
    owner = AipEvalAuthorityStore(bound)
    for ref in metric_refs:
        definition = owner.get_metric_definition(scope, ref.resource_id, ref.revision)
        latest = conn.execute(
            "SELECT max(revision) AS revision FROM public.aip_metric_definition_revision WHERE org_id=%s AND project_id=%s AND metric_id=%s",
            (*scope.key, ref.resource_id),
        ).fetchone()
        if (latest is None or latest["revision"] != ref.revision or definition.content_hash != ref.content_hash
                or canonical_hash(definition.model_dump(mode="json", by_alias=True, exclude={"content_hash"})) != ref.content_hash):
            raise ValueError("portrait metric definition is stale or drifted")
        metrics.append(definition)
    head = conn.execute(
        "SELECT current_revision FROM public.aip_eval_contract_head WHERE org_id=%s AND project_id=%s AND contract_id=%s FOR SHARE",
        (*scope.key, eval_ref.resource_id),
    ).fetchone()
    if head is None or head["current_revision"] != eval_ref.revision:
        raise ValueError("current portrait eval contract unavailable")
    contract = AipProductionContractStore(bound).get_eval_contract(scope, eval_ref.resource_id, conn=conn)
    original = CreateEvalContractRequest(**{name: getattr(contract, name) for name in CreateEvalContractRequest.model_fields})
    if ((contract.tenant.org_id, contract.tenant.project_id) != scope.key
            or contract.contract_id != eval_ref.resource_id or contract.revision != eval_ref.revision
            or contract.content_hash != eval_ref.content_hash
            or contract.lifecycle != "frozen" or contract.readiness != "ready" or contract.blockers
            or canonical_hash(original.model_dump(mode="json", by_alias=True)) != eval_ref.content_hash):
        raise ValueError("portrait eval contract is unavailable or drifted")
    gate_ref = contract.release_gate_ref
    if gate_ref is None:
        raise ValueError("portrait eval release gate missing")
    gate = conn.execute(
        "SELECT status,decision_hash,decided_at,expires_at FROM public.aip_release_gate_decision WHERE org_id=%s AND project_id=%s AND decision_id=%s",
        (*scope.key, gate_ref.resource_id),
    ).fetchone()
    if (gate is None or gate["status"] != "passed" or gate["decision_hash"] != gate_ref.content_hash
            or gate["decided_at"] is None or gate["expires_at"] is None
            or gate["decided_at"].utcoffset() is None or gate["expires_at"].utcoffset() is None
            or not gate["decided_at"] <= now < gate["expires_at"]):
        raise ValueError("portrait eval release gate is expired or unavailable")
    return method, metrics, contract
