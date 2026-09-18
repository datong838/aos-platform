"""Saved recovery retains source facts and cannot reserve another read."""
from dataclasses import replace
import pytest
from types import SimpleNamespace as NS
from aos_api.pipeline_source_claim_owner import (PipelineSourceClaimOwner,_SavedRecoveryAdmission,
    _validate_saved_recovery_context)
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_runtime_control_owner import decode_control_row
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.pipeline_snapshot_group_input_owner import PipelineSnapshotGroupInputOwner
from aos_api.pipeline_snapshot_group_claim_owner import PipelineSnapshotGroupClaimOwner

pytest_plugins=('test_snapshot_group_recovery_authority_pg',)


def recovered_claims(authority_case):
    runtime,owner,command,state,receipt,authority,args=authority_case
    return PipelineSourceClaimOwner(controls=owner._controls,recovery=authority,recovery_bindings=args['bindings'])


def test_original_input_uses_current_window_without_changing_original_claims(authority_case):
    runtime,_,command,state,receipt,authority,args=authority_case
    claims=recovered_claims(authority_case);inputs=PipelineSnapshotGroupInputOwner(claims=claims)
    with runtime._transaction(command['scope']) as conn:
        source=inputs.run_current(conn,**args,group_id=command['group_id'],execute=lambda value:value)
        assert source.recovery_ref.model_dump(mode='json',by_alias=True,exclude_none=True)==receipt['ref']
        assert source.group.not_before==command['not_before']
        assert source.read_completed_at<source.group.not_before
        assert source.manifest_hash==command['input_manifest_hash']
        assert source.claim.request_hash==receipt['body']['originalSourceClaimHash']
        old={m.control_ref.resource_id:m.control_ref for m in source.claim.members}
        assert all(ref.revision==old[ref.resource_id].revision+1 for ref,_,_ in source.group.members)
        assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==12
    assert state['calls']==1


def test_successor_family_requires_authority_admission_and_same_read_semantics(authority_case):
    runtime,_,command,state,_,authority,args=authority_case
    claims=recovered_claims(authority_case);ref,run=args['bindings'][0]
    with runtime._transaction(command['scope']) as conn:
        admission=claims._guard_schedule(conn,scope=command['scope'],run_id=run,control_ref=ref,actor=command['actor'])
        row=conn.execute('''SELECT r.* FROM pipeline_controlled_source_claim c
            JOIN pipeline_runtime_control_revision r ON r.org_id=c.org_id AND r.project_id=c.project_id
                AND r.control_id=c.control_id AND r.revision=c.control_revision
            WHERE c.org_id=%s AND c.project_id=%s AND c.run_id=%s''',(*command['scope'].key,run)).fetchone()
        original=decode_control_row(row)
        current=next(draft for current_ref,draft,_ in authority.run_current(conn,**args,execute=lambda value:value.execution.group).members
            if current_ref==ref)
        successor_ref=PipelineExactRef(resourceType='PipelineRuntimeControlRevision',
            resourceId='pipeline-control-00000000-0000-0000-0000-000000000001',revision=1,
            contentHash='sha256:'+'0'*64)
        proof=_SavedRecoveryAdmission(admission.original_controls,True)
        _validate_saved_recovery_context(proof,claims.read_saved_current(conn,scope=command['scope'],run_id=run,
            control_ref=ref,actor=command['actor']),successor_ref,current,original)
        with pytest.raises(RuntimeConflict,match='family'):
            _validate_saved_recovery_context(_SavedRecoveryAdmission(admission.original_controls,False),
                claims.read_saved_current(conn,scope=command['scope'],run_id=run,control_ref=ref,actor=command['actor']),
                successor_ref,current,original)
        claimed=claims.read_saved_current(conn,scope=command['scope'],run_id=run,control_ref=ref,actor=command['actor'])
        with pytest.raises(RuntimeConflict,match='context'):
            _validate_saved_recovery_context(proof,replace(claimed,generation='00000000-0000-0000-0000-000000000002'),
                successor_ref,current,original)
    assert state['calls']==1


def test_recovery_instance_cannot_reserve_prepare_or_adopt_another_run(authority_case):
    runtime,owner,command,state,receipt,authority,args=authority_case
    claims=recovered_claims(authority_case)
    ref,run=args['bindings'][0]
    with runtime._transaction(command['scope']) as conn:
        single=dict(scope=command['scope'],run_id=run,actor=command['actor'],control_ref=ref)
        with pytest.raises(PermissionError,match='reserve'):claims.reserve(conn,**single)
        with pytest.raises(PermissionError,match='prepare'):claims._guard_single_prepare(conn,scope=command['scope'],run_id=run)
        with pytest.raises(PermissionError,match='new group'):
            PipelineSnapshotGroupClaimOwner(claims=claims).reserve(conn,**args,group_id=command['group_id'])
        with pytest.raises(PermissionError,match='fixed member'):
            claims.read_saved_current(conn,**(single|dict(run_id='another-run')))
        # An ordinary Owner has no recovery shortcut for these renewed controls.
        ordinary=PipelineSourceClaimOwner(controls=owner._controls)
        with pytest.raises(ValueError,match='control or actor differs'):
            ordinary.read_saved_current(conn,**single)
        assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==12
    assert state['calls']==1


def test_saved_input_rejects_disable_during_consumer_and_rolls_it_back(authority_case):
    runtime,_,command,state,receipt,authority,args=authority_case
    inputs=PipelineSnapshotGroupInputOwner(claims=recovered_claims(authority_case))
    definition_id=receipt['body']['currentDefinitionRef']['resourceId'].removeprefix('snapshot-schedule-')
    with runtime._transaction(command['scope']) as conn:
        def disable(_):
            runtime._definitions.transition(conn,scope=command['scope'],definition_id=definition_id,actor=command['actor'],
                intent='disable',expected_ref=receipt['body']['currentDefinitionRef'],idempotency_key='disable-in-input')
        with pytest.raises(ValueError,match='current enabled'):
            inputs.run_current(conn,**args,group_id=command['group_id'],execute=disable)
        assert runtime._definitions.read(conn,scope=command['scope'],definition_id=definition_id)['ref']==receipt['body']['currentDefinitionRef']
    assert state['calls']==1


def test_incomplete_or_wrong_group_cannot_consume_saved_input(authority_case):
    runtime,_,command,state,_,_,args=authority_case
    inputs=PipelineSnapshotGroupInputOwner(claims=recovered_claims(authority_case))
    with runtime._transaction(command['scope']) as conn:
        with pytest.raises(PermissionError,match='fixed recovery group'):
            inputs.run_current(conn,**args,group_id='another-group',execute=lambda _:pytest.fail('wrong group consumed'))
        with pytest.raises(ValueError,match='complete'):
            inputs.run_current(conn,**(args|dict(bindings=args['bindings'][:-1])),group_id=command['group_id'],
                execute=lambda _:pytest.fail('partial group consumed'))
    assert state['calls']==1


def test_projection_serialization_keeps_original_fact_refs_with_current_journal_refs(authority_case,monkeypatch):
    """Named serializer seam only: real Store completion is tested in the next wave."""
    from aos_api.pipeline_snapshot_group_projection_owner import PipelineSnapshotGroupProjectionOwner
    import aos_api.pipeline_snapshot_group_projection_owner as module
    runtime,_,command,state,_,_,args=authority_case
    claims=recovered_claims(authority_case)
    inputs=PipelineSnapshotGroupInputOwner(claims=claims)
    with runtime._transaction(command['scope']) as conn:
        source=inputs.run_current(conn,**args,group_id=command['group_id'],execute=lambda value:value)
        projection=PipelineSnapshotGroupProjectionOwner(claims=claims,store=runtime._completion._store)
        monkeypatch.setattr(projection._inputs,'run_completed_current',lambda c,**kw:kw['execute'](source))
        journals=[]
        def named_events(c,scope,run_id,*,journal,store):
            journals.append((run_id,journal._ref));return ()
        monkeypatch.setattr(module,'read_saved_projection_evidence',named_events)
        class ReceiptRead:
            def __getattr__(self,name):return getattr(conn,name)
            def execute(self,query,params=()):
                if 'SELECT payload_hash' in str(query):return NS(fetchone=lambda:{'payload_hash':'named-serializer-receipt'})
                return conn.execute(query,params)
        result=projection.run_current(ReceiptRead(),**args,group_id=command['group_id'],execute=lambda value:value)
        old={m.run_id:m.control_ref for m in source.claim.members}
        for leaf in result.payload['members']:
            assert leaf['controlRef']==old[leaf['runId']].model_dump(mode='json',by_alias=True)
        assert all(ref.revision==old[run].revision+1 for run,ref in journals)
    assert state['calls']==1
