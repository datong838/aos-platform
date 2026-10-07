"""Caller transaction ownership, using fixture pools; no physical capacity grant."""
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_agent_registry_store import AipAgentRegistryTransitionBlocked
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_capacity_reservation import AipModelCapacityReservationGate
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.db import connect, connect_serializable, get_dsn
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('org-org', 'dev-project')


def fixture_pool():
    suffix = uuid4().hex
    def ref(kind):
        return VersionedAssetRef(assetType=kind, assetId=f'pool-txn:{kind}:{suffix}',
                                 revision=1, contentHash='b' * 64)
    route, model, provider = (ref(k) for k in
        ('ModelRouteRevision', 'RegisteredModelRevision', 'ProviderInstanceRevision'))
    pool = f'pool-txn:{suffix}'
    with psycopg.connect(get_dsn()) as admin:
        admin.execute("INSERT INTO twa_org(id,name) VALUES (%s,'test-only') ON CONFLICT DO NOTHING", (SCOPE.org_id,))
        admin.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES (%s,%s,'test-only') ON CONFLICT DO NOTHING", SCOPE.key)
    with connect(SCOPE) as conn:
        conn.execute('INSERT INTO aip_model_capacity_pool_head(org_id,project_id,pool_id,current_revision,version) VALUES (%s,%s,%s,1,1)', (*SCOPE.key, pool))
        conn.execute("""INSERT INTO aip_model_capacity_pool_revision
            (org_id,project_id,pool_id,revision,content_hash,route_ref,model_ref,provider_ref,
             route_id,route_revision,route_hash,model_id,model_revision,model_hash,
             provider_id,provider_revision,provider_hash,max_concurrency,max_token_units,
             token_unit_per_reservation,lease_seconds,lifecycle,created_by)
            VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,1,%s,%s,1,%s,%s,1,%s,2,100,10,300,'active','test-only')""",
            (*SCOPE.key, pool, 'b'*64, *(Jsonb(r.model_dump(mode='json', by_alias=True)) for r in (route,model,provider)),
             route.asset_id, route.content_hash, model.asset_id, model.content_hash, provider.asset_id, provider.content_hash))
    return pool, ModelRouteResolution(tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        route=route, policy=ref('RuntimePolicyRevision'), readiness=ModelRuntimeReadiness.READY,
        selectedModel=model, selectedProvider=provider, selectedPriceSnapshot=ref('ModelPriceSnapshotRevision'),
        blockerCodes=[], resolvedAt=datetime.now(UTC))


def persisted(pool):
    with connect(SCOPE) as observer:
        return observer.execute("""SELECT
            (SELECT count(*) FROM aip_model_capacity_reservation WHERE pool_id=%s) AS reservations,
            (SELECT count(*) FROM aip_model_capacity_event e JOIN aip_model_capacity_reservation r
              USING(org_id,project_id,reservation_id) WHERE r.pool_id=%s) AS events""", (pool,pool)).fetchone()


@pytest.mark.parametrize('finish', ['rollback', 'commit', 'exception'])
def test_caller_owns_pool_reservation_commit_and_rollback(finish):
    pool, resolution = fixture_pool()
    gate = AipModelCapacityReservationGate()
    class CallerFailure(Exception):
        pass
    try:
        with connect_serializable(SCOPE) as caller:
            xid = caller.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
            reservation = gate.reserve_pool_in_transaction(caller, SCOPE, resolution, 'pool-txn-run:'+uuid4().hex)
            assert caller.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid'] == xid
            assert caller.execute('SELECT reservation_id FROM aip_model_capacity_reservation WHERE reservation_id=%s', (reservation,)).fetchone()
            assert persisted(pool) == {'reservations':0, 'events':0}
            if finish == 'rollback':
                caller.rollback()
            elif finish == 'commit':
                caller.commit()
            else:
                raise CallerFailure()
    except CallerFailure:
        assert finish == 'exception'
    expected = 1 if finish == 'commit' else 0
    assert persisted(pool) == {'reservations':expected, 'events':expected}


def test_pool_lock_lives_until_caller_transaction_ends():
    pool, resolution = fixture_pool()
    with connect_serializable(SCOPE) as caller:
        AipModelCapacityReservationGate().reserve_pool_in_transaction(caller, SCOPE, resolution, 'pool-lock:'+uuid4().hex)
        with connect(SCOPE) as writer:
            writer.execute("SET LOCAL lock_timeout='150ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                writer.execute('UPDATE aip_model_capacity_pool_head SET version=version+1 WHERE pool_id=%s', (pool,))
            writer.rollback()
        caller.rollback()
    with connect(SCOPE) as writer:
        writer.execute("SET LOCAL lock_timeout='1s'")
        assert writer.execute('UPDATE aip_model_capacity_pool_head SET version=version+1 WHERE pool_id=%s RETURNING version', (pool,)).fetchone()['version'] == 2
        writer.rollback()
    assert persisted(pool) == {'reservations':0,'events':0}


def test_caller_replay_does_not_commit_or_duplicate_events():
    pool, resolution = fixture_pool()
    run_id = 'pool-replay:' + uuid4().hex
    gate = AipModelCapacityReservationGate()
    with connect_serializable(SCOPE) as caller:
        xid = caller.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        first = gate.reserve_pool_in_transaction(caller, SCOPE, resolution, run_id)
        assert gate.reserve_pool_in_transaction(caller, SCOPE, resolution, run_id) == first
        assert caller.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid'] == xid
        assert caller.execute('SELECT count(*) AS n FROM aip_model_capacity_event WHERE reservation_id=%s', (first,)).fetchone()['n'] == 1
        assert persisted(pool) == {'reservations':0,'events':0}
        caller.commit()
    assert persisted(pool) == {'reservations':1,'events':1}
    with connect_serializable(SCOPE) as caller:
        xid = caller.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        assert gate.reserve_pool_in_transaction(caller, SCOPE, resolution, run_id) == first
        assert caller.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid'] == xid
        caller.rollback()
    assert persisted(pool) == {'reservations':1,'events':1}


@pytest.mark.parametrize('fault', ['nonserial', 'scope', 'admin', 'proxy', 'autocommit',
    'readonly', 'sql_readonly', 'closed', 'idle', 'tuple_rows'])
def test_transaction_kernel_rejects_wrong_connection_without_occupation(fault):
    pool, resolution = fixture_pool()
    with (connect(SCOPE) if fault == 'nonserial' else connect_serializable(SCOPE)) as caller:
        target = caller
        if fault == 'scope':
            caller.execute("SELECT set_config('aos.org_id','dev-org',true)")
        elif fault == 'admin':
            caller.execute('RESET ROLE')
        elif fault == 'proxy':
            class Proxy:
                def execute(self, *args, **kwargs):
                    raise AssertionError('proxy must not be queried')
            target = Proxy()
        elif fault == 'autocommit':
            caller.rollback()
            caller.autocommit = True
        elif fault == 'readonly':
            caller.rollback()
            caller.read_only = True
        elif fault == 'sql_readonly':
            caller.execute('SET TRANSACTION READ ONLY')
        elif fault == 'closed':
            caller.close()
        elif fault == 'idle':
            caller.rollback()
        elif fault == 'tuple_rows':
            from psycopg.rows import tuple_row
            caller.row_factory = tuple_row
        with pytest.raises(AipAgentRegistryTransitionBlocked, match='capacity_caller_transaction_required'):
            AipModelCapacityReservationGate().reserve_pool_in_transaction(target, SCOPE, resolution, 'pool-neg:'+uuid4().hex)
        if not caller.closed:
            caller.rollback()
    assert persisted(pool) == {'reservations':0,'events':0}
