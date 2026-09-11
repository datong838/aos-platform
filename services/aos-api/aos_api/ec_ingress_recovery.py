"""Internal prepared-stage recovery, not a DLQ worker or execution grant."""
from aos_api.ec_ingress_journal import IngressJournal, IngressJournalConflict
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.ecom_core_models import BatchCommand, DerivedMetricCommand
from aos_api.tenant_scope import TenantScope


def _check_active(deadline=None,cancel_event=None):
    import time
    if cancel_event is not None and cancel_event.is_set():
        raise IngressJournalConflict('INGRESS_CANCELLED')
    if deadline is not None and time.monotonic() >= deadline:
        raise IngressJournalConflict('INGRESS_DEADLINE_EXCEEDED')


def resume_prepared_derived(conn, scope: TenantScope, run_id: str, *,
                            journal: IngressJournal, store: EcomConsistencyStore, deadline=None, cancel_event=None):
    """Resume exact saved commands under current running-schedule bindings.

    Caller must be the authorized internal executor and supply a tenant-scoped
    journal connection. Transaction retains binding locks across submissions.
    Each derived submission owns its existing receipt transaction: an exception
    can leave a committed prefix, which the next exact invocation safely replays.
    This function does not mark the run/DLQ or projection/Dataset complete.
    """
    with conn.transaction():
        journal.lock_run(conn, scope, run_id)
        parent = _bound_parent(conn, scope, run_id, journal)
        saved = journal.read_derived(conn, scope, run_id)
        if saved is None:
            raise IngressJournalConflict('INGRESS_DERIVED_PREPARATION_REQUIRED')
        if parent.get('kind') == 'empty_observation_v1':
            _check_active(deadline,cancel_event)
            return ()
        command = BatchCommand.model_validate(parent['command'])
        base = store.read_committed_batch(command)
        if base is None:
            raise IngressJournalConflict('INGRESS_BASE_RECEIPT_REQUIRED')
        commands = tuple(DerivedMetricCommand.model_validate(raw) for raw in saved['commands'])
        revision = store.read_committed_batch_revision(command)
        if any(item.input_revision != revision for item in commands):
            raise IngressJournalConflict('INGRESS_DERIVED_WATERMARK_DRIFT')
        bases = {(item.object_type,item.identity.scoped_key()):item for item in command.objects}
        results = []
        for item in commands:
            _check_active(deadline,cancel_event)
            results.append(store.update_derived_metrics(item,expected_base=bases[(item.object_type,item.identity.scoped_key())]))
        return tuple(results)


def _bound_parent(conn, scope, run_id, journal):
    parent = journal.read(conn, scope, run_id)
    if parent is None:
        raise IngressJournalConflict('INGRESS_PARENT_REQUIRED')
    journal.verify_running_schedule(
        conn, scope, run_id=run_id, pipeline_id=parent['pipelineId'],
        source_id=parent['sourceId'], source_revision=parent['sourceRevision'],
        pipeline_hash=parent['pipelineHash'])
    return parent


def recover_saved_authoritative_stages(connection_factory, scope: TenantScope, run_id: str, *,
                                        journal: IngressJournal, store: EcomConsistencyStore, deadline=None, cancel_event=None):
    """Recover base and derived stages of an already saved, authorized run.

    Factory must yield fresh tenant-scoped connections and COMMIT on successful
    context exit. No derived side effect occurs until that first commit returns.
    This is an internal executor primitive, not a run claim or completion marker.
    """
    from types import SimpleNamespace
    from aos_api.ec_ot_writer import prepare_derived_commands_for_batch
    with connection_factory(scope) as conn:
        with conn.transaction():
            journal.lock_run(conn, scope, run_id)
            parent = _bound_parent(conn, scope, run_id, journal)
            saved = journal.read_derived(conn, scope, run_id)
            if saved is None and 'outputRows' not in parent:
                raise IngressJournalConflict('INGRESS_OUTPUT_REQUIRED')
            if parent.get('kind') == 'empty_observation_v1':
                _check_active(deadline,cancel_event)
                if saved is None:
                    journal.save_derived(conn,scope,run_id,())
                return ()
            command = BatchCommand.model_validate(parent['command'])
            # The original command retains its original checkpoint/idempotency key.
            _check_active(deadline,cancel_event)
            store.apply_batch(command)
            if saved is None:
                commands = prepare_derived_commands_for_batch(
                    SimpleNamespace(ecom_consistency_store=store), scope,
                    SimpleNamespace(id=parent['pipelineId']), command, parent['outputRows'])
                _check_active(deadline,cancel_event)
                journal.save_derived(conn, scope, run_id, commands)
    with connection_factory(scope) as conn:
        return resume_prepared_derived(conn, scope, run_id, journal=journal, store=store,deadline=deadline,cancel_event=cancel_event)


def read_saved_projection_completion(conn, scope: TenantScope, run_id: str, *,
                                     journal: IngressJournal, store: EcomConsistencyStore):
    """Read completion for the complete saved preparation, never a caller subset."""
    with conn.transaction():
        journal.lock_run(conn, scope, run_id)
        parent = _bound_parent(conn, scope, run_id, journal)
        saved = journal.read_derived(conn, scope, run_id)
        if saved is None:
            raise IngressJournalConflict('INGRESS_DERIVED_PREPARATION_REQUIRED')
        if parent.get('kind') == 'empty_observation_v1':
            return {'expected':0,'projected':0,'pending':0}
        return store.read_batch_projection_completion(
            BatchCommand.model_validate(parent['command']),
            [DerivedMetricCommand.model_validate(raw) for raw in saved['commands']])
