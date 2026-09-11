import pytest
from test_ecommerce_product_content_evidence import database,prepared,pytestmark
from tests.test_ecommerce_product_joint_quality import row,SCOPE
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_product_content_evidence import ProductContentEvidenceStore
from aos_api.ecommerce_product_content_query import ProductContentQueryService


@pytest.mark.parametrize('rows,counts',[([],[0,0,0,0]),([row(),row(2,goods_stock=0),row(3,price=None)],[3,3,2,1])])
def test_exact_counts_replay_and_scope(rows,counts,monkeypatch):
    import tests.test_ecommerce_product_joint_quality as fixture
    from aos_api.configured_source_observation import ConfiguredSourceObservation
    old=fixture.bound
    def timed(conn,key):
        raw=old(conn,key).model_dump()
        raw["observation"]["read_finished_at"]=conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        return ConfiguredSourceObservation.model_validate(raw)
    monkeypatch.setattr(fixture,"bound",timed)
    with database() as connect:
        args=prepared(connect,rows)
        with connect(SCOPE) as conn:
            tx=HostTransaction(conn)
            source=ProductContentEvidenceStore(tx,SCOPE).put(**args,actor='actor')
            owner=ProductContentQueryService(tx,SCOPE)
            ref=owner.execute(evidence_ref=source,idempotency_key='query',actor='actor')
            result=owner.read_exact(ref)
            assert [result.rows[0].values[k] for k in ('observed','eligible','jointValid','preparable')]==counts
            assert result.status.value=='partial' and result.source_refs[0].freshness=='unknown'
            assert owner.execute(evidence_ref=source,idempotency_key='query',actor='actor')==ref
            with pytest.raises(ValueError):
                ProductContentQueryService(tx,type(SCOPE)('dev-org','dev-project')).read_exact(ref)
        from aos_api.aip_production_contract_store import AipProductionContractStore
        from aos_api.aip_production_contracts import RevokeEvidenceRequest
        AipProductionContractStore(connect).revoke_evidence(SCOPE,'actor',source.resource_id,'withdraw',
            RevokeEvidenceRequest(expectedContentHash=source.content_hash,reason='synthetic withdrawal'))
        with connect(SCOPE) as conn:
            with pytest.raises(ValueError): ProductContentQueryService(HostTransaction(conn),SCOPE).read_exact(ref)



def test_zero_interval_rejected_and_outer_rollback():
    with database() as connect:
        args=prepared(connect,[row()])
        with pytest.raises(ValueError):
            with connect(SCOPE) as conn:
                tx=HostTransaction(conn)
                source=ProductContentEvidenceStore(tx,SCOPE).put(**args,actor='actor')
                ProductContentQueryService(tx,SCOPE).execute(evidence_ref=source,idempotency_key='invalid-window',actor='actor')
        with connect(SCOPE) as conn:
            assert conn.execute("SELECT count(*) AS n FROM aip_analyst_query_job WHERE org_id=%s AND project_id=%s",SCOPE.key).fetchone()['n']==0
            assert conn.execute("SELECT count(*) AS n FROM aip_metric_definition_revision WHERE metric_id='niushop.product-content-preparation-counts'").fetchone()['n']==0
