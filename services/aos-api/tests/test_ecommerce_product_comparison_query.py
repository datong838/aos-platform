from datetime import timedelta
from uuid import uuid4

import pytest

from aos_api.configured_source_observation import ConfiguredSourceObservation
from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
from aos_api.db import connect_serializable
from aos_api.errors import ApiError
from aos_api.ecommerce_business_investigation_case_selection import PostgresCanonicalShopSelectionSource
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_comparison_query import ProductComparisonQueryService
from aos_api.ecommerce_product_observation_comparison import ProductObservationComparisonReader
from aos_api.source_read_observation import observed_rows_hash
from tests.test_configured_source_observation_evidence import bound,SCOPE
from tests.test_ecommerce_product_observation_comparison import product,setup

ROWS=[{"goods_id":1,"site_id":1,"goods_name":"商品","price":12,"goods_stock":3}]


def inputs(conn,rows=ROWS):
    setup(conn,[])
    item=bound(conn,"query-source-"+uuid4().hex)
    raw=item.model_dump()
    raw["observation"].update(read_finished_at=item.observation.read_started_at+timedelta(microseconds=1),
        fetched_count=len(rows),excluded_count=0,retained_count=len(rows),rows_hash=observed_rows_hash(rows))
    tx=HostTransaction(conn)
    evidence=ConfiguredObservationEvidenceStore(tx,SCOPE).put(ConfiguredSourceObservation.model_validate(raw),rows,actor="user:fixture")
    selected=PostgresCanonicalShopSelectionSource(TransactionBoundConnectFactory(tx,SCOPE)).read(SCOPE)
    return dict(evidence_ref=evidence,rows=rows,channel_ref=selected.channel_ref,
        entity_ref=selected.business_entity_ref,binding_ref=selected.entity_channel_binding_ref,
        idempotency_key="query-"+uuid4().hex,actor="user:fixture")


def test_fixed_query_persists_actual_owners_replays_and_rolls_back(monkeypatch):
    with connect_serializable(SCOPE) as conn:
        kwargs=inputs(conn)
        product(conn)
        service=ProductComparisonQueryService(HostTransaction(conn),SCOPE)
        ref=service.execute(**kwargs)
        result=service.read_exact(ref)
        assert result.status.value=="partial" and len(result.rows)==3
        assert result.rows[0].values["matched"]==1
        assert len(result.source_refs)==2
        assert result.confidence.score is None
        conn.execute("UPDATE public.ecom_object SET properties='{}'::jsonb WHERE object_type='Product'")
        def no_recompute(*args,**kwargs):raise AssertionError("replay must not recompute")
        monkeypatch.setattr(ProductObservationComparisonReader,"compare",no_recompute)
        assert service.execute(**kwargs)==ref
        assert service.read_exact(ref)==result
        conn.rollback()
    with connect_serializable(SCOPE) as conn:
        assert ProductComparisonQueryService(HostTransaction(conn),SCOPE).read_exact(ref) is None


def test_same_key_changed_actor_conflicts():
    with connect_serializable(SCOPE) as conn:
        kwargs=inputs(conn)
        product(conn)
        service=ProductComparisonQueryService(HostTransaction(conn),SCOPE)
        service.execute(**kwargs)
        with pytest.raises(ApiError) as error:
            service.execute(**{**kwargs,"actor":"user:other"})
        assert error.value.code=="IDEMPOTENCY_CONFLICT"
        conn.rollback()


def test_replay_rejects_drifted_rows_and_replaced_observation():
    with connect_serializable(SCOPE) as conn:
        kwargs=inputs(conn)
        service=ProductComparisonQueryService(HostTransaction(conn),SCOPE)
        service.execute(**kwargs)
        with pytest.raises(ValueError,match="rows"):
            service.execute(**{**kwargs,"rows":[{"goods_id":2}]})
        original=ConfiguredObservationEvidenceStore(HostTransaction(conn),SCOPE).read_exact(kwargs["evidence_ref"])
        replacement=ConfiguredObservationEvidenceStore(HostTransaction(conn),SCOPE).put(
            original.observation,ROWS,actor="user:another-observer")
        with pytest.raises(ApiError) as error:
            service.execute(**{**kwargs,"evidence_ref":replacement})
        assert error.value.code=="IDEMPOTENCY_CONFLICT"
        conn.rollback()


def test_serializable_waiter_exits_old_snapshot_then_fresh_transaction_replays():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    import psycopg
    from aos_api.tenant_scope import TenantScope
    with connect_serializable(SCOPE) as conn:
        kwargs=inputs(conn)
        product(conn)
        ProductComparisonQueryService(HostTransaction(conn),SCOPE)._metric(ensure=True)
        conn.commit()
    try:
        barrier=Barrier(2)
        def run(_):
            try:
                with connect_serializable(SCOPE) as conn:
                    conn.execute("SELECT count(*) FROM public.ecom_object").fetchone()
                    barrier.wait(timeout=10)
                    result=ProductComparisonQueryService(HostTransaction(conn),SCOPE).execute(**kwargs)
                    conn.commit()
                    return result
            except (psycopg.errors.SerializationFailure,psycopg.errors.UniqueViolation) as error:
                if isinstance(error,psycopg.errors.UniqueViolation):
                    assert error.diag.constraint_name=="aip_analyst_query_job_pkey"
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,range(2)))
        assert sum(r is None for r in results)==1
        ref=next(r for r in results if r is not None)
        with connect_serializable(SCOPE) as conn:
            assert ProductComparisonQueryService(HostTransaction(conn),SCOPE).execute(**kwargs)==ref
        canary=TenantScope("dev-org","dev-project")
        with connect_serializable(canary) as conn:
            assert ProductComparisonQueryService(HostTransaction(conn),canary).read_exact(ref) is None
    finally:
        with connect_serializable(SCOPE) as conn:
            conn.execute("""DELETE FROM public.ecom_object WHERE org_id=%s AND workspace_id=%s
                AND platform='niushop' AND shop_or_marketplace_id='1'
                AND ((object_type='Shop' AND external_id='1') OR
                     (object_type='Product' AND external_id='niushop:1:1'))""",SCOPE.key)
            conn.commit()


def test_observation_revocation_blocks_query_read_and_replay():
    with connect_serializable(SCOPE) as conn:
        kwargs=inputs(conn)
        service=ProductComparisonQueryService(HostTransaction(conn),SCOPE)
        ref=service.execute(**kwargs)
        evidence=kwargs["evidence_ref"]
        conn.execute("""INSERT INTO public.aip_evidence_revoke_event
            (org_id,project_id,event_id,evidence_id,content_hash,reason,actor)
            VALUES(%s,%s,%s,%s,%s,'fixture revoke','user:fixture')""",
            (*SCOPE.key,"revoke-"+uuid4().hex,evidence.resource_id,evidence.content_hash[7:]))
        with pytest.raises(ValueError,match="revoked"):service.read_exact(ref)
        with pytest.raises(ValueError,match="revoked"):service.execute(**kwargs)
        conn.rollback()


@pytest.mark.parametrize("mutation",["confidence","boolean_count","wrong_partition"])
def test_fixed_reader_rejects_unhashed_confidence_or_invalid_counts(monkeypatch,mutation):
    from aos_api.aip_analyst_query_store import AipAnalystQueryStore
    with connect_serializable(SCOPE) as conn:
        kwargs=inputs(conn)
        service=ProductComparisonQueryService(HostTransaction(conn),SCOPE)
        ref=service.execute(**kwargs)
        actual=service.read_exact(ref)
        raw=actual.model_dump()
        if mutation=="confidence":raw["confidence"]={"status":"measured","score":1.0,"basis":["invented"]}
        elif mutation=="boolean_count":raw["rows"][0]["values"]["matched"]=False
        else:raw["rows"][0]["values"]["commonCount"]=1
        from aos_api.aip_analyst_contracts import QueryResultRevision
        changed=QueryResultRevision.model_validate(raw)
        monkeypatch.setattr(AipAnalystQueryStore,"read_result_exact",lambda *args:changed)
        with pytest.raises(ValueError):service.read_exact(ref)
        conn.rollback()


def test_raw_revision_boolean_alias_cannot_reuse_query_reference():
    from copy import deepcopy
    from tests.test_source_read_observation_evidence import Connection
    with connect_serializable(SCOPE) as conn:
        kwargs=inputs(conn)
        service=ProductComparisonQueryService(HostTransaction(conn),SCOPE)
        ref=service.execute(**kwargs)
        class RawDrift:
            def execute(self,sql,params=()):
                cursor=conn.execute(sql,params)
                if "result_json" in sql:
                    row=cursor.fetchone()
                    if row is not None and row.get("result_json") is not None:
                        row=deepcopy(row)
                        row["result_json"]["revision"]=True
                    return Connection(row)
                return cursor
        with pytest.raises(ValueError):
            ProductComparisonQueryService(HostTransaction(RawDrift()),SCOPE).read_exact(ref)
        conn.rollback()


def test_empty_query_is_partial_with_observation_source_and_zero_counts():
    with connect_serializable(SCOPE) as conn:
        kwargs=inputs(conn,[])
        service=ProductComparisonQueryService(HostTransaction(conn),SCOPE)
        result=service.read_exact(service.execute(**kwargs))
        assert result.status.value=="partial" and len(result.source_refs)==1
        assert all(row.values["sourceCount"]==row.values["canonicalCount"]==0 for row in result.rows)
        conn.rollback()


def test_zero_interval_is_not_replaced_by_an_invented_window():
    with connect_serializable(SCOPE) as conn:
        kwargs=inputs(conn)
        owner=ConfiguredObservationEvidenceStore(HostTransaction(conn),SCOPE)
        raw=owner.read_exact(kwargs["evidence_ref"]).observation.model_dump()
        raw["observation"]["read_finished_at"]=raw["observation"]["read_started_at"]
        kwargs["evidence_ref"]=owner.put(ConfiguredSourceObservation.model_validate(raw),ROWS,actor="user:fixture")
        with pytest.raises(ValueError,match="positive observation interval"):
            ProductComparisonQueryService(HostTransaction(conn),SCOPE).execute(**kwargs)
        conn.rollback()


def test_fixed_owners_ignore_temporary_metric_and_query_tables():
    from psycopg import sql
    with connect_serializable(SCOPE) as conn:
        kwargs=inputs(conn)
        for name in ("aip_metric_definition_revision","aip_analyst_query_job","aip_analyst_query_event",
                     "aip_analyst_query_receipt","aip_analyst_query_result_revision"):
            conn.execute(sql.SQL("CREATE TEMP TABLE {} (LIKE public.{} INCLUDING DEFAULTS)").format(sql.Identifier(name),sql.Identifier(name)))
        service=ProductComparisonQueryService(HostTransaction(conn),SCOPE)
        ref=service.execute(**kwargs)
        assert service.read_exact(ref) is not None
        assert conn.execute("SELECT count(*) AS n FROM pg_temp.aip_metric_definition_revision").fetchone()["n"]==0
        assert conn.execute("SELECT count(*) AS n FROM pg_temp.aip_analyst_query_job").fetchone()["n"]==0
        conn.rollback()


def test_old_comparison_and_query_reject_new_quality_input_policy():
    with connect_serializable(SCOPE) as conn:
        kwargs = inputs(conn)
        store = ConfiguredObservationEvidenceStore(HostTransaction(conn), SCOPE)
        raw = store.read_exact(kwargs["evidence_ref"]).observation.model_dump()
        raw["observation"].update(spec_id="niushop.product-quality-observation/v1",
            cleaning_version="niushop.product-quality-fields/v1")
        kwargs["evidence_ref"] = store.put(ConfiguredSourceObservation.model_validate(raw), ROWS, actor="user:fixture")
        with pytest.raises(ValueError, match="specification"):
            ProductComparisonQueryService(HostTransaction(conn), SCOPE).execute(**kwargs)
        comparison_args = {key: value for key, value in kwargs.items() if key not in {"idempotency_key", "actor"}}
        with pytest.raises(ValueError, match="specification"):
            ProductObservationComparisonReader(HostTransaction(conn), SCOPE).compare(**comparison_args)
        conn.rollback()
