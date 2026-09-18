"""Recover original conditional retirements; report remaining current-row defects."""
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ingress_recovery import _check_active
from aos_api.pipeline_controlled_projection import _project_exact_command
from aos_api.pipeline_snapshot_group_link_executor import ControlledSnapshotGroupLinkExecutor
from aos_api.pipeline_snapshot_group_retirement_journal import PipelineSnapshotGroupRetirementJournal


class ControlledSnapshotGroupRetirementExecutor:
    def __init__(self, *, claims, store, connect, eng):
        self._links = ControlledSnapshotGroupLinkExecutor(claims=claims, store=store, connect=connect, eng=eng)
        self._retirement = PipelineSnapshotGroupRetirementJournal(claims=claims, store=store)
        self._store = store

    def _transaction(self, scope):
        return self._links._transaction(scope)

    def execute(self, *, scope, group_id, actor, bindings, policy_ref, deadline=None, cancel_event=None):
        args = dict(scope=scope, group_id=group_id, actor=actor, bindings=bindings, policy_ref=policy_ref)
        active = dict(deadline=deadline, cancel_event=cancel_event)
        links = self._links.execute(**args, **active)
        _check_active(**active)
        with self._transaction(scope) as conn:
            prepared = self._retirement.prepare(conn, **args)
        _check_active(**active)

        def current(conn):
            saved = self._retirement.read_current(conn, **args)
            if (saved.audit_hash, saved.preparation_hash, saved.command) != (
                    prepared.audit_hash, prepared.preparation_hash, prepared.command):
                raise IngressJournalConflict('RETIREMENT_PREPARATION_CHANGED')
            return saved

        with self._transaction(scope) as conn:
            saved = current(conn)
        _check_active(**active)
        result = self._store.apply_strict_link_retirement_batch(saved.command) if saved.command is not None else None
        _check_active(**active)
        with self._transaction(scope) as conn:
            current(conn)
        # Store effects are already committed; failures after here recover the
        # same original command and conditional Receipt, never a guessed batch.
        with self._transaction(scope) as conn:
            saved = current(conn)
            projection = (_project_exact_command(conn, scope, saved.command, [], store=self._store,
                          max_events=24000, **active) if saved.command is not None
                          else {'projected': 0, 'pending': 0})
            _check_active(**active)
            current(conn)
        with self._transaction(scope) as conn:
            saved = current(conn)
            completion = (self._store.read_batch_projection_completion(saved.command, [])
                          if saved.command is not None else {'expected': 0, 'projected': 0, 'pending': 0})
            if completion['pending']:
                raise IngressJournalConflict('RETIREMENT_PROJECTION_PENDING')
            audit = self._retirement._audit.read_current(conn, **args)
            _check_active(**active)
            current(conn)
        attention = any(counts[key] for counts in audit.counts.values()
                        for key in ('missingExpected', 'extraActive', 'uncertainReferences'))
        return dict(group_id=group_id, preparation_hash=prepared.preparation_hash, links=links,
                    replayed=result.replayed if result else not prepared.created,
                    projection=projection, completion=completion, reconciliation_scope='current_present_rows',
                    reconciliation_status='requires_attention' if attention else 'complete',
                    relationship_counts=audit.counts, relationship_audit_hash=audit.content_hash)
