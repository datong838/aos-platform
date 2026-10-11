"""The proposed amount observes buckets; it never authorizes cost or execution."""
from datetime import datetime,timedelta,timezone
import pytest
from aos_api.aip_budget_balance_snapshot import observe_bucket,BudgetBalanceSnapshotReader,BudgetBalanceSnapshotUnavailable
from aos_api.aip_budget_reservation_contracts import BudgetBucketAuthority

NOW=datetime(2026,10,11,18,tzinfo=timezone.utc)
def target():
 return BudgetBucketAuthority(kind='daily',accountId='budget:daily',periodStart=NOW,periodEnd=NOW+timedelta(days=1),currency='CNY',limitMinor=100)
def row(**changes):
 return dict(period_end=target().period_end,currency='CNY',limit_minor=100,held_minor=10,submitted_minor=20,settled_minor=30,unknown_minor=0,**changes)
def test_four_exposure_states_are_counted():
 item=observe_bucket(target(),row(),30)
 assert item.exposure_minor==60 and item.remaining_minor==40 and item.blocker_codes==()
def test_missing_bucket_is_unknown_not_zero():
 item=observe_bucket(target(),None,1)
 assert item.exposure_minor is None and item.remaining_minor is None and item.blocker_codes==('BUDGET_BUCKET_UNAVAILABLE',)
def test_unknown_exposure_is_retained_and_blocks():
 data=row();data['unknown_minor']=7
 item=observe_bucket(target(),data,1)
 assert item.exposure_minor==67 and 'BUDGET_USAGE_UNKNOWN' in item.blocker_codes
@pytest.mark.parametrize('field,value',[('period_end',NOW),('currency','USD'),('limit_minor',101)])
def test_exact_bucket_authority_drift_is_not_usable(field,value):
 data=row();data[field]=value
 item=observe_bucket(target(),data,1)
 assert item.remaining_minor is None and item.blocker_codes==('BUDGET_BUCKET_AUTHORITY_DRIFTED',)
@pytest.mark.parametrize('value',[-1,True,'10'])
def test_corrupt_exposure_fails_closed(value):
 data=row();data['held_minor']=value
 assert observe_bucket(target(),data,1).blocker_codes==('BUDGET_BUCKET_EXPOSURE_INVALID',)
def test_insufficient_capacity_is_observation_only():
 item=observe_bucket(target(),row(),41)
 assert item.remaining_minor==40 and item.blocker_codes==('BUDGET_LIMIT_EXCEEDED',)
@pytest.mark.parametrize('value',[0,-1,True,1.1])
def test_proposed_upper_bound_must_be_positive_integer(value):
 with pytest.raises(ValueError):observe_bucket(target(),row(),value)
def test_native_reader_rejects_invalid_scope_before_connection():
 def connection(_):raise AssertionError('invalid scope reached DB')
 with pytest.raises(BudgetBalanceSnapshotUnavailable):BudgetBalanceSnapshotReader(connection).read(None,None)

# Real PG through the repository session's disposable database, never a business DB.
import json,os,uuid
from contextlib import contextmanager
from aos_api.db import connect_read_only
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from aos_api.aip_budget_store import materialize_revision
from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_reservation_contracts import ReserveBudgetRequest,derive_bucket_authorities
from aos_api.tenant_scope import TenantScope
SCOPE=TenantScope('org-org','dev-project')
@pytest.fixture
def seeded_budget():
    now=datetime.now(timezone.utc)
    bid='test-snapshot-'+uuid.uuid4().hex[:12]
    schema='test_balance_'+uuid.uuid4().hex[:12]
    budget=materialize_revision(SCOPE,'isolated:test',BudgetRevisionCreate(budgetId=bid,revision=1,
        dailyLimitMinor=100,monthlyLimitMinor=1000,alertThresholdPct=80,
        effectiveFrom=now-timedelta(days=1),effectiveUntil=now+timedelta(days=2),
        owner='isolated:owner',overBudgetApprover='isolated:checker',lifecycle='active'))
    ref=lambda kind,rid:{'resourceType':kind,'resourceId':rid,'revision':1,'contentHash':'sha256:'+'a'*64}
    request=ReserveBudgetRequest(operationId='isolated:snapshot',invocationKey=uuid.uuid4().hex,
        taskRef=ref('Task','test-only:unapproved-task'),policyRef={**ref('BudgetRevision',bid),'contentHash':'sha256:'+budget.content_hash},
        pricingRef=ref('ModelPriceSnapshotRevision','test-only:no-price-grant'),
        approvalRef=ref('ActionApprovalEvent','test-only:no-execution-approval'),upperBoundMinor=30)
    targets=derive_bucket_authorities(request,checked_at=now,budget_effective_from=budget.effective_from,
        budget_effective_until=budget.effective_until,daily_limit_minor=100,pilot_limit_minor=1000)
    with psycopg.connect(os.environ['AOS_DATABASE_URL'],row_factory=dict_row) as c:
        assert c.info.dbname.startswith('aos_test_') and c.info.dbname.endswith('_ti4_test')
        # Observation fixtures omit activation triggers; original public guards stay intact.
        c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        for name in ['aip_budget_head','aip_budget_revision','aip_budget_bucket']:
            c.execute(sql.SQL('CREATE TABLE {}.{} (LIKE public.{} INCLUDING ALL)').format(sql.Identifier(schema),sql.Identifier(name),sql.Identifier(name)))
            c.execute(sql.SQL('GRANT SELECT ON {}.{} TO aos_runtime').format(sql.Identifier(schema),sql.Identifier(name)))
        c.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(schema)))
        c.execute(sql.SQL('SET LOCAL search_path TO {},public').format(sql.Identifier(schema)))
        c.execute('INSERT INTO aip_budget_head(org_id,project_id,budget_id,current_revision,version) VALUES(%s,%s,%s,1,1)',(*SCOPE.key,bid))
        insert_budget(c,budget)
        for t in targets:
            c.execute('INSERT INTO aip_budget_bucket(org_id,project_id,bucket_kind,account_id,period_start,period_end,currency,limit_minor,held_minor,submitted_minor,settled_minor,unknown_minor) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,3,2,1,0)',(*SCOPE.key,t.kind,t.account_id,t.period_start,t.period_end,t.currency,t.limit_minor))
    @contextmanager
    def read(scope):
        with connect_read_only(scope) as c:
            c.execute(sql.SQL('SET LOCAL search_path TO {},public').format(sql.Identifier(schema)))
            yield c
    return request,budget,targets,schema,read

def insert_budget(c,budget):
    names=['org_id','project_id','budget_id','revision','content_hash','lifecycle','environment','currency',
        'daily_limit_minor','monthly_limit_minor','alert_threshold_pct','hard_stop','unknown_usage_behavior',
        'effective_from','effective_until','owner','over_budget_approver','payload','created_by','created_at']
    data={**budget.model_dump(mode='python'),'org_id':budget.tenant.org_id,'project_id':budget.tenant.project_id,
        'lifecycle':budget.lifecycle.value,'payload':json.dumps(budget.model_dump(mode='json',by_alias=True))}
    c.execute(sql.SQL('INSERT INTO aip_budget_revision({}) VALUES({})').format(sql.SQL(',').join(map(sql.Identifier,names)),sql.SQL(',').join(sql.Placeholder() for _ in names)),[data[n] for n in names])

def test_pg_exact_current_three_buckets_do_not_authorize_proposed_cost(seeded_budget):
    request,budget,targets,schema,read=seeded_budget
    snap=BudgetBalanceSnapshotReader(read).read(SCOPE,request)
    assert snap.budget_hash==budget.content_hash and snap.head_version==1
    assert [x.exposure_minor for x in snap.buckets]==[6,6,6]
    assert [x.remaining_minor for x in snap.buckets]==[24,94,994]
    assert snap.buckets[0].blocker_codes==('BUDGET_LIMIT_EXCEEDED',)
    assert all(not x.blocker_codes for x in snap.buckets[1:])
    assert not snap.execution_authorized and not snap.cost_upper_bound_authorized
    assert len(snap.snapshot_hash)==64

@pytest.mark.parametrize('change,code',[('unknown','BUDGET_USAGE_UNKNOWN'),('limit','BUDGET_BUCKET_AUTHORITY_DRIFTED'),('missing','BUDGET_BUCKET_UNAVAILABLE')])
def test_pg_actual_ledger_fault_is_observed(seeded_budget,change,code):
    request,budget,targets,schema,read=seeded_budget;t=targets[1]
    with psycopg.connect(os.environ['AOS_DATABASE_URL']) as c:
        c.execute(sql.SQL('SET LOCAL search_path TO {},public').format(sql.Identifier(schema)))
        if change=='missing':c.execute('DELETE FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s AND bucket_kind=%s AND account_id=%s',(*SCOPE.key,t.kind,t.account_id))
        elif change=='unknown':c.execute('UPDATE aip_budget_bucket SET unknown_minor=9 WHERE org_id=%s AND project_id=%s AND bucket_kind=%s AND account_id=%s',(*SCOPE.key,t.kind,t.account_id))
        else:c.execute('UPDATE aip_budget_bucket SET limit_minor=101 WHERE org_id=%s AND project_id=%s AND bucket_kind=%s AND account_id=%s',(*SCOPE.key,t.kind,t.account_id))
    snap=BudgetBalanceSnapshotReader(read).read(SCOPE,request)
    assert code in snap.buckets[1].blocker_codes
    assert not snap.execution_authorized and not snap.cost_upper_bound_authorized

def test_pg_head_change_and_cross_tenant_are_not_old_authority(seeded_budget):
    request,budget,_,schema,read=seeded_budget
    with pytest.raises(BudgetBalanceSnapshotUnavailable):BudgetBalanceSnapshotReader(read).read(TenantScope('dev-org','dev-project'),request)
    with psycopg.connect(os.environ['AOS_DATABASE_URL']) as c:
        c.execute(sql.SQL('SET LOCAL search_path TO {},public').format(sql.Identifier(schema)))
        create=BudgetRevisionCreate.model_validate(budget.model_dump(include=set(BudgetRevisionCreate.model_fields)))
        newer=materialize_revision(SCOPE,'isolated:test',create.model_copy(update={'revision':2}))
        insert_budget(c,newer)
        c.execute('UPDATE aip_budget_head SET current_revision=2,version=2 WHERE org_id=%s AND project_id=%s AND budget_id=%s',(*SCOPE.key,budget.budget_id))
    with pytest.raises(BudgetBalanceSnapshotUnavailable):BudgetBalanceSnapshotReader(read).read(SCOPE,request)

def test_pg_readwrite_connection_is_rejected(seeded_budget):
    from aos_api.db import connect
    request,_,_,schema,read=seeded_budget
    with pytest.raises(BudgetBalanceSnapshotUnavailable):BudgetBalanceSnapshotReader(connect).read(SCOPE,request)

def test_pg_original_public_active_insert_guard_remains_intact(seeded_budget):
    request,budget,_,schema,read=seeded_budget
    with psycopg.connect(os.environ['AOS_DATABASE_URL']) as c:
        with pytest.raises(psycopg.Error,match='BUDGET_ACTIVATION_CONSUMPTION_REQUIRED'):
            insert_budget(c,budget)

def test_pg_native_repeatable_snapshot_does_not_mix_concurrent_bucket_commit(seeded_budget):
    request,budget,targets,schema,read=seeded_budget;t=targets[1]
    @contextmanager
    def concurrent_read(scope):
        with read(scope) as c:
            with psycopg.connect(os.environ['AOS_DATABASE_URL']) as writer:
                writer.execute(sql.SQL('SET LOCAL search_path TO {},public').format(sql.Identifier(schema)))
                writer.execute('UPDATE aip_budget_bucket SET held_minor=50 WHERE org_id=%s AND project_id=%s AND bucket_kind=%s AND account_id=%s',(*SCOPE.key,t.kind,t.account_id))
            yield c
    snapshot=BudgetBalanceSnapshotReader(concurrent_read).read(SCOPE,request)
    assert snapshot.buckets[1].exposure_minor==6
    assert snapshot.snapshot_started_at<=snapshot.checked_at
    fresh=BudgetBalanceSnapshotReader(read).read(SCOPE,request)
    assert fresh.buckets[1].exposure_minor==53 and fresh.snapshot_hash!=snapshot.snapshot_hash

def test_pg_read_committed_is_not_a_consistent_three_bucket_snapshot(seeded_budget):
    request,budget,targets,schema,_=seeded_budget
    @contextmanager
    def read(scope):
        from aos_api.tenant_scope import apply_transaction_scope
        with psycopg.connect(os.environ['AOS_DATABASE_URL'],row_factory=dict_row) as c:
            c.read_only=True
            apply_transaction_scope(c,scope)
            c.execute(sql.SQL('SET LOCAL search_path TO {},public').format(sql.Identifier(schema)))
            yield c
    with pytest.raises(BudgetBalanceSnapshotUnavailable):BudgetBalanceSnapshotReader(read).read(SCOPE,request)

def test_pg_actual_expired_budget_fixture_is_not_current(seeded_budget):
    request,budget,targets,schema,read=seeded_budget
    create=BudgetRevisionCreate.model_validate(budget.model_dump(include=set(BudgetRevisionCreate.model_fields)))
    expired=materialize_revision(SCOPE,'isolated:test',create.model_copy(update={'revision':2,
        'effective_from':datetime.now(timezone.utc)-timedelta(days=2),
        'effective_until':datetime.now(timezone.utc)-timedelta(days=1)}))
    with psycopg.connect(os.environ['AOS_DATABASE_URL']) as c:
        c.execute(sql.SQL('SET LOCAL search_path TO {},public').format(sql.Identifier(schema)))
        insert_budget(c,expired)
        c.execute('UPDATE aip_budget_head SET current_revision=2,version=2 WHERE org_id=%s AND project_id=%s AND budget_id=%s',(*SCOPE.key,budget.budget_id))
    ref=request.policy_ref.model_copy(update={'revision':2,'content_hash':'sha256:'+expired.content_hash})
    with pytest.raises(BudgetBalanceSnapshotUnavailable):BudgetBalanceSnapshotReader(read).read(SCOPE,request.model_copy(update={'policy_ref':ref}))
