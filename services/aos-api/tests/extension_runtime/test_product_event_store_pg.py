"""Host transport tests against the disposable PostgreSQL migration chain."""
import pytest
from test_product_event_write_pg import stored, pair, body
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_product_event_store import ProductEventPolicyStore


def store_for(conn):
    return ProductEventPolicyStore(HostTransaction(conn),TenantScope('org-org','dev-project'))


def write(store,binding,key='event-store'):
    return store.put(idempotency_key=key,expected_policy_revision=binding.policy.revision-1,
        expected_case_version=binding.case.revision-1,policy=binding.policy.authority_payload(),case=binding.case.authority_payload())


def test_put_get_and_original_receipt(stored):
    conn,binding=stored;store=store_for(conn)
    first=write(store,binding);second=write(store,binding)
    assert first['replayed'] is False and second['replayed'] is True
    assert store.get(binding.policy.policy_id)==binding.policy.authority_payload()
    receipt=store.find_receipt('event-store',binding.request_hash)
    assert receipt['policy_authority']==binding.policy.authority_payload()
    assert store.find_receipt('unknown',binding.request_hash) is None
    with pytest.raises(ValueError):store.find_receipt('event-store','sha256:'+'b'*64)


def test_outer_rollback_no_independent_commit(stored):
    conn,binding=stored;store=store_for(conn)
    with pytest.raises(RuntimeError),conn.transaction():
        write(store,binding)
        raise RuntimeError('outer owner rejected')
    assert store.get(binding.policy.policy_id) is None
    assert store.find_receipt('event-store',binding.request_hash) is None


def test_db_scope_is_required(stored):
    conn,binding=stored
    wrong=ProductEventPolicyStore(HostTransaction(conn),TenantScope('dev-org','dev-project'))
    with pytest.raises(ValueError):write(wrong,binding)
    with conn.transaction():
        conn.execute("SELECT set_config('aos.project_id','',true)")
        with pytest.raises(ValueError):store_for(conn).get(binding.policy.policy_id)


def test_rehashed_case_drift_is_not_accepted(stored):
    from ecommerce_growth.ecommerce_business_investigation_case import canonical_hash
    import psycopg
    conn,binding=stored;case=binding.case.authority_payload();case['title']='drift'
    case['contentHash']=canonical_hash({k:v for k,v in case.items() if k!='contentHash'})
    with pytest.raises(psycopg.errors.CheckViolation),conn.transaction():
        store_for(conn).put(idempotency_key='bad',expected_policy_revision=0,
            expected_case_version=binding.case.revision-1,policy=binding.policy.authority_payload(),case=case)
    assert store_for(conn).get(binding.policy.policy_id) is None


def test_corrupt_transport_response_rolls_back_in_owner(stored):
    conn,binding=stored
    class Connection:
        def execute(self,query,params=()):
            cursor=conn.execute(query,params)
            if 'FROM ecommerce_product_event_policy_put_a0v_040' not in query:return cursor
            row=cursor.fetchone();row['case_authority']={}
            class Result:
                def fetchone(self):return row
            return Result()
    store=ProductEventPolicyStore(HostTransaction(Connection()),TenantScope('org-org','dev-project'))
    with pytest.raises(ValueError,match='response mismatch'),conn.transaction():write(store,binding)
    assert store_for(conn).get(binding.policy.policy_id) is None


def test_receipt_is_original_after_successor(stored):
    from test_product_event_schedule import seal,ref
    from ecommerce_growth.ecommerce_product_event_schedule import ProductEventSchedulePolicy
    from ecommerce_growth.ecommerce_product_event_binding import prepare_event_case_binding
    conn,first=stored;store=store_for(conn);write(store,first)
    raw=first.policy.authority_payload();raw['revision']=2
    raw['priorRef']=ref('SchedulePolicyRevision',first.policy.policy_id)
    raw['priorRef']['contentHash']=first.policy.content_hash
    raw['caseRef'].update(revision=first.case.revision,contentHash=first.case.content_hash)
    second=prepare_event_case_binding(first.case,ProductEventSchedulePolicy.from_authority(seal(raw)),previous_policy=first.policy)
    write(store,second,'second')
    assert store.get(first.policy.policy_id)['revision']==2
    assert store.find_receipt('event-store',first.request_hash)['policy_authority']['revision']==1
    assert write(store,first)['replayed'] is True


def test_current_event_binding_reads_saved_policy_and_current_case(stored):
    conn,binding=stored;store=store_for(conn)
    assert store.get_current_binding(binding.policy.policy_id) is None
    write(store,binding)
    assert store.get_current_binding(binding.policy.policy_id)=={
        'policy':binding.policy.authority_payload(),'caseAuthority':binding.case.authority_payload()}


@pytest.mark.parametrize('fault',['head_hash','case_closed','case_policy'])
def test_current_event_binding_rejects_drift(stored,fault):
    from psycopg.types.json import Jsonb
    from aos_api.aip_budget_reservation_store import canonical_hash
    conn,binding=stored;store=store_for(conn);write(store,binding)
    with conn.transaction():
        conn.execute('RESET ROLE')
        if fault=='head_hash':
            conn.execute('UPDATE ecommerce_investigation_schedule_policy_head SET content_hash=%s',('sha256:'+'0'*64,))
        else:
            raw=binding.case.authority_payload()
            if fault=='case_closed':raw['lifecycle']='CLOSED'
            else:raw['schedulePolicyRef']['resourceId']='other'
            raw['revision']=raw['version']=binding.case.revision+1
            raw['priorRef']=dict(resourceType='BusinessInvestigationCaseRevision',resourceId=binding.case.case_id,
                revision=binding.case.revision,contentHash=binding.case.content_hash,receiptId=None)
            raw['contentHash']=canonical_hash({k:v for k,v in raw.items() if k!='contentHash'},prefixed=True)
            changes=dict(revision=raw['revision'],version=raw['version'],prior_revision=binding.case.revision,
                authority_data=raw,content_hash=raw['contentHash'],lifecycle=raw['lifecycle'],idempotency_key='successor-fixture')
            conn.execute('''INSERT INTO ecommerce_investigation_case_revision
                SELECT (jsonb_populate_record(NULL::ecommerce_investigation_case_revision,to_jsonb(r)||%s)).*
                FROM ecommerce_investigation_case_revision r WHERE revision=%s''',
                (Jsonb(changes),binding.case.revision))
            conn.execute('UPDATE ecommerce_investigation_case_head SET current_revision=%s,version=%s,lifecycle=%s',
                (raw['revision'],raw['version'],raw['lifecycle']))
        conn.execute('SET LOCAL ROLE aos_runtime')
        with pytest.raises(ValueError,match='current event binding'):
            store.get_current_binding(binding.policy.policy_id)
