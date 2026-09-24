import pytest

import a0v_w5c3p_cutover_approval as wave


def registration():
    return {"receipt": {"receiptId": "7861c44a-94b4-4e7a-8898-1d9f70a3d214",
        "requestHash": "sha256:" + "a" * 64, "contentHash": "sha256:" + "b" * 64,
        "executable": False}}


def test_non_effect_policy_and_exact_target(monkeypatch):
    monkeypatch.setattr(wave.registered, "_load", lambda _: {"requestHash": "sha256:" + "a" * 64})
    payload, policy = wave.material(registration())
    assert policy["externalEffectsAllowed"] is False
    assert policy["fallbackAllowed"] is False
    assert payload["expectedGroupRevision"] == 365
    assert payload["targetInstallationId"] == wave.registered.INSTALLATION
    assert payload["registrationReceiptRef"]["resourceId"] == registration()["receipt"]["receiptId"]


@pytest.mark.parametrize("field,value", [
    ("receiptId", "wrong"), ("executable", True), ("requestHash", "sha256:" + "c" * 64)])
def test_registration_drift_rejected(monkeypatch, field, value):
    monkeypatch.setattr(wave.registered, "_load", lambda _: {"requestHash": "sha256:" + "a" * 64})
    data = registration()
    data["receipt"][field] = value
    with pytest.raises(ValueError, match="EXACT_REGISTRATION_REQUIRED"):
        wave.material(data)
