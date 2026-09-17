"""Fixed S retirement executor remains fail-closed and intent-safe."""
import importlib.util
from pathlib import Path
import pytest


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_s_released_retirement.py'
SPEC=importlib.util.spec_from_file_location('a0v_s_released_retirement',PATH)
retirement=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(retirement)


def test_fixed_released_s_authority_and_actions():
    assert retirement.S_ID=='77b8e5c2-db96-4d55-a808-1b62e00163d2'
    assert retirement.GENERATION=='e621100a-baea-440f-9075-ae8a5290845a'
    assert retirement.ACTIONS==('preflight','request-disable','process-disable','audit')
    assert retirement.OCCURRENCES==(
        '3c927751-b91a-53d0-8a42-7c5223ea109d',
        '34733f17-f1ce-582d-b1b6-585a96aee2ff')


def test_run_rejects_unknown_action_without_calling_runtime():
    with pytest.raises(ValueError,match='unsupported S retirement action'):
        retirement.run('resend')


def test_immutable_intent_never_overwrites(tmp_path):
    path=tmp_path/'intent.json'
    retirement.freeze_or_match(path,{'operation':'original'})
    original=path.read_bytes()
    retirement.freeze_or_match(path,{'operation':'original'})
    with pytest.raises(ValueError,match='immutable intent differs'):
        retirement.freeze_or_match(path,{'operation':'replacement'})
    assert path.read_bytes()==original and path.stat().st_mode&0o777==0o600


def test_plan_requires_definition_nine_and_closed_occurrences():
    source=PATH.read_text(encoding='utf-8')
    assert 'dict(definition) != {"revision": 9, "state": "disabled"}' in source
    assert '"attempt_status": "closed_unaccepted"' in source
    assert 'enabled_event_bindings' in source
    assert 'EcommerceGrowthDisableDependent' in source
    assert '"claimedByHost": True, "resendDisable": False' in source


def test_process_recovers_host_completed_disable_without_runtime_claim(monkeypatch,tmp_path):
    monkeypatch.setattr(retirement,'STATE',tmp_path)
    retirement.freeze(tmp_path/'request-disable-result.json',{'operationId':'op-1'})
    completed={'phase':'detached'}
    monkeypatch.setattr(retirement,'snapshot',lambda phase,operation: completed if phase=='detached' else None)
    monkeypatch.setattr(retirement,'setup',lambda: pytest.fail('must not rebuild runtime'))
    result=retirement.process_disable()
    assert result['claimedByHost'] is True and result['resendDisable'] is False
    assert result['state']==completed
