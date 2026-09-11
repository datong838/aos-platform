from contextlib import contextmanager
from decimal import Decimal
import os

import pytest

from aos_api.ecommerce_product_content_evidence import ProductContentEvidenceStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import ResolveEvidenceDisclosureRequest,RevokeEvidenceRequest
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database
from tests.test_ecommerce_product_joint_quality import inputs,row,SCOPE
from tests.test_ecommerce_product_observation_comparison import setup

pytestmark=pytest.mark.skipif(os.getenv('AOS_GROWTH_DRAFT_FULL_GRAPH_TEST')!='1',reason='explicit disposable database opt-in required')


@contextmanager
def database():
    with disposable_database() as raw:
        @contextmanager
        def connect(scope):
            with raw(SCOPE) as conn:
                conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
                yield conn
        yield connect


def prepared(connect,rows):
    with connect(SCOPE) as conn:
        setup(conn,[])
        return inputs(conn,rows)


@pytest.mark.parametrize('revoke_target',['configured','original','root'])
def test_roundtrip_replay_and_upstream_revoke_blocks_disclosure(revoke_target):
    with database() as connect:
        args=prepared(connect,[row(price=Decimal('12.00'))])
        with connect(SCOPE) as conn:
            owner=ProductContentEvidenceStore(HostTransaction(conn),SCOPE)
            ref=owner.put(**args,actor='actor')
            first=owner.read_exact(ref)
            assert first.rows[0]['price']==Decimal('12.00') and isinstance(first.rows[0]['price'],Decimal)
            assert first.snapshot.preparable_product_count==1
        with connect(SCOPE) as conn:
            owner=ProductContentEvidenceStore(HostTransaction(conn),SCOPE)
            assert owner.put(**args,actor='actor')==ref
            assert owner.read_exact(ref).snapshot==first.snapshot
        # Source Evidence can be prepared before a TaskRun, with an actual Task
        # available for disclosure purpose binding once execution is prepared.
        from aos_api.aip_task_store import AipTaskStore
        from test_aip_taor_lease_adapter import running_run
        run=running_run(AipTaskStore(connect_factory=connect))
        production=AipProductionContractStore(connect)
        body=ResolveEvidenceDisclosureRequest(evidenceRef=ref.model_dump(mode='json',by_alias=True),purpose='source',requestedLevel='l3',taskId=run.task_id)
        grant=production.resolve_evidence_disclosure(SCOPE,'actor','snapshot-grant',body,markings=['internal','secret'])
        assert grant.status.value=='allowed'
        with connect(SCOPE) as conn:
            production.read_disclosed_evidence_source(conn,SCOPE,'actor',grant.decision_id,body,markings=['internal','secret'])
        upstream=args['evidence_ref']
        if revoke_target=='original':
            from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
            with connect(SCOPE) as conn:
                upstream=ConfiguredObservationEvidenceStore(HostTransaction(conn),SCOPE).read_exact(upstream).observation_evidence_ref
        if revoke_target=='root': upstream=ref
        production.revoke_evidence(SCOPE,'actor',upstream.resource_id,'snapshot-source-revoke',RevokeEvidenceRequest(expectedContentHash=upstream.content_hash.removeprefix('sha256:'),reason='synthetic source withdrawal'))
        with connect(SCOPE) as conn:
            with pytest.raises(ValueError): ProductContentEvidenceStore(HostTransaction(conn),SCOPE).read_exact(ref)
            with pytest.raises(RuntimeError): production.read_disclosed_evidence_source(conn,SCOPE,'actor',grant.decision_id,body,markings=['internal','secret'])


def test_scope_and_extra_fields_fail_closed():
    with database() as connect:
        args=prepared(connect,[row(unapproved_private_field='must-not-be-stored')])
        with connect(SCOPE) as conn:
            with pytest.raises(ValueError): ProductContentEvidenceStore(HostTransaction(conn),SCOPE).put(**args,actor='actor')
            assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='product-content-snapshot'").fetchone()['n']==0
            with pytest.raises(ValueError): ProductContentEvidenceStore(HostTransaction(conn),type(SCOPE)('dev-org','dev-project')).put(**args,actor='actor')


def test_outer_rollback_leaves_no_snapshot():
    with database() as connect:
        args=prepared(connect,[row()])
        with pytest.raises(RuntimeError,match='rollback'):
            with connect(SCOPE) as conn:
                ProductContentEvidenceStore(HostTransaction(conn),SCOPE).put(**args,actor='actor')
                raise RuntimeError('rollback')
        with connect(SCOPE) as conn:
            assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='product-content-snapshot'").fetchone()['n']==0


def test_concurrent_replay_preserves_first_snapshot():
    from concurrent.futures import ThreadPoolExecutor
    from psycopg.errors import SerializationFailure
    with database() as connect:
        args=prepared(connect,[row()])
        def save():
            for attempt in range(3):
                try:
                    with connect(SCOPE) as conn:
                        owner=ProductContentEvidenceStore(HostTransaction(conn),SCOPE)
                        ref=owner.put(**args,actor='actor')
                        return ref,owner.read_exact(ref).snapshot
                except SerializationFailure:
                    if attempt==2: raise
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:save(),range(2)))
        assert results[0]==results[1]
        with connect(SCOPE) as conn:
            assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='product-content-snapshot'").fetchone()['n']==1
