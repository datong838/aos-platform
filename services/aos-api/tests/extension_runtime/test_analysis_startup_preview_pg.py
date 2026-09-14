"""Stored startup preview references; source/selection/capability availability are fixtures."""
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from test_analysis_compilation_preparation_pg import (
    compilation_case,publications,context_publication,context_case,startup_case,analysis_case,
    consumer_case,host_case,control_governed,governed,service_case,stored,pair,body,
)
from tests.test_ecommerce_analysis_skill_set import data
from aos_api.ecommerce_analysis_compilation_selection import AnalysisCompilationSelectionReader
from aos_api.ecommerce_analysis_skill_set import AnalysisSkillBindingSet
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE


@pytest.fixture
def preview_case(compilation_case,publications,monkeypatch):
    conn,analysis,claimed,_,_=compilation_case
    scope=analysis.scope
    installation=analysis._phase(conn,claimed,lambda snapshot,*_:snapshot['source']['dispatch'])
    _,sample,_=data()
    budget=sample.budget_policy_ref.model_dump(mode='json',by_alias=True)
    budget['assetType']='BudgetPolicyRevision'
    selected_ids=[]
    for runtime in publications:
        skill=runtime.published
        old=conn.execute('SELECT binding_id,capability_refs FROM aip_skill_binding WHERE org_id=%s AND project_id=%s AND instance_id=%s ORDER BY binding_id LIMIT 1',
            (*scope.key,'ecommerce.data_advisor.default')).fetchone()
        row=conn.execute('SELECT binding_id FROM aip_skill_binding WHERE org_id=%s AND project_id=%s AND instance_id=%s AND skill_id=%s',
            (*scope.key,'ecommerce.data_advisor.default',skill.skill_id)).fetchone()
        identity=row['binding_id'] if row else 'fixture-preview-binding-'+uuid4().hex
        if not row:
            conn.execute('''INSERT INTO aip_skill_binding
                (org_id,project_id,binding_id,instance_id,skill_id,skill_revision,capability_refs,budget_policy_ref,status)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'active')''',
                (*scope.key,identity,'ecommerce.data_advisor.default',skill.skill_id,skill.revision,Jsonb(old['capability_refs']),Jsonb(budget)))
        conn.execute("""UPDATE aip_skill_binding SET budget_policy_ref=%s,readiness='available',readiness_reasons='[]',
            dependency_snapshot_hash=%s,last_evaluated_at=clock_timestamp(),readiness_expires_at=clock_timestamp()+interval '1 hour'
            WHERE org_id=%s AND project_id=%s AND binding_id=%s""",(Jsonb(budget),'e'*64,*scope.key,identity))
        selected_ids.append(identity)
    original=AnalysisCompilationSelectionReader.run_current
    def selected(self,connection,**kw):
        value=original(self,connection,**{**kw,'execute':lambda value:value})
        registry=AipSkillRegistry(TransactionBoundConnectFactory(HostTransaction(conn),scope))
        current={k:installation[k] for k in ('installationId','generation','executionEpoch')}
        raw=dict(value['skillBindingSet'],**current,bindings=[registry.get_binding(scope,identity).model_dump(mode='json',by_alias=True) for identity in sorted(selected_ids)])
        raw['contentHash']=canonical_sha256({k:v for k,v in raw.items() if k!='contentHash'})
        exact=AnalysisSkillBindingSet.model_validate(raw)
        value.update(currentInstallation=current,skillBindingSet=raw,skillBindingSetRef=exact.exact_ref.model_dump(mode='json',by_alias=True))
        return kw['execute'](value)
    monkeypatch.setattr(AnalysisCompilationSelectionReader,'run_current',selected)
    return compilation_case


def preview(data,execute=lambda value:value):
    from aos_api.ecommerce_analysis_context_preparation import AnalysisContextPreparation
    from aos_api.ecommerce_analysis_compilation_preparation import AnalysisCompilationPreparation
    from aos_api.ecommerce_analysis_startup_preview import AnalysisStartupPreviewPreparation
    conn,analysis,claimed,run_ref,blueprint=data
    service=AnalysisStartupPreviewPreparation(AnalysisCompilationPreparation(AnalysisContextPreparation(analysis)))
    return service.run_current(conn,claimed=claimed,run_ref=run_ref,domain_profile=INITIAL_STORE_PROFILE,blueprint=blueprint,execute=execute)


def test_startup_preview_is_task_bound_and_rollback_safe(preview_case):
    conn,analysis,_,_,_=preview_case
    with pytest.raises(RuntimeError,match='outer preview rollback'),conn.transaction():
        result=preview(preview_case)
        view=result['startupPreview']
        assert view['lifecycle']=='frozen' and view['readiness']=='ready'
        assert view['taskId']==result['compilationReceipt']['taskId']
        assert view['productionContextRef']==result['productionContextRef']
        assert view['impact']['cost']['value']['providerCalls']==0
        assert view['impact']['risks']['value']['businessExecutionAuthorized'] is False
        evidence=result['bootstrapEvidenceRef']
        row=conn.execute('SELECT payload,run_id FROM aip_evidence WHERE org_id=%s AND project_id=%s AND evidence_id=%s',
            (*analysis.scope.key,evidence['resourceId'])).fetchone()
        assert row['run_id'] is None and row['payload']['intent']==result['bootstrapIntent']
        assert conn.execute('SELECT count(*) AS n FROM aip_task_run WHERE org_id=%s AND project_id=%s AND task_id=%s',
            (*analysis.scope.key,view['taskId'])).fetchone()['n']==0
        raise RuntimeError('outer preview rollback')
    assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='analysis-bootstrap-intent'").fetchone()['n']==0


def test_preview_callback_failure_rolls_back_compilation(preview_case):
    conn,analysis,_,_,_=preview_case
    def fail(value):
        assert value['startupPreviewRef']['resourceId']
        raise RuntimeError('after preview failed')
    with pytest.raises(RuntimeError,match='after preview failed'),conn.transaction():preview(preview_case,execute=fail)
    assert conn.execute('SELECT count(*) AS n FROM aip_business_investigation_compile_receipt WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==0


@pytest.mark.parametrize('fault',['evidence-revoked','binding-version'])
def test_preview_rejects_changed_authority_after_creation(preview_case,fault):
    from aos_api.aip_production_contract_store import ProductionContractDependencyBlocked
    conn,analysis,_,_,_=preview_case
    def mutate(value):
        if fault=='evidence-revoked':
            ref=value['bootstrapEvidenceRef']
            conn.execute('''INSERT INTO aip_evidence_revoke_event
                (org_id,project_id,event_id,evidence_id,revision,content_hash,reason,actor)
                VALUES(%s,%s,%s,%s,1,%s,'fixture revoked','fixture')''',
                (*analysis.scope.key,uuid4().hex,ref['resourceId'],ref['contentHash'].removeprefix('sha256:')))
        else:
            ref=next(item for item in value['startupPreview']['bindingRefs'] if item['resourceType']=='SkillBinding')
            conn.execute('UPDATE aip_skill_binding SET version=version+1 WHERE org_id=%s AND project_id=%s AND binding_id=%s',
                (*analysis.scope.key,ref['resourceId']))
        return value
    message='bootstrap intent evidence' if fault=='evidence-revoked' else 'IMPACT_PREVIEW_'
    with pytest.raises((ValueError,ProductionContractDependencyBlocked),match=message),conn.transaction():
        preview(preview_case,execute=mutate)
    assert conn.execute('SELECT count(*) AS n FROM aip_business_investigation_compile_receipt WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==0


def test_preview_rejects_agent_version_different_from_configured_role(preview_case, monkeypatch):
    from aos_api.ecommerce_analysis_startup_preview import AnalysisStartupPreviewPreparation
    conn,analysis,_,_,_=preview_case
    original=AnalysisStartupPreviewPreparation._mutable_refs
    def drift(tx,scope,prepared):
        owner=next(slot['assignee'] for slot in prepared['responsibilityPlan']['slots']
                   if slot['assignee']['kind']=='agent_instance')
        conn.execute('UPDATE aip_agent_instance SET version=version+1 WHERE org_id=%s AND project_id=%s AND instance_id=%s',
                     (*scope.key,owner['resourceId']))
        return original(tx,scope,prepared)
    monkeypatch.setattr(AnalysisStartupPreviewPreparation,'_mutable_refs',staticmethod(drift))
    with pytest.raises(ValueError,match='bootstrap configured agent version differs'),conn.transaction():
        preview(preview_case)
    assert conn.execute('SELECT count(*) AS n FROM aip_business_investigation_compile_receipt WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==0
