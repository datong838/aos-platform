from datetime import timedelta
from uuid import uuid4

import pytest

from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.data_requirement_store import DataRequirementStore, DataRequirementNotFound, canonical_revision_content_hash
from aos_api.db import connect, connect_serializable
from aos_api.ecommerce_data_requirement_query_applicability import ProductQueryApplicabilityReader
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_comparison_query import ProductComparisonQueryService
from aos_api.ecommerce_product_observation_comparison import ProductObservationComparisonReader
from aos_api.tenant_scope import TenantScope
from tests.test_data_requirement_store import requirement
from tests.test_ecommerce_product_comparison_query import inputs, product, SCOPE


def authorities(conn, *, defect=None):
    kwargs = inputs(conn)
    product(conn)
    tx = HostTransaction(conn)
    query_ref = ProductComparisonQueryService(tx, SCOPE).execute(**kwargs)
    connect = TransactionBoundConnectFactory(tx, SCOPE)
    query = AipAnalystQueryStore(connect_factory=connect).get(SCOPE, query_ref.resource_id).query
    item = requirement(requirement_id="applicability-" + uuid4().hex)
    item.channel_ref, item.entity_ref = kwargs["channel_ref"], kwargs["entity_ref"]
    item.required_facts = ["Product"]
    item.requested_outputs = ["EvidenceBundleRevision"]
    item.time_window.start_at, item.time_window.end_at = query.window_start, query.window_end
    item.cutoff_at = item.created_at = query.cutoff_at
    item.expires_at = query.cutoff_at + timedelta(days=1)
    if defect == "window": item.time_window.start_at -= timedelta(days=30)
    if defect == "cutoff":
        item.cutoff_at += timedelta(microseconds=1)
        item.created_at = item.cutoff_at
    if defect == "expired": item.expires_at = item.created_at + timedelta(microseconds=1)
    if defect == "future":
        item.created_at += timedelta(hours=1)
        item.expires_at += timedelta(hours=1)
    if defect in {"channel", "entity"}:
        getattr(item, defect + "_ref").content_hash = "sha256:" + "f" * 64
    if defect == "outputs": item.requested_outputs = ["DataProductRevision", "DatasetRevision", "OntologyHydrationRevision"]
    item.content_hash = canonical_revision_content_hash(item)
    store = DataRequirementStore(connect)
    result = store.request(SCOPE, item.created_by, item.requirement_id, item, expected_version=0)
    if defect == "cancelled":
        item.prior_ref = result.exact_ref
        item.revision = 2
        item.status = "cancelled"
        item = type(item).model_validate(item.model_dump())
        item.content_hash = canonical_revision_content_hash(item)
        result = store.cancel(SCOPE, item.created_by, item.requirement_id + "-cancel", item, expected_version=1)
    return result.exact_ref, query_ref, kwargs


def test_all_three_fields_matching_never_cover_product_and_diagnostic_only_reads(monkeypatch):
    with connect_serializable(SCOPE) as conn:
        req, query, _ = authorities(conn)
        result = ProductComparisonQueryService(HostTransaction(conn), SCOPE).read_exact(query)
        assert all(row.values["matched"] == 1 for row in result.rows)
        conn.execute("CREATE TEMP TABLE data_requirement_revision (LIKE public.data_requirement_revision INCLUDING ALL)")
        calls = []
        original = HostTransaction.execute
        def execute(self, sql, params=()):
            calls.append(sql)
            return original(self, sql, params)
        monkeypatch.setattr(HostTransaction, "execute", execute)
        def no_recompute(*args, **kwargs): raise AssertionError("diagnostic must not recompute")
        monkeypatch.setattr(ProductObservationComparisonReader, "compare", no_recompute)
        diagnostic = ProductQueryApplicabilityReader(HostTransaction(conn), SCOPE).read(requirement_ref=req, query_result_ref=query)
        assert diagnostic.status == "not_applicable"
        assert diagnostic.reasons == ("HISTORICAL_SNAPSHOT_UNAVAILABLE", "SOURCE_FRESHNESS_UNKNOWN", "QUERY_PARTIAL",
            "POPULATION_POLICY_UNRESOLVED", "FACT_RULE_UNRESOLVED:Product", "OUTPUT_ARTIFACT_NOT_PRODUCED:EvidenceBundleRevision")
        assert all(sql.lstrip().startswith(("SELECT", "SHOW")) for sql in calls)
        assert not hasattr(diagnostic, "satisfied")
        conn.rollback()
    with connect_serializable(SCOPE) as conn:
        with pytest.raises(DataRequirementNotFound, match="not found"):
            ProductQueryApplicabilityReader(HostTransaction(conn), SCOPE).read(requirement_ref=req, query_result_ref=query)


@pytest.mark.parametrize("defect,reason", [("window", "BUSINESS_WINDOW_NOT_COVERED"),
    ("cutoff", "CUTOFF_MISMATCH"), ("expired", "REQUIREMENT_EXPIRED"),
    ("future", "REQUIREMENT_NOT_YET_CREATED"), ("cancelled", "REQUIREMENT_NOT_EVALUABLE"),
    ("outputs", "OUTPUT_ARTIFACT_NOT_PRODUCED:DataProductRevision")])
def test_requirement_gaps_remain_explicit(defect, reason):
    with connect_serializable(SCOPE) as conn:
        req, query, _ = authorities(conn, defect=defect)
        diagnostic = ProductQueryApplicabilityReader(HostTransaction(conn), SCOPE).read(requirement_ref=req, query_result_ref=query)
        assert reason in diagnostic.reasons and "FACT_RULE_UNRESOLVED:Product" in diagnostic.reasons
        if defect == "future": assert "QUERY_PREDATES_REQUIREMENT" in diagnostic.reasons
        conn.rollback()


@pytest.mark.parametrize("defect", ["channel", "entity"])
def test_scope_mismatch_fails_before_diagnostic(defect):
    with connect_serializable(SCOPE) as conn:
        req, query, _ = authorities(conn, defect=defect)
        with pytest.raises(ValueError, match="selection drifted"):
            ProductQueryApplicabilityReader(HostTransaction(conn), SCOPE).read(requirement_ref=req, query_result_ref=query)
        conn.rollback()


def test_revoked_observation_and_canary_cannot_be_used():
    with connect_serializable(SCOPE) as conn:
        req, query, kwargs = authorities(conn)
        evidence = kwargs["evidence_ref"]
        conn.execute("""INSERT INTO public.aip_evidence_revoke_event
            (org_id,project_id,event_id,evidence_id,content_hash,reason,actor)
            VALUES(%s,%s,%s,%s,%s,'fixture revoke','user:fixture')""",
            (*SCOPE.key,"revoke-"+uuid4().hex,evidence.resource_id,evidence.content_hash[7:]))
        with pytest.raises(ValueError, match="revoked"):
            ProductQueryApplicabilityReader(HostTransaction(conn), SCOPE).read(requirement_ref=req, query_result_ref=query)
        with pytest.raises(DataRequirementNotFound, match="not found"):
            ProductQueryApplicabilityReader(HostTransaction(conn), TenantScope("dev-org", "dev-project")).read(
                requirement_ref=req, query_result_ref=query)
        conn.rollback()


def test_unstable_snapshot_is_rejected():
    with connect(SCOPE) as conn:
        with pytest.raises(ValueError, match="snapshot"):
            ProductQueryApplicabilityReader(HostTransaction(conn), SCOPE).read(requirement_ref=None, query_result_ref=None)
        conn.rollback()
