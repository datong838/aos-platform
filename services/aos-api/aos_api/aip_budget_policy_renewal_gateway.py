"""Private C transport primitives; HTTP identity/configuration is a separate gate.

The immutable journal records attempted transport, never business permission.
Only original B native reconciliation can supply business results. No module
import starts a server, opens PostgreSQL, provisions a role or approves a budget.
"""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import threading

from pydantic import SecretStr, ValidationError

from aos_api.aip_budget_policy_renewal_connection import load_protected_config
from aos_api.aip_budget_policy_renewal_identity import _HUMAN
from aos_api.aip_budget_policy_renewal_process import (
    MAX_BYTES, _response, _unique, run_renewal_process,
)
from aos_api.aip_budget_policy_renewal_service import COMMANDS, RenewalRequest, RenewalService
from aos_api.aip_network_issuer_attempt import (
    AttemptBlocked, AttemptReceipt, _attempt_filename, _private_directory_fd,
    _reserve_attempt_receipt,
)


class RenewalTransportBlocked(ValueError):
    pass


class RenewalTransportUnknown(RenewalTransportBlocked):
    pass


class RenewalTransportConflict(RenewalTransportBlocked):
    pass


_NAMESPACE = "budget-policy-renewal/gateway/v1/"


def _checked_command(operation, command, subject):
    expected = COMMANDS.get(operation)
    if expected is None or type(command) is not expected or subject != _HUMAN:
        raise RenewalTransportBlocked("RENEWAL_TRANSPORT_EXACT_PRIVATE_REQUEST_REQUIRED")
    # Reparse model_copy/model_construct objects before any durable admission.
    try:
        return expected.model_validate(command.model_dump(mode="python", by_alias=True))
    except ValidationError:
        raise RenewalTransportBlocked("RENEWAL_TRANSPORT_EXACT_PRIVATE_REQUEST_REQUIRED") from None


def _snapshot_name(operation, key):
    return _attempt_filename(["gateway", operation, key]).removesuffix(".json") + ".snapshot.json"


def _marker_name(operation, command):
    return _attempt_filename([
        _NAMESPACE + operation, command.org_id, command.project_id, command.idempotency_key,
    ])


def _resource(operation, command):
    return command.source_policy_id if operation == "propose" else command.proposal_id


def _epoch(operation, command):
    if operation == "propose":
        return (command.expected_source_revision, command.expected_head_version,
                command.expected_source_hash)
    return (command.proposal_hash,)


def _chain_name(proposal_id):
    return _attempt_filename(['gateway-chain', proposal_id]).removesuffix('.json') + '.chain.json'


def _read_json(directory_fd, filename):
    try:
        fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=directory_fd)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                    or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1
                    or not 0 < before.st_size <= MAX_BYTES):
                raise ValueError()
            raw = stream.read(MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
        if (len(raw) > MAX_BYTES or (before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_ino, after.st_size, after.st_mtime_ns)):
            raise ValueError()
        value = json.loads(raw, object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if type(value) is not dict:
            raise ValueError()
        return value
    except (OSError, ValueError, TypeError):
        raise RenewalTransportUnknown("RENEWAL_TRANSPORT_JOURNAL_UNTRUSTED") from None


def _write_json(directory_fd, filename, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode()
    if not 0 < len(raw) <= MAX_BYTES:
        raise RenewalTransportUnknown("RENEWAL_TRANSPORT_JOURNAL_SIZE_REQUIRED")
    try:
        fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                     | os.O_CLOEXEC, 0o600, dir_fd=directory_fd)
        with os.fdopen(fd, "wb") as stream:
            if stat.S_IMODE(os.fstat(stream.fileno()).st_mode) != 0o600:
                raise ValueError()
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(directory_fd)
    except (OSError, ValueError):
        # Keep partial records. No cleanup followed by another execute.
        raise RenewalTransportUnknown("RENEWAL_TRANSPORT_PERSISTENCE_UNKNOWN") from None


class RenewalTransportJournal:
    """Single private journal, serialized across threads and gateway processes."""
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self._thread_lock = threading.RLock()

    @contextmanager
    def _locked(self):
        with self._thread_lock:
            directory_fd = lock_fd = None
            try:
                if (not self.directory.is_absolute()
                        or self.directory.resolve(strict=True) != self.directory):
                    raise ValueError()
                directory_fd = _private_directory_fd(self.directory)
                lock_flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
                try:
                    lock_fd = os.open(".gateway.lock", lock_flags | os.O_CREAT | os.O_EXCL,
                                      0o600, dir_fd=directory_fd)
                except (FileExistsError, FileNotFoundError):
                    # Concurrent first creation may report ENOENT on macOS.
                    # Open only an existing lock once; a genuinely missing or
                    # untrusted file still fails closed before any admission.
                    lock_fd = os.open(".gateway.lock", lock_flags, dir_fd=directory_fd)
                info = os.fstat(lock_fd)
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                        or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                    raise ValueError()
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            except (OSError, ValueError, AttemptBlocked):
                if lock_fd is not None:
                    os.close(lock_fd)
                if directory_fd is not None:
                    os.close(directory_fd)
                raise RenewalTransportBlocked("RENEWAL_TRANSPORT_PRIVATE_DIRECTORY_REQUIRED") from None
            try:
                yield directory_fd
            finally:
                os.close(lock_fd)
                os.close(directory_fd)

    @staticmethod
    def _snapshot(operation, command, subject):
        return {"schemaVersion": 1, "state": "ATTEMPTED", "operation": operation,
                "principalSubject": subject, "requestHash": command.request_hash,
                "command": command.canonical_payload()}

    @staticmethod
    def _parse_snapshot(value, filename):
        try:
            if (set(value) != {"schemaVersion", "state", "operation", "principalSubject",
                               "requestHash", "command"}
                    or type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1
                    or value["state"] != "ATTEMPTED" or value["principalSubject"] != _HUMAN):
                raise ValueError()
            operation = value["operation"]
            command = COMMANDS[operation].model_validate(value["command"])
            if (filename != _snapshot_name(operation, command.idempotency_key)
                    or command.request_hash != value["requestHash"]):
                raise ValueError()
            return operation, command
        except (ValueError, TypeError, KeyError):
            raise RenewalTransportUnknown("RENEWAL_TRANSPORT_SNAPSHOT_UNTRUSTED") from None

    @staticmethod
    def _observation(operation, command):
        # This records only a past native receipt observation. Every actual
        # result is still re-read from B; no cached proposal or permission here.
        return {"schemaVersion": 1, "state": "NATIVE_RECEIPT_OBSERVED", "operation": operation,
                "idempotencyKey": command.idempotency_key, "requestHash": command.request_hash}

    def _all(self, directory_fd):
        names = set(os.listdir(directory_fd))
        if len(names) > 4096:
            raise RenewalTransportUnknown("RENEWAL_TRANSPORT_JOURNAL_BOUND_EXCEEDED")
        chains = self._chains(directory_fd)
        accounted = {".gateway.lock", *(_chain_name(c.proposal_id) for c, _ in chains)}
        records = []
        for filename in sorted(n for n in names if n.endswith(".snapshot.json")):
            value = _read_json(directory_fd, filename)
            operation, command = self._parse_snapshot(value, filename)
            marker_name = _marker_name(operation, command)
            marker = _read_json(directory_fd, marker_name)
            expected = {
                "schemaVersion": 1, "state": "ATTEMPTED", "orgId": command.org_id,
                "projectId": command.project_id, "proposalId": _resource(operation, command),
                "idempotencyKey": command.idempotency_key, "requestHash": command.request_hash,
                "principalSubject": _HUMAN, "namespace": _NAMESPACE + operation,
            }
            if marker != expected or type(marker.get("schemaVersion")) is not int:
                raise RenewalTransportUnknown("RENEWAL_TRANSPORT_MARKER_UNTRUSTED")
            accounted.update((filename, marker_name))
            observed_name = filename.replace(".snapshot.json", ".observed.json")
            observed = observed_name in names
            if observed:
                observed_value = _read_json(directory_fd, observed_name)
                if (observed_value != self._observation(operation, command)
                        or type(observed_value.get("schemaVersion")) is not int):
                    raise RenewalTransportUnknown("RENEWAL_TRANSPORT_OBSERVATION_UNTRUSTED")
                accounted.add(observed_name)
            records.append((operation, command, observed))
        for operation, command, _ in records:
            self._chain_constraints(chains, operation, command)
        # A marker without its full original command is unknown, even when a
        # new key or epoch is supplied. Never leave an orphan out of the scan.
        if names != accounted:
            raise RenewalTransportUnknown("RENEWAL_TRANSPORT_ORPHAN_RECORD")
        return records

    @staticmethod
    def _parse_chain(value, filename):
        try:
            if (set(value) != {'schemaVersion', 'kind', 'principalSubject', 'decisionCommand',
                               'decisionRequestHash', 'consumeIdempotencyKey'}
                    or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
                    or value['kind'] != 'EXPLICIT_APPROVE_AND_PUBLISH'
                    or value['principalSubject'] != _HUMAN):
                raise ValueError()
            command = COMMANDS['decide'].model_validate(value['decisionCommand'])
            key = value['consumeIdempotencyKey']
            checked = COMMANDS['decide'].model_validate({**command.canonical_payload(), 'idempotencyKey': key})
            if (command.decision != 'approved' or checked.idempotency_key == command.idempotency_key
                    or command.request_hash != value['decisionRequestHash']
                    or filename != _chain_name(command.proposal_id)):
                raise ValueError()
            return command, key
        except (ValueError, TypeError, KeyError):
            raise RenewalTransportUnknown('RENEWAL_CHAIN_INTENT_UNTRUSTED') from None

    def _chains(self, directory_fd):
        names = os.listdir(directory_fd)
        if len(names) > 4096:
            raise RenewalTransportUnknown('RENEWAL_TRANSPORT_JOURNAL_BOUND_EXCEEDED')
        chains = [self._parse_chain(_read_json(directory_fd, name), name)
                  for name in sorted(names) if name.endswith('.chain.json')]
        if len({key for _, key in chains}) != len(chains):
            raise RenewalTransportUnknown('RENEWAL_CHAIN_CONSUME_KEY_CONFLICT')
        return chains

    @staticmethod
    def _chain_constraints(chains, operation, command):
        if operation not in {'decide', 'consume'}:
            return
        for decision, key in chains:
            if operation == 'consume' and command.idempotency_key == key and command.proposal_id != decision.proposal_id:
                raise RenewalTransportConflict('RENEWAL_CHAIN_CONSUME_KEY_CONFLICT')
            if command.proposal_id != decision.proposal_id:
                continue
            if ((operation == 'decide' and command != decision)
                    or (operation == 'consume' and (command.idempotency_key != key
                        or command.proposal_hash != decision.proposal_hash))):
                raise RenewalTransportConflict('RENEWAL_CHAIN_EXACT_INTENT_REQUIRED')

    def reserve_chain(self, decision, consume_key, subject):
        decision = _checked_command('decide', decision, subject)
        value = {'schemaVersion': 1, 'kind': 'EXPLICIT_APPROVE_AND_PUBLISH',
                 'principalSubject': subject, 'decisionCommand': decision.canonical_payload(),
                 'decisionRequestHash': decision.request_hash, 'consumeIdempotencyKey': consume_key}
        decision, consume_key = self._parse_chain(value, _chain_name(decision.proposal_id))
        with self._locked() as fd:
            records = self._all(fd)
            chains = self._chains(fd)
            for prior, key in chains:
                if prior.proposal_id == decision.proposal_id:
                    if prior != decision or key != consume_key:
                        raise RenewalTransportConflict('RENEWAL_CHAIN_EXACT_INTENT_REQUIRED')
                    return False
                if key == consume_key:
                    raise RenewalTransportConflict('RENEWAL_CHAIN_CONSUME_KEY_CONFLICT')
            if any(op in {'decide', 'consume'} and (c.proposal_id == decision.proposal_id
                    or (op == 'consume' and c.idempotency_key == consume_key)) for op, c, _ in records):
                raise RenewalTransportConflict('RENEWAL_CHAIN_PRIOR_ATTEMPT_EXISTS')
            _write_json(fd, _chain_name(decision.proposal_id), value)
            return True

    def read_chain(self, proposal_id, subject):
        if subject != _HUMAN:
            raise RenewalTransportBlocked('RENEWAL_CHAIN_CHECKER_REQUIRED')
        with self._locked() as fd:
            name = _chain_name(proposal_id)
            return self._parse_chain(_read_json(fd, name), name)

    def command_state(self, operation, command, subject):
        command = _checked_command(operation, command, subject)
        with self._locked() as fd:
            records = self._all(fd)
            self._chain_constraints(self._chains(fd), operation, command)
            for op, prior, _ in records:
                if op == operation and prior.idempotency_key == command.idempotency_key:
                    if prior != command:
                        raise RenewalTransportConflict('RENEWAL_TRANSPORT_KEY_CONFLICT')
                    return 'attempted'
            return 'not-attempted'

    def list_requests(self, subject):
        if subject != _HUMAN:
            raise RenewalTransportBlocked('RENEWAL_TRANSPORT_EXACT_PRIVATE_REQUEST_REQUIRED')
        with self._locked() as fd:
            return [(operation, command) for operation, command, _ in self._all(fd)]

    def admit(self, operation, command, subject):
        command = _checked_command(operation, command, subject)
        with self._locked() as directory_fd:
            records = self._all(directory_fd)
            self._chain_constraints(self._chains(directory_fd), operation, command)
            for prior_operation, prior, _ in records:
                if prior_operation == operation and prior.idempotency_key == command.idempotency_key:
                    if prior.canonical_payload() != command.canonical_payload():
                        raise RenewalTransportConflict("RENEWAL_TRANSPORT_KEY_CONFLICT")
                    return False
            for prior_operation, prior, observed in records:
                if prior_operation != operation or _resource(operation, prior) != _resource(operation, command):
                    continue
                if not observed:
                    raise RenewalTransportUnknown("RENEWAL_TRANSPORT_RESOURCE_UNRESOLVED")
                if operation != "propose" or _epoch(operation, prior) == _epoch(operation, command):
                    raise RenewalTransportConflict("RENEWAL_TRANSPORT_RESOURCE_CONFLICT")
            _write_json(directory_fd, _snapshot_name(operation, command.idempotency_key),
                        self._snapshot(operation, command, subject))
            try:
                _reserve_attempt_receipt(self.directory, AttemptReceipt(
                    command.org_id, command.project_id, _resource(operation, command),
                    command.idempotency_key, command.request_hash, subject,
                ), namespace=_NAMESPACE + operation)
            except AttemptBlocked:
                raise RenewalTransportUnknown("RENEWAL_TRANSPORT_ADMISSION_UNKNOWN") from None
            return True

    def restore(self, operation, key, subject):
        if operation not in COMMANDS or subject != _HUMAN or type(key) is not str:
            raise RenewalTransportBlocked("RENEWAL_TRANSPORT_EXACT_PRIVATE_REQUEST_REQUIRED")
        # A complete original snapshot can still drive read-only reconciliation
        # when its marker/index is missing. It can never authorize another
        # execute: admit() requires the complete journal and still returns False
        # for this original key. A missing/partial snapshot is never guessed.
        with self._locked() as directory_fd:
            filename = _snapshot_name(operation, key)
            value = _read_json(directory_fd, filename)
            prior_operation, command = self._parse_snapshot(value, filename)
            if prior_operation != operation or command.idempotency_key != key:
                raise RenewalTransportUnknown("RENEWAL_TRANSPORT_ORIGINAL_REQUEST_MISSING")
            return command

    def record_observation(self, operation, command, subject, result):
        command = _checked_command(operation, command, subject)
        if (type(result) is not dict or result.get("operation") != operation
                or result.get("requestHash") != command.request_hash
                or result.get("activationEligible") is not False
                or result.get("status") not in {"prepared", "decided", "revoked", "observed"}):
            return  # Unknown/conflict/unresolved must keep the coarse lock.
        with self._locked() as directory_fd:
            records = self._all(directory_fd)
            matched = [(c, observed) for op, c, observed in records
                       if op == operation and c.idempotency_key == command.idempotency_key]
            if len(matched) != 1 or matched[0][0] != command:
                raise RenewalTransportUnknown("RENEWAL_TRANSPORT_ORIGINAL_REQUEST_MISSING")
            if not matched[0][1]:
                _write_json(directory_fd, _snapshot_name(operation, command.idempotency_key)
                            .replace(".snapshot.json", ".observed.json"),
                            self._observation(operation, command))


class OwnedRenewalChild:
    """Drain this exact returned Popen. Never interpret or retain its output."""
    def __init__(self, process):
        if type(process) is not subprocess.Popen:
            raise RenewalTransportBlocked("RENEWAL_TRANSPORT_REAL_CHILD_REQUIRED")
        self.process = process
        self.discarded_bytes = 0
        for name in ("stdout", "stderr"):
            stream = getattr(process, name)
            if stream is not None:
                os.set_blocking(stream.fileno(), False)

    def finish_incomplete_input(self):
        # B returned the handle without its trusted remaining transport state.
        # EOF rejects a partial frame; resending raw would replay unknown input.
        stream = self.process.stdin
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass
            self.process.stdin = None

    def drain(self):
        for name in ("stdout", "stderr"):
            stream = getattr(self.process, name)
            if stream is None:
                continue
            remaining = MAX_BYTES
            while remaining > 0:
                try:
                    chunk = os.read(stream.fileno(), min(4096, remaining))
                except BlockingIOError:
                    break
                except OSError:
                    chunk = b""
                if not chunk:
                    stream.close()
                    setattr(self.process, name, None)
                    break
                self.discarded_bytes += len(chunk)
                remaining -= len(chunk)
        terminal = self.process.poll() is not None
        return terminal and self.process.stdout is None and self.process.stderr is None


class RenewalTransport:
    """One original B execute per durable C admission; every recovery is read-only.

    Call only after the gateway has checked protected deployment provenance and
    current original management identity. This private class is not an HTTP API.
    """
    def __init__(self, journal, config_path, attempt_directory, *, maximum_children=8):
        if (type(journal) is not RenewalTransportJournal
                or not Path(config_path).is_absolute() or not Path(attempt_directory).is_absolute()
                or type(maximum_children) is not int or not 1 <= maximum_children <= 32):
            raise RenewalTransportBlocked("RENEWAL_TRANSPORT_PROTECTED_CONFIGURATION_REQUIRED")
        self.journal = journal
        self.config_path = Path(config_path)
        self.attempt_directory = Path(attempt_directory)
        self.maximum_children = maximum_children
        self._children = {}
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._closing = False
        self._monitor = threading.Thread(target=self._monitor_children, daemon=True,
                                         name="budget-renewal-owned-children")
        self._monitor.start()

    @staticmethod
    def _request(operation, command, bearer_token, mode):
        fields = dict(schemaVersion=1, operation=operation, command=command, mode=mode)
        if operation in {"decide", "revoke"}:
            fields["bearerToken"] = bearer_token
        elif bearer_token is not None:
            raise RenewalTransportBlocked("RENEWAL_TRANSPORT_MACHINE_TOKEN_FORBIDDEN")
        return RenewalRequest.model_validate(fields)

    @staticmethod
    def _unknown(request):
        return {"status": "unknown", "requestHash": request.command.request_hash,
                "activationEligible": False}

    def _reconcile(self, request):
        try:
            result = RenewalService(load_protected_config(self.config_path),
                                    self.attempt_directory).reconcile(request)
            return _response(request, result)
        except Exception:
            return self._unknown(request)

    def _accept(self, request, subject, value):
        if type(value) is not dict:
            return self._unknown(request)
        if "process" in value:
            child = OwnedRenewalChild(value["process"])
            child.finish_incomplete_input()
            self._children[(request.operation, request.command.idempotency_key)] = child
            self._wake.set()
            return self._unknown(request)
        try:
            expected = _response(request, value["result"])
            if value != expected or type(value.get("schemaVersion")) is not int:
                return self._unknown(request)
            self.journal.record_observation(request.operation, request.command, subject, value["result"])
            return value
        except (KeyError, ValueError):
            return self._unknown(request)

    def execute(self, operation, command, subject, *, bearer_token: SecretStr | None = None):
        command = _checked_command(operation, command, subject)
        request = self._request(operation, command, bearer_token, "execute")
        with self._lock:
            if self._closing:
                raise RenewalTransportBlocked("RENEWAL_TRANSPORT_CLOSED")
            if len(self._children) >= self.maximum_children:
                raise RenewalTransportBlocked("RENEWAL_TRANSPORT_CHILD_BOUND_REACHED")
            admitted = self.journal.admit(operation, command, subject)
            if not admitted:
                request = self._request(operation, command, bearer_token, "reconcile")
                return self._accept(request, subject, self._reconcile(request))
            body = request.model_dump(mode="json", by_alias=True, exclude={"bearer_token"})
            if request.bearer_token is not None:
                body["bearerToken"] = request.bearer_token.get_secret_value()
            raw = json.dumps(body, separators=(",", ":"), allow_nan=False).encode()
            body.clear()
            try:
                value = run_renewal_process(self.config_path, self.attempt_directory, raw)
            except Exception:
                value = self._unknown(request)
            finally:
                raw = None
            return self._accept(request, subject, value)

    def reconcile(self, operation, key, subject, *, bearer_token: SecretStr | None = None):
        command = self.journal.restore(operation, key, subject)
        request = self._request(operation, command, bearer_token, "reconcile")
        with self._lock:
            return self._accept(request, subject, self._reconcile(request))

    def _monitor_children(self):
        while True:
            with self._lock:
                for key, child in list(self._children.items()):
                    if child.drain():
                        del self._children[key]
                if self._closing and not self._children:
                    return
            self._wake.wait(.05)
            self._wake.clear()

    def close(self):
        # Stop accepting, but keep ownership/draining of any live child. No
        # terminate, kill, restart or second write on HTTP disconnect/shutdown.
        with self._lock:
            self._closing = True
        self._wake.set()
        self._monitor.join(timeout=.2)


# Protected deployment inputs are private operator TCB, never HTTP parameters.
# Complete HTTP launcher pins must be added before that launcher is deployed.
GATEWAY_ROOT = Path(__file__).resolve().parents[3]
GATEWAY_FILES = (
    'scripts/a0v_qyh_budget_policy_renewal.py',
    'services/aos-api/aos_api/aip_budget_policy_renewal_gateway.py',
    'services/aos-api/aos_api/aip_budget_policy_renewal_review.py',
    'services/aos-api/aos_api/routers/aip_model_governance_policies.py',
)
_SOURCE_REQUIRED = {
    'scripts/a0v_qyh_restored_http.py', 'scripts/a0v_current_preview_http.py',
    'services/aos-api/aos_api/main.py', 'services/aos-api/aos_api/auth.py',
    'services/aos-api/aos_api/aip_budget_policy_renewal_review.py',
    'services/aos-api/aos_api/routers/aip_model_governance_policies.py',
}
_PROXY_ENV = ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
              'http_proxy', 'https_proxy', 'all_proxy')


def _digest(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def _hash(value):
    import re
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _private_gateway_bytes(path, maximum=65536):
    from aos_api.aip_budget_policy_renewal_connection import _private_bytes
    raw = _private_bytes(path, maximum=maximum)
    if Path(path).lstat().st_nlink != 1:
        raise RenewalTransportBlocked('RENEWAL_GATEWAY_PRIVATE_CONFIG_REQUIRED')
    return raw


def _json_object(raw):
    value = json.loads(raw, object_pairs_hook=_unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    if type(value) is not dict:
        raise ValueError()
    return value


def _loopback_origin(value):
    from urllib.parse import urlsplit
    if type(value) is not str or not value.isascii() or len(value) > 64:
        raise ValueError()
    url = urlsplit(value)
    port = url.port
    if (url.scheme != 'http' or url.hostname != '127.0.0.1'
            or type(port) is not int or not 1 <= port <= 65535
            or value != f'http://127.0.0.1:{port}'):
        raise ValueError()
    return port


def _system_output(argv):
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=3, check=True)
    if len(result.stdout) > 65536:
        raise ValueError()
    return result.stdout.decode('utf-8', errors='strict')


def _darwin_process(pid, port):
    import ctypes

    # sys/proc_info.h PROC_PIDTBSDINFO=3, struct proc_bsdinfo, MAXCOMLEN=16.
    class BsdInfo(ctypes.Structure):
        _fields_ = ([(n, ctypes.c_uint32) for n in (
            'flags', 'status', 'xstatus', 'pid', 'ppid', 'uid', 'gid', 'ruid',
            'rgid', 'svuid', 'svgid', 'reserved')]
            + [('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32)]
            + [(n, ctypes.c_uint32) for n in ('nfiles', 'pgid', 'pjobc', 'tdev', 'tpgid')]
            + [('nice', ctypes.c_int32), ('start_sec', ctypes.c_uint64),
               ('start_usec', ctypes.c_uint64)])

    library = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    function = library.proc_pidinfo
    function.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                         ctypes.c_void_p, ctypes.c_int)
    function.restype = ctypes.c_int

    def identity():
        info = BsdInfo()
        if (function(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info)) != ctypes.sizeof(info)
                or info.pid != pid or info.uid != os.geteuid() or info.status == 5
                or not info.start_sec or info.start_usec >= 1000000):
            raise ValueError()
        return (info.uid, info.start_sec, info.start_usec)

    before = identity()
    command = _system_output(['/bin/ps', '-ww', '-p', str(pid), '-o', 'command=']).strip()
    cwd_lines = _system_output(['/usr/sbin/lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn']).splitlines()
    cwds = [line[1:] for line in cwd_lines if line.startswith('n')]
    listeners = _system_output(['/usr/sbin/lsof', '-nP', f'-iTCP:{port}',
                                '-sTCP:LISTEN', '-Fpn']).splitlines()
    pids = {int(line[1:]) for line in listeners if line.startswith('p')}
    addresses = [line[1:] for line in listeners if line.startswith('n')]
    if (before != identity() or len(cwds) != 1 or pids != {pid}
            or addresses != [f'127.0.0.1:{port}']):
        raise ValueError()
    return {'pid': pid, 'uid': before[0],
            'startIdentity': f'darwin:{before[1]}:{before[2]}',
            'cwd': cwds[0], 'command': command}


def _linux_process(pid, port):
    import sys
    proc = Path('/proc') / str(pid)

    def identity():
        # comm can contain spaces/parentheses; fields after its final ')' start
        # at state (3), so starttime(22) has index19 in this suffix.
        raw = (proc / 'stat').read_text()
        fields = raw[raw.rindex(')') + 2:].split()
        if fields[0] == 'Z' or int(raw[:raw.index('(')].strip()) != pid:
            raise ValueError()
        uid_line, = [line for line in (proc / 'status').read_text().splitlines()
                     if line.startswith('Uid:')]
        uid = int(uid_line.split()[2])
        if uid != os.geteuid():
            raise ValueError()
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        return uid, boot, fields[19]

    before = identity()
    command = ' '.join(part.decode('utf-8') for part in (proc / 'cmdline').read_bytes().split(b'\0') if part)
    cwd = str((proc / 'cwd').resolve(strict=True))
    rows = []
    for name in ('tcp', 'tcp6'):
        for line in (proc / 'net' / name).read_text().splitlines()[1:]:
            parts = line.split()
            if parts[3] == '0A' and int(parts[1].split(':')[1], 16) == port:
                rows.append(parts)
    if len(rows) != 1 or rows[0][1] != f'0100007F:{port:04X}' or int(rows[0][7]) != before[0]:
        raise ValueError()
    inode = rows[0][9]
    owners = set()
    # Ensure exactly this process owns the unique listener, including inherited
    # socket holders. Unreadable same-uid process fd tables fail closed.
    for candidate in Path('/proc').iterdir():
        if not candidate.name.isdecimal():
            continue
        try:
            status_lines = (candidate / 'status').read_text().splitlines()
            uid_line, = [line for line in status_lines if line.startswith('Uid:')]
            if int(uid_line.split()[2]) != os.geteuid():
                continue
            raw = (candidate / 'stat').read_text()
            fields = raw[raw.rindex(')') + 2:].split()
            if int(raw[:raw.index('(')].strip()) != int(candidate.name):
                raise ValueError()
            if fields[0] == 'Z':
                # A zombie leader may still have live threads holding files.
                # Only a stable, wholly exited group has released all its FDs.
                thread_line, = [line for line in status_lines if line.startswith('Threads:')]
                tasks = list((candidate / 'task').iterdir())
                if int(thread_line.split()[1]) != 1 or len(tasks) != 1 or tasks[0].name != candidate.name:
                    raise ValueError()
                last = (tasks[0] / 'stat').read_text()
                tail = last[last.rindex(')') + 2:].split()
                if int(last[:last.index('(')].strip()) != int(candidate.name) or tail[0] != 'Z' or tail[19] != fields[19]:
                    raise ValueError()
                continue
            for fd in (candidate / 'fd').iterdir():
                try:
                    if os.readlink(fd) == f'socket:[{inode}]':
                        owners.add(int(candidate.name))
                except FileNotFoundError:
                    continue
        except FileNotFoundError:
            continue
    if owners != {pid} or before != identity():
        raise ValueError()
    return {'pid': pid, 'uid': before[0], 'startIdentity': f'linux:{before[1]}:{before[2]}',
            'cwd': cwd, 'command': command}


def probe_management_process(pid, port):
    """Read one actual same-user process and unique loopback listening socket."""
    import sys
    try:
        if (type(pid) is not int or pid <= 0 or type(port) is not int
                or not 1 <= port <= 65535):
            raise ValueError()
        if sys.platform == 'darwin':
            value = _darwin_process(pid, port)
        elif sys.platform == 'linux':
            value = _linux_process(pid, port)
        else:
            raise ValueError()
        if not value['command'] or len(value['command']) > 16384:
            raise ValueError()
        return value
    except Exception:
        raise RenewalTransportBlocked('RENEWAL_GATEWAY_MANAGEMENT_PROCESS_UNTRUSTED') from None


def _source_candidate(value):
    from pathlib import PurePosixPath
    candidate_raw = _private_gateway_bytes(value['sourceCandidatePath'])
    manifest_raw = _private_gateway_bytes(value['sourceManifestPath'], maximum=16 * 1024 * 1024)
    if (not _hash(value['sourceCandidateSha256']) or not _hash(value['sourceManifestSha256'])
            or _digest(candidate_raw) != value['sourceCandidateSha256']
            or _digest(manifest_raw) != value['sourceManifestSha256']):
        raise ValueError()
    report = _json_object(candidate_raw)
    manifest = _json_object(manifest_raw)
    root = Path(report['source'])
    head = report['head']
    if (not root.is_absolute() or root.resolve(strict=True) != root
            or type(head) is not str or len(head) != 40
            or any(c not in '0123456789abcdef' for c in head)
            or report['outcome'] != 'CURRENT_M1_API_SOURCE_CANDIDATE_FROZEN_NO_START'
            or type(report['fileCount']) is not int or report['fileCount'] != len(manifest)
            or report['manifestSha256'] != value['sourceManifestSha256']
            or not _SOURCE_REQUIRED.issubset(manifest) or len(manifest) > 40000):
        raise ValueError()
    for name, digest in manifest.items():
        path = PurePosixPath(name)
        if (type(name) is not str or path.is_absolute() or '..' in path.parts
                or str(path) != name or not _hash(digest)):
            raise ValueError()
    observed = {}
    for path in (root, *root.rglob('*')):
        info = path.lstat()
        is_file = stat.S_ISREG(info.st_mode)
        if (info.st_uid != os.geteuid() or (not is_file and not stat.S_ISDIR(info.st_mode))
                or stat.S_IMODE(info.st_mode) != (0o600 if is_file else 0o700)
                or (is_file and info.st_nlink != 1)):
            raise ValueError()
        if is_file:
            observed[path.relative_to(root).as_posix()] = _digest(path.read_bytes())
    if observed != manifest:
        raise ValueError()
    return root


from dataclasses import dataclass


@dataclass(frozen=True)
class ProtectedGatewayConfig:
    path: Path
    content_sha256: str
    web_origin: str
    management_origin: str
    source_root: Path
    process_binding: tuple[tuple[str, object], ...]
    writer_enabled: bool
    renewal_config: object | None
    journal_directory: Path | None
    attempt_directory: Path | None


def load_gateway_config(path):
    """Validate bytes/provenance only; no PG connection or role enablement."""
    try:
        raw = _private_gateway_bytes(path)
        value = _json_object(raw)
        required = {'schemaVersion', 'orgId', 'projectId', 'webOrigin', 'managementOrigin',
                    'sourceCandidatePath', 'sourceCandidateSha256', 'sourceManifestPath',
                    'sourceManifestSha256', 'managementProcess', 'gatewaySources'}
        optional = {'writerEnabled', 'protectedRenewalConfigPath', 'protectedRenewalConfigSha256',
                    'journalDirectory', 'attemptDirectory'}
        if (not required.issubset(value) or set(value) - required - optional
                or value['schemaVersion'] != 'aos.budget-policy-renewal.gateway/v1'
                or value['orgId'] != 'org-org' or value['projectId'] != 'dev-project'
                or type(value.get('writerEnabled', False)) is not bool):
            raise ValueError()
        port = _loopback_origin(value['managementOrigin'])
        _loopback_origin(value['webOrigin'])
        packages = value['gatewaySources']
        if type(packages) is not dict or set(packages) != set(GATEWAY_FILES):
            raise ValueError()
        for name, digest in packages.items():
            source = GATEWAY_ROOT / name
            if (not _hash(digest) or source.resolve(strict=True) != source
                    or not source.is_file() or _digest(source.read_bytes()) != digest):
                raise ValueError()
        root = _source_candidate(value)
        process = value['managementProcess']
        if (type(process) is not dict or set(process) != {'pid', 'startIdentity', 'uid', 'cwd', 'command'}
                or type(process['pid']) is not int or process['pid'] <= 0
                or type(process['uid']) is not int or process['uid'] != os.geteuid()
                or process['cwd'] != str(root)
                or any(type(process[k]) is not str or not process[k] or len(process[k]) > 16384
                       for k in ('command', 'startIdentity'))
                or probe_management_process(process['pid'], port) != process):
            raise ValueError()
        writer_keys = optional - {'writerEnabled'}
        present = set(value) & writer_keys
        if (present and present != writer_keys) or (value.get('writerEnabled', False) and not present):
            raise ValueError()
        renewal = None
        directories = []
        if present:
            b_raw = _private_gateway_bytes(value['protectedRenewalConfigPath'])
            if (not _hash(value['protectedRenewalConfigSha256'])
                    or _digest(b_raw) != value['protectedRenewalConfigSha256']):
                raise ValueError()
            renewal = load_protected_config(Path(value['protectedRenewalConfigPath']))
            if renewal.content_sha256 != _digest(b_raw) or (value.get('writerEnabled', False) and not renewal.enabled):
                raise ValueError()
            for field in ('journalDirectory', 'attemptDirectory'):
                directory = Path(value[field])
                if not directory.is_absolute() or directory.resolve(strict=True) != directory:
                    raise ValueError()
                fd = _private_directory_fd(directory)
                os.close(fd)
                directories.append(directory)
            if directories[0] == directories[1]:
                raise ValueError()
        if _private_gateway_bytes(path) != raw:
            raise ValueError()
        return ProtectedGatewayConfig(Path(path), _digest(raw), value['webOrigin'],
            value['managementOrigin'], root, tuple(sorted(process.items())),
            value.get('writerEnabled', False), renewal,
            directories[0] if directories else None, directories[1] if directories else None)
    except Exception:
        raise RenewalTransportBlocked('RENEWAL_GATEWAY_CONFIG_CLOSED_OR_DRIFTED') from None


class RenewalCheckerDenied(RenewalTransportBlocked):
    def __init__(self, status):
        self.status = status
        super().__init__('RENEWAL_GATEWAY_CHECKER_DENIED')


def relay_current_checker(config, bearer_token):
    """Fixed direct-loopback readonly observation; native B rechecks on write."""
    from datetime import datetime, timezone
    from http.client import HTTPConnection
    from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalCheckerView
    connection = None
    try:
        if (type(config) is not ProtectedGatewayConfig or type(bearer_token) is not SecretStr
                or any(os.environ.get(key) for key in _PROXY_ENV)):
            raise ValueError()
        token = bearer_token.get_secret_value()
        if (not 1 <= len(token) <= 16384 or not token.isascii()
                or any(ord(c) <= 32 or ord(c) >= 127 for c in token)):
            raise ValueError()
        if load_gateway_config(config.path) != config:
            raise ValueError()
        connection = HTTPConnection('127.0.0.1', _loopback_origin(config.management_origin), timeout=3)
        connection.request('GET', '/v1/aip/model-governance-policies/renewal-checker', headers={
            'Authorization': 'Bearer ' + token, 'X-Org-Id': 'org-org',
            'X-Project-Id': 'dev-project', 'Accept': 'application/json',
            'Cache-Control': 'no-store',
        })
        token = None
        response = connection.getresponse()
        raw = response.read(65537)
        if load_gateway_config(config.path) != config:
            raise ValueError()
        if response.status in {401, 403}:
            raise RenewalCheckerDenied(response.status)
        if (response.status != 200 or len(raw) > 65536
                or response.getheader('Content-Type', '').split(';')[0].strip().lower() != 'application/json'
                or response.getheader('Content-Encoding', 'identity') != 'identity'):
            raise ValueError()
        result = BudgetPolicyRenewalCheckerView.model_validate(_json_object(raw))
        age = (datetime.now(timezone.utc) - result.evaluated_at).total_seconds()
        if not 0 <= age <= 30:
            raise ValueError()
        return result
    except RenewalCheckerDenied:
        raise
    except Exception:
        raise RenewalTransportBlocked('RENEWAL_GATEWAY_CHECKER_UNAVAILABLE_OR_DRIFTED') from None
    finally:
        if connection is not None:
            connection.close()


_HTTP_PREFIX = '/v1/aip/budget-policy-renewal'
_GATEWAY_PORT = 18462


class RenewalHttpRejected(ValueError):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


def _http_reject(status, code):
    raise RenewalHttpRejected(status, code)


def _wire_command(operation, body):
    try:
        command = COMMANDS[operation].model_validate(body)
        if type(body) is not dict or set(body) != set(command.canonical_payload()):
            raise ValueError()
        return command
    except (ValueError, KeyError, TypeError):
        _http_reject(400, 'RENEWAL_HTTP_EXACT_COMMAND_REQUIRED')


def _route(path, method):
    import re
    if type(path) is not str or not path.startswith(_HTTP_PREFIX + '/'):
        _http_reject(404, 'RENEWAL_HTTP_ROUTE_NOT_FOUND')
    tail = path[len(_HTTP_PREFIX):]
    if tail in {'/status', '/requests'}:
        route = ('status' if tail == '/status' else 'history',)
        allowed = 'GET'
    elif tail[1:] in COMMANDS:
        route, allowed = ('operation', tail[1:]), 'POST'
    elif tail == '/decide-and-publish':
        route, allowed = ('chain-start',), 'POST'
    elif match := re.fullmatch(r'/requests/page/(0|[1-9][0-9]{0,3})', tail):
        route, allowed = ('history', int(match[1])), 'GET'
    elif match := re.fullmatch(r'/requests/(propose|decide|revoke|consume)/([A-Za-z0-9][A-Za-z0-9._:-]{0,119})', tail):
        route, allowed = ('request', match[1], match[2]), 'GET'
    elif match := re.fullmatch(r'/chains/([A-Za-z0-9][A-Za-z0-9._:-]{0,159})(/continue)?', tail):
        route, allowed = ('chain-continue' if match[2] else 'chain-read', match[1]), 'POST' if match[2] else 'GET'
    else:
        _http_reject(404, 'RENEWAL_HTTP_ROUTE_NOT_FOUND')
    if method != allowed:
        _http_reject(405, 'RENEWAL_HTTP_METHOD_NOT_ALLOWED')
    return route


def _http_headers(scope, config):
    headers = {}
    try:
        for raw_key, raw_value in scope['headers']:
            key, value = raw_key.decode('ascii').lower(), raw_value.decode('latin-1')
            if key in headers or key == 'forwarded' or key.startswith('x-forwarded-'):
                raise ValueError()
            headers[key] = value
    except (ValueError, UnicodeError, KeyError):
        _http_reject(400, 'RENEWAL_HTTP_HEADERS_INVALID')
    if (headers.get('host') != f'127.0.0.1:{_GATEWAY_PORT}' or scope.get('query_string')):
        _http_reject(400, 'RENEWAL_HTTP_HOST_OR_QUERY_INVALID')
    if headers.get('x-org-id') != 'org-org' or headers.get('x-project-id') != 'dev-project':
        _http_reject(403, 'RENEWAL_HTTP_TENANT_DENIED')
    origin = headers.get('origin')
    if (origin is not None and origin != config.web_origin) or (scope['method'] == 'POST' and origin != config.web_origin):
        _http_reject(403, 'RENEWAL_HTTP_ORIGIN_DENIED')
    auth = headers.get('authorization', '')
    if not auth.startswith('Bearer ') or not auth[7:] or len(auth) > 16391:
        _http_reject(401, 'RENEWAL_HTTP_BEARER_REQUIRED')
    token = auth[7:]
    if not token.isascii() or any(ord(c) <= 32 or ord(c) >= 127 for c in token):
        _http_reject(401, 'RENEWAL_HTTP_BEARER_REQUIRED')
    return headers, SecretStr(token)


async def _http_body(scope, headers, receive):
    import asyncio
    import time
    length = headers.get('content-length')
    if length is not None and (not length.isascii() or not length.isdecimal()):
        _http_reject(400, 'RENEWAL_HTTP_LENGTH_INVALID')
    expected = int(length) if length is not None else None
    if expected is not None and expected > MAX_BYTES:
        _http_reject(413, 'RENEWAL_HTTP_BODY_TOO_LARGE')
    if headers.get('content-encoding', 'identity') != 'identity':
        _http_reject(415, 'RENEWAL_HTTP_ENCODING_UNSUPPORTED')
    if scope['method'] == 'POST' and headers.get('content-type', '').lower() not in {
            'application/json', 'application/json; charset=utf-8'}:
        _http_reject(415, 'RENEWAL_HTTP_JSON_REQUIRED')
    raw = bytearray()
    deadline = time.monotonic() + 5
    for _ in range(256):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _http_reject(400, 'RENEWAL_HTTP_INCOMPLETE_BODY')
        try:
            message = await asyncio.wait_for(receive(), timeout=remaining)
        except asyncio.TimeoutError:
            _http_reject(400, 'RENEWAL_HTTP_INCOMPLETE_BODY')
        if message.get('type') != 'http.request' or type(message.get('body', b'')) is not bytes:
            _http_reject(400, 'RENEWAL_HTTP_INCOMPLETE_BODY')
        raw.extend(message.get('body', b''))
        if len(raw) > MAX_BYTES:
            _http_reject(413, 'RENEWAL_HTTP_BODY_TOO_LARGE')
        if not message.get('more_body', False):
            break
    else:
        _http_reject(400, 'RENEWAL_HTTP_INCOMPLETE_BODY')
    if expected is not None and len(raw) != expected:
        _http_reject(400, 'RENEWAL_HTTP_LENGTH_INVALID')
    if scope['method'] == 'GET':
        if raw:
            _http_reject(400, 'RENEWAL_HTTP_GET_BODY_FORBIDDEN')
        return None
    try:
        return _json_object(bytes(raw).decode('utf-8'))
    except (ValueError, UnicodeError, TypeError):
        _http_reject(400, 'RENEWAL_HTTP_JSON_INVALID')


class RenewalGatewayController:
    """HTTP orchestration only; original B/native receipt remains authority."""
    def __init__(self, config):
        if type(config) is not ProtectedGatewayConfig:
            raise RenewalTransportBlocked('RENEWAL_GATEWAY_CONFIG_REQUIRED')
        self.config = config
        self._lock = threading.RLock()
        self.transport = None
        if config.renewal_config is not None:
            self.transport = RenewalTransport(RenewalTransportJournal(config.journal_directory),
                config.renewal_config.path, config.attempt_directory)

    def close(self):
        with self._lock:
            if self.transport is not None:
                self.transport.close()

    def _available(self, write=False):
        if self.transport is None or (write and not self.config.writer_enabled):
            _http_reject(503, 'RENEWAL_GATEWAY_WRITER_CLOSED' if write else 'RENEWAL_GATEWAY_HISTORY_UNAVAILABLE')
        return self.transport

    @staticmethod
    def _frame(operation, command, frame):
        value = {'schemaVersion': 'aos.budget-policy-renewal.gateway-operation/v1',
            'operation': operation, 'idempotencyKey': command.idempotency_key,
            'requestHash': command.request_hash, 'activationEligible': False,
            'approvalVerified': False, 'state': 'unknown', 'receipt': None,
            'recoveryPath': f'{_HTTP_PREFIX}/requests/{operation}/{command.idempotency_key}'}
        try:
            if (type(frame) is not dict or type(frame.get('schemaVersion')) is not int
                    or frame['schemaVersion'] != 1 or frame['operation'] != operation
                    or frame['requestHash'] != command.request_hash
                    or frame['activationEligible'] is not False or set(frame) != {
                        'schemaVersion', 'operation', 'requestHash', 'activationEligible', 'result'}):
                return value
            result = frame['result']
            if (type(result) is not dict or result.get('operation') != operation
                    or result.get('requestHash') != command.request_hash
                    or result.get('activationEligible') is not False
                    or result.get('status') not in {'prepared', 'decided', 'revoked', 'observed',
                                                  'unresolved', 'conflict', 'blocked'}):
                return value
            value.update(state=result['status'], receipt=result)
        except (KeyError, ValueError, TypeError):
            pass
        return value

    def _read_request(self, operation, key, subject, token):
        transport = self._available()
        command = transport.journal.restore(operation, key, subject)
        frame = transport.reconcile(operation, key, subject,
            bearer_token=token if operation in {'decide', 'revoke'} else None)
        return self._frame(operation, command, frame)

    @staticmethod
    def _consume_command(decision, key, observed):
        try:
            result = observed['receipt']
            payload = result['decisionPayload']
            if (observed['state'] != 'observed' or decision.decision != 'approved'
                    or result['proposalId'] != decision.proposal_id
                    or result['proposalHash'] != decision.proposal_hash
                    or result['targetActiveHash'] != decision.target_active_hash
                    or result['actorSubject'] != _HUMAN or payload['actorSubject'] != _HUMAN
                    or payload['decision'] != 'approved'
                    or payload['command'] != decision.canonical_payload()
                    or payload['proposalId'] != decision.proposal_id
                    or payload['proposalHash'] != decision.proposal_hash
                    or payload['targetActiveHash'] != decision.target_active_hash):
                raise ValueError()
            return COMMANDS['consume'].model_validate({'schemaVersion': 1, 'orgId': 'org-org',
                'projectId': 'dev-project', 'idempotencyKey': key,
                'proposalId': decision.proposal_id, 'proposalHash': decision.proposal_hash,
                'decisionId': result['decisionId'], 'decisionHash': result['decisionHash']})
        except (KeyError, ValueError, TypeError):
            raise RenewalTransportUnknown('RENEWAL_CHAIN_OBSERVED_APPROVED_DECISION_REQUIRED') from None

    def _chain(self, decision, key, subject, token, *, advance):
        transport = self._available(write=advance)
        answer = {'schemaVersion': 'aos.budget-policy-renewal.gateway-chain/v1',
            'proposalId': decision.proposal_id, 'decisionIdempotencyKey': decision.idempotency_key,
            'consumeIdempotencyKey': key, 'decision': None, 'publication': None,
            'state': 'unknown', 'approvalVerified': False, 'activationEligible': False,
            'recoveryPath': f'{_HTTP_PREFIX}/chains/{decision.proposal_id}'}
        state = transport.journal.command_state('decide', decision, subject)
        if state == 'not-attempted':
            if not advance:
                answer['state'] = 'decision-not-attempted'
                return answer
            frame = transport.execute('decide', decision, subject, bearer_token=token)
            observed = self._frame('decide', decision, frame)
        else:
            observed = self._read_request('decide', decision.idempotency_key, subject, token)
        answer['decision'] = observed
        # An independently observed historic approval is not a current permit.
        # Original consumer native tx still checks revocation/dependency/expiry.
        if observed['state'] != 'observed':
            return answer
        consume = self._consume_command(decision, key, observed)
        state = transport.journal.command_state('consume', consume, subject)
        if state == 'not-attempted':
            if not advance:
                answer['state'] = 'publication-not-attempted'
                return answer
            frame = transport.execute('consume', consume, subject)
            publication = self._frame('consume', consume, frame)
        else:
            publication = self._read_request('consume', key, subject, token)
        answer.update(publication=publication, state='published' if publication['state'] == 'observed' else 'unknown')
        return answer

    def dispatch(self, route, body, token):
        with self._lock:
            parsed = None
            if route[0] == 'operation':
                parsed = _wire_command(route[1], body)
            elif route[0] == 'chain-start':
                if type(body) is not dict or set(body) != {'decisionCommand', 'consumeIdempotencyKey'}:
                    _http_reject(400, 'RENEWAL_HTTP_EXACT_CHAIN_REQUIRED')
                parsed = _wire_command('decide', body['decisionCommand'])
                if parsed.decision != 'approved':
                    _http_reject(400, 'RENEWAL_CHAIN_EXPLICIT_APPROVAL_REQUIRED')
                # Original command parser validates the common key contract.
                _wire_command('decide', {**parsed.canonical_payload(), 'idempotencyKey': body['consumeIdempotencyKey']})
                if body['consumeIdempotencyKey'] == parsed.idempotency_key:
                    _http_reject(400, 'RENEWAL_CHAIN_DISTINCT_KEYS_REQUIRED')
            elif route[0] == 'chain-continue':
                if type(body) is not dict or set(body) != {'decisionIdempotencyKey'}:
                    _http_reject(400, 'RENEWAL_HTTP_EXACT_CHAIN_REQUIRED')
            if load_gateway_config(self.config.path) != self.config:
                raise RenewalTransportBlocked('RENEWAL_GATEWAY_CONFIG_DRIFTED')
            checker = relay_current_checker(self.config, token)
            subject = checker.subject
            if route[0] == 'status':
                return {'schemaVersion': 'aos.budget-policy-renewal.gateway-status/v1',
                    'tenant': {'orgId': 'org-org', 'projectId': 'dev-project'},
                    'writerEnabled': self.config.writer_enabled,
                    'state': 'configured' if self.config.writer_enabled else 'closed',
                    'approvalVerified': False, 'activationEligible': False}
            if route[0] == 'operation':
                frame = self._available(write=True).execute(route[1], parsed, subject,
                    bearer_token=token if route[1] in {'decide', 'revoke'} else None)
                return self._frame(route[1], parsed, frame)
            if route[0] == 'request':
                return self._read_request(route[1], route[2], subject, token)
            if route[0] == 'history':
                records = self._available().journal.list_requests(subject)
                records.sort(key=lambda item: (item[0], item[1].idempotency_key))
                offset = route[1] if len(route) > 1 else 0
                page = records[offset:offset + 5]
                return {'schemaVersion': 'aos.budget-policy-renewal.gateway-history/v1',
                    'items': [self._read_request(op, c.idempotency_key, subject, token) for op, c in page],
                    'nextPage': offset + 5 if offset + 5 < len(records) else None,
                    'activationEligible': False, 'approvalVerified': False}
            if route[0] == 'chain-start':
                transport = self._available(write=True)
                is_new = transport.journal.reserve_chain(parsed, body['consumeIdempotencyKey'], subject)
                return self._chain(parsed, body['consumeIdempotencyKey'], subject, token, advance=is_new)
            decision, key = self._available(write=route[0] == 'chain-continue').journal.read_chain(route[1], subject)
            if route[0] == 'chain-continue' and body['decisionIdempotencyKey'] != decision.idempotency_key:
                _http_reject(409, 'RENEWAL_CHAIN_EXACT_INTENT_REQUIRED')
            return self._chain(decision, key, subject, token, advance=route[0] == 'chain-continue')


class RenewalGatewayApp:
    def __init__(self, config):
        self.config = config
        self.controller = RenewalGatewayController(config)

    async def __call__(self, scope, receive, send):
        import asyncio
        if scope['type'] == 'lifespan':
            while True:
                message = await receive()
                if message['type'] == 'lifespan.startup':
                    await send({'type': 'lifespan.startup.complete'})
                elif message['type'] == 'lifespan.shutdown':
                    await asyncio.to_thread(self.controller.close)
                    await send({'type': 'lifespan.shutdown.complete'})
                    return
        if scope['type'] != 'http':
            return
        status = 200
        try:
            route = _route(scope['path'], scope['method'])
            headers, token = _http_headers(scope, self.config)
            body = await _http_body(scope, headers, receive)
            value = await asyncio.to_thread(self.controller.dispatch, route, body, token)
        except RenewalHttpRejected as error:
            status, code = error.status, error.code
        except RenewalCheckerDenied as error:
            status, code = error.status, 'RENEWAL_HTTP_CHECKER_DENIED'
        except RenewalTransportConflict:
            status, code = 409, 'RENEWAL_HTTP_EXACT_INTENT_CONFLICT'
        except RenewalTransportUnknown:
            status, code = 409, 'RENEWAL_HTTP_OUTCOME_UNKNOWN_READONLY_RECONCILE'
        except RenewalTransportBlocked as error:
            # Fixed public categories only; never stringify private exceptions.
            reason = error.args[0] if len(error.args) == 1 and type(error.args[0]) is str else None
            status = 503
            code = {
                'RENEWAL_GATEWAY_CONFIG_CLOSED_OR_DRIFTED': 'RENEWAL_HTTP_CONFIG_UNAVAILABLE',
                'RENEWAL_GATEWAY_CONFIG_DRIFTED': 'RENEWAL_HTTP_CONFIG_UNAVAILABLE',
                'RENEWAL_GATEWAY_MANAGEMENT_PROCESS_UNTRUSTED': 'RENEWAL_HTTP_MANAGEMENT_UNAVAILABLE',
                'RENEWAL_GATEWAY_CHECKER_UNAVAILABLE_OR_DRIFTED': 'RENEWAL_HTTP_CHECKER_UNAVAILABLE',
            }.get(reason, 'RENEWAL_HTTP_UNAVAILABLE')
        except Exception:
            status, code = 503, 'RENEWAL_HTTP_UNAVAILABLE'
        if status != 200:
            value = {'schemaVersion': 'aos.budget-policy-renewal.gateway-error/v1',
                'code': code, 'activationEligible': False, 'approvalVerified': False}
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
        if len(raw) > 2 * 1024 * 1024:
            status = 503
            raw = b'{"code":"RENEWAL_HTTP_RESPONSE_BOUND_EXCEEDED","activationEligible":false,"approvalVerified":false}'
        await send({'type': 'http.response.start', 'status': status, 'headers': [
            (b'content-type', b'application/json; charset=utf-8'), (b'cache-control', b'no-store'),
            (b'pragma', b'no-cache'), (b'x-content-type-options', b'nosniff'),
            (b'content-length', str(len(raw)).encode('ascii'))]})
        await send({'type': 'http.response.body', 'body': raw})


def create_renewal_gateway(config_path):
    return RenewalGatewayApp(load_gateway_config(Path(config_path)))
