"""The first staged configuration must remain on the exact live fenced target."""

from types import SimpleNamespace

import pytest

import a0v_w5c3k_current_config_stage as wave


def test_preflight_rejects_stage_key_or_existing_config(monkeypatch):
    monkeypatch.setattr(wave.verified, "audit", lambda: {
        "installationId": wave.INSTALLATION, "generation": wave.GENERATION,
        "bindingRevision": 1, "executionEpoch": 1, "hostPid": 7})
    monkeypatch.setattr(wave.configuration, "_configure", lambda: None)
    monkeypatch.setattr(wave.configuration, "_document", lambda: SimpleNamespace(
        policyRef=SimpleNamespace(revision=13), roleRefs=(1,), dataRefs=(1,),
        model_dump=lambda **kwargs: {"policyRef": {"revision": 13}}))
    for counts in ({"configurations": 1, "stageCommands": 0, "attempts": 0},
                   {"configurations": 0, "stageCommands": 1, "attempts": 0},
                   {"configurations": 0, "stageCommands": 0, "attempts": 1}):
        monkeypatch.setattr(wave, "_counts", lambda counts=counts: {
            **counts, "businessCounts": {"claims": 40, "runs": 53}})
        with pytest.raises(ValueError, match="STAGE_ALREADY_USED"):
            wave.preflight()
