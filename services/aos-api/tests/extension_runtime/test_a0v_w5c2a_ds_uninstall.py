from types import SimpleNamespace

import pytest

import a0v_w5c2a_ds_uninstall as wave


def test_existing_uninstall_intent_never_replays(monkeypatch, tmp_path):
    monkeypatch.setattr(wave, "STATE", tmp_path)
    monkeypatch.setattr(wave, "preflight", lambda: pytest.fail("must not resend"))
    with pytest.raises(ValueError, match="EXISTING_INTENT"):
        wave.uninstall()


def test_formal_uninstall_uses_exact_original_owner_and_new_key(monkeypatch, tmp_path):
    monkeypatch.setattr(wave, "STATE", tmp_path / "new")
    successor_id = "ae42f0e5-270a-4b7b-8a82-fd3bfbb925dc"
    monkeypatch.setattr(wave, "preflight", lambda: {"successorInstallationId": successor_id})
    calls = []

    class Service:
        def uninstall(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(response_json={"state": "uninstalled"}, replayed=False)

    current = SimpleNamespace(TRUST_STATE=tmp_path, _installation_connection=object(),
                              _load=lambda _: SimpleNamespace(
                                  _build=lambda *args: (object(), Service())))
    monkeypatch.setattr(wave.ds, "_current", lambda: current)
    result = wave.uninstall()
    assert result["replayed"] is False and result["successorInstallationId"] == successor_id
    assert len(calls) == 1
    assert calls[0]["installation_id"] == wave.ds.DS_ID
    assert calls[0]["idempotency_key"] == wave.KEY
    assert calls[0]["if_match"] == '"5"'
    assert (tmp_path / "new/intent.json").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "new/result.json").stat().st_mode & 0o777 == 0o600
