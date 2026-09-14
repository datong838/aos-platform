"""Actual Case/Run/claim/evidence PG; source and installed identity are named doubles."""
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from test_product_event_analysis_service_pg import (
    analysis_case, consumer_case, host_case, control_governed, governed, service_case, stored, body,
)
from test_ecommerce_analysis_compilation_blueprint import request
from test_ecommerce_analysis_start_operation import _package
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_application import (
    EcommerceBusinessInvestigationApplication, CreateBusinessInvestigationRunRequest,
)
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunStore, BusinessInvestigationTriggerKind, BusinessInvestigationRunConflict,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory


@pytest.fixture
def pair(body):
    from test_product_event_binding import pair as original_pair
    from ecommerce_growth.ecommerce_business_investigation_case import BusinessInvestigationCase, canonical_hash
    from ecommerce_growth.ecommerce_product_event_schedule import ProductEventSchedulePolicy
    from test_product_event_schedule import seal
    current,policy=original_pair.__wrapped__(body)
    raw=current.authority_payload()
    raw['analysisType']=INITIAL_STORE_PROFILE.analysis_type
    raw['investigationProfileRef']=INITIAL_STORE_PROFILE.exact_ref.model_dump(mode='json',by_alias=True)
    raw['contentHash']=canonical_hash({k:v for k,v in raw.items() if k!='contentHash'})
    current=BusinessInvestigationCase.from_authority(raw)
    raw_policy=policy.authority_payload()
    raw_policy['caseRef']['contentHash']=current.content_hash
    raw_policy['methodRef']=raw['investigationProfileRef']
    return current,ProductEventSchedulePolicy.from_authority(seal(raw_policy))


@pytest.fixture
def startup_case(analysis_case):
    conn,service,claimed=analysis_case
    snapshot,command=service._phase(conn,claimed,lambda snapshot,request,dispatch:(snapshot,request))
    factory=TransactionBoundConnectFactory(HostTransaction(conn),service.scope)
    runs=BusinessInvestigationRunStore(factory)
    result=EcommerceBusinessInvestigationApplication(run_store=runs).create_run(
        service.scope,command['caseRef']['resourceId'],CreateBusinessInvestigationRunRequest(
            runId='startup-'+uuid4().hex,caseRef=InvestigationExactRef.model_validate(command['caseRef']),
            analysisType=INITIAL_STORE_PROFILE.analysis_type,triggerKind=BusinessInvestigationTriggerKind.RECOVERY,
            triggerKey=claimed.target_idempotency_key),idempotency_key='startup-'+uuid4().hex,
        actor='fixture-host',occurred_at=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
    run=result.run.authority
    from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseRevision
    case=BusinessInvestigationCaseRevision.model_validate(snapshot['source']['case'])
    assert case.calculated_content_hash()==case.content_hash
    assert case.investigation_profile_ref==INITIAL_STORE_PROFILE.exact_ref
    assert run.calculated_content_hash()==run.content_hash
    assert runs.get_verified(service.scope,run.run_id)==result.run
    assert run.case_ref.model_dump(mode='json',by_alias=True,exclude_none=True)==command['caseRef']
    assert datetime.fromisoformat(command['cutoffAt'])<=run.created_at<=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    ref=InvestigationExactRef(resourceType='BusinessInvestigationRun',resourceId=run.run_id,
        revision=run.version,contentHash=run.content_hash)
    original=service.source.reader.run_event
    event_at=conn.execute('SELECT transaction_timestamp() AS now').fetchone()['now'].replace(microsecond=0)
    def event(*args,**kw):
        callback=kw.pop('execute')
        return original(*args,**kw,execute=lambda row:callback(dict(row,payload_hash='d'*64,
            created_at=event_at,source_updated_at=event_at.isoformat())))
    service.source.reader.run_event=event
    return conn,service,claimed,ref


def record(data):
    from aos_api.ecommerce_analysis_startup_evidence import AnalysisStartupEvidenceService
    conn,service,claimed,ref=data
    return AnalysisStartupEvidenceService(service).record(conn,claimed=claimed,run_ref=ref,
        domain_profile=INITIAL_STORE_PROFILE,
        blueprint=_package().handle('ecommerce_growth_analysis_advance',request(),object()))


def test_startup_evidence_is_real_idempotent_and_rolled_back(startup_case):
    conn,service,_,_=startup_case
    with pytest.raises(RuntimeError,match='outer rollback'),conn.transaction():
        first=record(startup_case)
        assert record(startup_case)==first
        row=conn.execute('SELECT * FROM aip_evidence WHERE org_id=%s AND project_id=%s AND evidence_id=%s',
            (*service.scope.key,first.resource_id)).fetchone()
        assert row['run_id'] is None
        assert row['payload']['businessFactCoverage']=='not-evaluated'
        assert row['payload']['pendingBusinessFactProfiles']==list(INITIAL_STORE_PROFILE.required_fact_profiles)
        assert row['payload']['factIds']==['analysis.original-event-case-run-lineage']
        assert row['payload']['purpose']=='analysis-start'
        raise RuntimeError('outer rollback')
    assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='analysis-startup-lineage'").fetchone()['n']==0


def test_current_control_revoked_after_evidence_write_rolls_back(startup_case,monkeypatch):
    from aos_api.ecommerce_analysis_startup_evidence import AnalysisStartupEvidenceService
    conn,_,_,_=startup_case
    original=AnalysisStartupEvidenceService._put
    def revoke(*args,**kwargs):
        result=original(*args,**kwargs)
        conn.execute('RESET ROLE')
        conn.execute("DELETE FROM meta_membership WHERE subject='fixture-approver'")
        conn.execute('SET LOCAL ROLE aos_runtime')
        return result
    monkeypatch.setattr(AnalysisStartupEvidenceService,'_put',staticmethod(revoke))
    with pytest.raises(PermissionError),conn.transaction():record(startup_case)
    assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='analysis-startup-lineage'").fetchone()['n']==0


@pytest.mark.parametrize('fault',['run','control','source','revoked','state-hash','state-format'])
def test_startup_evidence_rejects_drift_or_revocation(startup_case,fault):
    conn,service,claimed,ref=startup_case
    if fault=='run':
        ref=ref.model_copy(update={'content_hash':'sha256:'+'f'*64})
        startup_case=(conn,service,claimed,ref)
    elif fault=='control':
        conn.execute('RESET ROLE')
        conn.execute("DELETE FROM meta_membership WHERE subject='fixture-approver'")
        conn.execute('SET LOCAL ROLE aos_runtime')
    elif fault=='source':service.source.reader._journal._run_id='different-source-run'
    elif fault.startswith('state-'):
        conn.execute('RESET ROLE')
        if fault=='state-hash':
            conn.execute('UPDATE ecommerce_investigation_run_state_head SET content_hash=%s WHERE run_id=%s',
                ('sha256:'+'f'*64,ref.resource_id))
        else:
            conn.execute("UPDATE ecommerce_investigation_run_state_head SET authority_data=authority_data||'{\"approved\":true}'::jsonb WHERE run_id=%s",
                (ref.resource_id,))
        conn.execute('SET LOCAL ROLE aos_runtime')
    else:
        evidence=record(startup_case)
        conn.execute('''INSERT INTO aip_evidence_revoke_event
            (org_id,project_id,event_id,evidence_id,revision,content_hash,reason,actor)
            VALUES(%s,%s,%s,%s,1,%s,'fixture revocation','fixture')''',
            (*service.scope.key,uuid4().hex,evidence.resource_id,evidence.content_hash.removeprefix('sha256:')))
    with pytest.raises((ValueError,PermissionError,BusinessInvestigationRunConflict)):record(startup_case)
