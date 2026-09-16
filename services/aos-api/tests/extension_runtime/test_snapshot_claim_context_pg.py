"""Only an original synchronous source-claim loop can avoid group re-expansion."""
import pytest

pytest_plugins=('test_snapshot_schedule_execution_guard_pg',)
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_runtime_control_owner import PipelineRuntimeControlOwner
from aos_api.pipeline_snapshot_group_claim_owner import PipelineSnapshotGroupClaimOwner


@pytest.fixture
def loop(guarded,defined):
    conn,_,_,claims,command,_=guarded
    _,_,_,owner,args,_=defined
    receipt=owner.read(conn,scope=args['scope'],group_id=args['group_id'])
    pairs=tuple((PipelineExactRef.model_validate(m['controlRef']),m['runId']) for m in receipt['members'])
    return conn,PipelineSnapshotGroupClaimOwner(claims=claims),dict(
        scope=args['scope'],actor=args['actor'],group_id=args['group_id'],bindings=pairs),command


def test_original_claim_loop_uses_only_outer_snapshot_checks(loop,monkeypatch):
    conn,owner,args,command=loop
    calls=[]
    original=PipelineRuntimeControlOwner.run_current_snapshot
    def counted(self,*pos,**kw):
        calls.append(kw['ref'])
        return original(self,*pos,**kw)
    monkeypatch.setattr(PipelineRuntimeControlOwner,'run_current_snapshot',counted)
    first=owner.reserve(conn,**args)
    assert first.created and len(first.record.members)==12
    assert len(calls)==24
    calls.clear()
    assert owner.read_current(conn,**args)==first.record
    assert len(calls)==24
    calls.clear()
    owner._claims.read_current(conn,**command)
    assert len(calls)==24  # No loop context survives the original callback.
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==12


def test_group_claim_validates_complete_members_under_outer_immediate(loop):
    conn,owner,args,_=loop
    conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
    assert owner.reserve(conn,**args).created
    conn.execute('SET CONSTRAINTS ALL IMMEDIATE')
    assert not owner.reserve(conn,**args).created


@pytest.mark.parametrize('fault',['connection','scope','actor','ref','run','group','thread','nested'])
def test_loop_identity_faults_fail_before_claims(loop,monkeypatch,fault):
    from contextvars import copy_context
    from concurrent.futures import ThreadPoolExecutor
    from copy import deepcopy
    from aos_api.tenant_scope import TenantScope
    from aos_api.pipeline_snapshot_claim_context import _current_source_claim_group
    import psycopg
    conn,owner,args,_=loop
    original=owner._claims.reserve
    def tampered(db,**kw):
        if fault=='connection':
            with psycopg.connect(conn.info.dsn) as other:
                return original(other,**kw)
        if fault=='scope':kw['scope']=TenantScope('dev-org','dev-project')
        elif fault=='actor':kw['actor']='wrong-actor'
        elif fault=='ref':kw['control_ref']=next(ref for ref,_ in args['bindings'] if ref!=kw['control_ref'])
        elif fault=='run':kw['run_id']='wrong-run'
        elif fault=='nested':return owner.reserve(db,**args)
        elif fault=='thread':
            context=copy_context()
            with ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(context.run,lambda:original(db,**kw)).result(timeout=3)
        elif fault=='group':
            record=owner._claims._guard_group(db,**args)
            record=deepcopy(record)
            record['request']['groupId']='00000000-0000-0000-0000-000000000001'
            _current_source_claim_group(db,scope=args['scope'],actor=args['actor'],record=record)
        return original(db,**kw)
    monkeypatch.setattr(owner._claims,'reserve',tampered)
    with pytest.raises(PermissionError,match='source claim loop'):
        owner.reserve(conn,**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0


def test_context_copied_out_of_callback_is_expired(loop,monkeypatch):
    from contextvars import copy_context
    conn,owner,args,command=loop
    copied=[]
    original=owner._claims.reserve
    def capture(db,**kw):
        if not copied:copied.append(copy_context())
        return original(db,**kw)
    monkeypatch.setattr(owner._claims,'reserve',capture)
    owner.reserve(conn,**args)
    with pytest.raises(PermissionError,match='expired'):
        copied[0].run(lambda:owner._claims.read_current(conn,**command))
    assert owner._claims.read_current(conn,**command).run_id==command['run_id']


def test_real_transaction_change_invalidates_context(loop):
    import psycopg
    from threading import get_ident
    from aos_api.pipeline_snapshot_claim_context import _ClaimLoop,_transaction_key
    conn,_,args,_=loop
    with psycopg.connect(conn.info.dsn,autocommit=True) as other:
        with other.transaction():
            other.execute('SELECT pg_current_xact_id()')
            context=_ClaimLoop(other,_transaction_key(other),get_ident(),args['scope'],args['actor'],
                args['group_id'],(),None)
        with other.transaction():
            other.execute('SELECT pg_current_xact_id()')
            with pytest.raises(PermissionError,match='transaction changed'):
                context.check(other,args['scope'],args['actor'])


@pytest.mark.parametrize('fault',['disabled','superseded','expired','exception'])
def test_mid_loop_change_rolls_back_all_claims_and_clears_context(loop,monkeypatch,fault):
    from aos_api.pipeline_runtime_control_owner import decode_control_row
    import aos_api.pipeline_snapshot_group_owner as group_module
    from aos_api.pipeline_snapshot_claim_context import _active_loop
    conn,owner,args,_=loop
    original=owner._claims.reserve
    seen=[]
    def changed(db,**kw):
        seen.append(kw['control_ref'])
        if len(seen)==12:
            if fault=='disabled':
                db.execute('UPDATE meta_schedule SET enabled=false WHERE id=(SELECT schedule_id FROM meta_schedule_run ORDER BY id LIMIT 1)')
            elif fault=='superseded':
                ref=seen[0]
                row=db.execute('SELECT * FROM pipeline_runtime_control_revision WHERE control_id=%s AND revision=%s',
                    (ref.resource_id.removeprefix('pipeline-control-'),ref.revision)).fetchone()
                control=decode_control_row(row)
                owner._claims._controls.append(db,draft=control.draft,actor=args['actor'],
                    idempotency_key='loop-supersede',previous_ref=ref)
            elif fault=='expired':
                end=_active_loop.get().group.expires_at
                monkeypatch.setattr(group_module,'_now',lambda db:end)
            else:raise RuntimeError('loop interrupted')
        return original(db,**kw)
    monkeypatch.setattr(owner._claims,'reserve',changed)
    with pytest.raises((ValueError,RuntimeError,PermissionError)):
        owner.reserve(conn,**args)
    assert _active_loop.get() is None
    assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==0
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_claim').fetchone()['n']==0
    monkeypatch.undo()
    assert owner.reserve(conn,**args).created
