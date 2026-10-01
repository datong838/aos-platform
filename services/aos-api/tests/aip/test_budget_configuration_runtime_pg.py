"""Derived cost source into the actual shared risk gate; not a full TaskRun proof."""
import pytest
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore,BudgetReservationBlocked
from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_model_runtime_store import AipModelRuntimeStore,canonical_hash
from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle
from aos_api.db import connect_serializable
from tests.aip.test_budget_cost_consumer_pg import caller,approved,consume
from tests.aip.test_budget_cost_configuration_pg import derive
from tests.aip.test_budget_cost_issuer_pg import issuer_factory
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE


@pytest.fixture
def configured_pair(caller,issuer_factory,https_signer):
    maker,_,proposal,saved,decision=approved(issuer_factory,https_signer)
    with caller() as conn:
        consume(conn,saved,decision);result=derive(conn,saved,decision)
    refs=result['receipt']
    def exact(ref):return BudgetExactRef(resourceType=ref['assetType'],resourceId=ref['assetId'],
        revision=ref['revision'],contentHash='sha256:'+ref['contentHash'])
    return maker,proposal,saved,decision,result,exact(refs['budgetRef']),exact(refs['priceRef'])


def withdraw(pair):
    maker,_,_,_,_,_,price=pair
    store=AipModelRuntimeStore();original=store.get_price_snapshot(SCOPE,price.resource_id)
    suspended=original.model_copy(update={'revision':2,'lifecycle':ModelRuntimeLifecycle.SUSPENDED})
    body=suspended.model_dump(mode='json',by_alias=True)
    suspended.content_hash=canonical_hash({k:v for k,v in body.items() if k not in store._META_FIELDS})
    store.publish_price_snapshot(SCOPE,maker.subject,'withdraw-'+price.resource_id,suspended,expected_version=1)


@pytest.mark.parametrize('new_hold',[True,False])
def test_withdrawn_derived_price_blocks_both_risk_entries(configured_pair,new_hold):
    _,p,_,_,_,budget,price=configured_pair
    store=AipBudgetReservationStore()
    with connect_serializable(SCOPE) as conn:
        store._cost_risk_authority(conn,SCOPE,budget,price,p.basis.per_request_risk_minor,new_hold=new_hold)
        conn.commit()
    withdraw(configured_pair)
    with pytest.raises(BudgetReservationBlocked):
        with connect_serializable(SCOPE) as conn:
            store._cost_risk_authority(conn,SCOPE,budget,price,p.basis.per_request_risk_minor,new_hold=new_hold)


def test_stale_serializable_snapshot_cannot_admit_withdrawn_price(configured_pair):
    _,p,_,_,_,budget,price=configured_pair
    with pytest.raises(BudgetReservationBlocked):
        with connect_serializable(SCOPE) as conn:
            assert conn.execute('SELECT current_revision FROM aip_model_price_snapshot_head WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s',
                (*SCOPE.key,price.resource_id)).fetchone()['current_revision']==1
            withdraw(configured_pair)
            AipBudgetReservationStore()._cost_risk_authority(conn,SCOPE,budget,price,p.basis.per_request_risk_minor)


def test_head_lock_holds_until_admission_transaction_finishes(configured_pair):
    import psycopg
    from aos_api.db import connect
    _,p,_,_,_,budget,price=configured_pair
    with connect_serializable(SCOPE) as conn:
        AipBudgetReservationStore()._cost_risk_authority(conn,SCOPE,budget,price,p.basis.per_request_risk_minor)
        with pytest.raises(psycopg.errors.LockNotAvailable):
            with connect(SCOPE) as other:
                other.execute("SET LOCAL lock_timeout='100ms'")
                other.execute('UPDATE aip_model_price_snapshot_head SET current_revision=2 WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s',
                    (*SCOPE.key,price.resource_id))
        conn.commit()
    withdraw(configured_pair)
    assert AipModelRuntimeStore().get_price_snapshot(SCOPE,price.resource_id).revision==2


def test_withdrawal_keeps_exact_configuration_history_readable(configured_pair,caller):
    _,_,saved,decision,result,_,price=configured_pair
    withdraw(configured_pair)
    with caller() as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        assert derive(conn,saved,decision,query=True)==result
    original=AipModelRuntimeStore().get_price_snapshot(SCOPE,price.resource_id,1)
    assert original.content_hash==price.content_hash.removeprefix('sha256:')
    assert original.lifecycle is ModelRuntimeLifecycle.ACTIVE
