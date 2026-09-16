"""Acknowledgement loss must not become a repeated approval request."""
import pytest
from a0v_snapshot_current_controls import confirm_once


def test_lost_ack_is_confirmed_from_original_ledger_and_not_repeated(tmp_path):
    state={'record':None,'calls':0}
    def submit():
        state.update(record={'ref':'exact'},calls=state['calls']+1)
        raise TimeoutError('lost acknowledgement')
    def read():return state['record']
    p=tmp_path/'intent.json';request={'draft':'exact'}
    assert confirm_once(p,request,submit=submit,read=read)=={'ref':'exact'}
    assert confirm_once(p,request,submit=submit,read=read)=={'ref':'exact'}
    assert state['calls']==1


def test_unknown_intent_never_reissues(tmp_path):
    calls=[];p=tmp_path/'intent.json'
    for _ in range(2):
        with pytest.raises(ValueError,match='unconfirmed'):
            confirm_once(p,{'draft':'exact'},submit=lambda:calls.append(1),read=lambda:None)
    assert calls==[1]


def test_changed_intent_or_corrupt_readback_does_not_submit(tmp_path):
    p=tmp_path/'intent.json'
    confirm_once(p,{'draft':'first'},submit=lambda:None,read=lambda:{'ref':'saved'})
    with pytest.raises(ValueError):
        confirm_once(p,{'draft':'changed'},submit=lambda:pytest.fail('changed intent submitted'),read=lambda:{'ref':'saved'})
    def corrupt():raise ValueError('receipt integrity differs')
    with pytest.raises(ValueError,match='integrity'):
        confirm_once(tmp_path/'new.json',{'draft':'first'},submit=lambda:pytest.fail('bad receipt submitted'),read=corrupt)
