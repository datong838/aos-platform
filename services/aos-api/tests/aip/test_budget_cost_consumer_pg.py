"""Atomic cost-approved budget activation in disposable PG; no live activation."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import secrets
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest
from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
from aos_api.aip_budget_store import AipBudgetAuthorityStore
from tests.aip.test_budget_cost_issuer_pg import prepared, command, issuer_factory
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner


@pytest.fixture
def caller(tmp_path):
    path=tmp_path/'consumer.pgpass';path.touch(mode=0o600)
    with isolated_owner() as admin:
        admin.execute("SELECT pg_advisory_lock(hashtext('budget-consumer-tests'))")
        assert admin.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname='aos_budget_consumer_call'").fetchone()=={'rolcanlogin':False}
        password=secrets.token_urlsafe(32)
        admin.execute(sql.SQL('ALTER ROLE aos_budget_consumer_call LOGIN PASSWORD {}').format(sql.Literal(password)));admin.commit()
        host,port,database=admin.info.host,admin.info.port,admin.info.dbname
        path.write_text(f'{host}:{port}:{database}:aos_budget_consumer_call:{password}\n')
        @contextmanager
        def factory(scope=SCOPE):
            with psycopg.connect(host=host,port=port,dbname=database,user='aos_budget_consumer_call',passfile=str(path),row_factory=dict_row,
                options='-c statement_timeout=10000 -c lock_timeout=5000') as conn:
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
                yield conn
        try:yield factory
        finally:
            admin.execute('ALTER ROLE aos_budget_consumer_call NOLOGIN PASSWORD NULL');admin.commit();path.write_text('# removed\n')
            admin.execute("SELECT pg_advisory_unlock(hashtext('budget-consumer-tests'))")


def consume(conn,saved,decision,scope=SCOPE):
    return conn.execute('SELECT public.aip_consume_budget_as_actor_a0v_127(%s,%s,%s,%s,%s,%s) AS result',
        (*scope.key,saved['proposalId'],decision['decisionId'],saved['proposal']['makerSubject'],saved['proposalHash'])).fetchone()['result']


def approved(issuer_factory,https_signer):
    sign,_=https_signer;maker,checker,other,p,saved=prepared()
    decision=BudgetCostIssuer(issuer_factory).execute(command(sign,checker,saved))
    return maker,checker,p,saved,decision


def counts(p):
    with isolated_owner() as conn:
        return conn.execute("SELECT (SELECT count(*) FROM aip_budget_revision WHERE budget_id=%s AND lifecycle='active') AS active, "
          "(SELECT count(*) FROM aip_budget_receipt WHERE operation='budget_revision.activate_cost' AND result_ref->>'resourceId'=%s) AS receipts",
          (p.target.budget_id,p.target.budget_id)).fetchone()


def test_real_caller_consumes_once_and_legacy_store_reads(caller,issuer_factory,https_signer):
    maker,_,p,saved,decision=approved(issuer_factory,https_signer)
    with caller() as conn:result=consume(conn,saved,decision)
    assert counts(p)==dict(active=1,receipts=1)
    with caller() as conn:assert consume(conn,saved,decision)==result
    actual=AipBudgetAuthorityStore().get(SCOPE,p.target.budget_id)
    assert actual.lifecycle.value=='active' and actual.content_hash==result['contentHash']
    assert result['proposalId']==saved['proposalId'] and result['decisionId']==decision['decisionId']


def test_concurrent_consume_and_rollback(caller,issuer_factory,https_signer):
    _,_,p,saved,decision=approved(issuer_factory,https_signer)
    with pytest.raises(psycopg.errors.DivisionByZero):
        with caller() as conn:consume(conn,saved,decision);conn.execute('SELECT 1/0')
    assert counts(p)==dict(active=0,receipts=0)
    barrier=Barrier(2)
    def run():
        with caller() as conn:barrier.wait(timeout=5);return consume(conn,saved,decision)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a,b=pool.submit(run),pool.submit(run)
        assert a.result(timeout=15)==b.result(timeout=15)
    assert counts(p)==dict(active=1,receipts=1)


@pytest.mark.parametrize('drift',['revoke','member','provider','head','decision'])
def test_current_drift_rejects_without_partial_writes(drift,caller,issuer_factory,https_signer):
    maker,checker,p,saved,decision=approved(issuer_factory,https_signer)
    if drift=='revoke':
        BudgetCostIssuer(issuer_factory).execute(command(https_signer[0],maker,saved,operation='revoke',decision=None,reason='withdraw'))
    elif drift=='decision':decision={**decision,'decisionId':'not-this-decision'}
    else:
        with isolated_owner() as conn:
            if drift=='member':conn.execute('DELETE FROM meta_membership WHERE subject=%s',(checker.subject,))
            elif drift=='head':conn.execute('UPDATE aip_budget_head SET version=version+1 WHERE budget_id=%s',(p.target.budget_id,))
            else:conn.execute('UPDATE aip_provider_instance_head SET current_revision=999 WHERE provider_instance_id=%s',(p.basis.provider.asset_id,))
            conn.commit()
    with pytest.raises(psycopg.Error):
        with caller() as conn:consume(conn,saved,decision)
    assert counts(p)==dict(active=0,receipts=0)


def test_caller_has_no_direct_table_writes_and_shared_api_cannot_consume(caller,issuer_factory,https_signer):
    from aos_api.db import connect
    _,_,_,saved,decision=approved(issuer_factory,https_signer)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with caller() as conn:conn.execute('SELECT * FROM aip_budget_revision')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connect(SCOPE) as conn:consume(conn,saved,decision)


def price_for(p,decision):
    from datetime import datetime, UTC
    from uuid import uuid4
    import json
    from aos_api.aip_model_runtime_contracts import ModelPriceSnapshotRevision
    from aos_api.aip_budget_store import canonical_hash
    from aos_api.aip_budget_reservation_contracts import BudgetExactRef
    price=ModelPriceSnapshotRevision(tenant=p.tenant,priceSnapshotId='risk-price-'+uuid4().hex,revision=1,
        contentHash='0'*64,currency='CNY',inputTokenPrice=None,outputTokenPrice=None,cachedTokenPrice=None,
        effectiveFrom=p.target.effective_from,effectiveUntil=p.target.effective_until,lifecycle='active',
        createdBy=p.maker_subject,createdAt=datetime.now(UTC),developmentCostAuthorization=dict(
            tenant=p.tenant,provider=p.basis.provider,providerModelId=p.basis.provider_model_id,
            approvalRef=decision['decisionId'],effectiveFrom=p.target.effective_from,effectiveUntil=p.target.effective_until))
    body=price.model_dump(mode='json',by_alias=True)
    price.content_hash=canonical_hash({k:v for k,v in body.items() if k not in {'tenant','revision','contentHash','createdBy','createdAt'}})
    with isolated_owner() as conn:
        # Historical adversarial fixture only; production active development writes stay guarded.
        conn.execute('ALTER TABLE aip_model_price_snapshot_revision DISABLE TRIGGER cost_configuration_write_guard')
        conn.execute('INSERT INTO aip_model_price_snapshot_head(org_id,project_id,model_price_snapshot_id,current_revision,version) VALUES(%s,%s,%s,1,1)',
            (*SCOPE.key,price.price_snapshot_id))
        conn.execute('INSERT INTO aip_model_price_snapshot_revision(org_id,project_id,model_price_snapshot_id,revision,content_hash,lifecycle,payload,created_by,created_at) VALUES(%s,%s,%s,1,%s,%s,%s::jsonb,%s,%s)',
            (*SCOPE.key,price.price_snapshot_id,price.content_hash,'active',json.dumps(price.model_dump(mode='json',by_alias=True)),p.maker_subject,price.created_at))
        conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
        conn.execute('ALTER TABLE aip_model_price_snapshot_revision ENABLE TRIGGER cost_configuration_write_guard')
        conn.commit()
    return BudgetExactRef(resourceType='ModelPriceSnapshotRevision',resourceId=price.price_snapshot_id,revision=1,contentHash="sha256:"+price.content_hash)


def test_consumed_risk_is_required_by_reservation_entry_and_revocation(caller,issuer_factory,https_signer):
    from aos_api.db import connect_serializable
    from aos_api.aip_budget_reservation_store import AipBudgetReservationStore,BudgetReservationBlocked
    from aos_api.aip_budget_reservation_contracts import BudgetExactRef
    maker,_,p,saved,decision=approved(issuer_factory,https_signer)
    with caller() as conn:result=consume(conn,saved,decision)
    policy=BudgetExactRef(resourceType='BudgetRevision',resourceId=result['resourceId'],revision=result['revision'],contentHash='sha256:'+result['contentHash'])
    price=price_for(p,decision);store=AipBudgetReservationStore()
    with connect_serializable(SCOPE) as conn:
        store._cost_risk_authority(conn,SCOPE,policy,price,p.basis.per_request_risk_minor)
        conn.commit()
    with pytest.raises(BudgetReservationBlocked):
        with connect_serializable(SCOPE) as conn:store._cost_risk_authority(conn,SCOPE,policy,price,1)
    BudgetCostIssuer(issuer_factory).execute(command(https_signer[0],maker,saved,operation='revoke',decision=None,reason='withdraw after activation'))
    with pytest.raises(BudgetReservationBlocked):
        with connect_serializable(SCOPE) as conn:store._cost_risk_authority(conn,SCOPE,policy,price,p.basis.per_request_risk_minor)
    # A revoked activation can still be reconciled without opening a new budget.
    with caller() as conn:assert consume(conn,saved,decision)==result


def ledger_hold(conn,p,policy,price):
    """Structurally real local hold fixture, no Provider request or source read."""
    from uuid import uuid4
    from psycopg.types.json import Jsonb
    invocation,reservation=uuid4(),uuid4();key='fixture-'+uuid4().hex
    pr=Jsonb(policy.model_dump(by_alias=True));price_ref=Jsonb(price.model_dump(by_alias=True));empty=Jsonb({})
    conn.execute("""INSERT INTO aip_capability_invocation(org_id,project_id,invocation_id,operation_id,invocation_key,
        request_hash,task_ref,policy_ref,approval_ref,pricing_ref,currency,upper_bound_minor,state,revision,content_hash)
        VALUES(%s,%s,%s,'risk-fixture',%s,%s,%s,%s,%s,%s,'CNY',%s,'prepared',1,%s)""",
        (*SCOPE.key,invocation,key,'a'*64,empty,pr,empty,price_ref,p.basis.per_request_risk_minor,'sha256:'+'b'*64))
    conn.execute("""INSERT INTO aip_budget_reservation(org_id,project_id,reservation_id,invocation_id,operation_id,invocation_key,
        task_ref,policy_ref,pricing_ref,approval_ref,currency,upper_bound_minor,state,request_hash,revision,content_hash)
        VALUES(%s,%s,%s,%s,'risk-fixture',%s,%s,%s,%s,%s,'CNY',%s,'held',%s,1,%s)""",
        (*SCOPE.key,reservation,invocation,key,empty,pr,price_ref,empty,p.basis.per_request_risk_minor,'a'*64,'sha256:'+'c'*64))


def test_concurrent_risk_holds_cannot_exceed_approved_count(caller,issuer_factory,https_signer):
    from uuid import uuid4
    from aos_api.db import connect_serializable
    from aos_api.aip_budget_cost_proposal_store import BudgetCostProposalStore
    from aos_api.aip_budget_reservation_contracts import BudgetExactRef
    from aos_api.aip_budget_cost_runtime import require_cost_risk,BudgetCostRuntimeBlocked
    maker,checker,_,p,_=prepared();p.basis.max_requests=1
    saved=BudgetCostProposalStore().create(maker,p,'one-'+uuid4().hex)
    decision=BudgetCostIssuer(issuer_factory).execute(command(https_signer[0],checker,saved))
    with caller() as conn:r=consume(conn,saved,decision)
    policy=BudgetExactRef(resourceType='BudgetRevision',resourceId=r['resourceId'],revision=r['revision'],contentHash='sha256:'+r['contentHash'])
    price=price_for(p,decision);start=Barrier(2)
    def reserve():
        try:
            with connect_serializable(SCOPE) as conn:
                conn.execute('SELECT count(*) FROM aip_budget_cost_runtime_fence');start.wait(timeout=5)
                require_cost_risk(conn,SCOPE,policy,price,p.basis.per_request_risk_minor)
                ledger_hold(conn,p,policy,price);conn.commit();return True
        except (BudgetCostRuntimeBlocked,psycopg.errors.SerializationFailure):return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        a,b=pool.submit(reserve),pool.submit(reserve)
        assert sorted([a.result(timeout=15),b.result(timeout=15)])==[False,True]
    with pytest.raises(BudgetCostRuntimeBlocked):
        with connect_serializable(SCOPE) as conn:require_cost_risk(conn,SCOPE,policy,price,p.basis.per_request_risk_minor)


def test_old_serializable_snapshot_cannot_submit_after_committed_revoke(caller,issuer_factory,https_signer):
    from aos_api.db import connect_serializable
    from aos_api.aip_budget_reservation_contracts import BudgetExactRef
    from aos_api.aip_budget_cost_runtime import require_cost_risk,BudgetCostRuntimeBlocked
    maker,_,p,saved,decision=approved(issuer_factory,https_signer)
    with caller() as conn:r=consume(conn,saved,decision)
    policy=BudgetExactRef(resourceType='BudgetRevision',resourceId=r['resourceId'],revision=r['revision'],contentHash='sha256:'+r['contentHash'])
    price=price_for(p,decision)
    with connect_serializable(SCOPE) as old:
        old.execute('SELECT count(*) FROM aip_budget_cost_runtime_fence')
        BudgetCostIssuer(issuer_factory).execute(command(https_signer[0],maker,saved,operation='revoke',decision=None,reason='withdraw'))
        with pytest.raises(BudgetCostRuntimeBlocked) as error:require_cost_risk(old,SCOPE,policy,price,p.basis.per_request_risk_minor,new_hold=False)
        assert isinstance(error.value.__cause__,psycopg.errors.SerializationFailure)
        old.rollback()


def test_fence_has_only_column_update_permission():
    with isolated_owner() as conn:
        row=conn.execute("SELECT has_table_privilege('aos_runtime','aip_budget_cost_runtime_fence','INSERT,UPDATE,DELETE,TRUNCATE') AS broad, "
            "has_column_privilege('aos_runtime','aip_budget_cost_runtime_fence','version','UPDATE') AS version").fetchone()
        assert row==dict(broad=False,version=True)


@pytest.mark.parametrize('drift',['model','provider','budget_head'])
def test_runtime_rejects_other_model_or_provider(drift,caller,issuer_factory,https_signer):
    from aos_api.db import connect_serializable
    from aos_api.aip_budget_reservation_contracts import BudgetExactRef
    from aos_api.aip_budget_cost_runtime import require_cost_risk,BudgetCostRuntimeBlocked
    _,_,p,saved,decision=approved(issuer_factory,https_signer)
    with caller() as conn:r=consume(conn,saved,decision)
    policy=BudgetExactRef(resourceType='BudgetRevision',resourceId=r['resourceId'],revision=r['revision'],contentHash='sha256:'+r['contentHash'])
    supplied=p.model_copy(deep=True)
    if drift=='model':supplied.basis.provider_model_id='unapproved-model'
    price=price_for(supplied,decision)
    if drift=='budget_head':
        with isolated_owner() as conn:
            conn.execute('UPDATE aip_budget_head SET version=version+1 WHERE budget_id=%s',(p.target.budget_id,));conn.commit()
    provider=BudgetExactRef(resourceType='ProviderInstanceRevision',resourceId='different-provider',revision=1,contentHash='sha256:'+'a'*64) if drift=='provider' else None
    with pytest.raises(BudgetCostRuntimeBlocked):
        with connect_serializable(SCOPE) as conn:require_cost_risk(conn,SCOPE,policy,price,p.basis.per_request_risk_minor,provider_ref=provider)


def test_expired_signed_decision_cannot_be_consumed(caller,issuer_factory,https_signer):
    from datetime import datetime,UTC
    import time
    _,checker,_,p,saved=prepared(window=2)
    decision=BudgetCostIssuer(issuer_factory).execute(command(https_signer[0],checker,saved))
    time.sleep(max(0,(p.target.effective_until-datetime.now(UTC)).total_seconds())+.02)
    with pytest.raises(psycopg.Error,match='EXPIRED'):
        with caller() as conn:consume(conn,saved,decision)
    assert counts(p)==dict(active=0,receipts=0)
