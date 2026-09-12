import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[4] / 'scripts/a0v_exact_text_live_eval.py'
SPEC = importlib.util.spec_from_file_location('exact_text_attempts', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_new_batch_preserves_completed_and_unknown_attempts(tmp_path):
    identity = {'caseId': 'instruction'}
    old = tmp_path / 'old/instruction.json'
    new = tmp_path / 'new/instruction.json'
    assert MODULE.claim(old, identity) is None
    with pytest.raises(RuntimeError, match='EVAL_ATTEMPT_UNRESOLVED'):
        MODULE.claim(old, identity)
    MODULE.complete(old, {'identity': identity, 'status': 'completed', 'result': {}})
    before = old.read_bytes()
    assert MODULE.claim(new, identity) is None
    assert MODULE.claim(old, identity)['status'] == 'completed'
    assert old.read_bytes() == before


@pytest.mark.parametrize('status,passed', [('healthy', False), ('unhealthy', True), ('timeout', False)])
def test_completed_failure_is_not_acceptance(status, passed):
    with pytest.raises(RuntimeError, match='EVAL_CASE_NOT_PASSED'):
        MODULE.require_passed({'status': 'completed', 'result': {
            'status': status, 'response_contract_passed': passed}})


def test_exact_success_accepted():
    MODULE.require_passed({'status': 'completed', 'result': {
        'status': 'healthy', 'response_contract_passed': True}})
