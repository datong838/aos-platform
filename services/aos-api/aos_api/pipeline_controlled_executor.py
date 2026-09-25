"""Internal controlled snapshot execution; no scheduling or approval authority."""
from functools import partial
from aos_api.ec_ingress_dataset import finalize_saved_dataset
from aos_api.ec_ingress_recovery import _bound_parent, _check_active, recover_saved_authoritative_stages
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_controlled_projection import project_saved_batch
from aos_api.pipeline_controlled_snapshot_ingress import ControlledSnapshotIngress, PreparedControlledSnapshot
from aos_api.extension_runtime.host_lease import OptInHostLease


class ControlledSnapshotExecutor:
    """Trusted host assembly with independent connections and original run keys."""

    def __init__(self, *, claims, store, connect, eng, schedule_binding=None, host_lease=None):
        if host_lease is not None and type(host_lease) is not OptInHostLease:
            raise TypeError('exact snapshot Single Host lease required')
        self._ingress = ControlledSnapshotIngress(claims=claims, store=store, connect=connect,
            schedule_binding=schedule_binding,host_lease=host_lease)
        self._claims, self._store, self._eng = claims, store, eng

    def execute(self, *, scope, run_id, control_ref, actor, deadline=None, cancel_event=None):
        args = dict(scope=scope, run_id=run_id, control_ref=control_ref, actor=actor)
        active = dict(deadline=deadline, cancel_event=cancel_event)
        prepared = self._ingress.prepare(**args, **active)
        journal = ControlledIngressJournal(claims=self._claims, **args)
        return self._finish(scope, run_id, journal, prepared, active)

    def resume_saved(self, *, scope, run_id, control_ref, actor, deadline=None, cancel_event=None):
        """Continue saved input only; never reserve or invoke the source reader."""
        self._ingress._require_binding_args(scope,control_ref,actor)
        active = dict(deadline=deadline, cancel_event=cancel_event)
        _check_active(**active)
        journal = ControlledIngressJournal(claims=self._claims, scope=scope, run_id=run_id,
            control_ref=control_ref, actor=actor, saved_recovery=True)
        with self._ingress._run_transaction(scope,run_id=run_id) as conn:
            journal.lock_run(conn, scope, run_id)
            parent = _bound_parent(conn, scope, run_id, journal)
        prepared = PreparedControlledSnapshot(parent, 0, True)
        return self._finish(scope, run_id, journal, prepared, active)

    def _finish(self, scope, run_id, journal, prepared, active):
        connection_factory = partial(self._ingress._run_transaction,run_id=run_id)
        common = dict(journal=journal, store=self._store, **active)
        _check_active(**active)
        result = finalize_saved_dataset(connection_factory, scope, run_id,
            **common, eng=self._eng, only_existing=True)
        completed_replay = result is not None
        derived = ()
        projection = {'projected': 0, 'pending': 0}
        if not completed_replay:
            derived = recover_saved_authoritative_stages(
                connection_factory, scope, run_id, **common)
            with connection_factory(scope) as conn:
                projection = project_saved_batch(conn, scope, run_id, **common)
            _check_active(**active)
            result = finalize_saved_dataset(connection_factory, scope, run_id,
                **common, eng=self._eng)
        return dict(
            input_ref='', output_ref='dataset://catalog/' + result['dataset']['rid'],
            lineage_ref='', quality_ref='', rows_read=prepared.rows_read,
            rows_written=result['build']['rows_written'],
            output_rows=prepared.parent.get('outputRows', []),
            empty_observation=prepared.parent.get('kind') == 'empty_observation_v1',
            completed_replay=completed_replay, completion=result['completion'],
            projection=projection,
            derived={
                'derived_updated': sum(int(item.updated and not item.replayed) for item in derived),
                'derived_replayed': sum(int(item.replayed) for item in derived),
            },
        )
