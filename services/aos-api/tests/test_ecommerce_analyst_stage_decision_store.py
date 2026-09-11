from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import os
import pytest
import psycopg
from aos_api.ecommerce_analyst_stage_decision_store import AnalystStageDecisionStore,stage_decision_id
from aos_api.ecommerce_analyst_authority_store import canonical_hash,AnalystAuthorityStoreError
from aos_api.ecommerce_growth_host_ports import HostTransaction
from test_ecommerce_analyst_stage_decision import decision,SCOPE,NOW
from test_ecommerce_analyst_method_authority import apply_migrations
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database

pytestmark=pytest.mark.skipif(os.getenv('AOS_GROWTH_DRAFT_FULL_GRAPH_TEST')!='1',reason='explicit disposable database')


def hashed(item):return item.model_copy(update={'content_hash':canonical_hash(item.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))})


def item():
    value=decision()
    return hashed(value.model_copy(update={'decision_id':stage_decision_id(value)}))


def migrate(connect):
    apply_migrations(connect)
    path=Path(__file__).resolve().parents[1]/'alembic/versions/a0v_014_analyst_stage_decision.py'
    spec=importlib.util.spec_from_file_location('stage_decision_migration_test',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with connect(SCOPE) as conn:
        migration.op=SimpleNamespace(execute=conn.execute);migration.upgrade()


def test_atomic_concurrent_receipt_and_revoke_history():
    with disposable_database() as connect:
        migrate(connect);value=item()
        with pytest.raises(RuntimeError,match='rollback'):
            with connect(SCOPE) as conn:
                AnalystStageDecisionStore(HostTransaction(conn),SCOPE).put(value,actor=value.created_by,key='rolled-back',expected_version=0)
                raise RuntimeError('rollback')
        with connect(SCOPE) as conn:
            assert conn.execute('SELECT count(*) AS n FROM ecommerce_analyst_stage_decision_head').fetchone()['n']==0
        def put():
            with connect(SCOPE) as conn:
                return AnalystStageDecisionStore(HostTransaction(conn),SCOPE).put(value,actor=value.created_by,key='accept',expected_version=0)
        with ThreadPoolExecutor(max_workers=2) as pool:refs=list(pool.map(lambda _:put(),range(2)))
        assert refs[0]==refs[1]
        old=refs[0]
        revoked=hashed(value.model_copy(update={'revision':2,'version':2,'prior_ref':old,'decision':'revoke','expires_at':None,'created_at':NOW+timedelta(seconds=1)}))
        with connect(SCOPE) as conn:
            owner=AnalystStageDecisionStore(HostTransaction(conn),SCOPE)
            new=owner.put(revoked,actor=value.created_by,key='revoke',expected_version=1)
            assert owner.read_current(new)==revoked and owner.read_exact(old)==value
            with pytest.raises(ValueError):owner.read_current(old)
            assert owner.put(value,actor=value.created_by,key='accept',expected_version=0)==old
            assert conn.execute('SELECT count(*) AS n FROM ecommerce_analyst_stage_decision_revision').fetchone()['n']==2
        with pytest.raises((ValueError,AnalystAuthorityStoreError)):
            with connect(SCOPE) as conn:
                AnalystStageDecisionStore(HostTransaction(conn),SCOPE).put(hashed(value.model_copy(update={'reason':'different'})),actor=value.created_by,key='accept',expected_version=0)


def test_runtime_isolation_and_immutable_history():
    with disposable_database() as connect:
        migrate(connect);value=item()
        @contextmanager
        def runtime(scope):
            with connect(SCOPE) as conn:
                conn.execute('SET LOCAL ROLE aos_runtime')
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
                yield conn
        with runtime(SCOPE) as conn:
            owner=AnalystStageDecisionStore(HostTransaction(conn),SCOPE)
            ref=owner.put(value,actor=value.created_by,key='runtime',expected_version=0)
            assert owner.read_current(ref)==value
            assert not conn.execute("SELECT has_table_privilege(current_user,'ecommerce_analyst_stage_decision_revision','UPDATE') AS allowed").fetchone()['allowed']
        canary=type(SCOPE)('dev-org','dev-project')
        with runtime(canary) as conn:
            assert conn.execute('SELECT count(*) AS n FROM ecommerce_analyst_stage_decision_revision').fetchone()['n']==0
            with pytest.raises(ValueError):AnalystStageDecisionStore(HostTransaction(conn),canary).read_exact(ref)
        for statement in ["UPDATE ecommerce_analyst_stage_decision_revision SET created_by='other'",'DELETE FROM ecommerce_analyst_stage_decision_revision','TRUNCATE ecommerce_analyst_stage_decision_revision']:
            with pytest.raises(psycopg.Error):
                with connect(SCOPE) as conn:conn.execute(statement)


@pytest.mark.parametrize('fault',['hash','actor','target','future','revoke'])
def test_invalid_publication_leaves_no_head(fault):
    with disposable_database() as connect:
        migrate(connect);value=item();actor=value.created_by
        if fault=='hash':value=value.model_copy(update={'reason':'changed'})
        if fault=='actor':actor='other'
        if fault=='target':value=hashed(value.model_copy(update={'task_run_id':'other','stage_attempt_ref':value.stage_attempt_ref.model_copy(update={'run_id':'other'})}))
        if fault=='future':value=hashed(value.model_copy(update={'created_at':NOW+timedelta(days=30),'expires_at':NOW+timedelta(days=30,hours=1)}))
        if fault=='revoke':value=hashed(value.model_copy(update={'decision':'revoke','expires_at':None}))
        with connect(SCOPE) as conn:
            with pytest.raises(ValueError):AnalystStageDecisionStore(HostTransaction(conn),SCOPE).put(value,actor=actor,key='invalid',expected_version=0)
            assert conn.execute('SELECT count(*) AS n FROM ecommerce_analyst_stage_decision_head').fetchone()['n']==0
