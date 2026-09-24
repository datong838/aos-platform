import pytest

import a0v_w5c2b_identity_recovery as identity
import a0v_w5c2b_ds_uninstall as wave


def test_existing_identity_intent_never_rotates_again(monkeypatch, tmp_path):
    monkeypatch.setattr(identity, "STATE", tmp_path)
    monkeypatch.setattr(identity, "preflight", lambda: pytest.fail("must not rotate"))
    with pytest.raises(ValueError, match="INTENT_EXISTS"):
        identity.rotate()


def test_new_uninstall_key_and_identity_are_scoped_then_restored(monkeypatch):
    seen = []
    monkeypatch.setattr(wave.identity, "verify", lambda: seen.append("verified"))
    old_state, old_key, old_current = wave.prior.STATE, wave.prior.KEY, wave.prior.ds._current

    def uninstall():
        assert wave.prior.STATE == wave.STATE
        assert wave.prior.KEY == wave.KEY
        assert wave.prior.KEY != old_key
        seen.append("uninstall")
        return {"outcome": "original-owner-called"}

    monkeypatch.setattr(wave.prior, "uninstall", uninstall)
    assert wave.uninstall() == {"outcome": "original-owner-called"}
    assert seen == ["verified", "uninstall"]
    assert wave.prior.STATE == old_state
    assert wave.prior.KEY == old_key
    assert wave.prior.ds._current is old_current
