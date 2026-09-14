"""Recover saved group candidates through the original Store and exact Projector."""
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ingress_recovery import _check_active
from aos_api.pipeline_controlled_projection import _project_exact_command
from aos_api.pipeline_snapshot_group_object_executor import ControlledSnapshotGroupObjectExecutor
from aos_api.pipeline_snapshot_group_link_command import PipelineSnapshotGroupLinkCommandJournal


class ControlledSnapshotGroupLinkExecutor:
    def __init__(self, *, claims, store, connect, eng):
        self._objects = ControlledSnapshotGroupObjectExecutor(claims=claims, store=store, connect=connect, eng=eng)
        self._commands = PipelineSnapshotGroupLinkCommandJournal(claims=claims, store=store)
        self._store = store

    def _transaction(self, scope):
        return self._objects._transaction(scope)

    def execute(self, *, scope, group_id, actor, bindings, policy_ref, deadline=None, cancel_event=None):
        args = dict(scope=scope, group_id=group_id, actor=actor, bindings=bindings, policy_ref=policy_ref)
        active = dict(deadline=deadline, cancel_event=cancel_event)
        objects = self._objects.execute(**args, **active)
        _check_active(**active)
        with self._transaction(scope) as conn:
            prepared = self._commands.prepare(conn, **args)
        # No application until preparation transaction AND connection exit confirm.
        _check_active(**active)

        def current(conn):
            saved = self._commands.read_current(conn, **args)
            if (saved.assessment_hash, saved.command_hash, saved.command) != (
                    prepared.assessment_hash, prepared.command_hash, prepared.command):
                raise IngressJournalConflict('GROUP_LINK_PREPARATION_CHANGED')
            return saved

        with self._transaction(scope) as conn:
            saved = current(conn)
            _check_active(**active)
            result = self._store.apply_strict_link_batch(saved.command) if saved.command is not None else None
            _check_active(**active)
            current(conn)
        # A Store commit is independently durable. On any later failure, retain
        # this original command and recover via its exact idempotency Receipt.
        _check_active(**active)
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
            if completion['pending'] != 0:
                raise IngressJournalConflict('GROUP_LINK_PROJECTION_PENDING')
            _check_active(**active)
            current(conn)
        return dict(group_id=group_id, assessment_hash=prepared.assessment_hash,
                    command_hash=prepared.command_hash, objects=objects,
                    relationships_applied=True, relationship_scope='current_candidates_only',
                    replayed=result.replayed if result else not prepared.created,
                    projection=projection, completion=completion)
