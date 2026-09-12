"""Internal controlled snapshot execution; no scheduling or approval authority."""
from aos_api.ec_ingress_dataset import finalize_saved_dataset
from aos_api.ec_ingress_recovery import _check_active, recover_saved_authoritative_stages
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_controlled_projection import project_saved_batch
from aos_api.pipeline_controlled_snapshot_ingress import ControlledSnapshotIngress


class ControlledSnapshotExecutor:
    """Trusted host assembly with independent connections and original run keys."""

    def __init__(self, *, claims, store, connect, eng):
        self._ingress = ControlledSnapshotIngress(claims=claims, store=store, connect=connect)
        self._claims, self._store, self._eng = claims, store, eng

    def execute(self, *, scope, run_id, control_ref, actor, deadline=None, cancel_event=None):
        args = dict(scope=scope, run_id=run_id, control_ref=control_ref, actor=actor)
        active = dict(deadline=deadline, cancel_event=cancel_event)
        prepared = self._ingress.prepare(**args, **active)
        journal = ControlledIngressJournal(claims=self._claims, **args)
        connection_factory = self._ingress._transaction
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
