"""Twelve real PG pipelines; source, release and analysis origin are named fixtures."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from test_analysis_snapshot_business_evidence_pg import (
    database, pytestmark, ledger, owner_case, claim_case, executor_case,
    journal_case, object_case, completed_group, bridge_case, business_case,
    fact_case, evidence_case, query_case, quality_case, inputs,
)
from test_snapshot_group_claim_owner_pg import group_claim_case as two_claims
from test_controlled_snapshot_group_ingress_pg import prepared_case as two_prepared
from test_pipeline_snapshot_group_owner_pg import mapping
from test_pipeline_source_selection_owner_pg import approve
from test_pipeline_runtime_control_owner_pg import append
from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft, PipelineRuntimeControlDraft, PipelineExactRef
from aos_api.pipeline_snapshot_group_assessment_owner import PipelineSnapshotGroupAssessmentOwner
from aos_api.pipeline_selected_snapshot_group import SelectedSnapshotGroupResult
from aos_api.ecommerce_analysis_snapshot_business_evidence import AnalysisSnapshotBusinessEvidence
from aos_api.ecommerce_analysis_snapshot_readiness_context import AnalysisSnapshotReadinessContext
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES
from aos_api.ec_ingress_journal import _digest
from aos_api.ecom_core_models import REQUIRED_PROPERTIES


@pytest.fixture
def group_claim_case(executor_case):
    conn, owner, args, state, claims = two_claims.__wrapped__(executor_case)
    controls = claims._controls
    with conn.transaction():
        first = controls.run_current_snapshot(conn,scope=args['scope'],ref=args['bindings'][0][0],actor=args['actor'],execute=lambda d,p:d)
    plans={}
    def assets(db,item,actor,callback,*,snapshot=False):
        if state['deny']:raise PermissionError('named installation denied')
        plan=plans[item.pipeline_id]
        return callback(plan if snapshot else plan.read_spec)
    controls._selections._guarded=assets
    bindings=[]
    for index,s in enumerate(CANONICAL_QYH_SOURCES):
        base=mapping('fixture_table_'+str(index))
        defaults={key:1 for key in REQUIRED_PROPERTIES[s.object_type] if key not in {'createdAt','updatedAt','name','shippedAt'}}
        defaults.update(status='active',currency='CNY',timezone='+08:00')
        plans[s.pipeline_id]=replace(base,read_spec=replace(base.read_spec,object_type=s.object_type),defaults=tuple(defaults.items()))
        graph=dict(pipeline_id=s.pipeline_id,write_mode='SNAPSHOT',nodes=[dict(id='source-node',name='source',pipeline_id=s.pipeline_id,node_type='source',config=dict(source_id=first.source_id))])
        body=first.model_dump(exclude={'schema_version','source_selection_ref'})
        body.update(pipeline_id=s.pipeline_id,graph_hash=_digest(graph))
        selected=approve(conn,controls._selections,PipelineSourceSelectionDraft.model_validate(body),'twelve-selection-'+str(index))
        body['source_selection_ref']=selected
        ref=append(conn,controls,PipelineRuntimeControlDraft.model_validate(body),'twelve-control-'+str(index))
        run='twelve-run-'+str(index);schedule='twelve-schedule-'+str(index)
        conn.execute('RESET ROLE')
        conn.execute('INSERT INTO meta_schedule VALUES(%s,%s,%s,%s,true,%s)',(*args['scope'].key,schedule,s.pipeline_id,Jsonb(dict(kind='pipeline-live-v1',pipelineId=s.pipeline_id))))
        conn.execute('INSERT INTO meta_schedule_run VALUES(%s,%s,%s,%s,%s)',(*args['scope'].key,run,schedule,'running'))
        conn.execute('INSERT INTO phase5_pipeline_graph VALUES(%s,%s,%s,1,%s)',(*args['scope'].key,s.pipeline_id,Jsonb(graph)))
        conn.execute('SET ROLE aos_runtime')
        bindings.append((ref,run))
    state['plans']=plans
    return conn,owner,args|{'group_id':str(uuid4()),'bindings':tuple(bindings)},state,claims


@pytest.fixture
def prepared_case(group_claim_case,monkeypatch):
    result=two_prepared.__wrapped__(group_claim_case,monkeypatch)
    executor,conn,args,state=result
    def assets(db,item,actor,callback,*,snapshot=False):
        if state['deny']:raise PermissionError('named installation denied')
        plan=state['plans'][item.pipeline_id]
        return callback(plan if snapshot else plan.read_spec)
    executor._claims._controls._selections._guarded=assets
    def source(**kwargs):
        state['calls']+=1
        assert conn.execute('SELECT count(*) AS n FROM pipeline_controlled_source_claim').fetchone()['n']==12
        now=datetime.now(timezone.utc)
        rows={plan.read_spec.table:[dict(site_id=1,site_name='named-twelve-fixture')] for _,_,plan in kwargs['group'].members}
        return SelectedSnapshotGroupResult(rows,kwargs['group'].members[0][1].source_configuration_ref,now,now)
    import aos_api.pipeline_controlled_snapshot_group_ingress as target
    monkeypatch.setattr(target,'read_selected_snapshot_group',source)
    return result


@pytest.fixture
def assessment_case(prepared_case):
    executor,conn,args,state=prepared_case
    selections=executor._claims._controls._selections
    with conn.transaction():
        draft=executor._claims._controls.run_current_snapshot(conn,scope=args['scope'],ref=args['bindings'][0][0],actor=args['actor'],execute=lambda d,p:d)
    p=draft.package_ref
    selected=NS(publisher=p.publisher,id=p.id,version=p.version,content_hash=p.content_hash,signature_fingerprint='fixture',release_evidence_revision=1)
    document=dict(schemaVersion='aos.snapshot-relationships/v1',objectTypes=[s.object_type for s in CANONICAL_QYH_SOURCES],rules=[dict(linkType='Shop.hasWeapp',rowType='Weapp',parentType='Shop',referenceProperty='siteId',direction='parent-to-row',encoding='positive-id',allowUnset=False)])
    state['policy_raw']=json.dumps(document).encode()
    selections._store=NS(load_active_baseline_in_transaction=lambda *a,**k:NS(lock=NS(payload=NS(resolved=[selected]))))
    selections._artifacts=NS(scope=args['scope'],load_record=lambda *a:NS(manifest=NS(spec=NS(exports=NS(policies=['content/policies/'])))),read_artifact=lambda *a:state['policy_raw'])
    def release(*a,**k):
        if state.get('policy_denied'):raise PermissionError('named release denied')
    selections._release_policy=NS(evaluate=release)
    ref=PipelineExactRef(resource_type='SnapshotRelationshipPolicy',resource_id='content/policies/fixture.json',revision=p.version,content_hash='sha256:'+hashlib.sha256(state['policy_raw']).hexdigest())
    return executor,conn,args,state,PipelineSnapshotGroupAssessmentOwner(claims=executor._claims),ref


@pytest.fixture
def business_evidence_case(quality_case,monkeypatch):
    conn,state,source,_,_,call,_=quality_case
    field=json.loads(state['field_raw'])
    document=dict(schemaVersion='aos.snapshot-business-facts/v1',fieldPolicyHash='sha256:'+_digest(field),purposeCode=field['purposeCode'],facts=[dict(objectType=s.object_type,mode='records',fields=['name']) for s in CANONICAL_QYH_SOURCES])
    state['business_raw']=json.dumps(document).encode()
    ref=call['field_ref'].model_copy(update=dict(resource_type='SnapshotBusinessFactPolicy',resource_id='content/policies/business.json',content_hash='sha256:'+hashlib.sha256(state['business_raw']).hexdigest()))
    artifacts=source._claims._controls._selections._artifacts;old=artifacts.read_artifact
    artifacts.read_artifact=lambda selected,path,limit:state['business_raw'] if path==ref.resource_id else old(selected,path,limit)
    import aos_api.ecommerce_analysis_snapshot_quality_evidence as q
    import aos_api.ecommerce_analysis_snapshot_business_evidence as b
    import aos_api.ecommerce_analysis_snapshot_readiness_context as r
    monkeypatch.setattr(b,'HostTransaction',q.HostTransaction)
    monkeypatch.setattr(r,'HostTransaction',q.HostTransaction)
    return quality_case,AnalysisSnapshotBusinessEvidence(source),ref


def test_twelve_original_business_evidence_is_complete(business_evidence_case):
    case,business,_=business_evidence_case
    conn,state=case[:2]
    ref=business.put_current(conn,**inputs(business_evidence_case))
    body=business.read_current(conn,reference=ref)
    assert set(body['factIds'])=={s.object_type for s in CANONICAL_QYH_SOURCES}
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_dataset_receipt').fetchone()['n']==12
    assert state['calls']==1


@pytest.fixture
def readiness_case(business_evidence_case,monkeypatch):
    """Actual binding row/Owner; Provider/dependency health remains named doubles."""
    from aos_api.aip_agent_registry_contracts import OperationalBindingDependencies,OperationalBindingReadiness,VersionedAssetRef
    from aos_api.aip_binding_readiness_service import AipBindingReadinessService
    case,business,business_policy=business_evidence_case
    conn,state,source,_,_,call,_=case
    field=json.loads(state['field_raw'])
    policy=dict(schemaVersion='aos.snapshot-readiness-policy/v1',fieldPolicyHash='sha256:'+_digest(field),
        relationshipQualityPolicyHash=field['relationshipQualityPolicyHash'],purposeCode='initial_store_analysis',
        freshnessMode='requirement-oldest-observation',reconciliationMode='current-original-base-and-derived',
        queryBindingId='query-twelve',sources=[dict(pipelineId=s.pipeline_id,objectType=s.object_type) for s in CANONICAL_QYH_SOURCES])
    state['readiness_raw']=json.dumps(policy).encode()
    policy_ref=business_policy.model_copy(update=dict(resource_type='SnapshotReadinessPolicy',resource_id='content/policies/readiness.json',content_hash='sha256:'+hashlib.sha256(state['readiness_raw']).hexdigest()))
    artifacts=source._claims._controls._selections._artifacts;old=artifacts.read_artifact
    artifacts.read_artifact=lambda selected,path,limit:state['readiness_raw'] if path==policy_ref.resource_id else old(selected,path,limit)
    root=Path(__file__).resolve().parents[2]/'alembic/versions'
    conn.execute('RESET ROLE')
    for file,prefix in [('aip6_001_agent_skill_registry.py','CREATE TABLE aip_capability_binding ('),('bind1_001_operational_bindings.py','ALTER TABLE aip_capability_binding\n        ADD COLUMN provider_ref')]:
        strings=[n.value for n in ast.walk(ast.parse((root/file).read_text())) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith(prefix)]
        assert len(strings)==1;conn.execute(strings[0])
    spec=importlib.util.spec_from_file_location('twelve_binding_scope',root/'aip6_001_agent_skill_registry.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=NS(execute=conn.execute);module._scope('aip_capability_binding')
    conn.execute('GRANT SELECT,INSERT,UPDATE ON aip_capability_binding TO aos_runtime')
    conn.execute('CREATE TABLE readiness_test_probe(value text); GRANT SELECT,INSERT ON readiness_test_probe TO aos_runtime')
    cap=VersionedAssetRef(asset_type='CapabilityRevision',asset_id='strategy.plan',revision=1,content_hash='1'*64)
    deps=OperationalBindingDependencies();digest=AipBindingReadinessService.snapshot_hash(cap,deps)
    now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    conn.execute('''INSERT INTO aip_capability_binding(org_id,project_id,binding_id,capability_ref,secret_ref,health,
        network_policy_revision,quota_policy_revision,timeout_ms,max_concurrency,status,version,observed_at,
        operational_readiness,readiness_reasons,dependency_snapshot_hash,last_evaluated_at,readiness_expires_at,created_at)
        VALUES(%s,%s,'query-twelve',%s,'vault://named-fixture','healthy','network','quota',1000,1,'active',2,%s,
        'available','[]',%s,%s,%s,%s)''',(*business.scope.key,Jsonb(cap.model_dump(mode='json',by_alias=True)),now,digest,now,now+timedelta(hours=1),now-timedelta(seconds=1)))
    conn.execute('SET ROLE aos_runtime')
    import aos_api.ecommerce_analysis_query_binding as target
    monkeypatch.setattr(target.PostgresBindingDependencyAuthority,'capability',lambda self,ref:dict(lifecycle='published',content_hash=ref.content_hash,required_data_refs=[],required_tool_refs=[]))
    def evaluate(self,scope,ref,dependencies,*,evaluated_at):
        assert scope==business.scope
        return OperationalBindingReadiness(readiness='available',reasons=[],dependencies=dependencies,
            dependency_snapshot_hash=self.snapshot_hash(ref,dependencies),evaluated_at=evaluated_at,expires_at=evaluated_at+timedelta(minutes=15))
    monkeypatch.setattr(target.AipBindingReadinessService,'evaluate_capability',evaluate)
    def strict(*a,**k):
        if state.get('binding_denied'):raise ValueError('named binding dependency revoked')
    monkeypatch.setattr(target.ContentGenerateHostService,'_binding_dependency_authority',strict)
    ref=business.put_current(conn,**inputs(business_evidence_case))
    return conn,state,AnalysisSnapshotReadinessContext(business),dict(business_ref=ref,policy_ref=policy_ref)


def test_twelve_current_readiness_consumes_original_pg_owners(readiness_case):
    from aos_api.source_readiness import SourceReadinessService
    conn,state,owner,call=readiness_case
    first=owner.run_current(conn,**call,execute=lambda value:SourceReadinessService.evaluate_installed_snapshot(value))
    assert first.status=='ready' and len(first.sources)==12 and first.receipt_ref is None
    assert state['calls']==1
    assert all(s.counts.source_total==s.counts.projection_total==1 for s in first.sources)
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_dataset_receipt').fetchone()['n']==12


@pytest.mark.parametrize('fault',['input','run','policy','binding','release','deferred','control'])
def test_late_changes_cannot_commit_consumption(readiness_case,fault):
    conn,state,owner,call=readiness_case
    called=[]
    def consume(value):
        called.append(True)
        conn.execute("INSERT INTO readiness_test_probe VALUES('must-rollback')")
        if fault=='input':value.sources.pop()
        elif fault=='run':conn.execute("UPDATE meta_schedule_run SET finished_at=finished_at-interval '1 second' WHERE id='twelve-run-0'")
        elif fault=='policy':state['readiness_raw']=b'{}'
        elif fault=='binding':state['binding_denied']=True
        elif fault=='release':state['policy_denied']=True
        elif fault=='deferred':return (x for x in [value])
        elif fault=='control':
            business=owner.business._record(conn,call['business_ref'])
            source=owner.source._record(conn,business['selection']['evidenceRef'])
            first=source['members'][0]
            append(conn,owner.source._claims._controls,
                PipelineRuntimeControlDraft.model_validate(first['control']),
                'twelve-late-control',PipelineExactRef.model_validate(first['controlRef']))
    with pytest.raises((ValueError,PermissionError,RuntimeError,TypeError)):
        owner.run_current(conn,**call,execute=consume)
    assert called==[True]
    assert conn.execute('SELECT count(*) AS n FROM readiness_test_probe').fetchone()['n']==0
    assert state['calls']==1
