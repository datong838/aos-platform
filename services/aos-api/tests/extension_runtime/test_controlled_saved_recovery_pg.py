"""Actual saved claims and renewed controls; signed assets/source remain fixtures."""
from datetime import timedelta
import pytest
from test_controlled_snapshot_ingress_pg import executor_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_pipeline_source_selection_owner_pg import owner_case,approve
from test_pipeline_source_selection_schema_pg import ledger
from test_lifecycle_pg import database,pytestmark
from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft,PipelineRuntimeControlDraft
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


def renew(claim_case,monkeypatch,**changes):
    conn,claims,args,controls,draft,selections=claim_case
    import aos_api.pipeline_source_selection_owner as module
    now=draft.expires_at+timedelta(seconds=1)
    monkeypatch.setattr(module,'_now',lambda db:now)
    body=draft.model_dump(exclude={'schema_version','source_selection_ref'})
    body.update(not_before=now,expires_at=now+timedelta(hours=1),**changes)
    selection=PipelineSourceSelectionDraft.model_validate(body)
    selected=approve(conn,selections,selection,'renew-selection',draft.source_selection_ref)
    renewed=PipelineRuntimeControlDraft.model_validate(body|{'source_selection_ref':selected})
    with conn.transaction():
        return controls.append(conn,draft=renewed,actor=args['actor'],idempotency_key='renew-control',previous_ref=args['control_ref'])


@pytest.mark.parametrize('mode',['saved','missing','row_limit','max_source_calls','actor','denied'])
def test_renewal_only_recovers_original_saved_scope(executor_case,claim_case,monkeypatch,mode):
    preparation,conn,args,state=executor_case
    claims=preparation._claims
    if mode=='missing':
        with preparation._transaction(args['scope']) as db:claims.reserve(db,**args)
    else:preparation.prepare(**args)
    changes={}
    if mode=='row_limit':changes['row_limit']=101
    if mode=='max_source_calls':changes['max_source_calls']=2
    ref=renew(claim_case,monkeypatch,**changes)
    current=args|{'control_ref':ref}
    if mode=='actor':current['actor']='another-actor'
    if mode=='denied':state['deny']=True
    with preparation._transaction(args['scope']) as db:
        if mode=='saved':
            record=claims.read_saved_current(db,**current)
            assert record.control_ref==args['control_ref'] and record.call_ordinal==1
        else:
            with pytest.raises((RuntimeConflict,PermissionError,LookupError,ValueError)):
                claims.read_saved_current(db,**current)
    assert conn.execute('SELECT count(*) FROM pipeline_controlled_source_claim').fetchone()=={'count':1}
    assert state['calls']==(0 if mode=='missing' else 1)
    if mode=='saved':
        with pytest.raises(RuntimeConflict):preparation.prepare(**current)
        assert state['calls']==1
