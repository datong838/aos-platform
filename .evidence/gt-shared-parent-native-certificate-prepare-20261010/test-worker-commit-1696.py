"""Unchanged original test functions; retained, redirected test-owned schemas."""
import pytest
from psycopg.conninfo import conninfo_to_dict
from aos_api.db import get_dsn
import test_aip_budget_reservation_pg as budget_fixture
from test_a0v_content_execution_worker_pg import (
    test_concurrent_worker_commits_before_send_and_restart_replays,
    test_unknown_outcome_never_resubmits_after_restart,
    test_preparation_failure_keeps_unsubmitted_reservation,
    test_result_persistence_failure_is_not_a_resubmission_license,
    test_real_invoker_result_shape_is_persisted_and_replayed,
)
from test_a0v_content_result_consumer_pg import (
    test_exact_owner_envelope_runs_once_to_measured_readable_artifact,
    test_usage_artifact_and_budget_commit_or_rollback_together,
)

pytest_plugins = ('tests.conftest',)

@pytest.fixture
def database(_isolated_postgres_database):
    # Original reduced fixture defaults to aos_meta, independent of session DSN.
    # Explicitly bind it to the newly created retained test-only session DB.
    params = conninfo_to_dict(get_dsn())
    assert params['dbname'].startswith('aos_test_')
    assert params['host'] == '127.0.0.1' and params['port'] == '5441'
    previous = dict(budget_fixture.PG)
    budget_fixture.PG.update({k: params[k] for k in ('host', 'port', 'user', 'dbname')})
    original = budget_fixture.database.__wrapped__()
    try:
        yield next(original)
    finally:
        try:
            next(original)
        except StopIteration:
            pass
        finally:
            budget_fixture.PG.clear()
            budget_fixture.PG.update(previous)

import json
from pathlib import Path
from test_a0v_content_execution_worker_pg import setup, ContentExecutionWorker, ContentExecutionFailure
PROOFS=[]

def snapshot(factory,scope,rid):
    with factory(scope) as conn:
        conn.execute("SET LOCAL lock_timeout='500ms'")
        r=conn.execute("SELECT state,provider_request_receipt_ref,xmin::text AS xmin,pg_xact_status(xmin::text::xid8) AS origin_state FROM aip_budget_reservation WHERE reservation_id=%s FOR UPDATE NOWAIT",(rid,)).fetchone()
        buckets=conn.execute("SELECT held_minor,submitted_minor,unknown_minor FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s ORDER BY bucket_id",scope.key).fetchall()
        journal=ContentExecutionJournal(storage_schema=ACTIVE_SCHEMA).read(conn,scope,rid)
        return dict(reservation=dict(r),buckets=[dict(x) for x in buckets],result_present=journal['result'] is not None)

from aos_api.ecommerce_content_execution_journal import ContentExecutionJournal
@pytest.mark.parametrize('outcome',['timeout','persist_failure'])
def test_independent_committed_request_and_risk_survive_unknown(database,outcome):
    global ACTIVE_SCHEMA
    scope,factory,store,rid,prepare=setup(database);ACTIVE_SCHEMA=database.schema
    before=snapshot(factory,scope,rid)
    assert len(before['buckets'])==3
    risk=lambda b:b['held_minor']+b['submitted_minor']+b['unknown_minor']
    assert all(risk(x)>0 for x in before['buckets'])
    calls=[];at_call=[]
    def invoke(*args):
        seen=snapshot(factory,scope,rid);at_call.append(seen);calls.append(1)
        assert seen['reservation']['state']=='submitted'
        assert seen['reservation']['origin_state']=='committed'
        assert seen['reservation']['provider_request_receipt_ref'] is not None
        assert not seen['result_present']
        assert [risk(x) for x in seen['buckets']]==[risk(x) for x in before['buckets']]
        assert all(x['held_minor']==0 and x['unknown_minor']==0 and x['submitted_minor']>0 for x in seen['buckets'])
        if outcome=='timeout':raise TimeoutError('synthetic unknown transport')
        return {'answer':'synthetic observed response'}
    worker=ContentExecutionWorker(factory,prepare=prepare,invoke=invoke,storage_schema=database.schema)
    if outcome=='persist_failure':
        def fail(*a,**k):raise RuntimeError('synthetic persistence failure')
        worker.journal.record_result=fail
    with pytest.raises(ContentExecutionFailure,match='reconciliation required' if outcome=='timeout' else 'do not resubmit'):
        worker.run_one(scope,rid)
    after=snapshot(factory,scope,rid)
    assert after['reservation']['state']==('unknown' if outcome=='timeout' else 'submitted')
    assert after['reservation']['origin_state']=='committed'
    assert after['reservation']['provider_request_receipt_ref']==at_call[0]['reservation']['provider_request_receipt_ref']
    assert not after['result_present']
    assert [risk(x) for x in after['buckets']]==[risk(x) for x in before['buckets']]
    assert all(x['held_minor']==0 and x['unknown_minor' if outcome=='timeout' else 'submitted_minor']>0 for x in after['buckets'])
    restarted=ContentExecutionWorker(factory,prepare=prepare,invoke=invoke,storage_schema=database.schema)
    assert restarted.run_one(scope,rid)['status']=='RECONCILE_ONLY'
    assert len(calls)==1
    assert snapshot(factory,scope,rid)==after
    PROOFS.append(dict(outcome=outcome,schema=database.schema,reservation_id=rid,before=before,at_call=at_call,after=after,synthetic_invocations=len(calls),real_provider_calls=0))
