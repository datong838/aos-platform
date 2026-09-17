"""Saved successor recovery aligns immutable parents by fixed run identity."""
from dataclasses import replace

from aos_api.pipeline_snapshot_group_input_owner import PipelineSnapshotGroupInputOwner
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner

pytest_plugins=('test_snapshot_group_recovery_authority_pg',)


def test_successor_control_order_realigns_original_parents_by_run(authority_case,monkeypatch):
    runtime,owner,command,_,_,authority,args=authority_case
    claims=PipelineSourceClaimOwner(
        controls=owner._controls,recovery=authority,recovery_bindings=args['bindings'])
    inputs=PipelineSnapshotGroupInputOwner(claims=claims)
    with runtime._transaction(command['scope']) as conn:
        original=inputs.run_current(
            conn,**args,group_id=command['group_id'],execute=lambda value:value)
        current=authority.run_current(conn,**args,execute=lambda value:value)
        reversed_group=replace(
            current.execution.group,members=tuple(reversed(current.execution.group.members)))
        reordered_current=replace(
            current,execution=replace(current.execution,group=reversed_group))
        records={record.run_id:record for record in original.claim.members}
        run_by_control={ref.resource_id:run for ref,run in args['bindings']}
        monkeypatch.setattr(
            authority,'run_current',lambda _conn,**kwargs:kwargs['execute'](reordered_current))
        monkeypatch.setattr(
            claims,'read_saved_current',lambda _conn,**kwargs:records[kwargs['run_id']])

        reordered=inputs.run_current(
            conn,**args,group_id=command['group_id'],execute=lambda value:value)

        for (ref,_,_),parent,record in zip(
                reordered.group.members,reordered.parents,reordered.claim.members):
            expected_run=run_by_control[ref.resource_id]
            assert parent['runId']==expected_run
            assert record.run_id==expected_run
