"""Private durable at-most-once marker for an isolated approval issuer."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from aos_api.auth import Principal
from aos_api.aip_network_issuer_contracts import NetworkIssuerDecisionCommand


class AttemptBlocked(RuntimeError):
    pass


class AttemptAlreadyRecorded(AttemptBlocked):
    pass


class AttemptConflict(AttemptBlocked):
    pass


class AttemptUnknown(AttemptBlocked):
    pass


@dataclass(frozen=True)
class AttemptReceipt:
    org_id: str
    project_id: str
    proposal_id: str
    idempotency_key: str
    request_hash: str
    principal_subject: str


def _private_directory_fd(directory: Path) -> int:
    try:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(fd)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            os.close(fd)
            raise AttemptBlocked("ISSUER_ATTEMPT_PRIVATE_DIRECTORY_REQUIRED")
        return fd
    except OSError as exc:
        raise AttemptBlocked("ISSUER_ATTEMPT_PRIVATE_DIRECTORY_REQUIRED") from exc


def _read_marker(directory_fd: int, filename: str, *, allow_missing: bool = False) -> dict | None:
    try:
        fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                     dir_fd=directory_fd)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 4096):
                raise AttemptUnknown("ISSUER_ATTEMPT_RECEIPT_UNTRUSTED")
            raw = os.read(fd, 4097)
        finally:
            os.close(fd)
        if not raw or len(raw) > 4096:
            raise AttemptUnknown("ISSUER_ATTEMPT_RECEIPT_UNTRUSTED")
        prior = json.loads(raw)
    except FileNotFoundError as exc:
        if allow_missing:
            return None
        raise AttemptUnknown("ISSUER_ATTEMPT_RECEIPT_UNTRUSTED") from exc
    except (OSError, ValueError, TypeError) as exc:
        raise AttemptUnknown("ISSUER_ATTEMPT_RECEIPT_UNTRUSTED") from exc
    if not isinstance(prior, dict):
        raise AttemptUnknown("ISSUER_ATTEMPT_RECEIPT_UNTRUSTED")
    return prior


def _read_prior(directory_fd: int, filename: str, expected: dict[str, str | int]) -> None:
    prior = _read_marker(directory_fd, filename)
    if not isinstance(prior, dict) or set(prior) != set(expected):
        raise AttemptUnknown("ISSUER_ATTEMPT_RECEIPT_UNTRUSTED")
    if prior != expected:
        raise AttemptConflict("ISSUER_ATTEMPT_EXACT_REQUEST_CONFLICT")
    raise AttemptAlreadyRecorded("ISSUER_ATTEMPT_ALREADY_RECORDED")


def _attempt_filename(parts: list[str]) -> str:
    key = json.dumps(parts, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(key).hexdigest() + ".json"


def read_decision_attempt(private_directory: Path, *, org_id: str, project_id: str,
                          proposal_id: str, idempotency_key: str, principal_subject: str) -> str | None:
    """Read one authenticated caller's original hash; no directory listing or reservation."""
    directory_fd = _private_directory_fd(private_directory)
    try:
        prior = _read_marker(directory_fd, _attempt_filename([org_id, project_id, idempotency_key]),
                             allow_missing=True)
    finally:
        os.close(directory_fd)
    if prior is None:
        return None
    expected = {'schemaVersion': 1, 'state': 'ATTEMPTED', 'orgId': org_id,
                'projectId': project_id, 'proposalId': proposal_id, 'idempotencyKey': idempotency_key,
                'principalSubject': principal_subject}
    if (set(prior) != set(expected) | {'requestHash'} or type(prior.get('schemaVersion')) is not int
            or any(prior.get(k) != v for k, v in expected.items())
            or not isinstance(prior.get('requestHash'), str)
            or re.fullmatch('[0-9a-f]{64}', prior['requestHash']) is None):
        raise AttemptUnknown('ISSUER_ATTEMPT_RECEIPT_UNTRUSTED')
    return prior['requestHash']


def reserve_decision_attempt(
    private_directory: str | Path,
    command: NetworkIssuerDecisionCommand,
    principal: Principal,
) -> AttemptReceipt:
    """Persist before one call; every later call with the key is denied."""
    if (type(command) is not NetworkIssuerDecisionCommand or type(principal) is not Principal
            or principal.token_kind != "oidc" or principal.org_id != command.org_id
            or principal.project_id != command.project_id or not principal.subject
            or principal.subject == "unknown" or principal.subject != principal.subject.strip()
            or not principal.subject.isprintable()):
        raise AttemptBlocked("ISSUER_ATTEMPT_AUTHENTICATED_SCOPE_REQUIRED")
    receipt = AttemptReceipt(command.org_id, command.project_id, command.proposal_id,
                             command.idempotency_key, command.request_hash,
                             principal.subject)
    return _reserve_attempt_receipt(private_directory, receipt)


def _reserve_attempt_receipt(
    private_directory: str | Path,
    receipt: AttemptReceipt,
    *, namespace: str | None = None,
) -> AttemptReceipt:
    """Shared persistence primitive; callers own authenticated request validation."""
    expected: dict[str, str | int] = {
        "schemaVersion": 1, "state": "ATTEMPTED",
        "orgId": receipt.org_id, "projectId": receipt.project_id,
        "proposalId": receipt.proposal_id,
        "idempotencyKey": receipt.idempotency_key,
        "requestHash": receipt.request_hash,
        "principalSubject": receipt.principal_subject,
    }
    key_parts = [receipt.org_id, receipt.project_id, receipt.idempotency_key]
    if namespace is not None:
        expected['namespace'] = namespace
        key_parts.insert(0, namespace)
    filename = _attempt_filename(key_parts)
    payload = json.dumps(expected, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    directory_fd = _private_directory_fd(Path(private_directory))
    try:
        try:
            fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory_fd)
        except FileExistsError:
            _read_prior(directory_fd, filename, expected)
            raise AssertionError("prior receipt reader must deny")
        except OSError as exc:
            raise AttemptBlocked("ISSUER_ATTEMPT_RESERVATION_FAILED") from exc
        try:
            if stat.S_IMODE(os.fstat(fd).st_mode) != 0o600:
                raise AttemptUnknown("ISSUER_ATTEMPT_RECEIPT_UNTRUSTED")
            written = 0
            while written < len(payload):
                chunk = os.write(fd, payload[written:])
                if chunk <= 0:
                    raise AttemptUnknown("ISSUER_ATTEMPT_PERSISTENCE_UNKNOWN")
                written += chunk
            os.fsync(fd)
            os.fsync(directory_fd)
        except (OSError, AttemptUnknown) as exc:
            raise AttemptUnknown("ISSUER_ATTEMPT_PERSISTENCE_UNKNOWN") from exc
        finally:
            os.close(fd)
        return receipt
    finally:
        os.close(directory_fd)
