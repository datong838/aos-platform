from types import SimpleNamespace
import importlib
import pytest
from test_bootstrap_successor_business import profile

@pytest.fixture
def cutover(profile):
    f,s,p=profile
    c=importlib.import_module('a0v_bootstrap_successor_cutover')
    request=f.request_from(s,p)
    return c,dict(outcome='CURRENT_H_SUCCESSOR_REGISTERED',request=request.model_dump(mode='json',by_alias=True),
        receipt=dict(receiptId=c.RECEIPT,contentHash=c.RECEIPT_HASH,requestHash=request.request_hash()))


def test_new_target_is_exact_successor_not_original_first_registration(cutover):
    c,registered=cutover;t,p=c.target(registered)
    assert t['expectedGroupRevision']==22 and t['targetRuntimeRevision']==4
    assert t['registrationReceiptRef']['resourceType']=='SuccessorDispatchRegistrationReceipt'
    assert t['targetInstallationId']==c.f.G_ID and t['targetGeneration']==c.f.G_GENERATION
    assert len(t['operationIds'])==9
    assert not p['externalEffectsAllowed'] and not p['fallbackAllowed']
    assert c.OPERATION!='b5555da7-6d0e-52f8-a443-d39b8264f40c'


@pytest.mark.parametrize('field',['receiptId','contentHash','requestHash'])
def test_registered_receipt_drift_rejected(cutover,field):
    c,registered=cutover;registered['receipt'][field]='changed'
    with pytest.raises(ValueError,match='exact I'):c.target(registered)


@pytest.mark.parametrize('phase',['approve','prepare','pause','commit','validate','resume'])
def test_existing_phase_intent_never_invokes_service(cutover,monkeypatch,tmp_path,phase):
    c,_=cutover;monkeypatch.setattr(c,'STATE',tmp_path)
    (tmp_path/(phase+'-intent.json')).write_text('{}')
    with pytest.raises(ValueError,match='never resend'):
        c.invoke(phase,SimpleNamespace(ecommerce_growth_cutover_service=object()))
