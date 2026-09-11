import os
from dataclasses import asdict

import pytest

from aos_api.ecommerce_product_content_snapshot import ProductContentSnapshotReader
from aos_api.ecommerce_growth_host_ports import HostTransaction
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database
from tests.test_ecommerce_product_joint_quality import inputs,row,SCOPE
from tests.test_ecommerce_product_observation_comparison import setup

pytestmark=pytest.mark.skipif(os.getenv('AOS_GROWTH_DRAFT_FULL_GRAPH_TEST')!='1',reason='explicit disposable database opt-in required')


@pytest.fixture
def connection():
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
            setup(conn,[])
            yield conn
            conn.rollback()


def test_candidates_use_all_valid_rows_and_explicit_stock_order(connection):
    rows=[row(i,goods_stock=i) for i in range(1,9)]
    value=ProductContentSnapshotReader(HostTransaction(connection),SCOPE).read(**inputs(connection,rows))
    assert value.quality.observed_count==value.quality.eligible_count==8
    assert value.quality.joint_valid_count==8 and value.preparable_product_count==8
    assert len(value.candidates)==5 and [item.product_id for item in value.candidates]==[8,7,6,5,4]
    body=asdict(value)
    assert all(set(item)=={'product_id','title','stock','observed_row_hash'} for item in body['candidates'])
    assert 'price' not in body['candidates'][0] and not hasattr(value,'ready') and not hasattr(value,'growth_rate')


def test_filter_before_dedup_and_invalid_rows_do_not_become_candidates(connection):
    rows=[row(1),row(1,is_delete=1),row(2),row(2,goods_stock=99),row(3,goods_stock=0),row(4,goods_name=''),row(None),row(5,goods_state=0)]
    value=ProductContentSnapshotReader(HostTransaction(connection),SCOPE).read(**inputs(connection,rows))
    assert (value.quality.observed_count,value.quality.excluded_count,value.quality.duplicate_count,value.quality.eligible_count)==(8,2,2,4)
    assert [item.product_id for item in value.candidates]==[1] and value.preparable_product_count==1


@pytest.mark.parametrize('change',[{'goods_stock':True},{'goods_stock':'2.5'},{'price':None},{'category_id':None},{'modify_time':0}])
def test_incomplete_goods_remain_in_quality_denominator(connection,change):
    value=ProductContentSnapshotReader(HostTransaction(connection),SCOPE).read(**inputs(connection,[row(**change)]))
    assert value.quality.eligible_count==1 and value.quality.joint_valid_count==0
    assert value.candidates==() and value.preparable_product_count==0


def test_zero_population_preserves_empty_measurement(connection):
    value=ProductContentSnapshotReader(HostTransaction(connection),SCOPE).read(**inputs(connection,[]))
    assert value.quality.eligible_count==0 and value.candidates==() and value.preparable_product_count==0
    assert value.limitations


def test_source_drift_and_scope_are_rejected(connection):
    args=inputs(connection,[row()])
    with pytest.raises(ValueError): ProductContentSnapshotReader(HostTransaction(connection),SCOPE).read(**dict(args,rows=[row(goods_name='changed')]))
    with pytest.raises(ValueError): ProductContentSnapshotReader(HostTransaction(connection),type(SCOPE)('dev-org','dev-project')).read(**args)


def test_top_five_is_stable_under_input_order_and_ties(connection):
    reader=ProductContentSnapshotReader(HostTransaction(connection),SCOPE)
    rows=[row(i) for i in range(1,8)]
    first=reader.read(**inputs(connection,rows))
    second=reader.read(**inputs(connection,list(reversed(rows))))
    assert first.candidates==second.candidates
    assert [x.product_id for x in first.candidates]==[1,2,3,4,5]


def test_unrepresentable_stock_is_rejected_without_integer_coercion(connection):
    with pytest.raises(ValueError,match='stock'):
        ProductContentSnapshotReader(HostTransaction(connection),SCOPE).read(**inputs(connection,[row(goods_stock='1e100')]))


def test_long_title_is_rejected_without_truncation(connection):
    with pytest.raises(ValueError,match='title'):
        ProductContentSnapshotReader(HostTransaction(connection),SCOPE).read(**inputs(connection,[row(goods_name='商'*4001)]))


@pytest.mark.parametrize('name',[
    'test_same_marginal_counts_cannot_determine_joint_validity',
    'test_filter_before_duplicate_quarantine_preserves_bad_denominator_and_order',
    'test_empty_population_is_zero_measurement_not_quality_pass',
    'test_wrong_spec_scope_selection_rows_and_revocation_rejected',
    'test_reader_rejects_unstable_snapshot_and_only_reads',
    'test_mutated_boolean_selection_revision_cannot_equal_integer_authority',
    'test_measurement_clock_cannot_precede_observation',
])
def test_existing_quality_regression_in_owned_database(monkeypatch,name):
    from contextlib import contextmanager
    import inspect
    from tests import test_ecommerce_product_joint_quality as legacy
    with disposable_database() as connect:
        @contextmanager
        def plain(scope):
            with connect(scope) as conn:
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
                yield conn
        @contextmanager
        def serial(scope):
            with connect(scope) as conn:
                conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
                yield conn
        monkeypatch.setattr(legacy,'connect',plain)
        monkeypatch.setattr(legacy,'connect_serializable',serial)
        test=getattr(legacy,name)
        test(**({'monkeypatch':monkeypatch} if 'monkeypatch' in inspect.signature(test).parameters else {}))
