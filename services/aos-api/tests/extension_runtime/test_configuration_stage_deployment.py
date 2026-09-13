import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[4]

def load():
    spec=importlib.util.spec_from_file_location('configuration_stage_deploy_test',ROOT/'scripts/a0v_configuration_stage_deploy.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_exact_deployment_chain_and_separate_clone():
    module=load()
    assert module.SOURCE=='a0v_035' and module.TARGET=='a0v_038'
    assert module.CHAIN==['a0v_038','a0v_037','a0v_036']
    assert module.CLONE=='aos_configuration_stage_20260914_test'
    assert module.storage.CLONE==module.CLONE
    assert len(module.FILES)==3 and len(module.FUNCTIONS)==4

def test_missing_or_tampered_proof_cannot_authorize_apply():
    module=load()
    with pytest.raises(ValueError):module.validate_proof({})
