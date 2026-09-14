"""Real formal initialization to pending data; source/capability fixtures remain explicit."""
import asyncio
from datetime import datetime,timedelta
import pytest
from test_product_event_analysis_bootstrap_pg import (
    formal_case,preview_case,review_identity,compilation_case,publications,context_publication,
    context_case,startup_case,analysis_case,consumer_case,host_case,control_governed,governed,
    service_case,stored,pair,body,
)
from aos_api.ecommerce_business_investigation_data_command import RequestBusinessInvestigationMissingDataCommand
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE

pytestmark=[pytest.mark.parametrize('startup_case',['defer-host'],indirect=True),
            pytest.mark.parametrize('stored',['qualified-runtime'],indirect=True)]


@pytest.fixture
def data_case(formal_case):
    conn,analysis,claimed=formal_case
    asyncio.run(analysis.handle(claimed))
    snapshot,request=analysis._phase(conn,claimed,lambda snapshot,request,dispatch:(snapshot,request))
    cutoff=datetime.fromisoformat(request['cutoffAt'])
    spec=RequestBusinessInvestigationMissingDataCommand(purposeCode='initial_store_analysis',
        requiredFacts=list(INITIAL_STORE_PROFILE.required_fact_profiles),
        timeWindow=dict(startAt=cutoff-timedelta(days=30),endAt=cutoff),grain='store',cutoffAt=cutoff,
        freshnessMaxAgeSeconds=3600,qualityThreshold=1.0,markings=[],minPopulation=1,
        acceptableDegradation=[],requestedOutputs=['EvidenceBundleRevision'],budgetMinor=0,
        expiresAt=datetime.fromisoformat(snapshot['source']['policy']['effectiveUntil']))
    return conn,analysis,claimed,spec


def prepare(data):
    from aos_api.ecommerce_analysis_data_preparation import AnalysisDataRequirementPreparation
    conn,analysis,claimed,spec=data
    return AnalysisDataRequirementPreparation(analysis).run_current(conn,claimed=claimed,request=spec)


def test_actual_requirement_waiting_and_replay(data_case):
    conn,analysis,claimed,spec=data_case
    receipt=prepare(data_case)
    assert prepare(data_case)==receipt
    assert receipt['requirementRef']['resourceType']=='DataRequirementRevision'
    rows=conn.execute('SELECT status FROM aip_task_run WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchall()
    assert len(rows)==1 and rows[0]['status']=='paused'
    assert conn.execute('SELECT count(*) AS n FROM aip_step_run WHERE org_id=%s AND project_id=%s',analysis.scope.key).fetchone()['n']==0


@pytest.mark.parametrize('fault',['facts','cutoff','expiry'])
def test_rejects_nonoriginal_data_intent(data_case,fault):
    conn,analysis,claimed,spec=data_case
    raw=spec.model_dump(mode='json',by_alias=True)
    if fault=='facts':raw['requiredFacts']=['fabricated.fact']
    elif fault=='cutoff':raw['cutoffAt']=(spec.cutoff_at+timedelta(seconds=1)).isoformat()
    else:raw['expiresAt']=(spec.expires_at+timedelta(seconds=1)).isoformat()
    invalid=RequestBusinessInvestigationMissingDataCommand.model_validate(raw)
    with pytest.raises(ValueError),conn.transaction():prepare((conn,analysis,claimed,invalid))


def test_outer_failure_rolls_back_pending_requirement(data_case):
    from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory,_HostAnalysisReceiptStore
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    conn,analysis,claimed,spec=data_case
    tx=HostTransaction(conn)
    original=_HostAnalysisReceiptStore(tx,analysis.scope).read(claimed.target_idempotency_key)
    runs=BusinessInvestigationRunStore(TransactionBoundConnectFactory(tx,analysis.scope))
    with pytest.raises(RuntimeError,match='after requirement'),conn.transaction():
        prepare(data_case)
        raise RuntimeError('after requirement')
    assert runs.get_verified(analysis.scope,original['runRef']['resourceId']).state.lifecycle.value=='PREPARING'


def test_same_event_changed_data_policy_is_not_a_second_request(data_case):
    conn,analysis,claimed,spec=data_case
    receipt=prepare(data_case)
    changed=spec.model_copy(update={'min_population':spec.min_population+1})
    with pytest.raises(ValueError,match='drifted'),conn.transaction():
        prepare((conn,analysis,claimed,changed))
    assert prepare(data_case)==receipt
