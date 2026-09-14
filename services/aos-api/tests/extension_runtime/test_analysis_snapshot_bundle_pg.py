"""Original Bundle store in isolated PG; pending/runtime remain named fixtures."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_analysis_snapshot_brief_pg import (
    database,pytestmark,ledger,owner_case,claim_case,executor_case,group_claim_case,
    assessment_case,journal_case,object_case,completed_group,bridge_case,business_case,fact_case,
    evidence_case,query_case,quality_case,business_evidence_case,brief_case,revoke,
)
from aos_api.ecommerce_analysis_snapshot_bundle import AnalysisSnapshotBundle
from test_controlled_snapshot_group_ingress_pg import prepared_case as base_prepared_case


@pytest.fixture
def prepared_case(group_claim_case,monkeypatch):
    from dataclasses import replace
    from datetime import datetime,timezone
    import time
    import aos_api.pipeline_controlled_snapshot_group_ingress as module
    case=base_prepared_case.__wrapped__(group_claim_case,monkeypatch)
    original=module.read_selected_snapshot_group
    def source(**kwargs):
        value=original(**kwargs)
        # The original source double uses start=end. This fixture explicitly
        # supplies a nonzero read interval BEFORE any authority is persisted.
        time.sleep(0.01)
        return replace(value,completed_at=datetime.now(timezone.utc))
    monkeypatch.setattr(module,'read_selected_snapshot_group',source)
    return case


@pytest.fixture
def bundle_case(business_evidence_case,monkeypatch,request):
    configured=business_evidence_case
    mode=getattr(request,'param','complete')
    if mode in ('partial','blocked'):
        import json,hashlib
        from aos_api.ec_ingress_journal import _digest
        case,business,policy=configured;state=case[1];call=case[5]
        field=json.loads(state['field_raw'])
        for fact in field['facts']:
            if mode=='blocked' or fact['objectType']=='Weapp':
                fact['fields'].append(dict(property='missingPublicField',kind='nonblank-string'))
        state['field_raw']=json.dumps(field).encode()
        call['field_ref']=call['field_ref'].model_copy(update={'content_hash':'sha256:'+hashlib.sha256(state['field_raw']).hexdigest()})
        policy_body=json.loads(state['business_raw']);policy_body['fieldPolicyHash']='sha256:'+_digest(field)
        state['business_raw']=json.dumps(policy_body).encode()
        policy=policy.model_copy(update={'content_hash':'sha256:'+hashlib.sha256(state['business_raw']).hexdigest()})
        configured=(case,business,policy)
    case,business,evidence,brief=brief_case.__wrapped__(configured,monkeypatch);conn=case[0]
    conn.execute('RESET ROLE')
    path=Path(__file__).resolve().parents[2]/'alembic/versions/w2_005_evidence_revoke_disclosure.py'
    spec=importlib.util.spec_from_file_location('bundle_ddl',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    conn.execute('SET ROLE aos_runtime')
    return case,business,evidence,AnalysisSnapshotBundle(brief)


def test_original_bundle_replay_retains_real_observation_time(bundle_case):
    case,business,evidence,owner=bundle_case;conn=case[0]
    before=business.read_current(conn,reference=evidence)
    ref=owner.prepare_current(conn,business_ref=evidence)
    assert owner.prepare_current(conn,business_ref=evidence)==ref
    bundle=owner.read_current(conn,business_ref=evidence,bundle_ref=ref)
    assert bundle.coverage.value=='complete' and bundle.freshness.value=='fresh'
    assert bundle.uncertainties[0]['code']=='SNAPSHOT_OBSERVATION_NOT_SOURCE_TRANSACTION_TIME'
    assert business.read_current(conn,reference=evidence)==before
    assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revision').fetchone()['n']==1
    assert conn.execute('SELECT count(*) AS n FROM aip_task').fetchone()['n']==1


def test_business_revocation_blocks_bundle_replay(bundle_case):
    case,_,evidence,owner=bundle_case;conn,_,source=case[:3]
    owner.prepare_current(conn,business_ref=evidence);revoke(conn,source,evidence)
    with pytest.raises(ValueError):owner.prepare_current(conn,business_ref=evidence)


def test_late_policy_change_rolls_back_bundle_and_brief(bundle_case,monkeypatch):
    from aos_api.aip_production_contract_store import AipProductionContractStore
    case,_,evidence,owner=bundle_case;conn,state=case[:2]
    original=AipProductionContractStore.build_evidence_bundle
    def build(self,*args,**kwargs):
        result=original(self,*args,**kwargs);state['business_raw']=b'{}';return result
    monkeypatch.setattr(AipProductionContractStore,'build_evidence_bundle',build)
    with pytest.raises(ValueError):owner.prepare_current(conn,business_ref=evidence)
    assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revision').fetchone()['n']==0
    assert conn.execute('SELECT count(*) AS n FROM aip_task_brief_head').fetchone()['n']==0


@pytest.mark.parametrize('bundle_case',['partial','blocked'],indirect=True)
def test_missing_facts_are_not_promoted_to_complete(bundle_case):
    case,business,evidence,owner=bundle_case;conn=case[0]
    ref=owner.prepare_current(conn,business_ref=evidence)
    bundle=owner.read_current(conn,business_ref=evidence,bundle_ref=ref)
    assert bundle.coverage.value in ('partial','blocked')
    assert {'factId':'Weapp'} in bundle.missing
    if not business.read_current(conn,reference=evidence)['factIds']:
        assert bundle.coverage.value=='blocked' and bundle.freshness.value=='blocked'


def test_original_generic_freshness_rule_remains_stale(bundle_case):
    from aos_api.aip_production_contract_store import AipProductionContractStore
    case,_,evidence,owner=bundle_case;conn=case[0]
    brief_ref=owner.brief.prepare_current(conn,business_ref=evidence)
    def check(tx,store,body,*args):
        original=AipProductionContractStore._compute_evidence_bundle_coverage(store,tx,owner.scope,body)
        assert original[-1].value=='stale'
    owner._during(conn,evidence,brief_ref,check)


def test_original_bundle_revocation_blocks_read_and_replay(bundle_case):
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import RevokeEvidenceBundleRequest
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    import aos_api.ecommerce_analysis_snapshot_brief as module
    case,_,evidence,owner=bundle_case;conn=case[0]
    ref=owner.prepare_current(conn,business_ref=evidence)
    store=AipProductionContractStore(TransactionBoundConnectFactory(module.HostTransaction(conn),owner.scope))
    store.revoke_evidence_bundle(owner.scope,'fixture',ref.resource_id,'revoke-bundle',RevokeEvidenceBundleRequest(
        expected_revision=1,expected_content_hash=ref.content_hash[7:],reason='fixture revoke'))
    with pytest.raises(ValueError):owner.read_current(conn,business_ref=evidence,bundle_ref=ref)
    from aos_api.aip_business_investigation_evidence import BusinessInvestigationEvidenceBlocked
    with pytest.raises(BusinessInvestigationEvidenceBlocked):owner.prepare_current(conn,business_ref=evidence)


def test_exact_hash_mismatch_rejected(bundle_case):
    case,_,evidence,owner=bundle_case;conn=case[0]
    ref=owner.prepare_current(conn,business_ref=evidence)
    with pytest.raises(ValueError,match='authority differs'):
        owner.read_current(conn,business_ref=evidence,bundle_ref=ref.model_copy(update={'content_hash':'sha256:'+'f'*64}))


@pytest.mark.parametrize('timing',['after-persist','replay'])
def test_actual_quality_evaluation_rejects_expired_observation(bundle_case,monkeypatch,timing):
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.aip_production_contract_store import AipProductionContractStore
    case,_,evidence,owner=bundle_case;conn=case[0]
    execute=HostTransaction.execute
    def advance_clock():
        # Isolated test clock: actual DB statement/result and original quality
        # evaluator; no wall clock change and no fabricated assessment result.
        monkeypatch.setattr(HostTransaction,'execute',lambda self,query,params=():execute(
            self,query.replace('clock_timestamp()',"(clock_timestamp()+interval '2 hours')"),params))
    if timing=='replay':
        ref=owner.prepare_current(conn,business_ref=evidence);advance_clock()
        with pytest.raises(ValueError):owner.read_current(conn,business_ref=evidence,bundle_ref=ref)
        with pytest.raises(ValueError):owner.prepare_current(conn,business_ref=evidence)
    else:
        original=AipProductionContractStore.build_evidence_bundle
        def build(self,*args,**kwargs):
            result=original(self,*args,**kwargs);advance_clock();return result
        monkeypatch.setattr(AipProductionContractStore,'build_evidence_bundle',build)
        with pytest.raises(ValueError):owner.prepare_current(conn,business_ref=evidence)
        assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revision').fetchone()['n']==0
