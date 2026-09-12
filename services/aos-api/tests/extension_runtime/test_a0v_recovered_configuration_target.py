"""Recovery must not overwrite the prior installation command namespace."""
import json
from pathlib import Path
import sys
from uuid import uuid4
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
import a0v_ecommerce_1_7_configure as executor


def test_original_target_is_unchanged():
    installation,state,key,command=executor.configuration_target()
    assert installation==executor.INSTALLATION and state==executor.STATE
    assert key=='a0v-ecommerce-1.7' and command=='ecommerce-1.7'


@pytest.mark.parametrize('case',['fresh','old','invalid'])
def test_recovery_requires_distinct_valid_installation_and_state(tmp_path,monkeypatch,case):
    monkeypatch.setattr(executor,'RECOVERY',tmp_path)
    state=tmp_path/'state';state.mkdir()
    identity=str(uuid4()) if case=='fresh' else executor.INSTALLATION if case=='old' else 'invalid'
    (state/'ecommerce-1.7-recovered-first-install.json').write_text(json.dumps({'installationId':identity}))
    if case!='fresh':
        with pytest.raises(ValueError):executor.configuration_target(True)
    else:
        installation,path,key,command=executor.configuration_target(True)
        assert installation==identity and path.name=='ecommerce-1.7-recovered-configuration.json'
        assert key=='a0v-ecommerce-1.7-recovered' and command=='ecommerce-1.7-recovered'
