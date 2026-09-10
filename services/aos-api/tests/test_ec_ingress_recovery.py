"""Saved-command recovery with real SQLite receipt/CAS owner, mocked PG journal."""
from contextlib import nullcontext
from unittest.mock import Mock

import pytest
from sqlalchemy import select, func

from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ingress_recovery import resume_prepared_derived
from aos_api.ecom_consistency_store import ecom_derived_receipt
from aos_api.tenant_scope import TenantScope
from test_ecom_consistency_store import store, batch, obj, scope, _derived_command, NOW, ident


@pytest.fixture
def prepared(store):
    command = batch(obj('Payment', 'payment-1', properties={'orderId':'o-1','outTradeNo':'t-1','payStatus':'1','updatedAt':NOW}), batch_scope=scope(stream='P12-payment'))
    envelope = dict(runId='run-1',pipelineId='P12-payment',sourceId='source-1',
                    sourceRevision='00000000-0000-0000-0000-000000000001',
                    pipelineHash='a'*64,command=command.model_dump(mode='json'))
    journal = Mock()
    journal.read.return_value = envelope
    journal.read_derived.return_value = {'commands': [_derived_command().model_copy(update={'input_revision':1}).model_dump(mode='json')]}
    conn = Mock()
    conn.transaction.return_value = nullcontext()
    return command, journal, conn


def resume(store, prepared):
    _, journal, conn = prepared
    return resume_prepared_derived(conn, TenantScope('org-a','workspace-a'), 'run-1',
                                   journal=journal, store=store)


def test_saved_command_replay_keeps_one_derived_receipt(store, prepared):
    command, journal, conn = prepared
    store.apply_batch(command)
    assert resume(store,prepared)[0].replayed is False
    # The stored expected revision remains zero after the first commit.
    assert resume(store,prepared)[0].replayed is True
    with store._engine.connect() as c:
        assert c.execute(select(func.count()).select_from(ecom_derived_receipt)).scalar_one() == 1
    assert journal.verify_running_schedule.call_count == 2
    assert journal.save.call_count == 0


@pytest.mark.parametrize('missing', ['parent','derived','base'])
def test_missing_stage_never_submits(store,prepared,missing):
    command,journal,_ = prepared
    if missing != 'base':
        store.apply_batch(command)
    if missing == 'parent':
        journal.read.return_value = None
    elif missing == 'derived':
        journal.read_derived.return_value = None
    store.update_derived_metrics = Mock()
    with pytest.raises(IngressJournalConflict):
        resume(store,prepared)
    store.update_derived_metrics.assert_not_called()


def test_current_binding_denial_never_submits(store,prepared):
    command,journal,_ = prepared
    store.apply_batch(command)
    journal.verify_running_schedule.side_effect = IngressJournalConflict('INGRESS_SOURCE_CONFIGURATION_DRIFT')
    store.update_derived_metrics = Mock()
    with pytest.raises(IngressJournalConflict,match='INGRESS_SOURCE_CONFIGURATION_DRIFT'):
        resume(store,prepared)
    store.update_derived_metrics.assert_not_called()


def test_ignored_base_requires_reconciliation(store,prepared):
    command,_,_ = prepared
    store.apply_batch(command)
    original = store.read_committed_batch(command)
    store.read_committed_batch = Mock(return_value=original.model_copy(update={'links_ignored':1}))
    store.update_derived_metrics = Mock()
    with pytest.raises(IngressJournalConflict,match='INGRESS_BASE_RECONCILIATION_REQUIRED'):
        resume(store,prepared)
    store.update_derived_metrics.assert_not_called()


def test_partial_submission_resumes_original_commands(store,prepared):
    command,journal,_ = prepared
    second = command.objects[0].model_copy(update={'identity':ident('payment-2')})
    command = batch(command.objects[0],second,batch_scope=command.scope)
    journal.read.return_value['command'] = command.model_dump(mode='json')
    derived2 = _derived_command(key='metric-2').model_copy(update={'identity':ident('payment-2')})
    journal.read_derived.return_value['commands'].append(derived2.model_dump(mode='json'))
    for item in journal.read_derived.return_value['commands']:
        item['input_revision'] = 2
    store.apply_batch(command)
    original = store.update_derived_metrics
    calls = 0
    def fail_second(cmd):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('SIMULATED_INTERRUPTION')
        return original(cmd)
    store.update_derived_metrics = fail_second
    with pytest.raises(RuntimeError,match='SIMULATED_INTERRUPTION'):
        resume(store,prepared)
    store.update_derived_metrics = original
    results = resume(store,prepared)
    assert [r.replayed for r in results] == [True,False]
    with store._engine.connect() as c:
        assert c.execute(select(func.count()).select_from(ecom_derived_receipt)).scalar_one() == 2


def test_recovery_saves_before_submitting_and_does_not_reprepare_on_retry(store):
    from contextlib import contextmanager
    from test_ec_ingress_input import prepared as prepare_input
    from aos_api.ec_ingress_recovery import recover_saved_authoritative_stages
    tenant,pipeline,row,command,_ = prepare_input()
    journal = Mock()
    journal.read.return_value = dict(runId='run',pipelineId=pipeline.id,sourceId='source',sourceRevision='revision',pipelineHash='a'*64,
                                    command=command.model_dump(mode='json'),outputRows=[row])
    journal.read_derived.return_value = None
    committed = False
    pending = None
    @contextmanager
    def connect(scope):
        nonlocal committed,pending
        conn=Mock()
        conn.transaction.return_value=nullcontext()
        yield conn
        if pending is not None:
            journal.read_derived.return_value=pending
            pending=None
            committed=True
    def save(conn,scope,run_id,commands):
        nonlocal pending
        pending={'commands':[c.model_dump(mode='json') for c in commands]}
        return pending
    journal.save_derived.side_effect=save
    original=store.update_derived_metrics
    def submit(command):
        assert committed
        return original(command)
    store.update_derived_metrics=submit
    first=recover_saved_authoritative_stages(connect,tenant,'run',journal=journal,store=store)
    assert first[0].updated
    second=recover_saved_authoritative_stages(connect,tenant,'run',journal=journal,store=store)
    assert second[0].replayed
    assert journal.save_derived.call_count == 1


def test_saved_wrong_watermark_never_submits(store,prepared):
    command,journal,_=prepared
    store.apply_batch(command)
    journal.read_derived.return_value['commands'][0]['input_revision']=999
    store.update_derived_metrics=Mock()
    with pytest.raises(IngressJournalConflict,match='INGRESS_DERIVED_WATERMARK_DRIFT'):
        resume(store,prepared)
    store.update_derived_metrics.assert_not_called()


def test_old_unprepared_batch_without_input_never_applies_base(store,prepared):
    from contextlib import contextmanager
    from aos_api.ec_ingress_recovery import recover_saved_authoritative_stages
    _,journal,conn=prepared
    journal.read_derived.return_value=None
    @contextmanager
    def factory(scope):
        yield conn
    store.apply_batch=Mock()
    with pytest.raises(IngressJournalConflict,match='INGRESS_OUTPUT_REQUIRED'):
        recover_saved_authoritative_stages(factory,TenantScope('org-a','workspace-a'),'run-1',journal=journal,store=store)
    store.apply_batch.assert_not_called()


def test_completion_reads_full_saved_preparation(store,prepared):
    from aos_api.ec_ingress_recovery import read_saved_projection_completion
    from aos_api.ecom_core_models import DerivedMetricCommand
    command,journal,conn=prepared
    store.apply_batch(command)
    store.update_derived_metrics(DerivedMetricCommand.model_validate(journal.read_derived.return_value['commands'][0]))
    assert read_saved_projection_completion(conn,TenantScope('org-a','workspace-a'),'run-1',journal=journal,store=store)=={'expected':2,'projected':0,'pending':2}
