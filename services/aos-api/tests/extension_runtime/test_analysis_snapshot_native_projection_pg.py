"""Native twelve-object Store/Projector/Dataset composition; assets/source named."""
import hashlib
import json
from types import SimpleNamespace as NS

import pytest

from test_analysis_snapshot_native_ingress_pg import (
    private_database,stored,native_claims_case,native_input_case,
    host_case,control_governed,governed,service_case,pair,body,
)
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_object_executor import ControlledSnapshotGroupObjectExecutor
from aos_api.phase5_pipeline_engine import PipelineEngine
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES


@pytest.fixture
def native_projection_case(native_input_case):
    source,conn,args,state = native_input_case
    source.prepare(**args)
    controls = source._claims._controls
    with source._transaction(args['scope']) as db:
        draft = controls.run_current_snapshot(db,scope=args['scope'],ref=args['bindings'][0][0],
            actor=args['actor'],execute=lambda draft,plan:draft)
    package = draft.package_ref
    selected = NS(publisher=package.publisher,id=package.id,version=package.version,
        content_hash=package.content_hash,signature_fingerprint='named-signature',release_evidence_revision=1)
    document = dict(schemaVersion='aos.snapshot-relationships/v1',
        objectTypes=[item.object_type for item in CANONICAL_QYH_SOURCES],
        rules=[dict(linkType='Shop.hasWeapp',rowType='Weapp',parentType='Shop',
            referenceProperty='siteId',direction='parent-to-row',encoding='positive-id',allowUnset=False)])
    raw = json.dumps(document).encode()
    state['policy_raw'] = raw
    ref = PipelineExactRef(resource_type='SnapshotRelationshipPolicy',resource_id='content/policies/native.json',
        revision=package.version,content_hash='sha256:'+hashlib.sha256(raw).hexdigest())
    selections = controls._selections
    selections._store = NS(load_active_baseline_in_transaction=lambda *a,**k:NS(lock=NS(payload=NS(resolved=[selected]))))
    selections._artifacts = NS(scope=args['scope'],
        load_record=lambda *a:NS(manifest=NS(spec=NS(exports=NS(policies=['content/policies/'])))),
        read_artifact=lambda *a:state['policy_raw'])
    def release(*a,**k):
        if state.get('denied'):
            raise PermissionError('named installed policy denied')
    selections._release_policy = NS(evaluate=release)
    engine = object.__new__(PipelineEngine)
    engine._datasets,engine._builds = {},{}
    executor = ControlledSnapshotGroupObjectExecutor(claims=source._claims,store=source._store,
        connect=source._connect,eng=engine)
    return executor,conn,args|dict(policy_ref=ref),state


@pytest.mark.parametrize('interrupted',[False,True])
def test_native_twelve_object_projection_and_recovery(native_projection_case,monkeypatch,interrupted):
    executor,conn,args,state = native_projection_case
    original = executor._single.resume_saved
    count = 0
    def interrupt(**kwargs):
        nonlocal count
        result = original(**kwargs)
        count += 1
        if count == 1:
            raise RuntimeError('native first member committed')
        return result
    if interrupted:
        monkeypatch.setattr(executor._single,'resume_saved',interrupt)
        with pytest.raises(RuntimeError,match='first member committed'):
            executor.execute(**args)
        assert conn.execute('SELECT count(*) AS n FROM obj_instance').fetchone()['n'] == 1
        monkeypatch.setattr(executor._single,'resume_saved',original)
    result = executor.execute(**args)
    assert len(result['members']) == 12 and result['relationships_applied'] is False
    assert all(member['completion']['pending'] == 0 for member in result['members'])
    tables = ('ecom_object','ecom_ingest_receipt','obj_instance','meta_dataset',
              'meta_dataset_history','ecommerce_ingress_dataset_receipt')
    before = {table:conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in tables}
    assert all(count == 12 for count in before.values())
    again = executor.execute(**args)
    assert all(member['completed_replay'] for member in again['members'])
    assert before == {table:conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in tables}
    assert state['calls'] == 1


def test_native_denied_policy_never_starts_object_application(native_projection_case):
    executor,conn,args,state = native_projection_case
    state['denied'] = True
    with pytest.raises(PermissionError,match='named installed policy denied'):
        executor.execute(**args)
    assert conn.execute('SELECT count(*) AS n FROM ecom_object').fetchone()['n'] == 0
    assert state['calls'] == 1
