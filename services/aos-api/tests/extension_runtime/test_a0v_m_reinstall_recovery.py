import importlib

import pytest


@pytest.mark.parametrize('action',[
    'disable-policy9','approve-event-fence','event-fence',
    'approve-event-shrink','event-shrink'])
def test_released_event_unknown_outcome_never_resends(monkeypatch,tmp_path,action):
    module=importlib.import_module('a0v_m_reinstall_recovery')
    monkeypatch.setattr(module,'STATE',tmp_path)
    (tmp_path/(action+'-intent.json')).write_text('{}')
    monkeypatch.setattr(module,'profile',lambda:pytest.fail('unknown outcome resent'))
    with pytest.raises(ValueError,match='read-only inspection'):
        module.run(action)


def test_m_recovery_identity_and_order_are_fixed():
    module=importlib.import_module('a0v_m_reinstall_recovery')
    assert module.L_ID=='19620ea4-4a36-4cf1-a14a-8b24ee7d9fc3'
    assert module.L_GENERATION=='64742c68-5e71-485b-a3c8-edc20be3d101'
    assert module.ACTIONS.index('disable-policy9')<module.ACTIONS.index('event-fence')
    assert module.ACTIONS.index('event-shrink')<module.ACTIONS.index('settle-l')
    assert module.ACTIONS.index('uninstall-l')<module.ACTIONS.index('prepare-m')
    assert module.ACTIONS.index('verify-m')<module.ACTIONS.index('reset-m')
    assert module.ACTIONS.index('reset-m')<module.ACTIONS.index('create-n')
    assert module.ACTIONS.index('create-n')<module.ACTIONS.index('uninstall-m')
    assert module.ACTIONS.index('uninstall-m')<module.ACTIONS.index('prepare-n')


def _interrupted_m(*, expired):
    return {
        'head':{'state':'applied','etag_version':4,'lock_hash':'lock'},
        'bindings':[],
        'operations':[
            {'operation_id':'apply','kind':'runtime-apply','status':'succeeded',
             'phase':'succeeded','deadline_expired':False},
            {'operation_id':'verify','kind':'runtime-verify','status':'accepted',
             'phase':'accepted','deadline_expired':expired},
        ],
        'resources':[{'cleanup_state':'released','observed_release':True} for _ in range(3)],
        'canaryInstallations':0,
    }


def test_m_reset_requires_expired_verify_and_released_resources():
    module=importlib.import_module('a0v_m_reinstall_recovery')
    class Current:
        def _initial(self,label):
            assert label=='m'
            return {'installationId':'m-id','lockHash':'lock'}
        def observe_installation(self,installation_id):
            assert installation_id=='m-id'
            return _interrupted_m(expired=True)
    assert module.require_interrupted_m(Current(),reset=True)['head']['state']=='applied'

    current=Current()
    current.observe_installation=lambda _installation_id:_interrupted_m(expired=False)
    with pytest.raises(ValueError,match='exact resettable'):
        module.require_interrupted_m(current,reset=True)

    current.observe_installation=lambda _installation_id:{
        **_interrupted_m(expired=True),'resources':[
            {'cleanup_state':'held','observed_release':False} for _ in range(3)]}
    with pytest.raises(ValueError,match='exact resettable'):
        module.require_interrupted_m(current,reset=True)
