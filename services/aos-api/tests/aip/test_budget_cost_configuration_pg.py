"""Formal derived configuration in disposable PostgreSQL, not live deployment."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import psycopg
import pytest
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_binding_readiness_service import PostgresBindingDependencyAuthority
from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
from aos_api.db import connect_read_only
from aos_api.aip_model_runtime_contracts import ModelPriceSnapshotRevision
from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevision
from tests.aip.test_budget_cost_consumer_pg import caller, approved, consume
from tests.aip.test_budget_cost_issuer_pg import issuer_factory, command
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner


def derive(conn, saved, decision, *, query=False, actor=None):
    name='aip_reconcile_cost_configuration_a0v_128' if query else 'aip_configure_budget_cost_a0v_128'
    return conn.execute(f'SELECT public.{name}(%s,%s,%s,%s,%s,%s) AS result',
        (*SCOPE.key,saved['proposalId'],decision['decisionId'],actor or saved['proposal']['makerSubject'],saved['proposalHash'])).fetchone()['result']


def totals(saved):
    with isolated_owner() as c:
        return c.execute("SELECT count(*) AS n FROM aip_model_governance_policy_receipt WHERE operation='budget_cost.configure' AND idempotency_key=%s",(saved['proposalId'],)).fetchone()['n']


def test_signed_budget_pair_reaches_runtime_candidate_reader_without_other_authority(
        caller, issuer_factory, https_signer):
    from aos_api.extension_runtime.runtime_configuration_candidates import read_candidates
    from aos_api.tenant_scope import TenantScope

    other = TenantScope('dev-org', 'dev-project')
    _, _, _, saved, decision = approved(issuer_factory, https_signer)
    with isolated_owner() as conn:
        before = read_candidates(conn, SCOPE).counts
        other_before = read_candidates(conn, other).counts
    with caller() as conn:
        consume(conn, saved, decision)
        configured = derive(conn, saved, decision)
    assert configured['activationEligible'] is False
    with isolated_owner() as conn:
        after = read_candidates(conn, SCOPE).counts
        assert read_candidates(conn, other).counts == other_before
    assert after['budgets'] == before['budgets'] + 1
    assert after['budget_policies'] == before['budget_policies'] + 1
    assert {key: value for key, value in after.items() if key not in {'budgets', 'budget_policies'}} == {
        key: value for key, value in before.items() if key not in {'budgets', 'budget_policies'}}


def test_signed_budget_policy_is_exact_for_binding_readiness_and_tenant_isolated(
        caller, issuer_factory, https_signer):
    from aos_api.tenant_scope import TenantScope

    _, _, _, saved, decision = approved(issuer_factory, https_signer)
    with caller() as conn:
        consume(conn, saved, decision)
        configured = derive(conn, saved, decision)
    assert configured['activationEligible'] is False
    budget = VersionedAssetRef.model_validate(configured['receipt']['policyRef'])
    authority = PostgresBindingDependencyAuthority(connect_read_only)
    with isolated_owner() as conn:
        window = conn.execute("""SELECT effective_from,effective_until FROM aip_model_governance_policy_revision
            WHERE org_id=%s AND project_id=%s AND policy_kind='budget' AND policy_id=%s AND revision=%s""",
            (*SCOPE.key, budget.asset_id, budget.revision)).fetchone()
    assert authority.budget_policy_available(SCOPE, budget, datetime.now(UTC))
    assert not authority.budget_policy_available(TenantScope('dev-org', 'dev-project'), budget, datetime.now(UTC))
    assert not authority.budget_policy_available(SCOPE, budget, window['effective_until'])
    assert not authority.budget_policy_available(SCOPE, budget.model_copy(update={'revision': 2}), datetime.now(UTC))
    with isolated_owner() as conn:
        conn.execute("""UPDATE aip_model_governance_policy_head SET current_revision=2
            WHERE org_id=%s AND project_id=%s AND policy_kind='budget' AND policy_id=%s""",
            (*SCOPE.key, budget.asset_id))
        conn.commit()
    assert not authority.budget_policy_available(SCOPE, budget, datetime.now(UTC))


def test_derived_pair_is_atomic_exact_and_idempotent(caller,issuer_factory,https_signer):
    _,_,p,saved,d=approved(issuer_factory,https_signer)
    with caller() as c:consume(c,saved,d)
    with pytest.raises(psycopg.errors.DivisionByZero):
        with caller() as c:derive(c,saved,d);c.execute('SELECT 1/0')
    assert totals(saved)==0
    with caller() as c:result=derive(c,saved,d)
    with caller() as c:assert derive(c,saved,d)==result
    assert result['status']=='observed' and result['activationEligible'] is False and totals(saved)==1
    refs=result['receipt']
    with isolated_owner() as c:
        price=ModelPriceSnapshotRevision.model_validate(c.execute('SELECT payload FROM aip_model_price_snapshot_revision WHERE model_price_snapshot_id=%s',(refs['priceRef']['assetId'],)).fetchone()['payload'])
        policy=BudgetPolicyRevision.model_validate(c.execute("SELECT payload FROM aip_model_governance_policy_revision WHERE policy_kind='budget' AND policy_id=%s",(refs['policyRef']['assetId'],)).fetchone()['payload'])
    assert price.development_cost_authorization==policy.development_cost_authorization
    assert price.input_token_price is None and price.output_token_price is None
    assert policy.budget_revision_ref.asset_id==p.target.budget_id
    assert policy.approval_ref==d['decisionId'] and not policy.allow_zero_price
    from aos_api.aip_budget_store import canonical_hash
    for item, excluded in [(price,{'tenant','revision','contentHash','createdBy','createdAt'}),
                           (policy,{'tenant','contentHash','createdBy','createdAt'})]:
        body=item.model_dump(mode='json',by_alias=True)
        assert item.content_hash==canonical_hash({k:v for k,v in body.items() if k not in excluded})



def test_revocation_preserves_readonly_history(caller,issuer_factory,https_signer):
    maker,_,_,saved,d=approved(issuer_factory,https_signer)
    with caller() as c:consume(c,saved,d);result=derive(c,saved,d)
    BudgetCostIssuer(issuer_factory).execute(command(https_signer[0],maker,saved,operation='revoke',decision=None,reason='withdraw'))
    with caller() as c:
        c.execute('SET TRANSACTION READ ONLY')
        assert derive(c,saved,d,query=True)==result
    with caller() as c:assert derive(c,saved,d)==result
    assert totals(saved)==1


@pytest.mark.parametrize('drift',['revoke','member','provider','budget','actor','decision','unconsumed'])
def test_drift_rejects_first_derivation(caller,issuer_factory,https_signer,drift):
    maker,checker,p,saved,d=approved(issuer_factory,https_signer)
    if drift!='unconsumed':
        with caller() as c:consume(c,saved,d)
    if drift=='revoke':
        BudgetCostIssuer(issuer_factory).execute(command(https_signer[0],maker,saved,operation='revoke',decision=None,reason='withdraw'))
    elif drift in ('member','provider','budget'):
        with isolated_owner() as c:
            if drift=='member':c.execute('DELETE FROM meta_membership WHERE subject=%s',(checker.subject,))
            elif drift=='provider':c.execute('UPDATE aip_provider_instance_head SET current_revision=999 WHERE provider_instance_id=%s',(p.basis.provider.asset_id,))
            else:c.execute('UPDATE aip_budget_head SET version=version+1 WHERE budget_id=%s',(p.target.budget_id,))
            c.commit()
    if drift=='decision':d={**d,'decisionId':'wrong'}
    with pytest.raises(psycopg.Error):
        with caller() as c:derive(c,saved,d,actor=checker.subject if drift=='actor' else None)
    assert totals(saved)==0


def test_concurrent_configuration_and_readonly_gate(caller,issuer_factory,https_signer):
    _,_,_,saved,d=approved(issuer_factory,https_signer)
    with caller() as c:consume(c,saved,d)
    def work(_):
        with caller() as c:return derive(c,saved,d)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a,b=list(pool.map(work,range(2)))
    assert a==b and totals(saved)==1
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with caller() as c:derive(c,saved,d,query=True)


def test_runtime_cannot_insert_active_development_configuration(caller,issuer_factory,https_signer):
    from aos_api.db import connect
    _,_,_,saved,d=approved(issuer_factory,https_signer)
    with caller() as c:consume(c,saved,d);result=derive(c,saved,d)
    with isolated_owner() as c:
        price=c.execute('SELECT * FROM aip_model_price_snapshot_revision WHERE model_price_snapshot_id=%s',
            (result['receipt']['priceRef']['assetId'],)).fetchone()
        policy=c.execute("SELECT * FROM aip_model_governance_policy_revision WHERE policy_id=%s",
            (result['receipt']['policyRef']['assetId'],)).fetchone()
    from psycopg.types.json import Jsonb
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='CONSUMER_REQUIRED'):
        with connect(SCOPE) as c:
            c.execute('INSERT INTO aip_model_price_snapshot_revision(org_id,project_id,model_price_snapshot_id,revision,content_hash,lifecycle,payload,created_by) VALUES(%s,%s,%s,2,%s,%s,%s,%s)',
                (*SCOPE.key,price['model_price_snapshot_id'],price['content_hash'],'active',Jsonb(price['payload']),'test'))
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='CONSUMER_REQUIRED'):
        with connect(SCOPE) as c:
            c.execute("INSERT INTO aip_model_governance_policy_revision(org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,effective_from,effective_until,payload,created_by) VALUES(%s,%s,'budget',%s,2,%s,'active',%s,%s,%s,'test')",
                (*SCOPE.key,policy['policy_id'],policy['content_hash'],policy['effective_from'],policy['effective_until'],Jsonb(policy['payload'])))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with caller() as c:c.execute('SELECT * FROM aip_model_governance_policy_receipt')


def test_wrong_scope_and_owner_helper_are_not_callable(caller,issuer_factory,https_signer):
    from aos_api.tenant_scope import TenantScope
    _,_,_,saved,d=approved(issuer_factory,https_signer)
    with caller() as c:consume(c,saved,d)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with caller(TenantScope('dev-org','dev-project')) as c:derive(c,saved,d)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with caller() as c:c.execute("SELECT public.aip_cost_configuration_expected_a0v_128('org-org','dev-project','p','d','a',%s)",('a'*64,))
    assert totals(saved)==0


def test_expired_source_cannot_create_pair(caller,issuer_factory,https_signer):
    from datetime import datetime, UTC
    import time
    from tests.aip.test_budget_cost_issuer_pg import prepared
    maker,checker,_,p,saved=prepared(window=5)
    d=BudgetCostIssuer(issuer_factory).execute(command(https_signer[0],checker,saved))
    with caller() as c:consume(c,saved,d)
    time.sleep(max(0,(p.target.effective_until-datetime.now(UTC)).total_seconds())+0.05)
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='EXPIRED'):
        with caller() as c:derive(c,saved,d)
    assert totals(saved)==0


def test_withdrawn_price_stays_historical_and_cannot_be_reactivated(caller,issuer_factory,https_signer):
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore, canonical_hash, require_current_development_price, ModelRuntimeDependencyBlocked
    from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle
    _,_,_,saved,d=approved(issuer_factory,https_signer)
    with caller() as c:consume(c,saved,d);result=derive(c,saved,d)
    store=AipModelRuntimeStore();identity=result['receipt']['priceRef']['assetId']
    original=store.get_price_snapshot(SCOPE,identity)
    suspended=original.model_copy(update={'revision':2,'lifecycle':ModelRuntimeLifecycle.SUSPENDED})
    body=suspended.model_dump(mode='json',by_alias=True)
    suspended.content_hash=canonical_hash({k:v for k,v in body.items() if k not in store._META_FIELDS})
    store.publish_price_snapshot(SCOPE,original.created_by,'withdraw-'+identity,suspended,expected_version=1)
    with pytest.raises(ModelRuntimeDependencyBlocked):require_current_development_price(store,SCOPE,original)
    with caller() as c:
        c.execute('SET TRANSACTION READ ONLY');assert derive(c,saved,d,query=True)==result
    with caller() as c:assert derive(c,saved,d)==result
    assert store.get_price_snapshot(SCOPE,identity).lifecycle is ModelRuntimeLifecycle.SUSPENDED
