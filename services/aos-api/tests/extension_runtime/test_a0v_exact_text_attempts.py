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


def test_failed_call_preserves_intent_and_never_resends(tmp_path):
    import json
    path = tmp_path/'instruction.json'; identity = {'caseId':'instruction'}
    calls = []
    def fail():
        calls.append(1)
        raise ValueError('secret-value-and-private-response')
    with pytest.raises(ValueError): MODULE.execute_case(path, identity, fail)
    failure = json.loads(path.with_suffix('.failure.json').read_text())
    assert failure['outcomeUnknown'] is True and failure['retryAllowed'] is False
    assert failure['code'] == 'UNCLASSIFIED_FAILURE'
    assert json.loads(path.read_text())['status'] == 'submitted'
    assert 'secret-value' not in ''.join(p.read_text() for p in tmp_path.glob('*.json'))
    with pytest.raises(RuntimeError, match='EVAL_ATTEMPT_UNRESOLVED'):
        MODULE.execute_case(path, identity, fail)
    assert calls == [1]


def test_success_is_reused_without_calling_again(tmp_path):
    path = tmp_path/'instruction.json'; identity = {'caseId':'instruction'}
    calls = []
    class Result:
        def model_dump(self, **kwargs):
            return {'status':'healthy','response_contract_passed':True}
    def invoke(): calls.append(1); return Result()
    result, called = MODULE.execute_case(path, identity, invoke)
    assert called and result['status'] == 'completed'
    assert MODULE.execute_case(path, identity, invoke) == (result, False)
    assert calls == [1]


def test_failure_marker_blocks_even_with_missing_original_intent(tmp_path):
    path=tmp_path/'instruction.json'
    path.with_suffix('.failure.json').write_text('{}')
    calls=[]
    with pytest.raises(RuntimeError, match='EVAL_ATTEMPT_UNRESOLVED'):
        MODULE.execute_case(path, {'caseId':'instruction'}, lambda: calls.append(1))
    assert calls == [] and not path.exists()
