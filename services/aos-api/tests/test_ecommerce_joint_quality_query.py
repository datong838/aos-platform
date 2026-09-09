from datetime import timedelta
from uuid import uuid4

import pytest

from aos_api.configured_source_observation import ConfiguredSourceObservation
from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
from aos_api.db import connect_serializable
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_joint_quality_query import ProductJointQualityQueryService
from aos_api.ecommerce_product_joint_quality import ProductJointQualityReader
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope
from tests.test_ecommerce_product_joint_quality import inputs as measured_inputs, row, setup, SCOPE


def inputs(conn, rows=None):
    setup(conn, [])
    kwargs = measured_inputs(conn, [row()] if rows is None else rows)
    store = ConfiguredObservationEvidenceStore(HostTransaction(conn), SCOPE)
    raw = store.read_exact(kwargs["evidence_ref"]).observation.model_dump()
    raw["observation"]["read_finished_at"] += timedelta(microseconds=1)
    kwargs["evidence_ref"] = store.put(ConfiguredSourceObservation.model_validate(raw), kwargs["rows"], actor="user:fixture")
    return {**kwargs, "idempotency_key": "joint-query-"+uuid4().hex, "actor": "user:fixture"}


def test_joint_quality_query_roundtrip_replay_and_rollback(monkeypatch):
    with connect_serializable(SCOPE) as conn:
        kwargs = inputs(conn, [row(1, goods_name=""), row(2, price=-1)])
        service = ProductJointQualityQueryService(HostTransaction(conn), SCOPE)
        ref = service.execute(**kwargs)
        result = service.read_exact(ref)
        assert len(result.rows) == 8 and result.status.value == "partial"
        assert {r.values["jointValid"] for r in result.rows} == {0}
        assert {r.values["population"] for r in result.rows} == {2}
        assert len(result.source_refs) == 1 and result.source_refs[0].freshness == "unknown"
        def forbidden(*args, **kw): raise AssertionError("replay must not measure again")
        monkeypatch.setattr(ProductJointQualityReader, "read", forbidden)
        conn.execute("DELETE FROM public.ecom_object WHERE object_type='Shop'")
        assert service.execute(**kwargs) == ref
        assert service.read_exact(ref) == result
        conn.rollback()
    with connect_serializable(SCOPE) as conn:
        assert ProductJointQualityQueryService(HostTransaction(conn), SCOPE).read_exact(ref) is None


def test_joint_quality_zero_population_stays_partial():
    with connect_serializable(SCOPE) as conn:
        kwargs = inputs(conn, [])
        service = ProductJointQualityQueryService(HostTransaction(conn), SCOPE)
        result = service.read_exact(service.execute(**kwargs))
        assert result.status.value == "partial" and result.confidence.score is None
        assert all(v == 0 for r in result.rows for k, v in r.values.items() if k != "field")
        conn.rollback()


def test_joint_query_actor_rows_and_boolean_selection_cannot_drift():
    with connect_serializable(SCOPE) as conn:
        kwargs = inputs(conn)
        service = ProductJointQualityQueryService(HostTransaction(conn), SCOPE)
        service.execute(**kwargs)
        with pytest.raises(ApiError) as error:
            service.execute(**{**kwargs, "actor": "user:another"})
        assert error.value.code == "IDEMPOTENCY_CONFLICT"
        with pytest.raises(ValueError, match="rows"):
            service.execute(**{**kwargs, "rows": [row(price=99)]})
        kwargs["binding_ref"].revision = True
        with pytest.raises(ValueError, match="selection"): service.execute(**kwargs)
        conn.rollback()


def test_joint_query_exact_revocation_and_canary():
    with connect_serializable(SCOPE) as conn:
        kwargs = inputs(conn)
        service = ProductJointQualityQueryService(HostTransaction(conn), SCOPE)
        ref = service.execute(**kwargs)
        assert ProductJointQualityQueryService(HostTransaction(conn), TenantScope("dev-org", "dev-project")).read_exact(ref) is None
        evidence = kwargs["evidence_ref"]
        conn.execute("""INSERT INTO public.aip_evidence_revoke_event
            (org_id,project_id,event_id,evidence_id,content_hash,reason,actor)
            VALUES(%s,%s,%s,%s,%s,'fixture revoke','user:fixture')""",
            (*SCOPE.key,"revoke-"+uuid4().hex,evidence.resource_id,evidence.content_hash[7:]))
        with pytest.raises(ValueError, match="revoked"): service.read_exact(ref)
        with pytest.raises(ValueError, match="revoked"): service.execute(**kwargs)
        conn.rollback()


def test_joint_query_raw_boolean_revision_is_rejected():
    with connect_serializable(SCOPE) as conn:
        kwargs = inputs(conn)
        service = ProductJointQualityQueryService(HostTransaction(conn), SCOPE)
        ref = service.execute(**kwargs)
        from copy import deepcopy
        from tests.test_source_read_observation_evidence import Connection
        class RawDrift:
            def execute(self, sql, params=()):
                cursor = conn.execute(sql, params)
                if "result_json" in sql:
                    saved = cursor.fetchone()
                    if saved is not None and saved.get("result_json") is not None:
                        saved = deepcopy(saved)
                        saved["result_json"]["revision"] = True
                    return Connection(saved)
                return cursor
        with pytest.raises(ValueError, match="raw authority"):
            ProductJointQualityQueryService(HostTransaction(RawDrift()), SCOPE).read_exact(ref)
        conn.rollback()


def test_joint_query_zero_interval_rejected_before_query_job():
    with connect_serializable(SCOPE) as conn:
        setup(conn, [])
        kwargs = measured_inputs(conn, [row()])
        with pytest.raises(ValueError, match="positive observation interval"):
            ProductJointQualityQueryService(HostTransaction(conn), SCOPE).execute(
                **kwargs,idempotency_key="zero-"+uuid4().hex,actor="user:fixture")
        conn.rollback()


def test_joint_query_serializable_conflict_reconciles_in_fresh_transaction():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    import psycopg
    with connect_serializable(SCOPE) as conn:
        kwargs = inputs(conn)
        ProductJointQualityQueryService(HostTransaction(conn), SCOPE)._metric(ensure=True)
        conn.commit()
    try:
        barrier = Barrier(2)
        def run(_):
            try:
                with connect_serializable(SCOPE) as conn:
                    conn.execute("SELECT count(*) FROM public.ecom_object").fetchone()
                    barrier.wait(timeout=10)
                    ref = ProductJointQualityQueryService(HostTransaction(conn), SCOPE).execute(**kwargs)
                    conn.commit()
                    return ref
            except (psycopg.errors.SerializationFailure, psycopg.errors.UniqueViolation) as error:
                if isinstance(error, psycopg.errors.UniqueViolation):
                    assert error.diag.constraint_name == "aip_analyst_query_job_pkey"
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        assert sum(ref is None for ref in results) == 1
        original = next(ref for ref in results if ref is not None)
        with connect_serializable(SCOPE) as conn:
            assert ProductJointQualityQueryService(HostTransaction(conn), SCOPE).execute(**kwargs) == original
    finally:
        with connect_serializable(SCOPE) as conn:
            conn.execute("""DELETE FROM public.ecom_object WHERE org_id=%s AND workspace_id=%s
                AND platform='niushop' AND shop_or_marketplace_id='1' AND object_type='Shop' AND external_id='1'""", SCOPE.key)
            conn.commit()


def test_joint_query_refuses_different_executable_rule(monkeypatch):
    from aos_api import ecommerce_joint_quality_query as module
    with connect_serializable(SCOPE) as conn:
        kwargs = inputs(conn)
        service = ProductJointQualityQueryService(HostTransaction(conn), SCOPE)
        ref = service.execute(**kwargs)
        monkeypatch.setattr(module, "_RULE", ("invented", "1", "sha256:"+"0"*64))
        with pytest.raises(ValueError, match="request drifted"): service.read_exact(ref)
        conn.rollback()


@pytest.mark.parametrize("mutation", ["boolean", "joint", "duplicate", "impossible_joint"])
def test_joint_query_validates_fixed_count_contract_after_owner_read(monkeypatch, mutation):
    from copy import deepcopy
    from aos_api.aip_analyst_query_store import AipAnalystQueryStore
    from aos_api.aip_analyst_contracts import QueryResultRevision
    from tests.test_source_read_observation_evidence import Connection
    with connect_serializable(SCOPE) as conn:
        kwargs = inputs(conn)
        service = ProductJointQualityQueryService(HostTransaction(conn), SCOPE)
        ref = service.execute(**kwargs)
        raw = service.read_exact(ref).model_dump()
        for item in raw["rows"]:
            if mutation == "boolean": item["values"]["observed"] = True
            if mutation == "joint": item["values"]["jointValid"] = 2
            if mutation == "impossible_joint": item["values"]["jointValid"] = 0
            if mutation == "duplicate":
                item["values"].update(duplicate=1,eligible=0,population=0,jointValid=0,fieldValid=0)
        changed = QueryResultRevision.model_validate(raw)
        monkeypatch.setattr(AipAnalystQueryStore, "read_result_exact", lambda *args: changed)
        class ReturnedBodyDrift:
            def execute(self, sql, params=()):
                cursor = conn.execute(sql, params)
                if "SELECT r.result_json,j.request_json" in sql:
                    saved = deepcopy(cursor.fetchone())
                    saved["result_json"] = changed.model_dump(mode="json", by_alias=True)
                    return Connection(saved)
                return cursor
        with pytest.raises(ValueError, match="count type|population partition|joint intersection"):
            ProductJointQualityQueryService(HostTransaction(ReturnedBodyDrift()), SCOPE).read_exact(ref)
        conn.rollback()
