from types import SimpleNamespace
import subprocess
import pytest
import offline_registry as module


@pytest.mark.parametrize('failure',['nonzero','timeout'])
def test_all_cleanup_targets_verified_despite_removal_failure(monkeypatch,failure):
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        if 'inspect' in command:
            # Container and first image gone, helper still present.
            return SimpleNamespace(returncode=0 if command[-1]=='helper' else 1,stderr='No such object')
        if failure=='timeout':raise subprocess.TimeoutExpired(command,1)
        return SimpleNamespace(returncode=1,stderr='remove failed')
    monkeypatch.setattr(module.subprocess,'run',run)
    with pytest.raises(RuntimeError,match='helper'):
        module.cleanup(['docker'],'container','image-ref','helper')
    assert len(calls)==6


def test_missing_targets_are_confirmed_after_uncertain_removal(monkeypatch):
    def run(command,**kwargs):
        if 'inspect' not in command:raise subprocess.TimeoutExpired(command,1)
        return SimpleNamespace(returncode=1,stderr='Error: No such object')
    monkeypatch.setattr(module.subprocess,'run',run)
    module.cleanup(['docker'],'container','image-ref','helper')
