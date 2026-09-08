from datetime import UTC, datetime
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from aos_api.configured_source_observation import ConfiguredSourceObservation
from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
from aos_api.db import connect_serializable
from aos_api.ecom_core_models import CoreObjectRecord
from aos_api.ecommerce_business_investigation_case_selection import PostgresCanonicalShopSelectionSource
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_observation_comparison import ProductObservationComparisonReader
from aos_api.source_read_observation import observed_rows_hash
from tests.test_configured_source_observation_evidence import bound, SCOPE

NOW = datetime(2026, 9, 8, tzinfo=UTC)


def product(conn, external_id="1", **changes):
    external_id = "niushop:1:" + external_id
    props = {"shopId": "1", "title": "商品", "status": "active", "categoryId": "1",
        "createdAt": NOW.isoformat(), "updatedAt": NOW.isoformat(), "price": "12.00", "stock": "3"}
    props.update(changes)
    record = CoreObjectRecord(identity={"org_id": SCOPE.org_id,"workspace_id": SCOPE.project_id,
        "platform": "niushop", "shop_or_marketplace_id": "1", "external_id": external_id},
        object_type="Product",source_updated_at=NOW,source_timezone="UTC",
        status={"canonical_value": "active", "raw_status": "1", "unknown": False},properties=props)
    conn.execute("""INSERT INTO public.ecom_object
        (org_id,workspace_id,platform,shop_or_marketplace_id,object_type,external_id,properties,
         source_updated_at,source_timezone,canonical_status,raw_status,schema_version,payload_hash)
        VALUES(%s,%s,'niushop','1','Product',%s,%s,%s,'UTC','active','1',1,%s)""",
        (*SCOPE.key, external_id, Jsonb(record.properties), NOW, record.payload_hash()))


def setup(conn, rows):
    item = bound(conn, "comparison-" + uuid4().hex)
    raw = item.model_dump()
    raw["observation"].update(rows_hash=observed_rows_hash(rows), fetched_count=len(rows),
                              excluded_count=0,retained_count=len(rows))
    item = ConfiguredSourceObservation.model_validate(raw)
    tx = HostTransaction(conn)
    evidence = ConfiguredObservationEvidenceStore(tx, SCOPE).put(item, rows, actor="user:fixture")
    conn.execute("""INSERT INTO public.ecom_object
        (org_id,workspace_id,platform,shop_or_marketplace_id,object_type,external_id,
         source_updated_at,source_timezone,canonical_status,payload_hash)
        VALUES(%s,%s,'niushop','1','Shop','1',%s,'UTC','active',%s)""", (*SCOPE.key,NOW,"a"*64))
    selected = PostgresCanonicalShopSelectionSource(TransactionBoundConnectFactory(tx,SCOPE)).read(SCOPE)
    return lambda: ProductObservationComparisonReader(tx,SCOPE).compare(
        evidence_ref=evidence,rows=rows,channel_ref=selected.channel_ref,
        entity_ref=selected.business_entity_ref,binding_ref=selected.entity_channel_binding_ref)


def test_actual_sql_compares_fields_and_preserves_missing_populations():
    rows=[{"goods_id":1,"site_id":1,"goods_name":"商品","price":12,"goods_stock":3},
          {"goods_id":2,"site_id":1,"goods_name":"第二件","price":5,"goods_stock":2}]
    with connect_serializable(SCOPE) as conn:
        compare=setup(conn,rows)
        product(conn)
        product(conn,"3")
        result=compare()
        assert (result.source_count,result.canonical_count,result.common_count)==(2,2,1)
        assert result.only_source_count==result.only_canonical_count==1
        assert result.match_counts==(("title",1),("price",1),("stock",1))
        assert len(result.canonical_refs)==2
        conn.execute("UPDATE public.ecom_object SET properties=jsonb_set(properties,'{title}','\"drifted\"'::jsonb) WHERE object_type='Product'")
        with pytest.raises(ValueError,match="hash"):
            compare()
        conn.rollback()


@pytest.mark.parametrize("rows", [
    [{"goods_id":True,"site_id":1}], [{"goods_id":"1","site_id":1}],
    [{"goods_id":1,"site_id":2}], [{"goods_id":1,"site_id":1},{"goods_id":1,"site_id":1}],
])
def test_ambiguous_or_wrong_scope_identity_rejected(rows):
    with connect_serializable(SCOPE) as conn:
        compare=setup(conn,rows)
        with pytest.raises(ValueError):compare()
        conn.rollback()


@pytest.mark.parametrize("price,stock", [(None,None),(-1,-1),("NaN","3.5"),(True,True)])
def test_invalid_values_never_count_as_valid(price,stock):
    with connect_serializable(SCOPE) as conn:
        compare=setup(conn,[{"goods_id":1,"site_id":1,"goods_name":" ","price":price,"goods_stock":stock}])
        product(conn)
        result=compare()
        assert result.match_counts==(("title",0),("price",0),("stock",0))
        assert result.invalid_counts==(("title",1),("price",1),("stock",1))
        assert result.mismatch_counts==(("title",0),("price",0),("stock",0))
        conn.rollback()


def test_empty_populations_report_zero_without_success_claim():
    with connect_serializable(SCOPE) as conn:
        result=setup(conn,[])()
        assert result.source_count==result.canonical_count==result.common_count==0
        assert result.match_counts==(("title",0),("price",0),("stock",0))
        conn.rollback()


def test_empty_canonical_collection_cannot_accept_another_observation_shop():
    with connect_serializable(SCOPE) as conn:
        item = bound(conn, "comparison-" + uuid4().hex)
        raw = item.model_dump()
        raw["observation"].update(site_id=2,rows_hash=observed_rows_hash([]),fetched_count=0,retained_count=0,excluded_count=0)
        item = ConfiguredSourceObservation.model_validate(raw)
        tx = HostTransaction(conn)
        evidence = ConfiguredObservationEvidenceStore(tx,SCOPE).put(item,[],actor="user:fixture")
        setup(conn,[])
        selected=PostgresCanonicalShopSelectionSource(TransactionBoundConnectFactory(tx,SCOPE)).read(SCOPE)
        with pytest.raises(ValueError,match="shop"):
            ProductObservationComparisonReader(tx,SCOPE).compare(evidence_ref=evidence,rows=[],
                channel_ref=selected.channel_ref,entity_ref=selected.business_entity_ref,
                binding_ref=selected.entity_channel_binding_ref)
        conn.rollback()


def test_same_identity_but_different_values_are_mismatches():
    with connect_serializable(SCOPE) as conn:
        compare=setup(conn,[{"goods_id":1,"site_id":1,"goods_name":"另一标题","price":15,"goods_stock":8}])
        product(conn)
        result=compare()
        assert result.match_counts==result.invalid_counts==(("title",0),("price",0),("stock",0))
        assert result.mismatch_counts==(("title",1),("price",1),("stock",1))
        conn.rollback()


@pytest.mark.parametrize("column,value",[("platform","other"),("shop_or_marketplace_id","2")])
def test_empty_collection_still_rejects_changed_physical_shop(column,value):
    from psycopg import sql
    with connect_serializable(SCOPE) as conn:
        compare=setup(conn,[])
        conn.execute(sql.SQL("UPDATE public.ecom_object SET {}=%s WHERE object_type='Shop'").format(sql.Identifier(column)),(value,))
        with pytest.raises(ValueError,match="shop"):
            compare()
        conn.rollback()


def test_temporary_ecom_table_cannot_hide_canonical_population():
    with connect_serializable(SCOPE) as conn:
        compare=setup(conn,[{"goods_id":1,"site_id":1,"goods_name":"商品","price":12,"goods_stock":3}])
        product(conn)
        conn.execute("CREATE TEMP TABLE ecom_object (LIKE public.ecom_object INCLUDING DEFAULTS)")
        result=compare()
        assert result.canonical_count==result.common_count==1
        assert result.match_counts==(("title",1),("price",1),("stock",1))
        conn.rollback()
