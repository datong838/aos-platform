"""The current same-UID API cannot claim issuer credential isolation."""

import os
import subprocess
from pathlib import Path

import pytest

from scripts.a0v_network_issuer_identity_gate import (
    IssuerIdentityBlocked, assess_credential_isolation,
)


def test_credential_mode_and_owner_contract(tmp_path: Path) -> None:
    issuer_dir = tmp_path / "issuer"
    issuer_dir.mkdir(mode=0o700)
    credential = issuer_dir / "issuer.pgpass"
    credential.write_text("algorithm-only-placeholder")
    credential.chmod(0o600)
    issuer_uid = os.getuid()
    api_uid = issuer_uid + 1
    assess_credential_isolation(api_uid, issuer_uid, credential)
    credential.chmod(0o644)
    with pytest.raises(IssuerIdentityBlocked, match="ISSUER_OS_IDENTITY_NOT_ISOLATED"):
        assess_credential_isolation(api_uid, issuer_uid, credential)
    credential.chmod(0o600)
    alias = issuer_dir / "alias"
    alias.symlink_to(credential)
    with pytest.raises(IssuerIdentityBlocked, match="ISSUER_OS_IDENTITY_NOT_ISOLATED"):
        assess_credential_isolation(api_uid, issuer_uid, alias)
    issuer_dir.chmod(0o755)
    with pytest.raises(IssuerIdentityBlocked, match="ISSUER_OS_IDENTITY_NOT_ISOLATED"):
        assess_credential_isolation(api_uid, issuer_uid, credential)


def test_same_uid_private_file_is_still_not_process_isolation() -> None:
    private = os.environ.get("AOS_BG00CO_PROOF_DIR")
    if not private:
        pytest.skip("explicit isolated proof directory required")
    path = Path(private) / "issuer.pgpass"
    with pytest.raises(IssuerIdentityBlocked, match="ISSUER_OS_IDENTITY_NOT_ISOLATED"):
        assess_credential_isolation(os.getuid(), os.getuid(), path)
    result = subprocess.run(
        ["python3", "scripts/a0v_network_issuer_identity_gate.py",
         "--api-pid", str(os.getpid()), "--issuer-pid", str(os.getpid()),
         "--credential-file", str(path)],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 2
    assert result.stdout.strip() == "ISSUER_OS_IDENTITY_NOT_ISOLATED"
