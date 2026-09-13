import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
import a0v_qyh_registration_cycle as cycle


class Owner:
    def __init__(self):self.writes=0;self.reads=[]
    def register(self,**kwargs):
        self.writes+=1
        raise RuntimeError('unknown outcome')
    def read_receipt(self,**kwargs):
        self.reads.append(kwargs)
        return {'receiptId':'saved'}


def request():
    return {'schemaVersion':'aos.ecommerce.first-dispatch-registration/v1',
        'installationRef':{'installationId':cycle.INSTALLATION,'revision':5,
            'lockHash':'sha256:'+'a'*64,'overlayRevision':'test'},
        'generation':cycle.GENERATION,'bindingRevision':4,'executionEpoch':3,
        'configRef':{'configurationId':'721433ba-5256-4b12-9043-0bcfab658bf0','revision':1,'hash':'sha256:'+'b'*64},
        'groupId':'1c5040b8-c4c2-4b0b-8c46-8b3e5f6b5f15','idempotencyKey':cycle.KEY}


def test_unknown_registration_never_resends_and_read_uses_original_key(tmp_path):
    cycle.freeze(tmp_path/'request.json',request())
    owner=Owner()
    with pytest.raises(RuntimeError,match='unknown'):cycle.execute('register',owner,tmp_path)
    with pytest.raises(FileExistsError):cycle.execute('register',owner,tmp_path)
    assert owner.writes==1
    assert cycle.execute('read',owner,tmp_path)=={'receiptId':'saved'}
    assert owner.reads[0]['idempotency_key']==cycle.KEY
    assert owner.reads[0]['actor']==cycle.ACTOR


def test_wrong_installation_rejected_before_submission(tmp_path):
    value=request();value['installationRef']['installationId']='ec0bff31-0110-4dfb-91f5-154f799a0ea8'
    cycle.freeze(tmp_path/'request.json',value)
    owner=Owner()
    with pytest.raises(ValueError):cycle.execute('register',owner,tmp_path)
    assert owner.writes==0


def test_freeze_cannot_overwrite_and_is_private(tmp_path):
    p=tmp_path/'test.json';cycle.freeze(p,{'a':1})
    assert p.stat().st_mode&0o777==0o600
    with pytest.raises(FileExistsError):cycle.freeze(p,{'a':2})
    assert json.loads(p.read_text())=={'a':1}


class WithdrawalOwner(Owner):
    def __init__(self,drift=False):super().__init__();self.drift=drift
    def registration_status(self,**kwargs):
        return dict(state='registered',allowedActions=['withdraw'],expectedInstallationEtag=5,
            registrationReceiptRef=dict(resourceType='FirstDispatchRegistrationReceipt',revision=1,
                resourceId=('721433ba-5256-4b12-9043-0bcfab658bf0' if self.drift else '1c5040b8-c4c2-4b0b-8c46-8b3e5f6b5f15'),contentHash='sha256:'+'c'*64))
    def read_receipt(self,**kwargs):
        value=cycle.FirstDispatchRegistrationRequest.model_validate(request())
        return dict(receiptId='1c5040b8-c4c2-4b0b-8c46-8b3e5f6b5f15',contentHash='sha256:'+'c'*64,
                    groupId=value.groupId,requestHash=value.request_hash())
    def withdraw(self,**kwargs):self.writes+=1;raise RuntimeError('unknown withdrawal')


def test_withdrawal_cannot_target_another_unused_registration(tmp_path):
    cycle.freeze(tmp_path/'request.json',request());owner=WithdrawalOwner(drift=True)
    with pytest.raises(ValueError,match='ORIGIN'):cycle.execute('withdraw',owner,tmp_path)
    assert owner.writes==0


def test_unknown_withdrawal_never_resends(tmp_path):
    cycle.freeze(tmp_path/'request.json',request());owner=WithdrawalOwner()
    with pytest.raises(RuntimeError,match='unknown withdrawal'):cycle.execute('withdraw',owner,tmp_path)
    with pytest.raises(FileExistsError):cycle.execute('withdraw',owner,tmp_path)
    assert owner.writes==1


def test_operating_profile_is_independent_and_requires_exact_predecessor():
    from a0v_qyh_operating_registration import load_profile
    other=load_profile()
    assert other.KEY!=cycle.KEY and other.STATE!=cycle.STATE
    assert other.PREDECESSOR_WITHDRAWAL_KEY==cycle.KEY+'-withdraw'
    class Prior:
        def read_withdrawal_receipt(self,**kwargs):
            assert kwargs['idempotency_key']==cycle.KEY+'-withdraw'
            return {'receiptId':'prior'}
    with pytest.raises(ValueError):other.require_predecessor(Prior(),{'state':'unregistered'})
    with pytest.raises(ValueError):other.require_predecessor(Prior(),{'state':'withdrawn','withdrawalReceiptId':'wrong'})
    other.require_predecessor(Prior(),{'state':'withdrawn','withdrawalReceiptId':'prior'})
    cycle.require_predecessor(Prior(),{'state':'unregistered'})
    with pytest.raises(ValueError):cycle.require_predecessor(Prior(),{'state':'withdrawn','withdrawalReceiptId':'prior'})


def test_profile_default_state_is_not_bound_to_acceptance_directory(monkeypatch):
    from a0v_qyh_operating_registration import load_profile
    other=load_profile()
    monkeypatch.setattr(other,'prepare',lambda owner,state:state)
    assert other.execute('prepare',object())==other.STATE
