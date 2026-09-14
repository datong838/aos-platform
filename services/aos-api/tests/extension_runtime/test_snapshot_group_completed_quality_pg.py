"""Actual PG object/projection/dataset receipts; termination and assets are fixtures."""
import hashlib
import json
from types import SimpleNamespace
import pytest
from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from test_snapshot_group_assessment_owner_pg import assessment_case
from test_snapshot_group_relationship_journal_pg import journal_case
from test_snapshot_group_object_executor_pg import object_case
from aos_api.pipeline_snapshot_group_quality_owner import PipelineSnapshotGroupQualityOwner
from aos_api.pipeline_snapshot_relationships import compile_relationship_policy
from aos_api.ec_ingress_journal import IngressJournalConflict


@pytest.fixture
def completed_group(object_case):
    executor, conn, args, state = object_case
    executor.execute(**args)
    relation = compile_relationship_policy(json.loads(state['policy_raw']))
    document = dict(schemaVersion='aos.snapshot-relationship-quality/v1', relationshipPolicyHash=relation.content_hash,
        purposes=[dict(purposeCode='initial_store_analysis', rules=[dict(linkType='Shop.hasWeapp',requirement='required')])])
    raw = json.dumps(document).encode()
    ref = args['policy_ref'].model_copy(update={'resource_type':'SnapshotRelationshipQualityPolicy',
        'resource_id':'content/policies/quality.json', 'content_hash':'sha256:'+hashlib.sha256(raw).hexdigest()})
    claims = executor._single._ingress._claims
    claims._controls._selections._artifacts.read_artifact = lambda selected,path,limit: raw if path == ref.resource_id else state['policy_raw']
    conn.execute('RESET ROLE')
    conn.execute('ALTER TABLE meta_schedule_run ADD COLUMN IF NOT EXISTS executor_id text, ADD COLUMN IF NOT EXISTS executor_stopped boolean, ADD COLUMN IF NOT EXISTS finished_at timestamptz')
    conn.execute("UPDATE meta_schedule_run SET status='succeeded',executor_id='ec-live-v1',executor_stopped=true,finished_at=clock_timestamp()")
    conn.execute('SET ROLE aos_runtime')
    return executor, conn, args | {'quality_ref':ref}, state, PipelineSnapshotGroupQualityOwner(claims=claims)


def test_completed_group_read_does_not_reopen_running_write_path(completed_group):
    executor, conn, args, state, owner = completed_group
    with conn.transaction(): first = owner.run_completed_current(conn, **args, execute=lambda c:c)
    with conn.transaction(): again = owner.run_completed_current(conn, **args, execute=lambda c:c)
    assert first == again and first.measurement.counts['Shop.hasWeapp']['completeRows'] == 1
    with pytest.raises(IngressJournalConflict), conn.transaction(): owner.run_current(conn, **args, execute=lambda c:c)
    with pytest.raises(IngressJournalConflict): executor.execute(**{k:v for k,v in args.items() if k != 'quality_ref'})
    assert state['calls'] == 1
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_dataset_receipt').fetchone()['n'] == 2


@pytest.mark.parametrize('fault',['running','failed','not_stopped','no_finish','missing_receipt','bad_receipt'])
def test_one_incomplete_member_blocks_whole_completed_group(completed_group, fault):
    _, conn, args, state, owner = completed_group
    updates = dict(running="status='running'", failed="status='failed'", not_stopped='executor_stopped=false', no_finish='finished_at=NULL')
    if fault in updates:
        conn.execute('RESET ROLE')
        conn.execute('UPDATE meta_schedule_run SET '+updates[fault]+' WHERE id=%s',(args['bindings'][0][1],))
        conn.execute('SET ROLE aos_runtime')
    class Proxy:
        def __getattr__(self,name):return getattr(conn,name)
        def execute(self,query,params=()):
            cursor=conn.execute(query,params)
            if fault in ('missing_receipt','bad_receipt') and 'payload,payload_hash' in str(query):
                row=cursor.fetchone()
                return SimpleNamespace(fetchone=lambda:None if fault=='missing_receipt' else dict(row,payload_hash='bad'))
            return cursor
    with pytest.raises(IngressJournalConflict), conn.transaction():
        owner.run_completed_current(Proxy(), **args, execute=lambda c:pytest.fail('incomplete group'))
    assert state['calls'] == 1


def test_completed_group_still_rechecks_current_release(completed_group):
    _, conn, args, state, owner = completed_group
    def consume(current): state['policy_denied'] = True
    with pytest.raises(PermissionError), conn.transaction(): owner.run_completed_current(conn, **args, execute=consume)
    assert state['calls'] == 1
