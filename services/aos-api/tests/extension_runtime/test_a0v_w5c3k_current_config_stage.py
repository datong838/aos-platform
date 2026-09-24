"""The first staged configuration must remain on the exact live fenced target."""

from types import SimpleNamespace

import pytest

import a0v_w5c3k_current_config_stage as wave


def test_json_roundtrip_recovers_strict_ref_tuples():
    from aos_api.extension_runtime.configuration_contracts import (
        ConfigurationDocument, ConfigurationSourceRef)

    ref = ConfigurationSourceRef(authority="aip.responsibility_plan_revision",
        id="plan", revision=1, hash="sha256:" + "a" * 64)
    data = ConfigurationSourceRef(authority="aip.data_classification_policy_revision",
        id="data", revision=1, hash="sha256:" + "b" * 64)
    budget = ConfigurationSourceRef(authority="aip.budget_revision",
        id="budget", revision=1, hash="sha256:" + "c" * 64)
    policy = ConfigurationSourceRef(authority="aip.runtime_policy_revision",
        id="policy", revision=13, hash="sha256:" + "d" * 64)
    document = ConfigurationDocument(roleRefs=(ref,), dataRefs=(data,),
        budgetRef=budget, policyRef=policy)
    import json
    frozen = document.model_dump(mode="json")
    assert isinstance(frozen["roleRefs"], list)
    with pytest.raises(ValueError):
        ConfigurationDocument.model_validate(frozen)
    recovered = ConfigurationDocument.model_validate_json(json.dumps(frozen))
    assert recovered == document
    assert isinstance(recovered.roleRefs, tuple)


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
