"""Whole stored description drift never silently inherits an original hash."""
from pathlib import Path
import copy,json
import pytest
from aos_api.aip_physical_capacity_occupation_contracts import SharedParentRiskDescriptionPreparation as Description
from aos_api.aip_model_runtime_store import canonical_hash


def valid():
    p=json.loads(Path(__file__).with_name('shared-parent-risk-binding-native-1670-r2').joinpath('native-risk-binding-proof.json').read_text())
    m=p['manifest']; body=dict(schemaVersion='aos.shared-parent-risk-description-preparation/v1',
        planId=m['executionId'],tenant=m['tenant'],originalRiskHash=p['plan']['contentHash'],manifest=m,
        manifestHash=canonical_hash(m),callerLogin='aos_provider_capacity_occupation',callerXid=p['xid'],
        callerPid=p['plan']['immutable']['callerPid'],state='prepared_description_only',
        executorsAuthenticated=False,executionAllowed=False)
    return dict(planId=m['executionId'],immutable=body,contentHash='sha256:'+canonical_hash(body),executionAllowed=False)


def test_complete_description_is_not_authenticated():
    obj=Description.model_validate(valid())
    assert not obj.immutable.executors_authenticated and not obj.execution_allowed
    assert len(obj.immutable.manifest.cases)==2


@pytest.mark.parametrize('field',['identityId','intentRef','jointReceiptRef'])
def test_stale_hash_cannot_cover_changed_obligations(field):
    q=valid();leg=q['immutable']['manifest']['cases'][0]['target']
    if field=='identityId':leg[field]+='-different'
    else:leg[field]['resourceId']+='-different'
    with pytest.raises(ValueError):Description.model_validate(q)


@pytest.mark.parametrize('where,field,value',[
    ('outer','executionAllowed',True),('outer','executionAllowed',0),
    ('inner','executorsAuthenticated',True),('inner','executorsAuthenticated',0),
    ('inner','callerXid','0'),('inner','callerPid',True),
    ('inner','originalRiskHash','sha256:'+'a'*64),
])
def test_grant_origin_and_native_body_drift_rejected(where,field,value):
    q=valid();(q if where=='outer' else q['immutable'])[field]=value
    with pytest.raises(ValueError):Description.model_validate(q)


def test_invented_leg_money_rejected_even_with_fresh_outer_hash():
    q=valid();q['immutable']['manifest']['cases'][0]['target']['allocationUpperBoundMinor']=1
    q['immutable']['manifestHash']=canonical_hash(q['immutable']['manifest'])
    q['contentHash']='sha256:'+canonical_hash(q['immutable'])
    with pytest.raises(ValueError):Description.model_validate(q)
