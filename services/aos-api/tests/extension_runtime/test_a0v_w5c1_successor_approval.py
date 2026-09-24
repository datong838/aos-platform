from types import SimpleNamespace

import pytest

import a0v_w5c1_successor_approval as wave
import a0v_w5_definition_rebuild as definition


def test_existing_intent_never_replays_installer(monkeypatch, tmp_path):
    monkeypatch.setattr(wave, "STATE", tmp_path)
    monkeypatch.setattr(wave, "preflight", lambda: pytest.fail("no preflight or resend"))
    with pytest.raises(ValueError, match="EXISTING_INTENT"):
        wave.approve()


def test_approval_uses_exact_original_owner_once_without_database_backup(monkeypatch, tmp_path):
    monkeypatch.setattr(wave, "STATE", tmp_path / "new")
    predecessor = {"installationId": wave.ds.DS_ID, "revision": 5,
                   "lockHash": wave.ds.LOCK,
                   "overlayRevision": "a0v-canonical-ecommerce-v1"}
    monkeypatch.setattr(wave, "preflight", lambda: {"predecessor": predecessor})
    monkeypatch.setattr(definition, "_configure", lambda: None)
    recorded = []

    class Installer:
        def container_database_connect_factory(self, **kwargs):
            recorded.append(("connect", kwargs))
            return object()

        def create_approved_first_installation(self, **kwargs):
            recorded.append(("approve", kwargs))
            return {"installationState": "approved", "installationId": "successor"}

    monkeypatch.setattr(wave.prior.replacement, "load_profile", lambda: SimpleNamespace(
        _load=lambda name: Installer() if name == "a0v_canonical_ecommerce_first_install"
        else pytest.fail("unexpected loader")))
    result = wave.approve()
    assert result["installationState"] == "approved"
    assert [kind for kind, _ in recorded] == ["connect", "approve"]
    kwargs = recorded[1][1]
    assert kwargs["current_installation_ref"] == predecessor
    assert kwargs["idempotency_prefix"] == wave.PREFIX
    assert (kwargs["core_version"], kwargs["adapter_version"], kwargs["growth_version"],
            kwargs["operations_version"]) == tuple(wave.VERSIONS.values())
    assert (tmp_path / "new/intent.json").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "new/result.json").stat().st_mode & 0o777 == 0o600
