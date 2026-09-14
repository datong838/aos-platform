"""Actual canonical TaskBrief/Receipt with named pending/runtime fixtures."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_analysis_snapshot_business_evidence_pg import (
    database,pytestmark,ledger,owner_case,claim_case,executor_case,group_claim_case,prepared_case,
    assessment_case,journal_case,object_case,completed_group,bridge_case,business_case,fact_case,evidence_case,query_case,quality_case,
    business_evidence_case,inputs,revoke,
)
from aos_api.ecommerce_analysis_snapshot_brief import AnalysisSnapshotBrief


@pytest.fixture
def brief_case(business_evidence_case,monkeypatch):
    case,business,policy=business_evidence_case;conn,_,source,_,_,_,pending=case
    from tests.test_aip_business_investigation_evidence import runtime
    value=runtime().model_dump(mode='json',by_alias=True)
    req=pending['requirement']
    for key,reqkey in [('caseRef','caseRef'),('businessInvestigationRunRef','runRef')]:
        value[key]={k:v for k,v in req[reqkey].items() if k in ('resourceType','resourceId','revision','contentHash')};value[key]['contentHash']=value[key]['contentHash'][7:]
    checkpoint=req['checkpointRef']
    value['checkpointRef']=dict(resourceId=checkpoint['resourceId'],sequence=checkpoint['revision'],stateHash=checkpoint['contentHash'][7:])
    pending['runtime']=value
    conn.execute('RESET ROLE')
    path=Path(__file__).resolve().parents[2]/'alembic/versions/w2_001_brief_evidence.py'
    spec=importlib.util.spec_from_file_location('brief_ddl',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    conn.execute('SET ROLE aos_runtime')
    conn.execute("INSERT INTO aip_task(org_id,project_id,task_id,task_type,title,status,idempotency_key,request_hash,created_by,version) VALUES(%s,%s,'task-1','analysis','fixture','paused','fixture-task',repeat('1',64),'fixture',2)",source.analysis.scope.key)
    import aos_api.ecommerce_analysis_snapshot_brief as target
    import aos_api.ecommerce_analysis_snapshot_business_evidence as origin
    monkeypatch.setattr(target,'HostTransaction',origin.HostTransaction)
    evidence=business.put_current(conn,**inputs(business_evidence_case))
    return case,business,evidence,AnalysisSnapshotBrief(business)


def test_frozen_brief_reuses_original_task_and_replays(brief_case):
    case,_,evidence,owner=brief_case;conn=case[0]
    ref=owner.prepare_current(conn,business_ref=evidence)
    assert owner.prepare_current(conn,business_ref=evidence)==ref
    brief=owner.read_current(conn,business_ref=evidence,brief_ref=ref)
    assert brief.task_id=='task-1' and brief.lifecycle.value=='frozen' and brief.revision==2
    assert conn.execute('SELECT count(*) AS n FROM aip_task').fetchone()['n']==1
    assert conn.execute('SELECT count(*) AS n FROM aip_task_brief_head').fetchone()['n']==1


def test_revoked_business_blocks_brief_replay(brief_case):
    case,_,evidence,owner=brief_case;conn,_,source=case[:3]
    owner.prepare_current(conn,business_ref=evidence);revoke(conn,source,evidence)
    with pytest.raises(ValueError):owner.prepare_current(conn,business_ref=evidence)


def test_changed_task_version_blocks_brief(brief_case):
    case,_,evidence,owner=brief_case;conn=case[0]
    conn.execute("UPDATE aip_task SET version=version+1 WHERE task_id='task-1'")
    with pytest.raises(ValueError,match='original paused Task changed'):owner.prepare_current(conn,business_ref=evidence)


def test_failed_freeze_rolls_back_original_brief(brief_case,monkeypatch):
    from aos_api.aip_production_contract_store import AipProductionContractStore
    case,_,evidence,owner=brief_case;conn,state=case[:2]
    original=AipProductionContractStore.freeze_brief
    def freeze(self,*args,**kwargs):
        value=original(self,*args,**kwargs);state['business_raw']=b'{}';return value
    monkeypatch.setattr(AipProductionContractStore,'freeze_brief',freeze)
    with pytest.raises(ValueError):owner.prepare_current(conn,business_ref=evidence)
    assert conn.execute('SELECT count(*) AS n FROM aip_task_brief_head').fetchone()['n']==0


def test_frozen_brief_cannot_be_revised(brief_case):
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import ReviseBriefRequest
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    import aos_api.ecommerce_analysis_snapshot_brief as module
    case,_,evidence,owner=brief_case;conn=case[0]
    ref=owner.prepare_current(conn,business_ref=evidence)
    brief=owner.read_current(conn,business_ref=evidence,brief_ref=ref)
    store=AipProductionContractStore(TransactionBoundConnectFactory(module.HostTransaction(conn),owner.scope))
    from aos_api.aip_production_contract_store import ProductionContractConflict
    with pytest.raises(ProductionContractConflict,match='only a draft brief can be revised'):
        store.revise_brief(owner.scope,brief.created_by,brief.brief_id,'fixture-revise',ReviseBriefRequest(
            expected_version=brief.version,brief_type=brief.brief_type,schema_ref=brief.schema_ref,spec=brief.spec|{'note':'user edit'}))
    assert owner.prepare_current(conn,business_ref=evidence)==ref
    assert conn.execute('SELECT current_revision FROM aip_task_brief_head').fetchone()['current_revision']==2


def test_fault_injected_head_drift_blocks_replay(brief_case):
    case,_,evidence,owner=brief_case;conn=case[0]
    owner.prepare_current(conn,business_ref=evidence)
    # Explicit storage fault; the normal API does not revise a frozen brief.
    conn.execute('UPDATE aip_task_brief_head SET current_revision=1,version=version+1')
    with pytest.raises(ValueError,match='brief authority differs'):owner.prepare_current(conn,business_ref=evidence)
    assert conn.execute('SELECT current_revision FROM aip_task_brief_head').fetchone()['current_revision']==1


@pytest.mark.parametrize('fault',['task','business-revoke'])
def test_late_dependency_change_rolls_back_brief(brief_case,monkeypatch,fault):
    from aos_api.aip_production_contract_store import AipProductionContractStore
    case,_,evidence,owner=brief_case;conn,_,source=case[:3]
    original=AipProductionContractStore.freeze_brief
    def freeze(self,*args,**kwargs):
        value=original(self,*args,**kwargs)
        if fault=='task':conn.execute("UPDATE aip_task SET status='cancelled',version=version+1 WHERE task_id='task-1'")
        else:revoke(conn,source,evidence)
        return value
    monkeypatch.setattr(AipProductionContractStore,'freeze_brief',freeze)
    with pytest.raises(ValueError):owner.prepare_current(conn,business_ref=evidence)
    assert conn.execute('SELECT count(*) AS n FROM aip_task_brief_head').fetchone()['n']==0
