import importlib

import pytest


def snapshot(module,*,settled=False):
    revision,epoch,desired=(9,5,'disabled') if settled else (7,4,'enabled')
    return {'head':{'installation_id':module.N_ID,'etag_version':5,'state':'active',
      'lock_hash':module.LOCK},'bindings':[{'generation':module.N_GENERATION,
      'revision':revision,'execution_epoch':epoch,'enabled':False,'operation_fence':True,
      'desired_state':desired,'observed_state':'unknown'}],
      'resources':[{'cleanup_state':'released','observed_release':True} for _ in range(3)],
      'operations':[{'status':'succeeded'}],'canaryInstallations':0}


def test_o_recovery_accepts_only_exact_released_n():
    module=importlib.import_module('a0v_o_recovery')
    value=snapshot(module)
    assert module.require_n(value) is value
    value['bindings'][0]['operation_fence']=False
    with pytest.raises(ValueError,match='exact released N'):
        module.require_n(value)


def test_o_recovery_distinguishes_settled_n():
    module=importlib.import_module('a0v_o_recovery')
    value=snapshot(module,settled=True)
    assert module.require_n(value,settled=True) is value
    with pytest.raises(ValueError,match='exact released N'):
        module.require_n(value)


def test_o_recovery_action_surface_is_fixed():
    module=importlib.import_module('a0v_o_recovery')
    assert module.ACTIONS[-8:]==(
      'reset-o','create-p','uninstall-o','prepare-p','verify-p','stage-p','configure-p','enable-p')
    with pytest.raises(ValueError,match='unsupported'):
        module.run('repair-n')


def test_o_recovery_profile_loads_canonical_o(tmp_path,monkeypatch):
    module=importlib.import_module('a0v_o_recovery')
    identity='11111111-1111-4111-8111-111111111111'
    monkeypatch.setattr(module,'O_DIR',tmp_path)
    (tmp_path/'create-result.json').write_text('{"installationId":"'+identity+'"}')
    profile=module.current()
    assert profile._initial('o')['installationId']==identity
    with pytest.raises(ValueError,match='only fixed N/O/P'):
        profile._initial('q')
