"""Real storage transactions in the disposable test database, not live approval."""
import os
from copy import deepcopy
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

from test_product_event_binding import pair, body
from ecommerce_growth.ecommerce_product_event_binding import prepare_event_case_binding
from ecommerce_growth.ecommerce_business_investigation_case import canonical_hash


@pytest.fixture
def stored(pair):
    current,policy=pair
    with psycopg.connect(os.environ['AOS_DATABASE_URL'],row_factory=dict_row) as conn:
        assert conn.execute('SELECT current_database() AS db').fetchone()['db'].endswith('_ti4_test')
        raw=current.authority_payload()
        conn.execute('''INSERT INTO ecommerce_investigation_case_head
            (org_id,project_id,case_id,current_revision,version,lifecycle,analysis_type,channel_id,business_entity_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (current.tenant.org_id,current.tenant.project_id,current.case_id,current.revision,current.version,
             current.lifecycle.value,current.analysis_type.value,current.channel_ref.resource_id,current.business_entity_ref.resource_id))
        conn.execute('''INSERT INTO ecommerce_investigation_case_revision
            (org_id,project_id,case_id,revision,version,prior_revision,content_hash,lifecycle,analysis_type,
             channel_id,business_entity_id,entity_channel_binding_id,idempotency_key,request_hash,authority_data,created_by,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (current.tenant.org_id,current.tenant.project_id,current.case_id,current.revision,current.version,
             current.revision-1,current.content_hash,current.lifecycle.value,current.analysis_type.value,
             current.channel_ref.resource_id,current.business_entity_ref.resource_id,current.entity_channel_binding_ref.resource_id,
             'fixture-seed',current.content_hash,Jsonb(raw),current.created_by,current.created_at))
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
            (current.tenant.org_id,current.tenant.project_id))
        conn.execute('SET LOCAL ROLE aos_runtime')
        try:yield conn,prepare_event_case_binding(current,policy)
        finally:conn.rollback()


def put(conn,binding,key='first',policy=None,case=None):
    policy=policy or binding.policy.authority_payload();case=case or binding.case.authority_payload()
    digest=canonical_hash({'policy':policy,'case':case})
    return conn.execute('SELECT * FROM ecommerce_product_event_policy_put_a0v_040(%s,%s,%s,%s,%s,%s)',
        (key,binding.policy.revision-1,binding.case.revision-1,digest,Jsonb(policy),Jsonb(case))).fetchone()


def test_atomic_binding_replay_and_disabled_projection(stored):
    conn,binding=stored
    first=put(conn,binding);again=put(conn,binding)
    assert first['replayed'] is False and again['replayed'] is True
    assert first['policy_authority']==again['policy_authority']==binding.policy.authority_payload()
    assert first['case_authority']==binding.case.authority_payload()
    row=conn.execute('SELECT current_revision,enabled FROM ecommerce_investigation_schedule_policy_head').fetchone()
    assert row=={'current_revision':1,'enabled':False}
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_investigation_schedule_policy_command_receipt').fetchone()['n']==1
    with pytest.raises(psycopg.errors.CheckViolation),conn.transaction():put(conn,binding,'stale')
    with pytest.raises(psycopg.errors.InsufficientPrivilege),conn.transaction():
        conn.execute('UPDATE ecommerce_investigation_schedule_policy_head SET enabled=true')


@pytest.mark.parametrize('change',['tenant','hash','case-business','missing-schema','method'])
def test_invalid_pair_cannot_write_half(stored,change):
    conn,binding=stored;p=deepcopy(binding.policy.authority_payload());c=deepcopy(binding.case.authority_payload())
    if change=='tenant':p['tenant']['orgId']='other'
    elif change=='hash':p['contentHash']='sha256:'+'b'*64
    elif change=='case-business':c['title']='different'
    elif change=='missing-schema':p.pop('schemaVersion')
    else:p['methodRef']['contentHash']='sha256:'+'b'*64
    if change in ('tenant','method'):
        p['contentHash']=canonical_hash({k:v for k,v in p.items() if k!='contentHash'})
        c['schedulePolicyRef']['contentHash']=p['contentHash']
    if change!='hash':c['contentHash']=canonical_hash({k:v for k,v in c.items() if k!='contentHash'})
    with pytest.raises(psycopg.errors.CheckViolation),conn.transaction():put(conn,binding,policy=p,case=c)
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_investigation_schedule_policy_revision').fetchone()['n']==0
    assert conn.execute('SELECT current_revision FROM ecommerce_investigation_case_head').fetchone()['current_revision']==binding.case.revision-1


def test_outer_failure_rolls_back_both_histories(stored):
    conn,binding=stored
    with pytest.raises(RuntimeError),conn.transaction():
        put(conn,binding)
        raise RuntimeError('fixture outer rollback')
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_investigation_schedule_policy_command_receipt').fetchone()['n']==0
    assert conn.execute('SELECT current_revision FROM ecommerce_investigation_case_head').fetchone()['current_revision']==binding.case.revision-1


def test_successor_and_original_receipt_survive_current_head_change(stored):
    from test_product_event_schedule import seal, ref
    from ecommerce_growth.ecommerce_product_event_schedule import ProductEventSchedulePolicy
    conn,first=stored
    put(conn,first)
    raw=first.policy.authority_payload();raw['revision']=2
    raw['priorRef']=ref('SchedulePolicyRevision',first.policy.policy_id)
    raw['priorRef']['contentHash']=first.policy.content_hash
    raw['caseRef'].update(revision=first.case.revision,contentHash=first.case.content_hash)
    second=prepare_event_case_binding(first.case,ProductEventSchedulePolicy.from_authority(seal(raw)),previous_policy=first.policy)
    assert put(conn,second,'second')['replayed'] is False
    assert put(conn,first)['replayed'] is True
    assert conn.execute('SELECT current_revision,enabled FROM ecommerce_investigation_schedule_policy_head').fetchone()=={'current_revision':2,'enabled':False}
    assert conn.execute('SELECT current_revision FROM ecommerce_investigation_case_head').fetchone()['current_revision']==second.case.revision


@pytest.mark.parametrize('field',['objectTypes','effectiveFrom','createdBy','sourceSelectionRef','priorRef','maxSourceAgeSeconds'])
def test_rehashed_null_is_rejected(stored,field):
    conn,binding=stored
    p=deepcopy(binding.policy.authority_payload());c=deepcopy(binding.case.authority_payload())
    p[field]=None if field!='priorRef' else {}
    p['contentHash']=canonical_hash({k:v for k,v in p.items() if k!='contentHash'})
    c['schedulePolicyRef']['contentHash']=p['contentHash']
    c['contentHash']=canonical_hash({k:v for k,v in c.items() if k!='contentHash'})
    with pytest.raises(psycopg.errors.CheckViolation),conn.transaction():put(conn,binding,policy=p,case=c)


def test_scope_missing_and_same_key_conflict(stored):
    conn,binding=stored;put(conn,binding)
    p=deepcopy(binding.policy.authority_payload());c=deepcopy(binding.case.authority_payload())
    p['shopId']='other-shop'
    p['contentHash']=canonical_hash({k:v for k,v in p.items() if k!='contentHash'})
    c['schedulePolicyRef']['contentHash']=p['contentHash']
    c['contentHash']=canonical_hash({k:v for k,v in c.items() if k!='contentHash'})
    with pytest.raises(psycopg.errors.CheckViolation),conn.transaction():put(conn,binding,policy=p,case=c)
    with pytest.raises(psycopg.errors.CheckViolation),conn.transaction():
        conn.execute("SELECT set_config('aos.project_id','',true)")
        put(conn,binding)


@pytest.mark.parametrize('stamp',['2026-09-13T06:00:60+00:00','2026-09-13T06:00:00.000000+00:00'])
def test_noncanonical_utc_cannot_be_normalized_by_database(stored,stamp):
    conn,binding=stored;p=binding.policy.authority_payload();c=binding.case.authority_payload()
    p['effectiveFrom']=stamp
    p['contentHash']=canonical_hash({k:v for k,v in p.items() if k!='contentHash'})
    c['schedulePolicyRef']['contentHash']=p['contentHash']
    c['contentHash']=canonical_hash({k:v for k,v in c.items() if k!='contentHash'})
    with pytest.raises(psycopg.errors.CheckViolation),conn.transaction():put(conn,binding,policy=p,case=c)
