import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_product_profile_keeps_old_profiles_independent_and_validates_actual_candidate():
    new=load('build_niushop_product_candidates').load_builder()
    old=load('build_niushop_snapshot_candidates').load_builder()
    original=load('build_ecommerce_runtime_candidates')
    assert [new.RUNTIME_CASES[1][2],old.RUNTIME_CASES[1][2],original.RUNTIME_CASES[1][2]]==['1.5.0','1.4.0','1.3.0']
    assert new.RUNTIME_CASES[0]==original.RUNTIME_CASES[0]
    assert new.RUNTIME_CASES[2]==original.RUNTIME_CASES[2]
    assert new.ALL_CASES[3:]==original.ALL_CASES[3:]
    result=new.preflight()
    assert (result['bundleCount'],result['runtimeMemberCount'],result['moduleCount'],result['operationCount'])==(4,3,8,12)
