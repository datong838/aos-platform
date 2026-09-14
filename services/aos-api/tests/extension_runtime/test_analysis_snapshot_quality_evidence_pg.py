"""Current quality over actual group/Query/Evidence; named original pending fixture."""
from datetime import datetime,timedelta
import pytest
from test_analysis_snapshot_fact_query_pg import (
    database,pytestmark,ledger,owner_case,claim_case,executor_case,group_claim_case,prepared_case,
    assessment_case,journal_case,object_case,completed_group,bridge_case,business_case,fact_case,evidence_case,query_case,revoke,
)
from aos_api.ecommerce_analysis_snapshot_quality_evidence import AnalysisSnapshotQualityEvidence
from aos_api.data_requirement_store import canonical_revision_content_hash
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from tests.test_data_requirement_store import requirement


@pytest.fixture
def quality_case(query_case,monkeypatch):
    conn,state,source,query,call,pending=query_case
    raw=requirement().model_dump(mode='json',by_alias=True)
    raw.update(pending['requirement'])
    raw.update(grain='store',minPopulation=1,qualityThreshold=1,acceptableDegradation=[],
        freshnessMaxAgeSeconds=3600,createdAt=datetime.now().astimezone().isoformat())
    parsed=DataRequirementRevisionRecord.model_validate(raw)
    raw['contentHash']=canonical_revision_content_hash(parsed)
    pending['requirement']=raw
    import aos_api.ecommerce_analysis_snapshot_quality_evidence as module
    import aos_api.ecommerce_analysis_snapshot_fact_query as query_module
    monkeypatch.setattr(module,'HostTransaction',query_module.HostTransaction)
    return conn,state,source,query,AnalysisSnapshotQualityEvidence(source),call,pending


def prepare(case):
    conn,_,source,query,quality,call,_=case
    evidence=source.capture_current(conn,**call)
    result=query.execute_current(conn,evidence_ref=evidence)
    return evidence,result,quality.put_current(conn,evidence_ref=evidence,query_ref=result)


def test_current_quality_replay_and_exact_population_freshness(quality_case):
    conn,state,source,query,quality,call,_=quality_case
    evidence,result,ref=prepare(quality_case)
    assert quality.put_current(conn,evidence_ref=evidence,query_ref=result)==ref
    current=quality.read_current(conn,quality_ref=ref,evidence_ref=evidence,query_ref=result)
    assert current.value.measurement.distinct_population_count==1
    body=source.run_current(conn,evidence_ref=evidence,execute=lambda body:body)
    assert current.value.measurement.source_observed_at==datetime.fromisoformat(body['projection']['readStartedAt'])
    assert len(current.value.measurement.facts)==2 and current.value.run_id is None
    assert state['calls']==1
    assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='data-requirement-quality'").fetchone()['n']==1


@pytest.mark.parametrize('target',['source','quality'])
def test_revocation_invalidates_quality_current_read(quality_case,target):
    conn,_,source,_,quality,_,_=quality_case
    evidence,result,ref=prepare(quality_case)
    revoke(conn,source,evidence if target=='source' else ref)
    with pytest.raises(ValueError):quality.read_current(conn,quality_ref=ref,evidence_ref=evidence,query_ref=result)


def test_wrong_grain_is_not_reinterpreted_as_shop_population(quality_case):
    conn,_,source,query,quality,call,pending=quality_case
    pending['requirement']['grain']='day'
    parsed=DataRequirementRevisionRecord.model_validate(pending['requirement'])
    pending['requirement']['contentHash']=canonical_revision_content_hash(parsed)
    evidence=source.capture_current(conn,**call);result=query.execute_current(conn,evidence_ref=evidence)
    with pytest.raises(ValueError):quality.put_current(conn,evidence_ref=evidence,query_ref=result)


def test_quality_write_rolls_back_if_policy_changes(quality_case,monkeypatch):
    from aos_api.data_requirement_quality_evidence import QualityEvidenceStore
    conn,state,source,query,quality,call,_=quality_case
    evidence=source.capture_current(conn,**call);result=query.execute_current(conn,evidence_ref=evidence)
    original=QualityEvidenceStore.put
    def put(self,value):
        ref=original(self,value);state['field_raw']=b'{}';return ref
    monkeypatch.setattr(QualityEvidenceStore,'put',put)
    with pytest.raises(ValueError):quality.put_current(conn,evidence_ref=evidence,query_ref=result)
    assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='data-requirement-quality'").fetchone()['n']==0


def test_low_field_quality_is_persisted_as_failure_not_upgraded(quality_case):
    import json
    conn,state,source,query,quality,call,_=quality_case
    document=json.loads(state['field_raw'])
    # Named installed policy fixture adds a genuinely missing public field.
    for fact in document['facts']:
        if fact['objectType']=='Weapp':fact['fields'].append(dict(property='missingPublicField',kind='nonblank-string'))
    # Policy ref must be new and match bytes; this is not mutation of persisted Evidence.
    import hashlib
    state['field_raw']=json.dumps(document).encode()
    call['field_ref']=call['field_ref'].model_copy(update={'content_hash':'sha256:'+hashlib.sha256(state['field_raw']).hexdigest()})
    evidence,result,ref=prepare(quality_case)
    current=quality.read_current(conn,quality_ref=ref,evidence_ref=evidence,query_ref=result)
    assert not current.assessment.satisfied
    assert 'QUALITY_BELOW_THRESHOLD:Weapp' in current.assessment.reasons


def test_quality_revoked_during_write_rolls_back(quality_case,monkeypatch):
    from aos_api.data_requirement_quality_evidence import QualityEvidenceStore
    conn,_,source,query,quality,call,_=quality_case
    evidence=source.capture_current(conn,**call);result=query.execute_current(conn,evidence_ref=evidence)
    original=QualityEvidenceStore.put
    def put(self,value):
        ref=original(self,value);revoke(conn,source,ref);return ref
    monkeypatch.setattr(QualityEvidenceStore,'put',put)
    with pytest.raises(ValueError):quality.put_current(conn,evidence_ref=evidence,query_ref=result)
    assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_type='data-requirement-quality'").fetchone()['n']==0
