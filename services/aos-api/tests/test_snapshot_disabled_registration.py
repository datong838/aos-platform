import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]


def module():
    spec = importlib.util.spec_from_file_location('disabled_registration', ROOT/'scripts/a0v_snapshot_disabled_registration.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_intent_precedes_single_write_and_ack_loss_reads_back(tmp_path):
    m=module(); state={}; calls=[]; body={'id':'s','enabled':False}
    def api(method,path,request):
        assert (tmp_path/'s.json').exists()
        calls.append(request); state.update(request)
        raise OSError('ack lost')
    args=(tmp_path/'s.json','POST','/v1/schedules',body)
    result=m.register_once(*args,api=api,read=lambda:state or None)
    assert result['confirmed'] and len(calls)==1
    assert m.register_once(*args,api=api,read=lambda:state or None)['confirmed']
    assert len(calls)==1


def test_unknown_empty_read_never_resends(tmp_path):
    m=module();calls=[]
    def api(*args): calls.append(1);raise OSError('timeout')
    args=(tmp_path/'s.json','POST','/v1/schedules',{'id':'s','enabled':False})
    for _ in range(2):
        with pytest.raises(ValueError,match='unconfirmed'):
            m.register_once(*args,api=api,read=lambda:None)
    assert len(calls)==1


def test_existing_conflict_never_writes(tmp_path):
    with pytest.raises(ValueError,match='differs'):
        module().register_once(tmp_path/'s.json','POST','/v1/schedules',{'enabled':False},
            api=lambda *args:pytest.fail('write'),read=lambda:{'enabled':True})


def test_subset_is_strict_for_boolean_and_full_list():
    m=module()
    assert not m.matches({'enabled':False},{'enabled':0})
    assert not m.matches({'nodes':[{'id':'a'}]},{'nodes':[{'id':'a'},{'id':'b'}]})
    assert m.matches({'nodes':[{'id':'a'}]},{'nodes':[{'id':'a','server':'extra'}]})
