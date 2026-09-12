import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[4] / 'scripts/a0v_ecommerce_never_enabled_retire.py'
SPEC = importlib.util.spec_from_file_location('exact_retirement_targets', PATH)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


@pytest.mark.parametrize('flag,identity,etag,key', [
    (None, '3d267738-ba0a-49ef-812b-d6b72d3374fd', '"7"', 'a0v-ecommerce-1.6-never-enabled-retire-v1'),
    ('reinstall_generation', 'efc4e640-1b15-403f-9d06-4c6d1a5330a7', '"5"', 'a0v-ecommerce-1.6-reinstall-never-enabled-retire-v1'),
    ('configured_1_7', 'e42e042b-1fe7-4cfa-bb83-469ff256081d', '"5"', 'a0v-ecommerce-1.7-configured-disabled-retire-v1'),
    ('enabled_undispatched_1_7', 'af1992e8-89c2-406a-816d-01e61d7bf982', '"5"', 'a0v-ecommerce-1.7-enabled-undispatched-retire-v1'),
    ('second_sleep_1_7', 'a0fd8e25-cb6f-49e5-aa77-7faddae12099', '"5"', 'a0v-ecommerce-1.7-second-sleep-retire-v1'),
])
def test_known_target_and_command_namespaces_are_preserved(flag, identity, etag, key):
    assert M.retirement_target(**({flag: True} if flag else {})) == (identity, etag, key)


def test_ambiguous_or_non_boolean_target_rejected():
    with pytest.raises(ValueError):
        M.retirement_target(configured_1_7=True, second_sleep_1_7=True)
    with pytest.raises(ValueError):
        M.retirement_target(second_sleep_1_7='yes')
