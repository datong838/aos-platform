"""Read-only diagnostic of an exact requirement against the fixed product query.

A diagnostic is neither a current-head admission decision nor fulfillment.
The fixed query has no governed fact/population mapping or historical snapshot.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_store import DataRequirementStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_comparison_query import ProductComparisonQueryService
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True, slots=True)
class QueryApplicabilityDiagnostic:
    checked_at: datetime
    reasons: tuple[str, ...]
    status: Literal["not_applicable"] = "not_applicable"


class ProductQueryApplicabilityReader:
    def __init__(self, transaction: HostTransaction, scope: TenantScope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("query applicability requires HostTransaction and TenantScope")
        self._transaction, self._scope = transaction, scope

    def read(self, *, requirement_ref: InvestigationExactRef,
             query_result_ref: InvestigationExactRef) -> QueryApplicabilityDiagnostic:
        isolation = self._transaction.execute("SHOW transaction_isolation").fetchone()
        if isolation["transaction_isolation"] not in {"repeatable read", "serializable"}:
            raise ValueError("query applicability requires a stable transaction snapshot")
        connect = TransactionBoundConnectFactory(self._transaction, self._scope)
        requirement = DataRequirementStore(connect).get_exact(self._scope, requirement_ref)
        result = ProductComparisonQueryService(self._transaction, self._scope).read_exact(query_result_ref)
        if result is None:
            raise ValueError("fixed comparison query unavailable")
        query = AipAnalystQueryStore(connect_factory=connect).get(self._scope, result.query_id).query
        # The fixed query reader already validated the four filters and their
        # exact bodies against Metric, observation and stored query authorities.
        channel = InvestigationExactRef.model_validate(query.filters[1].value)
        entity = InvestigationExactRef.model_validate(query.filters[2].value)
        if requirement.channel_ref != channel or requirement.entity_ref != entity:
            raise ValueError("requirement and fixed query selection drifted")
        now = self._transaction.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        reasons = []
        if requirement.status.value not in {"requested", "accepted", "planned"} or requirement.blockers:
            reasons.append("REQUIREMENT_NOT_EVALUABLE")
        if now >= requirement.expires_at:
            reasons.append("REQUIREMENT_EXPIRED")
        if now < requirement.created_at:
            reasons.append("REQUIREMENT_NOT_YET_CREATED")
        if result.created_at < requirement.created_at:
            reasons.append("QUERY_PREDATES_REQUIREMENT")
        if (requirement.time_window.start_at != query.window_start
                or requirement.time_window.end_at != query.window_end):
            reasons.append("BUSINESS_WINDOW_NOT_COVERED")
        if requirement.cutoff_at != query.cutoff_at:
            reasons.append("CUTOFF_MISMATCH")
        reasons.extend(("HISTORICAL_SNAPSHOT_UNAVAILABLE", "SOURCE_FRESHNESS_UNKNOWN",
                        "QUERY_PARTIAL", "POPULATION_POLICY_UNRESOLVED"))
        reasons.extend("FACT_RULE_UNRESOLVED:" + fact for fact in requirement.required_facts)
        reasons.extend("OUTPUT_ARTIFACT_NOT_PRODUCED:" + output for output in requirement.requested_outputs)
        return QueryApplicabilityDiagnostic(checked_at=now, reasons=tuple(reasons))
