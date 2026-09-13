"""Owner callback sequencing only; source/journal are named test doubles."""
from types import SimpleNamespace
import pytest
from tests.test_ecommerce_product_event_policy import case
import aos_api.ecommerce_product_event_reader as module


@pytest.fixture
def reader(monkeypatch):
    policy,selection=case();events=[]
    mapping=module.SnapshotMapping(selection.read_spec,(),(),(),'niushop','site_id','1','Asia/Shanghai',())
    def owned(self,conn,*,execute,**kw):
        events.append('owner-enter')
        result=execute(selection.draft,mapping)
        events.append('owner-exit')
        return result
    monkeypatch.setattr(module.PipelineSourceSelectionOwner,'run_current_snapshot',owned)
    monkeypatch.setattr(module.ControlledIngressJournal,'lock_run',lambda *args:events.append('run-lock'))
    monkeypatch.setattr(module.ControlledIngressJournal,'read_derived',lambda *args:{'commands':[]})
    draft=selection.draft
    parent=dict(pipelineId=draft.pipeline_id,sourceId=draft.source_id,
        sourceRevision=draft.source_configuration_ref.resource_id.removeprefix('source-config-'),
        pipelineHash=draft.graph_hash,kind='empty_observation_v1')
    monkeypatch.setattr(module,'_bound_parent',lambda *args:parent)
    value=module.ProductEventCandidateReader(object.__new__(module.PipelineSourceSelectionOwner),
        journal=object.__new__(module.ControlledIngressJournal),store=object.__new__(module.EcomConsistencyStore))
    return value,policy,events,parent


def test_empty_observation_callback_is_inside_owner(reader):
    value,policy,events,_=reader
    def consume(rows):
        assert rows==()
        events.append('consume')
        return 'done'
    assert value.run_candidates(object(),policy=policy,actor='fixture',run_id='run',execute=consume)=='done'
    assert events==['owner-enter','run-lock','consume','owner-exit']


def test_callback_failure_is_not_swallowed(reader):
    value,policy,events,_=reader
    def fail(rows):raise RuntimeError('rollback required')
    with pytest.raises(RuntimeError,match='rollback'):
        value.run_candidates(object(),policy=policy,actor='fixture',run_id='run',execute=fail)
    assert events==['owner-enter','run-lock']


def test_deferred_callback_rejected_inside_owner(reader):
    value,policy,events,_=reader
    def consume(rows):yield 'later'
    with pytest.raises(ValueError,match='locked transaction'):
        value.run_candidates(object(),policy=policy,actor='fixture',run_id='run',execute=consume)
    assert events==['owner-enter','run-lock']


def test_read_remains_metadata_only(reader):
    value,policy,events,_=reader
    assert value.read(object(),policy=policy,actor='fixture',run_id='run')==()
    assert events==['owner-enter','run-lock','owner-exit']


def test_wrong_original_source_never_calls_consumer(reader):
    value,policy,events,parent=reader;parent['sourceId']='other'
    with pytest.raises(PermissionError):
        value.run_candidates(object(),policy=policy,actor='fixture',run_id='run',
                             execute=lambda rows:pytest.fail('untrusted source reached callback'))
    assert events==['owner-enter','run-lock']


def test_nonempty_candidates_consumed_before_owner_exit(reader,monkeypatch):
    value,policy,events,parent=reader
    parent['kind']='batch';parent['command']={'fixture':'batch'}
    monkeypatch.setattr(module,'BatchCommand',SimpleNamespace(model_validate=lambda raw:raw))
    monkeypatch.setattr(module.EcomConsistencyStore,'read_batch_projection_evidence',lambda *args:())
    rows=({'event_key':'a'*64},)
    monkeypatch.setattr(module,'_read_candidates',lambda *args:rows)
    def consume(actual):
        assert actual==rows
        events.append('consume')
        return ('receipt',)
    assert value.run_candidates(object(),policy=policy,actor='fixture',run_id='run',execute=consume)==('receipt',)
    assert events==['owner-enter','run-lock','consume','owner-exit']


def test_exact_event_cannot_use_empty_observation(reader):
    value,policy,events,_=reader
    with pytest.raises(ValueError,match='unique'):
        value.run_event(object(),policy=policy,actor='fixture',run_id='run',event_key='a'*64,
                        execute=lambda row:pytest.fail('missing event reached analysis'))
    assert events==['owner-enter','run-lock']


def test_exact_event_callback_stays_inside_owner(reader,monkeypatch):
    value,policy,events,parent=reader
    parent['kind']='batch';parent['command']={'fixture':'batch'}
    monkeypatch.setattr(module,'BatchCommand',SimpleNamespace(model_validate=lambda raw:raw))
    monkeypatch.setattr(module.EcomConsistencyStore,'read_batch_projection_evidence',lambda *args:())
    row={'event_key':'a'*64}
    def read(*args,**kwargs):
        assert kwargs=={'event_key':'a'*64}
        return (row,)
    monkeypatch.setattr(module,'_read_candidates',read)
    def consume(actual):
        assert actual==row
        events.append('consume')
        return 'prepared'
    assert value.run_event(object(),policy=policy,actor='fixture',run_id='run',event_key='a'*64,execute=consume)=='prepared'
    assert events==['owner-enter','run-lock','consume','owner-exit']


@pytest.mark.parametrize('fault',['duplicate','wrong-key','deferred'])
def test_exact_event_rejects_ambiguous_or_deferred_consumption(reader,monkeypatch,fault):
    value,policy,events,parent=reader
    parent['kind']='batch';parent['command']={}
    monkeypatch.setattr(module,'BatchCommand',SimpleNamespace(model_validate=lambda raw:raw))
    monkeypatch.setattr(module.EcomConsistencyStore,'read_batch_projection_evidence',lambda *args:())
    rows=({'event_key':'a'*64},)
    if fault=='duplicate':rows=rows+rows
    elif fault=='wrong-key':rows=({'event_key':'b'*64},)
    monkeypatch.setattr(module,'_read_candidates',lambda *args,**kwargs:rows)
    def deferred(row):yield 'outside-lock'
    with pytest.raises(ValueError):
        value.run_event(object(),policy=policy,actor='fixture',run_id='run',event_key='a'*64,
                        execute=deferred if fault=='deferred' else lambda row:pytest.fail('ambiguous event admitted'))
    assert events==['owner-enter','run-lock']
