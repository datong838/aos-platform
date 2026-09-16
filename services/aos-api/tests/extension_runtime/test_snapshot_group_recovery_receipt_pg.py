"""Recovery history storage only; no recovery execution or source rereads."""
from copy import deepcopy
from contextlib import contextmanager
from datetime import timedelta
from uuid import UUID
import pytest
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

pytest_plugins=('test_snapshot_schedule_runtime_pg',)
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft,PipelineRuntimeControlDraft
from aos_api.pipeline_runtime_control_owner import decode_control_row
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
from aos_api.pipeline_snapshot_schedule_claim import _member
from aos_api.pipeline_snapshot_schedule_definition import _CONSTRAINTS
from aos_api.pipeline_snapshot_group_recovery_receipt import recovery_body,read_recovery_receipt


@pytest.fixture
def renewal_row(runtime_case,monkeypatch,request):
    runtime,args,state,_,_,_,database=runtime_case
    def input_ready(**kw):raise RuntimeError('named fixture stops after original input')
    monkeypatch.setattr(runtime._completion,'complete',input_ready)
    no_input=getattr(request,'param',None)=='no-input'
    if no_input:
        original_transaction=runtime._ingress._transaction
        @contextmanager
        def stop_after_claim(scope):
            with original_transaction(scope) as conn:yield conn
            raise RuntimeError('named fixture stops before original input')
        monkeypatch.setattr(runtime._ingress,'_transaction',stop_after_claim)
    with pytest.raises(RuntimeError,match='original input'):runtime.execute(**args)
    assert state['calls']==(0 if no_input else 1)
    scope=args['scope'];controls=runtime._claims._groups._controls
    with runtime._transaction(scope) as conn:
        old=runtime._definitions.read(conn,scope=scope,definition_id=args['definition_ref']['resourceId'].removeprefix('snapshot-schedule-'))
        bindings=runtime._definitions._saved_bindings(conn,scope,old['body'])
        originals=[]
        for b in bindings:
            originals.append(decode_control_row(conn.execute('SELECT * FROM pipeline_runtime_control_revision WHERE org_id=%s AND project_id=%s AND control_id=%s AND revision=%s',
                (*scope.key,b.control_ref.resource_id.removeprefix('pipeline-control-'),b.control_ref.revision)).fetchone()))
        start=max(c.draft.not_before for c in originals)
        end=max(c.draft.expires_at for c in originals)+timedelta(hours=1)
        current=[]
        for index,(old_control,binding) in enumerate(zip(originals,bindings)):
            data=old_control.draft.model_dump(exclude={'schema_version','source_selection_ref'})
            data.update(not_before=start,expires_at=end)
            if index==0 and getattr(request,'param',None)=='budget':data['max_source_calls']+=1
            selected=PipelineSourceSelectionDraft.model_validate(data)
            selection=controls._selections.append(conn,draft=selected,actor=args['actor'],
                previous_ref=old_control.draft.source_selection_ref,idempotency_key=f'renew-selection-{index}')
            draft=PipelineRuntimeControlDraft.model_validate(dict(data,source_selection_ref=selection))
            control=controls.append(conn,draft=draft,actor=args['actor'],previous_ref=old_control.ref,idempotency_key=f'renew-control-{index}')
            current.append(PipelineScheduleControlOwner(controls=controls).bind(conn,scope=scope,
                schedule_id=binding.schedule_id,actor=args['actor'],control_ref=control,
                previous_ref=binding.ref,idempotency_key=f'renew-binding-{index}'))
        body=deepcopy(old['body'])
        body.update(revision=body['revision']+1,priorRef=old['ref'],members=[_member(b) for b in current],
            createdAt=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'].isoformat())
        conn.execute('SET CONSTRAINTS '+_CONSTRAINTS+' DEFERRED')
        # Explicit storage fixture, NOT a production recovery authorization Owner.
        new=runtime._definitions._save(conn,scope,body,tuple(current),
            dict(intent='renew_saved_group'), 'named-renewal-definition', [b.schedule_id for b in current])
        conn.execute('SET CONSTRAINTS '+_CONSTRAINTS+' IMMEDIATE')
        original=conn.execute('SELECT content_hash FROM pipeline_snapshot_schedule_claim WHERE group_id=%s',(args['group_id'],)).fetchone()
        source=conn.execute('SELECT request_hash FROM pipeline_snapshot_group_claim WHERE group_id=%s',(args['group_id'],)).fetchone()
        saved=conn.execute('SELECT manifest_hash FROM pipeline_snapshot_group_input WHERE group_id=%s',(args['group_id'],)).fetchone()
        if no_input:
            assert saved is None
            saved={'manifest_hash':'sha256:'+'0'*64}
        created=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        request=dict(schemaVersion='aos.snapshot-group-recovery-request/v1',orgId=scope.org_id,projectId=scope.project_id,
            groupId=args['group_id'],actor=args['actor'],expectedDefinitionRef=old['ref'],expectedRecoveryRef=None,
            inputManifestHash=saved['manifest_hash'],notBefore=start.isoformat(),expiresAt=end.isoformat())
        row=dict(org_id=scope.org_id,project_id=scope.project_id,group_id=UUID(args['group_id']),revision=1,
            previous_revision=None,previous_hash=None,definition_id=UUID(body['definitionId']),
            original_definition_revision=old['ref']['revision'],original_definition_hash=old['ref']['contentHash'],
            current_definition_revision=new['ref']['revision'],current_definition_hash=new['ref']['contentHash'],
            original_schedule_hash=original['content_hash'],original_source_hash=source['request_hash'],
            input_manifest_hash=saved['manifest_hash'],actor=args['actor'],executor=args['actor'],
            policy_ref=body['policyRef'],idempotency_key='named-recovery',request=request,
            request_hash=canonical_sha256(request),created_at=created)
        row['body']=recovery_body(row);row['content_hash']=canonical_sha256(row['body'])
    yield runtime,args,row,state


def insert(conn,row):
    return conn.execute(sql.SQL('INSERT INTO public.pipeline_snapshot_group_recovery_receipt ({}) VALUES ({})').format(
        sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row)),
        tuple(Jsonb(v) if isinstance(v,dict) else v for v in row.values()))


def test_immutable_receipt_reads_original_facts_on_new_connection(renewal_row):
    runtime,args,row,state=renewal_row
    with runtime._transaction(args['scope']) as conn:insert(conn,row)
    with runtime._transaction(args['scope']) as conn:
        conn.execute("SET LOCAL timezone='Asia/Shanghai'")
        result=read_recovery_receipt(conn,scope=args['scope'],group_id=args['group_id'])
        assert result['body']==row['body']
        assert result['ref']['contentHash']==row['content_hash']
    assert state['calls']==1


@pytest.mark.parametrize('renewal_row',['budget'],indirect=True)
def test_even_approved_new_controls_cannot_raise_recovery_budget(renewal_row):
    runtime,args,row,_=renewal_row
    with pytest.raises(psycopg.errors.CheckViolation,match='member semantics'),runtime._transaction(args['scope']) as conn:
        insert(conn,row)
        conn.execute('SET CONSTRAINTS ALL IMMEDIATE')


@pytest.mark.parametrize('renewal_row',['no-input'],indirect=True)
def test_unknown_source_claim_without_input_cannot_receive_recovery_receipt(renewal_row):
    runtime,args,row,state=renewal_row
    with pytest.raises(psycopg.errors.ForeignKeyViolation),runtime._transaction(args['scope']) as conn:
        insert(conn,row)
    assert state['calls']==0


def test_receipt_cannot_be_read_or_written_through_negative_tenant(renewal_row):
    from aos_api.tenant_scope import TenantScope
    runtime,args,row,_=renewal_row
    with runtime._transaction(args['scope']) as conn:insert(conn,row)
    negative=TenantScope('dev-org','dev-project')
    with runtime._transaction(negative) as conn:
        assert read_recovery_receipt(conn,scope=negative,group_id=args['group_id']) is None
    with pytest.raises(psycopg.errors.InsufficientPrivilege),runtime._transaction(negative) as conn:
        insert(conn,row)


def test_original_receipt_key_is_unique_and_public_read_cannot_be_shadowed(renewal_row):
    runtime,args,row,_=renewal_row
    with runtime._transaction(args['scope']) as conn:insert(conn,row)
    with pytest.raises(psycopg.errors.UniqueViolation),runtime._transaction(args['scope']) as conn:insert(conn,row)
    with runtime._transaction(args['scope']) as conn:
        conn.execute('CREATE TEMP TABLE pipeline_snapshot_group_recovery_receipt AS SELECT * FROM public.pipeline_snapshot_group_recovery_receipt WHERE false')
        result=read_recovery_receipt(conn,scope=args['scope'],group_id=args['group_id'],idempotency_key=row['idempotency_key'])
        assert result['body']==row['body']
        assert read_recovery_receipt(conn,scope=args['scope'],group_id=args['group_id'],revision=99) is None


def test_recovery_history_chain_requires_exact_previous_hash(renewal_row):
    runtime,args,row,state=renewal_row
    with runtime._transaction(args['scope']) as conn:insert(conn,row)
    with runtime._transaction(args['scope']) as conn:
        first=read_recovery_receipt(conn,scope=args['scope'],group_id=args['group_id'])
        current=runtime._definitions.read(conn,scope=args['scope'],definition_id=str(row['definition_id']))
        bindings=runtime._definitions._saved_bindings(conn,args['scope'],current['body'])
        body=deepcopy(current['body'])
        body.update(revision=body['revision']+1,priorRef=current['ref'],
            createdAt=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'].isoformat())
        conn.execute('SET CONSTRAINTS '+_CONSTRAINTS+' DEFERRED')
        # Named storage-only definition fixture, still no recovery execution.
        successor=runtime._definitions._save(conn,args['scope'],body,bindings,dict(intent='renew_saved_group'),
            'named-second-definition',[b.schedule_id for b in bindings])
        conn.execute('SET CONSTRAINTS '+_CONSTRAINTS+' IMMEDIATE')
        second=deepcopy(row)
        second.update(revision=2,previous_revision=1,previous_hash=row['content_hash'],
            current_definition_revision=successor['ref']['revision'],current_definition_hash=successor['ref']['contentHash'],
            idempotency_key='second-recovery',created_at=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
        second['request'].update(expectedRecoveryRef=first['ref'],expectedDefinitionRef=current['ref'])
        second['request_hash']=canonical_sha256(second['request'])
        second['body']=recovery_body(second);second['content_hash']=canonical_sha256(second['body'])
    bad=deepcopy(second);bad['previous_hash']='sha256:'+'0'*64
    bad['request']['expectedRecoveryRef']['contentHash']=bad['previous_hash']
    bad['request_hash']=canonical_sha256(bad['request']);bad['body']=recovery_body(bad);bad['content_hash']=canonical_sha256(bad['body'])
    with pytest.raises(psycopg.errors.ForeignKeyViolation),runtime._transaction(args['scope']) as conn:insert(conn,bad)
    with runtime._transaction(args['scope']) as conn:insert(conn,second)
    with runtime._transaction(args['scope']) as conn:
        assert read_recovery_receipt(conn,scope=args['scope'],group_id=args['group_id'])['body']==second['body']
        assert read_recovery_receipt(conn,scope=args['scope'],group_id=args['group_id'],revision=1)['body']==row['body']
    assert state['calls']==1


def test_immutability_trigger_also_rejects_table_owner_writes(renewal_row):
    runtime,args,row,_=renewal_row
    with runtime._transaction(args['scope']) as conn:
        insert(conn,row)
        dsn=conn.info.dsn
    with psycopg.connect(dsn,autocommit=True) as owner:
        for command in ("UPDATE public.pipeline_snapshot_group_recovery_receipt SET actor='other'",
                'DELETE FROM public.pipeline_snapshot_group_recovery_receipt',
                'TRUNCATE public.pipeline_snapshot_group_recovery_receipt'):
            with pytest.raises(psycopg.errors.RaiseException,match='immutable'),owner.transaction():owner.execute(command)


@pytest.mark.parametrize('fault',['input','schedule','source','policy','executor','window','definition-kind'])
def test_rehashed_wrong_associations_are_rejected(renewal_row,fault):
    runtime,args,original,_=renewal_row
    row=deepcopy(original)
    if fault in {'input','schedule','source'}:
        name={'input':'input_manifest_hash','schedule':'original_schedule_hash','source':'original_source_hash'}[fault]
        row[name]='sha256:'+'0'*64
    elif fault=='policy':row['policy_ref']['contentHash']='sha256:'+'0'*64
    elif fault=='executor':row['executor']='wrong-executor'
    elif fault=='window':row['request']['expiresAt']=row['request']['notBefore']
    row['request_hash']=canonical_sha256(row['request'])
    row['body']=recovery_body(row)
    if fault=='definition-kind':row['body']['currentDefinitionRef']['resourceType']='Other'
    row['content_hash']=canonical_sha256(row['body'])
    with pytest.raises(psycopg.IntegrityError),runtime._transaction(args['scope']) as conn:
        insert(conn,row)
        conn.execute('SET CONSTRAINTS ALL IMMEDIATE')


@pytest.mark.parametrize('operation',['UPDATE','DELETE','TRUNCATE'])
def test_recovery_history_rejects_mutation(renewal_row,operation):
    runtime,args,row,_=renewal_row
    with runtime._transaction(args['scope']) as conn:insert(conn,row)
    command={'UPDATE':"UPDATE public.pipeline_snapshot_group_recovery_receipt SET actor='other'",
        'DELETE':'DELETE FROM public.pipeline_snapshot_group_recovery_receipt',
        'TRUNCATE':'TRUNCATE public.pipeline_snapshot_group_recovery_receipt'}[operation]
    with pytest.raises((psycopg.errors.InsufficientPrivilege,psycopg.errors.RaiseException)),runtime._transaction(args['scope']) as conn:
        conn.execute(command)
