"""Historical facts are readable under current management, never executable permits."""
import pytest
from copy import deepcopy
from datetime import timedelta
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ec_ingress_journal import IngressJournalConflict,_digest
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.pipeline_snapshot_group_saved_facts import SnapshotSavedFactsReader
from aos_api.tenant_scope import TenantScope

pytest_plugins=('test_snapshot_group_recovery_receipt_pg',)


def test_original_input_remains_readable_after_controls_are_superseded(renewal_row,monkeypatch):
    runtime,args,row,state=renewal_row
    def forbidden(*a,**k):raise AssertionError('historical read invoked expired execution authority')
    monkeypatch.setattr(runtime._claims._groups._controls,'run_current',forbidden)
    import aos_api.pipeline_snapshot_group_saved_facts as module
    clock=module._now
    monkeypatch.setattr(module,'_now',lambda conn:clock(conn)+timedelta(days=2))
    reader=SnapshotSavedFactsReader(definitions=runtime._definitions,claims=runtime._claims)
    with runtime._transaction(args['scope']) as conn:
        conn.execute('CREATE TEMP TABLE pipeline_snapshot_group_input AS SELECT * FROM public.pipeline_snapshot_group_input WHERE false')
        conn.execute('CREATE TEMP TABLE pipeline_controlled_source_claim AS SELECT * FROM public.pipeline_controlled_source_claim WHERE false')
        facts=reader.read(conn,scope=args['scope'],group_id=args['group_id'],actor=args['actor'],
            expected_manifest_hash=row['input_manifest_hash'])
        assert facts.manifest_hash==row['input_manifest_hash']
        assert len(facts.parents)==len(facts.controls)==12
        assert facts.definition['ref']==args['definition_ref']
        assert conn.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==12
        assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_recovery_receipt').fetchone()['n']==0
    assert state['calls']==1


def test_current_manager_and_exact_tenant_are_required(renewal_row):
    runtime,args,row,state=renewal_row
    reader=SnapshotSavedFactsReader(definitions=runtime._definitions,claims=runtime._claims)
    kw=dict(scope=args['scope'],group_id=args['group_id'],actor=args['actor'],expected_manifest_hash=row['input_manifest_hash'])
    with runtime._transaction(args['scope']) as conn:
        with pytest.raises(RuntimeConflict,match='membership'):
            reader.read(conn,**(kw|dict(actor='not-a-current-member')))
        with pytest.raises(IngressJournalConflict,match='BINDING_DRIFT'):
            reader.read(conn,**(kw|dict(expected_manifest_hash='sha256:'+'0'*64)))
        with pytest.raises(PermissionError,match='tenant'):
            reader.read(conn,**(kw|dict(scope=TenantScope('dev-org','dev-project'))))
    with runtime._transaction(TenantScope('dev-org','dev-project')) as conn:
        with pytest.raises(IngressJournalConflict,match='CLAIM_REQUIRED'):
            reader.read(conn,**(kw|dict(scope=TenantScope('dev-org','dev-project'))))
    assert state['calls']==1


@pytest.mark.parametrize('renewal_row',['no-input'],indirect=True)
def test_unknown_source_call_does_not_become_historical_input(renewal_row):
    runtime,args,row,state=renewal_row
    reader=SnapshotSavedFactsReader(definitions=runtime._definitions,claims=runtime._claims)
    with runtime._transaction(args['scope']) as conn:
        with pytest.raises(IngressJournalConflict,match='INPUT_REQUIRED'):
            reader.read(conn,scope=args['scope'],group_id=args['group_id'],actor=args['actor'],expected_manifest_hash=row['input_manifest_hash'])
    assert state['calls']==0


class AlteredRead:
    """Change fetched facts only; never alter database constraints or stored rows."""
    def __init__(self,conn,table,mutate):self.conn,self.table,self.mutate=conn,table,mutate
    def __getattr__(self,name):return getattr(self.conn,name)
    def execute(self,query,*a,**k):
        cursor=self.conn.execute(query,*a,**k)
        text=query if isinstance(query,str) else query.as_string(self.conn)
        if 'FROM public.'+self.table+'\n' not in text and 'FROM "public"."'+self.table+'"' not in text:
            return cursor
        mutate=self.mutate
        class Result:
            def fetchone(self):
                value=deepcopy(cursor.fetchone())
                return mutate(value) if value is not None else None
            def fetchall(self):return mutate(deepcopy(cursor.fetchall()))
        return Result()


def test_rehashed_or_missing_original_facts_are_rejected_without_writes(renewal_row):
    runtime,args,row,state=renewal_row
    reader=SnapshotSavedFactsReader(definitions=runtime._definitions,claims=runtime._claims)
    kw=dict(scope=args['scope'],group_id=args['group_id'],actor=args['actor'],expected_manifest_hash=row['input_manifest_hash'])
    def changed(**updates):return lambda value:value|updates
    def parent_changed(key,value):
        def mutate(row):
            row['envelope'][key]=value
            row['envelope_hash']=_digest(row['envelope'])
            if key=='sourceId':row['source_id']=value
            return row
        return mutate
    def manifest_changed(row):
        row['manifest']['members'][0]['rowCount']+=1
        row['manifest_hash']=canonical_sha256(row['manifest'])
        return row
    cases=[
        ('pipeline_snapshot_group_member',lambda values:values[:-1],'SOURCE_MEMBERS'),
        ('pipeline_snapshot_group_claim',changed(member_count=11),'SOURCE_GROUP'),
        ('pipeline_controlled_source_claim',changed(actor='different-executor'),'SOURCE_CLAIM_DIFFERS'),
        ('meta_schedule_run',changed(schedule_id='another-schedule'),'RUN_DIFFERS'),
        ('ecommerce_ingress_command',lambda r:None,'PARENT_REQUIRED'),
        ('ecommerce_ingress_command',parent_changed('sourceId','another-source'),'PARENT_BINDING'),
        ('ecommerce_ingress_command',parent_changed('pipelineHash','0'*64),'PARENT_BINDING'),
        ('pipeline_snapshot_group_input',lambda r:r|dict(read_completed_at=r['read_completed_at']+timedelta(days=2)),'BINDING_DRIFT'),
        ('pipeline_snapshot_group_input',manifest_changed,'BINDING_DRIFT'),
    ]
    with runtime._transaction(args['scope']) as conn:
        original=reader.read(conn,**kw)
        for table,mutate,message in cases:
            with pytest.raises(IngressJournalConflict,match=message):
                reader.read(AlteredRead(conn,table,mutate),**kw)
        # Even a supplied new manifest digest cannot repair a false leaf count.
        value=manifest_changed(dict(manifest=deepcopy(original.manifest)))
        with pytest.raises(IngressJournalConflict,match='INPUT_MEMBER'):
            reader.read(AlteredRead(conn,'pipeline_snapshot_group_input',manifest_changed),
                **(kw|dict(expected_manifest_hash=value['manifest_hash'])))
        assert reader.read(conn,**kw)==original
        assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_recovery_receipt').fetchone()['n']==0
    assert state['calls']==1
