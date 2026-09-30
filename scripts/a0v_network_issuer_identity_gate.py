#!/usr/bin/env python3
"""Read-only OS identity gate for a separate network approval issuer process."""

from __future__ import annotations

import argparse
import stat
import subprocess
from pathlib import Path


class IssuerIdentityBlocked(RuntimeError):
    pass


def _no_extended_acl(path: Path) -> bool:
    result = subprocess.run(["ls", "-lde", str(path.absolute())],
                            capture_output=True, text=True, timeout=5, check=False)
    lines = result.stdout.splitlines()
    if result.returncode != 0 or len(lines) != 1:
        return False
    fields = lines[0].split()
    if not fields:
        return False
    mode = fields[0]
    return len(mode) >= 10 and mode[10:] in {"", "@"}


def assess_credential_isolation(api_uid: int, issuer_uid: int, credential_file: Path) -> None:
    if (type(api_uid) is not int or type(issuer_uid) is not int
            or api_uid <= 0 or issuer_uid <= 0 or api_uid == issuer_uid):
        raise IssuerIdentityBlocked("ISSUER_OS_IDENTITY_NOT_ISOLATED")
    try:
        parent = credential_file.parent.lstat()
        secret = credential_file.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or not stat.S_ISREG(secret.st_mode)
                or parent.st_uid != issuer_uid or secret.st_uid != issuer_uid
                or stat.S_IMODE(parent.st_mode) != 0o700
                or stat.S_IMODE(secret.st_mode) != 0o600
                or not _no_extended_acl(credential_file.parent)
                or not _no_extended_acl(credential_file)):
            raise IssuerIdentityBlocked("ISSUER_OS_IDENTITY_NOT_ISOLATED")
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as exc:
        raise IssuerIdentityBlocked("ISSUER_OS_IDENTITY_NOT_ISOLATED") from exc


def _uid_for_pid(pid: int) -> int:
    if pid <= 0:
        raise IssuerIdentityBlocked("ISSUER_OS_IDENTITY_NOT_ISOLATED")
    result = subprocess.run(["ps", "-o", "uid=", "-p", str(pid)],
                            capture_output=True, text=True, timeout=5, check=False)
    values = result.stdout.strip().splitlines()
    if result.returncode != 0 or len(values) != 1 or not values[0].strip().isdigit():
        raise IssuerIdentityBlocked("ISSUER_OS_IDENTITY_NOT_ISOLATED")
    return int(values[0].strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-pid", type=int, required=True)
    parser.add_argument("--issuer-pid", type=int, required=True)
    parser.add_argument("--credential-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        assess_credential_isolation(_uid_for_pid(args.api_pid),
                                    _uid_for_pid(args.issuer_pid), args.credential_file)
    except (IssuerIdentityBlocked, subprocess.TimeoutExpired):
        print("ISSUER_OS_IDENTITY_NOT_ISOLATED")
        return 2
    print("ISSUER_OS_IDENTITY_GATE_GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
