"""Private durable at-most-once marker for an isolated approval issuer."""

from __future__ import annotations

import hashlib
import json
import os
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


def _read_prior(directory_fd: int, filename: str, expected: dict[str, str | int]) -> None:
    try:
        fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
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
    except (OSError, ValueError, TypeError) as exc:
        raise AttemptUnknown("ISSUER_ATTEMPT_RECEIPT_UNTRUSTED") from exc
    if not isinstance(prior, dict) or set(prior) != set(expected):
        raise AttemptUnknown("ISSUER_ATTEMPT_RECEIPT_UNTRUSTED")
    if prior != expected:
        raise AttemptConflict("ISSUER_ATTEMPT_EXACT_REQUEST_CONFLICT")
    raise AttemptAlreadyRecorded("ISSUER_ATTEMPT_ALREADY_RECORDED")


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
    expected: dict[str, str | int] = {
        "schemaVersion": 1, "state": "ATTEMPTED",
        "orgId": receipt.org_id, "projectId": receipt.project_id,
        "proposalId": receipt.proposal_id,
        "idempotencyKey": receipt.idempotency_key,
        "requestHash": receipt.request_hash,
        "principalSubject": receipt.principal_subject,
    }
    key = json.dumps([receipt.org_id, receipt.project_id, receipt.idempotency_key],
                     separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    filename = hashlib.sha256(key).hexdigest() + ".json"
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
