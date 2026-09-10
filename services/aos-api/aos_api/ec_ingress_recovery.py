"""Internal prepared-stage recovery, not a DLQ worker or execution grant."""
from aos_api.ec_ingress_journal import IngressJournal, IngressJournalConflict
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.ecom_core_models import BatchCommand, DerivedMetricCommand
from aos_api.tenant_scope import TenantScope


def resume_prepared_derived(conn, scope: TenantScope, run_id: str, *,
                            journal: IngressJournal, store: EcomConsistencyStore):
    """Resume exact saved commands under current running-schedule bindings.

    Caller must be the authorized internal executor and supply a tenant-scoped
    journal connection. Transaction retains binding locks across submissions.
    Each derived submission owns its existing receipt transaction: an exception
    can leave a committed prefix, which the next exact invocation safely replays.
    This function does not mark the run/DLQ or projection/Dataset complete.
    """
    with conn.transaction():
        parent = journal.read(conn, scope, run_id)
        if parent is None:
            raise IngressJournalConflict('INGRESS_PARENT_REQUIRED')
        journal.verify_running_schedule(
            conn, scope, run_id=run_id, pipeline_id=parent['pipelineId'],
            source_id=parent['sourceId'], source_revision=parent['sourceRevision'],
            pipeline_hash=parent['pipelineHash'])
        saved = journal.read_derived(conn, scope, run_id)
        if saved is None:
            raise IngressJournalConflict('INGRESS_DERIVED_PREPARATION_REQUIRED')
        command = BatchCommand.model_validate(parent['command'])
        base = store.read_committed_batch(command)
        if base is None:
            raise IngressJournalConflict('INGRESS_BASE_RECEIPT_REQUIRED')
        if base.objects_ignored or base.links_ignored:
            raise IngressJournalConflict('INGRESS_BASE_RECONCILIATION_REQUIRED')
        commands = tuple(DerivedMetricCommand.model_validate(raw) for raw in saved['commands'])
        return tuple(store.update_derived_metrics(command) for command in commands)
