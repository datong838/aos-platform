"""KMS Crypto — AES-256-GCM transparent encryption for provider credentials.

Phase A · 222plan · 对应 222 文档第 23 章 Tab 1 凭据管理。

设计：
  - 主密钥来自环境变量 AOS_KMS_MASTER_KEY（32字节 base64 或 hex）
  - 如果环境变量不存在，使用进程级固定密钥（开发环境兼容）
  - 加密格式: "enc:v1:{base64(nonce + ciphertext + tag)}"
  - decrypt() 对非 enc: 前缀的值透明返回（向后兼容已有明文数据）
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.kms_crypto")

_PREFIX = "enc:v1:"
_VERSION = 1
_NONCE_SIZE = 12  # GCM 推荐 96-bit nonce
_KEY_SIZE = 32     # AES-256


def _derive_master_key() -> bytes:
    """Get master key from env or derive a stable fallback."""
    raw = (os.environ.get("AOS_KMS_MASTER_KEY") or "").strip()
    if raw:
        # Support base64 or hex
        try:
            decoded = base64.b64decode(raw)
            if len(decoded) == _KEY_SIZE:
                return decoded
        except Exception:
            pass
        # Try hex
        if len(raw) == _KEY_SIZE * 2:
            return bytes.fromhex(raw)
        # Fallback: hash the raw value
        return hashlib.sha256(raw.encode()).digest()

    # Development fallback: deterministic key (NOT for production)
    log.warning("kms_master_key_missing using derived fallback")
    return hashlib.sha256(b"aos-platform-dev-kms-key-v1").digest()


_MASTER_KEY: bytes | None = None


def _get_master_key() -> bytes:
    global _MASTER_KEY
    if _MASTER_KEY is None:
        _MASTER_KEY = _derive_master_key()
    return _MASTER_KEY


def _get_aesgcm():
    """Lazy import to avoid hard dependency at module load."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    return AESGCM(_get_master_key())


def encrypt(plaintext: str) -> str:
    """Encrypt plaintext → 'enc:v1:{base64}' token.

    Args:
        plaintext: The secret string to encrypt (e.g. API key).

    Returns:
        Encrypted token string with 'enc:v1:' prefix.
    """
    if not plaintext:
        return plaintext
    if is_encrypted(plaintext):
        return plaintext  # Already encrypted

    aesgcm = _get_aesgcm()
    nonce = secrets.token_bytes(_NONCE_SIZE)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    token = base64.b64encode(nonce + ct).decode("ascii")
    result = f"{_PREFIX}{token}"
    log.debug("kms_encrypt ok len=%d→%d", len(plaintext), len(result))
    return result


def decrypt(token: str) -> str:
    """Decrypt 'enc:v1:{base64}' token → plaintext.

    For backward compatibility, if the value doesn't have the enc: prefix,
    it's returned as-is (assumed to be legacy plaintext).

    Args:
        token: Encrypted token or plaintext string.

    Returns:
        The decrypted plaintext string.
    """
    if not token:
        return token
    if not is_encrypted(token):
        return token  # Plaintext passthrough (backward compat)

    raw_b64 = token[len(_PREFIX):]
    try:
        raw = base64.b64decode(raw_b64)
    except Exception as exc:
        log.error("kms_decrypt b64_decode_fail err=%s", exc)
        return token  # Can't decode, return as-is

    if len(raw) < _NONCE_SIZE + 16:  # nonce + minimal GCM tag (16 bytes)
        log.error("kms_decrypt payload_too_short len=%d", len(raw))
        return token

    nonce = raw[:_NONCE_SIZE]
    ct = raw[_NONCE_SIZE:]

    aesgcm = _get_aesgcm()
    try:
        pt = aesgcm.decrypt(nonce, ct, None)
        return pt.decode("utf-8")
    except Exception as exc:
        log.error("kms_decrypt aesgcm_fail err=%s", exc)
        return token  # Decryption failed, return raw


def is_encrypted(val: str) -> bool:
    """Check if a value is an encrypted token."""
    return bool(val) and val.startswith(_PREFIX)


def mask_key(api_key: str, visible_tail: int = 4) -> str:
    """Mask an API key, showing only the last N characters.

    Args:
        api_key: The plaintext API key.
        visible_tail: Number of trailing characters to show.

    Returns:
        Masked string like '...sk-xxxx'
    """
    if not api_key:
        return ""
    if len(api_key) <= visible_tail:
        return "*" * len(api_key)
    return f"...{api_key[-visible_tail:]}"
