import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_product_registry_profile_has_exact_predecessor_and_build_without_changing_old_profile():
    new=load('a0v_niushop_1_5_registry_successor').load_successor()
    old=load('a0v_niushop_1_4_registry_successor').load_successor()
    assert new.OLD_ROOT==old.NEW_ROOT
    assert (new.EXPECTED_OLD_COUNT,new.EXPECTED_NEW_COUNT)==(12,13)
    assert new.VERSIONS==dict(old.VERSIONS,**{'platform.ecommerce.niushop':'1.5.0'})
    assert new.legacy()._builder().RUNTIME_CASES[1][2]=='1.5.0'
    assert old.legacy()._builder().RUNTIME_CASES[1][2]=='1.4.0'
    assert new.BUILD==ROOT.parent/'.aos-recovery-20260913/state/niushop-1.5-build-v1'
    assert new.NEW_ROOT==ROOT.parent/'.aos-recovery-20260913/state/niushop-1.5-registry/signed-bundles-niushop-1.5'
    assert new.EXTRA_BUILD_PATHS==('scripts/build_niushop_product_candidates.py',)
