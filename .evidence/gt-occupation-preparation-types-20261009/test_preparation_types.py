import copy, json, hashlib
from pathlib import Path
import pytest
from pydantic import ValidationError
from aos_api.aip_model_runtime_store import canonical_hash
from aos_api import aip_physical_capacity_occupation_contracts as contracts
B=Path(__file__).resolve().parent;R=B.parents[1]

def fixture():
    ref=json.loads((B/'fixture-reference.json').read_text());p=R/ref['path']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==ref['sha256']
    return json.loads(p.read_text())['ledger']

def parse(v):
    return contracts.PhysicalOccupationPreparation.model_validate(v)

def test_real_native_response_roundtrip():
    v=fixture();m=parse(v);assert m.model_dump(mode='json',by_alias=True)==v
    assert m.execution_allowed is False and m.counts_as_inflight is False

@pytest.mark.parametrize('path,value',[
 ('executionAllowed',0),('executionAllowed',True),('countsAsInflight',0),
 ('immutable.countsAsInflight',True),('immutable.executionAllowed',0),
 ('immutable.initialState','admitted'),('initialEvent.state','unknown'),
 ('initialEvent.eventSeq',True),('initialEvent.eventSeq',2),
 ('initialEvent.previousEventHash','sha256:'+'a'*64),
 ('immutable.tokenUpperBound',True),('immutable.tokenUpperBound',0),
 ('immutable.callerPid',True),('immutable.callerXid','0'),
 ('immutable.tenant.orgId','dev-org'),('initialEvent.tenant.projectId','other'),
 ('immutable.callerLogin','aos_app'),('immutable.callId','not-uuid'),
 ('initialEvent.callerPid',99),('initialEvent.callerXid','999999'),
 ('initialEvent.callId','00000000-0000-0000-0000-000000000001'),
 ('callId','00000000-0000-0000-0000-000000000001'),
 ('initialEvent.occupationHash','sha256:'+'a'*64),
 ('immutable.extraPermission',True),('initialEvent.extraPermission',True),
 ('extraPermission',True),('immutable.caseId',''),
])
def test_rejects_resigned_semantic_mutations(path,value):
    v=copy.deepcopy(fixture());p=v
    keys=path.split('.')
    for k in keys[:-1]:p=p[k]
    p[keys[-1]]=value
    v['occupationHash']='sha256:'+canonical_hash(v['immutable'])
    if path!='initialEvent.occupationHash':v['initialEvent']['occupationHash']=v['occupationHash']
    v['eventHash']='sha256:'+canonical_hash(v['initialEvent'])
    with pytest.raises(ValidationError):parse(v)

@pytest.mark.parametrize('field',['occupationHash','eventHash'])
def test_rejects_content_hash_forgery(field):
    v=fixture();v[field]='sha256:'+'0'*64
    with pytest.raises(ValidationError):parse(v)

def test_revalidates_constructed_instance():
    m=parse(fixture());bad=m.model_copy(update={'execution_allowed':True})
    with pytest.raises(ValidationError):parse(bad)
