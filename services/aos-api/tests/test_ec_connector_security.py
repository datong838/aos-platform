import base64

import pytest

from aos_api.kms_crypto import StrictCryptoError, decrypt_strict, encrypt_strict


def test_strict_cipher_random_aad_and_tamper(monkeypatch):
    monkeypatch.setenv("AOS_KMS_MASTER_KEY", base64.b64encode(b"z" * 32).decode())
    one = encrypt_strict("secret", aad="o|w|p|t|access")
    two = encrypt_strict("secret", aad="o|w|p|t|access")
    assert one != two and decrypt_strict(one, aad="o|w|p|t|access") == "secret"
    with pytest.raises(StrictCryptoError): decrypt_strict(one, aad="other")
    with pytest.raises(StrictCryptoError): decrypt_strict(one[:-2] + "AA", aad="o|w|p|t|access")


def test_strict_cipher_requires_production_key(monkeypatch):
    monkeypatch.delenv("AOS_KMS_MASTER_KEY", raising=False)
    with pytest.raises(StrictCryptoError, match="KMS_MASTER_KEY_REQUIRED"):
        encrypt_strict("secret", aad="scope")
