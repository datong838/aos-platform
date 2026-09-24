from types import SimpleNamespace

import pytest

import a0v_w5c3b_successor_lifecycle as wave


def test_prepare_intent_never_resends(monkeypatch, tmp_path):
    monkeypatch.setattr(wave, "STATE", tmp_path)
    (tmp_path / "prepare-intent.json").write_text("{}")
    monkeypatch.setattr(wave, "preflight_prepare", lambda: pytest.fail("must not resend"))
    with pytest.raises(ValueError, match="INTENT_EXISTS"):
        wave.request_prepare()


def test_prepare_uses_original_owner_once_with_exact_etag_and_key(monkeypatch, tmp_path):
    monkeypatch.setattr(wave, "STATE", tmp_path / "new")
    installation = "ae42f0e5-270a-4b7b-8a82-fd3bfbb925dc"
    monkeypatch.setattr(wave, "preflight_prepare", lambda: {
        "installationId": installation, "hostPid": 123, "etag": 3,
    })
    calls = []

    class Lifecycle:
        def request_preparation(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(response_json={"operationId": "exact"}, replayed=False)

    activation = SimpleNamespace(ACTOR="actor", ROLES=["admin"], MARKINGS=[])
    current = SimpleNamespace(_setup_runtime_plane=lambda: (
        activation, None, Lifecycle(), None, None))
    monkeypatch.setattr(wave.ds, "_current", lambda: current)
    result = wave.request_prepare()
    assert result["replayed"] is False and len(calls) == 1
    assert calls[0]["installation_id"] == installation
    assert calls[0]["kind"] == "runtime-apply"
    assert calls[0]["idempotency_key"] == wave.KEYS["prepare"]
    assert calls[0]["if_match"] == '"3"'
    assert (tmp_path / "new/prepare-intent.json").stat().st_mode & 0o777 == 0o600


def test_verify_rejects_replaced_host_even_if_apply_succeeded(monkeypatch):
    installation = "ae42f0e5-270a-4b7b-8a82-fd3bfbb925dc"
    monkeypatch.setattr(wave, "observe_prepare", lambda: {
        "operation": {"kind": "runtime-apply", "status": "succeeded"}})
    monkeypatch.setattr(wave, "_facts", lambda: {
        "installationId": installation,
        "new": {"head": {"state": "applied", "etag_version": 4},
                "bindings": [], "resources": [
                    {"cleanup_state": "held", "observed_release": False}] * 3},
        "host": {"pid": 456, "liveTargets": [{
            "installationId": installation, "tenant": ["org-org", "dev-project"],
            "generation": "generation"}]},
    })
    monkeypatch.setattr(wave, "_load", lambda _: {"hostPid": 123})
    with pytest.raises(ValueError, match="OWNER_LOST"):
        wave.preflight_verify()
