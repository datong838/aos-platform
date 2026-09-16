"""Committed schedule claim readback on a new connection; no remote source call."""
import psycopg
from psycopg.rows import dict_row

from test_analysis_snapshot_native_ingress_pg import (
    private_database, stored, complete_named_installation_draft,
)
from test_analysis_snapshot_native_claims_pg import (
    native_claims_case, host_case, control_governed, governed, service_case, pair, body,
)
from test_pipeline_snapshot_schedule_claim_pg import schedule_group
from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner


def test_committed_ack_loss_recovers_same_twelve_runs(schedule_group, private_database):
    conn, owner, args = schedule_group
    plans = {}
    owner._groups.run_current(conn, scope=args['scope'], actor=args['actor'],
        refs=tuple(b.control_ref for b in args['bindings']),
        execute=lambda group:plans.update({draft.pipeline_id:mapping for _,draft,mapping in group.members}))
    def assets(db, draft, actor, consume, *, snapshot=False):
        assert db.info.dbname == conn.info.dbname and actor == args['actor']
        plan = plans[draft.pipeline_id]
        return consume(plan if snapshot else plan.read_spec)
    owner._groups._controls._selections._guarded = assets
    complete_named_installation_draft(conn,args['scope'])
    conn.commit()
    conn.execute('SET ROLE aos_runtime')
    conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",args['scope'].key)
    original = owner.claim(conn, **args)
    conn.commit()  # The caller lost this acknowledgement; do not allocate a new group.
    with psycopg.connect(private_database, row_factory=dict_row) as recovered:
        recovered.execute('SET SESSION AUTHORIZATION aos_runtime')
        recovered.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",args['scope'].key)
        restarted = PipelineSnapshotScheduleClaimOwner(controls=owner._groups._controls)
        assert restarted.read(recovered,scope=args['scope'],group_id=args['group_id']) == original
        assert restarted.claim(recovered, **args) == original
        assert recovered.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n'] == 12
        assert recovered.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_claim').fetchone()['n'] == 1
        assert recovered.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n'] == 0
