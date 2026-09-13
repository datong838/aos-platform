"""Candidate SQL semantics only; this fixture is not live source authorization."""
import psycopg
import hashlib
import json
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from test_lifecycle_pg import database, pytestmark
from tests.test_ecommerce_product_event_policy import case
from aos_api.ecommerce_product_event_policy import ProductEventPolicyDraft
from aos_api.ecom_consistency_store import ProjectionEventEvidence
from aos_api.ecommerce_product_event_reader import ProductEventCandidateReader, _read_candidates


def payload_hash():
    raw,_=case()
    return hashlib.sha256(json.dumps({'record':{'source_updated_at':raw['effectiveFrom'].isoformat(),
        'properties':{'private':'never returned'}}},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def proof(*numbers):
    return tuple(ProjectionEventEvidence(str(n).zfill(64),payload_hash(),n,False) for n in numbers)


@pytest.fixture
def events(database):
    conn, _, schema = database
    conn.execute('''CREATE TABLE projection_outbox(outbox_id bigint,input_revision bigint,
        org_id text,project_id text,workspace_id text,platform text,shop_or_marketplace_id text,
        object_type text,event_source text,change_kind text,event_key text,payload_hash text,
        authority_tx_id text,external_id text,created_at timestamptz,payload jsonb,projected boolean)''')
    conn.execute('CREATE TABLE automation_occurrence(org_id text,project_id text,policy_id text,source_event_id text)')
    body, _ = case(); policy = ProductEventPolicyDraft.model_validate(body)
    def insert(db, number, **changes):
        row = dict(outbox_id=number,input_revision=number,org_id=policy.org_id,project_id=policy.project_id,
            workspace_id=policy.project_id,platform=policy.platform,shop_or_marketplace_id=policy.shop_or_marketplace_id,
            object_type='Product',event_source='authoritative_store',change_kind='objects_written',
            event_key=str(number).zfill(64),payload_hash=payload_hash(),authority_tx_id='b'*64,external_id=str(number),
            created_at=policy.effective_from,payload=Jsonb({'record':{'source_updated_at':policy.effective_from.isoformat(),
                'properties':{'private':'never returned'}}}),projected=False)
        row.update(changes)
        db.execute(sql.SQL('INSERT INTO projection_outbox ({}) VALUES ({})').format(
            sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row)),tuple(row.values()))
    return conn, schema, policy, insert


def test_late_committing_smaller_sequence_is_not_lost(events):
    conn,schema,policy,insert=events
    with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres') as late:
        late.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
        insert(late,1)
        insert(conn,2,projected=True)
        assert [item['outbox_id'] for item in _read_candidates(conn,policy,100,proof(1,2))]==[2]
        conn.execute('INSERT INTO automation_occurrence VALUES (%s,%s,%s,%s)',
            (policy.org_id,policy.project_id,policy.policy_id,str(2).zfill(64)))
        late.commit()
        assert [item['outbox_id'] for item in _read_candidates(conn,policy,100,proof(1,2))]==[1]


def test_scope_and_existing_occurrence_are_exact(events):
    conn,_,policy,insert=events
    insert(conn,1);insert(conn,2,projected=True);insert(conn,99)
    for number,change in enumerate([{'org_id':'other'},{'workspace_id':'other'},
        {'shop_or_marketplace_id':'2'},{'object_type':'Order'},{'event_source':'projection'},
        {'created_at':policy.effective_until}],start=3):insert(conn,number,**change)
    conn.execute('INSERT INTO automation_occurrence VALUES (%s,%s,%s,%s)',
        ('other',policy.project_id,policy.policy_id,str(1).zfill(64)))
    rows=_read_candidates(conn,policy,100,proof(*range(1,9)))
    assert [row['outbox_id'] for row in rows]==[1,2]
    assert all('payload' not in row and 'private' not in str(row) for row in rows)
    assert len(_read_candidates(conn,policy,1,proof(1,2)))==1


def test_candidate_reader_rejects_untrusted_owner():
    with pytest.raises(TypeError): ProductEventCandidateReader(object(),journal=object(),store=object())


def test_wrong_original_digest_is_rejected(events):
    conn,_,policy,insert=events;insert(conn,1)
    with pytest.raises(ValueError,match='evidence differs'):
        _read_candidates(conn,policy,100,(ProjectionEventEvidence(str(1).zfill(64),'c'*64,1,False),))


def test_payload_drift_cannot_hide_behind_original_hash(events):
    conn,_,policy,insert=events
    insert(conn,1)
    conn.execute("UPDATE projection_outbox SET payload=jsonb_set(payload,'{record,properties,private}',%s)",
                 (Jsonb('tampered'),))
    with pytest.raises(ValueError,match='payload integrity'):
        _read_candidates(conn,policy,100,proof(1))
