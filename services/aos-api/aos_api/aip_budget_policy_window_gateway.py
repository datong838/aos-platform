"""One protected native request per process; HTTP admission is a separate gate.

No provisioning, public endpoint, automatic retry or approval logic. Successful
stdout never replaces independent native READ ONLY reconciliation.
"""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
import hashlib
import io
import json
import logging
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

from aos_api.aip_budget_policy_renewal_connection import ROOT, _private_bytes, _unique
from aos_api.aip_budget_policy_renewal_process import MAX_BYTES, observe_process
from aos_api.aip_budget_policy_window_service import (
    ProtectedWindowConfig, WindowRequest, WindowService, load_protected_config,
)
from aos_api.aip_budget_policy_window_store import WindowAuthorityStore
from aos_api.aip_network_issuer_attempt import _private_directory_fd, _attempt_filename
from aos_api.aip_budget_policy_renewal_identity import _HUMAN as HUMAN
from aos_api.aip_budget_policy_renewal_gateway import (
    RenewalTransportJournal as _DirectoryLock,
    OwnedRenewalChild, _read_json, _write_json,
    _source_candidate, probe_management_process, _PROXY_ENV,
    _http_body as _read_http_body, RenewalHttpRejected,
)
from aos_api.aip_budget_policy_window_service import COMMANDS, PACKAGE_FILES as _WINDOW_PACKAGE_FILES
from aos_api.aip_budget_policy_renewal_review import BudgetPolicyRenewalCheckerView
from pydantic import SecretStr
from http.client import HTTPConnection as _WindowHTTPConnection

GATEWAY_FILES = (
    'services/aos-api/aos_api/aip_budget_policy_window_gateway.py',
    'scripts/a0v_qyh_budget_policy_window.py',
    'services/aos-api/aos_api/aip_budget_policy_renewal_process.py',
    'services/aos-api/aos_api/aip_budget_policy_renewal_gateway.py',
)
_HASH = re.compile(r'^[0-9a-f]{64}$')


class WindowProtocolBlocked(ValueError):
    pass


@dataclass(frozen=True)
class ProtectedWindowGatewayConfig:
    path: Path
    content_sha256: str
    enabled: bool
    service: ProtectedWindowConfig
    attempt_directory: Path
    package_sources: tuple[tuple[str, str], ...]


def _object(raw):
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    if type(value) is not dict:
        raise ValueError()
    return value


def decode_window_request(raw):
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
            raise ValueError()
        return WindowRequest.model_validate(_object(raw))
    except Exception:
        raise WindowProtocolBlocked('POLICY_WINDOW_WIRE_INVALID') from None


def load_gateway_config(path):
    try:
        raw = _private_bytes(path)
        value = _object(raw)
        if (set(value) != {'schemaVersion', 'enabled', 'serviceConfigPath',
                'serviceConfigSha256', 'attemptDirectory', 'packageSources'}
                or value['schemaVersion'] != 'aos.budget-policy-window.process-gateway/v1'
                or type(value['enabled']) is not bool
                or type(value['serviceConfigPath']) is not str
                or type(value['attemptDirectory']) is not str
                or type(value['serviceConfigSha256']) is not str
                or not _HASH.fullmatch(value['serviceConfigSha256'])
                or type(value['packageSources']) is not dict
                or set(value['packageSources']) != set(GATEWAY_FILES)):
            raise ValueError()
        for relative, digest in value['packageSources'].items():
            source = ROOT/relative
            if (type(digest) is not str or not _HASH.fullmatch(digest)
                    or source.resolve(strict=True) != source or not source.is_file()
                    or hashlib.sha256(source.read_bytes()).hexdigest() != digest):
                raise ValueError()
        service = load_protected_config(Path(value['serviceConfigPath']))
        if service.content_sha256 != value['serviceConfigSha256']:
            raise ValueError()
        directory = Path(value['attemptDirectory'])
        if not directory.is_absolute() or directory.resolve(strict=True) != directory:
            raise ValueError()
        fd = _private_directory_fd(directory)
        os.close(fd)
        return ProtectedWindowGatewayConfig(Path(path), hashlib.sha256(raw).hexdigest(),
            value['enabled'], service, directory, tuple(sorted(value['packageSources'].items())))
    except Exception:
        raise WindowProtocolBlocked('POLICY_WINDOW_PRIVATE_GATEWAY_REQUIRED') from None


def _fresh_enabled(config):
    if (type(config) is not ProtectedWindowGatewayConfig
            or not config.enabled or not config.service.enabled
            or load_gateway_config(config.path) != config):
        raise WindowProtocolBlocked('POLICY_WINDOW_GATEWAY_CLOSED_OR_DRIFTED')


def _frame(request, result, *, reconciliation=False):
    """Only the existing Owner validates native receipts and their exact links."""
    request = request.revalidated()
    if type(result) is not dict or result.get('activationEligible') is not False:
        raise WindowProtocolBlocked('POLICY_WINDOW_FALSE_ADMISSION_REQUIRED')
    if not reconciliation and type(result) is dict and result.get('status') in {'blocked', 'conflict', 'unresolved'}:
        expected = dict(operation=request.operation, requestHash=request.command.request_hash,
            status=result['status'], activationEligible=False)
        if result != expected:
            # Native reconcile's unresolved result has no operation/hash fields.
            WindowAuthorityStore.validate_result(result, request.command, reconcile=True)
    else:
        WindowAuthorityStore.validate_result(result, request.command,
            reconcile=reconciliation or (type(result) is dict and 'receipt' in result))
    return dict(schemaVersion=1, operation=request.operation, requestHash=request.command.request_hash,
        activationEligible=False, result=result)


def _valid_child_frame(request, raw):
    try:
        value = _object(raw)
        if (set(value) != {'schemaVersion', 'operation', 'requestHash', 'activationEligible', 'result'}
                or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
                or value['activationEligible'] is not False
                or value != _frame(request, value['result'], reconciliation=request.mode == 'reconcile')):
            raise ValueError()
        return True
    except Exception:
        return False


def run_window_process(config_path, raw, *, timeout=15):
    """Return an owned handle on observation expiry; never restart or reexecute."""
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 60:
        raise WindowProtocolBlocked('POLICY_WINDOW_PARENT_DEADLINE_REQUIRED')
    request = decode_window_request(raw)
    config = load_gateway_config(config_path)
    _fresh_enabled(config)
    result = dict(transportStatus='spawn-unknown', exitCode=None, nativeObservation=None,
        operation=request.operation, requestHash=request.command.request_hash, activationEligible=False)
    try:
        child = subprocess.Popen([sys.executable, '-m', 'aos_api.aip_budget_policy_window_gateway',
            '--config', str(config.path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception:
        return result
    try:
        state, stdout, stderr = observe_process(child, raw, timeout)
    except Exception:
        state, stdout, stderr = 'unknown', None, None
    if state != 'terminal':
        result.update(transportStatus=state, process=child)
        return result
    result.update(exitCode=child.returncode, transportStatus='terminal-invalid')
    if (type(stdout) is bytes and type(stderr) is bytes and len(stdout) <= MAX_BYTES
            and len(stderr) <= MAX_BYTES and child.returncode == 0 and _valid_child_frame(request, stdout)):
        result['transportStatus'] = 'terminal-valid'
    # Even valid stdout proves only framing. A failed transport is retained as
    # failed while a separate read may still locate the original committed work.
    try:
        _fresh_enabled(config)
        observation = WindowService(config.service, config.attempt_directory).reconcile(request)
        result['nativeObservation'] = _frame(request, observation, reconciliation=True)
    except Exception:
        pass
    return result


MAX_JOURNAL_ENTRIES = 4096
_TRANSPORT_NAMESPACE = 'aos.budget-policy-window.transport/v1'


class WindowTransportBlocked(ValueError):
    pass


class WindowTransportUnknown(WindowTransportBlocked):
    pass


class WindowTransportConflict(WindowTransportBlocked):
    pass


def _transport_filename(operation, key):
    return _attempt_filename([_TRANSPORT_NAMESPACE, 'org-org', 'dev-project', operation, key]).removesuffix('.json')+'.window.json'


def _transport_identity(operation, key, subject):
    if (type(operation) is not str or operation not in COMMANDS or type(subject) is not str or subject != HUMAN
            or type(key) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,119}', key)):
        raise WindowTransportBlocked('POLICY_WINDOW_EXACT_TRANSPORT_IDENTITY_REQUIRED')


class WindowTransportJournal:
    """Immutable attempted commands, not authenticated identities or approvals."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self._persistence = _DirectoryLock(self.directory)

    @staticmethod
    def _inventory(fd):
        entries = os.listdir(fd)
        if len(entries) > MAX_JOURNAL_ENTRIES or any(name != '.gateway.lock' and
                not re.fullmatch(r'[0-9a-f]{64}\.window\.json', name) for name in entries):
            raise WindowTransportUnknown('POLICY_WINDOW_TRANSPORT_JOURNAL_UNTRUSTED')
        return entries

    @staticmethod
    def _parse(value, name):
        try:
            if (type(value) is not dict or set(value) != {'schemaVersion', 'state', 'operation',
                    'principalSubject', 'command', 'requestHash'}
                    or type(value['schemaVersion']) is not int or value['schemaVersion'] != 1
                    or value['state'] != 'ATTEMPTED' or value['principalSubject'] != HUMAN):
                raise ValueError()
            command = COMMANDS[value['operation']].model_validate(value['command'])
            _transport_identity(value['operation'], command.idempotency_key, value['principalSubject'])
            if (command.canonical_payload() != value['command'] or command.request_hash != value['requestHash']
                    or name != _transport_filename(value['operation'], command.idempotency_key)):
                raise ValueError()
            return command
        except Exception:
            raise WindowTransportUnknown('POLICY_WINDOW_TRANSPORT_JOURNAL_UNTRUSTED') from None

    def admit(self, request, subject):
        if type(request) is not WindowRequest or request.mode != 'execute':
            raise WindowTransportBlocked('POLICY_WINDOW_EXACT_EXECUTE_REQUIRED')
        try:
            request = request.revalidated()
            command = request.command
            _transport_identity(request.operation, command.idempotency_key, subject)
            name = _transport_filename(request.operation, command.idempotency_key)
            with self._persistence._locked() as fd:
                entries = self._inventory(fd)
                if name in entries:
                    original = self._parse(_read_json(fd, name), name)
                    if original.canonical_payload() != command.canonical_payload():
                        raise WindowTransportConflict('POLICY_WINDOW_EXACT_TRANSPORT_CONFLICT')
                    return False
                # A fresh key is not permission to replay an unsettled intent.
                # Reuse Owner command hashes; do not recreate approval logic.
                for previous_name in entries:
                    if previous_name == '.gateway.lock':
                        continue
                    previous = self._parse(_read_json(fd, previous_name), previous_name)
                    if previous.operation != command.operation:
                        continue
                    duplicate = (previous.request_hash == command.request_hash if command.operation == 'propose'
                        else previous.proposal_id == command.proposal_id)
                    if duplicate:
                        raise WindowTransportConflict('POLICY_WINDOW_ORIGINAL_REQUEST_KEY_REQUIRED')
                if len(entries) >= MAX_JOURNAL_ENTRIES:
                    raise WindowTransportBlocked('POLICY_WINDOW_TRANSPORT_JOURNAL_CAPACITY')
                _write_json(fd, name, dict(schemaVersion=1, state='ATTEMPTED', operation=request.operation,
                    principalSubject=subject, command=command.canonical_payload(), requestHash=command.request_hash))
                return True
        except WindowTransportBlocked:
            raise
        except Exception:
            raise WindowTransportUnknown('POLICY_WINDOW_TRANSPORT_PERSISTENCE_UNKNOWN') from None

    def restore(self, operation, key, subject):
        _transport_identity(operation, key, subject)
        name = _transport_filename(operation, key)
        try:
            with self._persistence._locked() as fd:
                self._inventory(fd)
                return self._parse(_read_json(fd, name), name)
        except WindowTransportBlocked:
            raise
        except Exception:
            raise WindowTransportUnknown('POLICY_WINDOW_TRANSPORT_JOURNAL_UNTRUSTED') from None

    def history(self, subject):
        if type(subject) is not str or subject != HUMAN:
            raise WindowTransportBlocked('POLICY_WINDOW_EXACT_TRANSPORT_IDENTITY_REQUIRED')
        try:
            result = []
            with self._persistence._locked() as fd:
                for name in self._inventory(fd):
                    if name == '.gateway.lock':
                        continue
                    command = self._parse(_read_json(fd, name), name)
                    result.append(dict(operation=command.operation, idempotencyKey=command.idempotency_key,
                        requestHash=command.request_hash))
            return sorted(result, key=lambda item: (item['operation'], item['idempotencyKey']))
        except WindowTransportBlocked:
            raise
        except Exception:
            raise WindowTransportUnknown('POLICY_WINDOW_TRANSPORT_JOURNAL_UNTRUSTED') from None


class WindowTransport:
    """Private serial component. HTTP must first authenticate the current checker.

    A subject string, journal or typed request never proves authentication.
    Native purpose/issuer authentication is still required by WindowService.
    """
    def __init__(self, journal, config_path, *, maximum_children=8):
        if (type(journal) is not WindowTransportJournal or type(maximum_children) is not int
                or not 1 <= maximum_children <= 32):
            raise WindowTransportBlocked('POLICY_WINDOW_PROTECTED_TRANSPORT_REQUIRED')
        config = load_gateway_config(config_path)
        if (not journal.directory.is_absolute() or journal.directory.resolve(strict=True) != journal.directory
                or journal.directory == config.attempt_directory):
            raise WindowTransportBlocked('POLICY_WINDOW_SEPARATE_TRANSPORT_JOURNAL_REQUIRED')
        fd = _private_directory_fd(journal.directory)
        os.close(fd)
        self.config, self.journal = config, journal
        self.maximum_children = maximum_children
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._children = {}
        self._monitor = None
        self._closing = False

    @staticmethod
    def _request(operation, command, token, mode):
        fields = dict(schemaVersion=1, operation=operation, command=command, mode=mode)
        if operation in {'decide', 'revoke'}:
            fields['bearerToken'] = token
        elif token is not None:
            raise WindowTransportBlocked('POLICY_WINDOW_MACHINE_TOKEN_FORBIDDEN')
        try:
            return WindowRequest.model_validate(fields)
        except Exception:
            raise WindowTransportBlocked('POLICY_WINDOW_EXACT_TRANSPORT_REQUEST_REQUIRED') from None

    @staticmethod
    def _unknown(request):
        return dict(status='unknown', operation=request.operation, requestHash=request.command.request_hash,
            activationEligible=False)

    def _reconcile(self, request):
        try:
            _fresh_enabled(self.config)
            result = WindowService(self.config.service, self.config.attempt_directory).reconcile(request)
            return _frame(request, result, reconciliation=True)
        except Exception:
            return self._unknown(request)

    def _accept(self, request, value):
        if type(value) is not dict:
            return self._unknown(request)
        if 'process' in value:
            process = value['process']
            if type(process) is not subprocess.Popen:
                return self._unknown(request)
            key = (request.operation, request.command.idempotency_key)
            # Keep ownership even if nonblocking pipe setup fails. Monitoring
            # may retry observation of this same handle, never its execution.
            self._children[key] = process
            try:
                child = OwnedRenewalChild(process)
                child.finish_incomplete_input()
                self._children[key] = child
            except Exception:
                pass
            if self._monitor is None or not self._monitor.is_alive():
                self._monitor = threading.Thread(target=self._monitor_children, daemon=True,
                    name='budget-policy-window-owned-children')
                self._monitor.start()
            self._wake.set()
            return self._unknown(request)
        try:
            observation = value['nativeObservation']
            expected = _frame(request, observation['result'], reconciliation=True)
            if (type(observation['schemaVersion']) is not int or observation['schemaVersion'] != 1
                    or observation.get('activationEligible') is not False or observation != expected):
                raise ValueError()
            return expected
        except Exception:
            return self._unknown(request)

    def execute(self, request, subject):
        if type(request) is not WindowRequest or request.mode != 'execute':
            raise WindowTransportBlocked('POLICY_WINDOW_EXACT_EXECUTE_REQUIRED')
        request = request.revalidated()
        _transport_identity(request.operation, request.command.idempotency_key, subject)
        with self._lock:
            if self._closing or len(self._children) >= self.maximum_children:
                raise WindowTransportBlocked('POLICY_WINDOW_TRANSPORT_CLOSED_OR_CAPACITY')
            _fresh_enabled(self.config)
            if not self.journal.admit(request, subject):
                restored = self._request(request.operation, request.command, request.bearer_token, 'reconcile')
                return self._reconcile(restored)
            # The immutable command is durable before any child or stdin exists.
            # This transient byte string is never stored on the transport object.
            try:
                body = request.model_dump(mode='json', by_alias=True, exclude={'bearer_token'})
                if request.bearer_token is not None:
                    body['bearerToken'] = request.bearer_token.get_secret_value()
                raw = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
                return self._accept(request, run_window_process(self.config.path, raw))
            except Exception:
                return self._unknown(request)

    def reconcile(self, operation, key, subject, *, bearer_token=None):
        command = self.journal.restore(operation, key, subject)
        request = self._request(operation, command, bearer_token, 'reconcile')
        with self._lock:
            return self._reconcile(request)

    def _monitor_children(self):
        while True:
            with self._lock:
                for key, child in list(self._children.items()):
                    try:
                        if type(child) is subprocess.Popen:
                            child = OwnedRenewalChild(child)
                            child.finish_incomplete_input()
                            self._children[key] = child
                        if child.drain():
                            del self._children[key]
                    except Exception:
                        # Failed observation cannot prove termination.
                        pass
                if not self._children:
                    self._monitor = None
                    return
            self._wake.wait(.05)
            self._wake.clear()

    def close(self):
        with self._lock:
            self._closing = True
            monitor = self._monitor
        self._wake.set()
        if monitor is not None:
            monitor.join(timeout=.2)


HTTP_PORT = 18468
_HTTP_PREFIX = '/v1/aip/budget-policy-window'
_WEB_ORIGIN = 'http://127.0.0.1:18434'
_MANAGEMENT_ORIGIN = 'http://127.0.0.1:18080'
HTTP_SOURCES = tuple(sorted(set(GATEWAY_FILES) | set(_WINDOW_PACKAGE_FILES) | {
    'services/aos-api/aos_api/aip_budget_policy_renewal_review.py',
    'services/aos-api/aos_api/routers/aip_model_governance_policies.py',
}))


class WindowHttpUnavailable(ValueError):
    pass


class WindowHttpDenied(ValueError):
    def __init__(self, status):
        self.status = status
        super().__init__('POLICY_WINDOW_CURRENT_CHECKER_DENIED')


class WindowHttpRejected(ValueError):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


@dataclass(frozen=True)
class ProtectedWindowHttpConfig:
    path: Path
    content_sha256: str
    web_origin: str
    management_origin: str
    source_root: Path
    management_process: tuple[tuple[str, object], ...]
    writer_enabled: bool
    process_gateway: ProtectedWindowGatewayConfig | None
    journal_directory: Path | None


def load_window_http_config(path):
    try:
        raw = _private_bytes(path)
        value = _object(raw)
        required = {'schemaVersion', 'orgId', 'projectId', 'webOrigin', 'managementOrigin',
            'sourceCandidatePath', 'sourceCandidateSha256', 'sourceManifestPath',
            'sourceManifestSha256', 'managementProcess', 'gatewaySources'}
        writer_keys = {'processGatewayConfigPath', 'processGatewayConfigSha256', 'journalDirectory'}
        if (not required.issubset(value) or set(value)-required-writer_keys-{'writerEnabled'}
                or value['schemaVersion'] != 'aos.budget-policy-window.http-gateway/v1'
                or value['orgId'] != 'org-org' or value['projectId'] != 'dev-project'
                or value['webOrigin'] != _WEB_ORIGIN or value['managementOrigin'] != _MANAGEMENT_ORIGIN
                or type(value.get('writerEnabled', False)) is not bool
                or type(value['gatewaySources']) is not dict or set(value['gatewaySources']) != set(HTTP_SOURCES)):
            raise ValueError()
        for relative, digest in value['gatewaySources'].items():
            source = ROOT/relative
            if (type(digest) is not str or not _HASH.fullmatch(digest)
                    or source.resolve(strict=True) != source or not source.is_file()
                    or hashlib.sha256(source.read_bytes()).hexdigest() != digest):
                raise ValueError()
        source_root = _source_candidate(value)
        process = value['managementProcess']
        if (type(process) is not dict or set(process) != {'pid', 'startIdentity', 'uid', 'cwd', 'command'}
                or type(process['pid']) is not int or process['pid'] <= 0
                or type(process['uid']) is not int or process['uid'] != os.geteuid()
                or process['cwd'] != str(source_root)
                or any(type(process[k]) is not str or not 0 < len(process[k]) <= 16384 for k in ('startIdentity', 'cwd', 'command'))
                or probe_management_process(process['pid'], 18080) != process):
            raise ValueError()
        present = set(value) & writer_keys
        if (present and present != writer_keys) or (value.get('writerEnabled', False) and not present):
            raise ValueError()
        process_gateway = None
        journal_directory = None
        if present:
            if any(type(value[k]) is not str for k in writer_keys):
                raise ValueError()
            process_gateway = load_gateway_config(Path(value['processGatewayConfigPath']))
            if (process_gateway.content_sha256 != value['processGatewayConfigSha256']
                    or (value.get('writerEnabled', False) and not (process_gateway.enabled and process_gateway.service.enabled))):
                raise ValueError()
            journal_directory = Path(value['journalDirectory'])
            if (not journal_directory.is_absolute() or journal_directory.resolve(strict=True) != journal_directory
                    or journal_directory == process_gateway.attempt_directory):
                raise ValueError()
            fd = _private_directory_fd(journal_directory)
            os.close(fd)
        if _private_bytes(path) != raw:
            raise ValueError()
        return ProtectedWindowHttpConfig(Path(path), hashlib.sha256(raw).hexdigest(), value['webOrigin'],
            value['managementOrigin'], source_root, tuple(sorted(process.items())),
            value.get('writerEnabled', False), process_gateway, journal_directory)
    except Exception:
        raise WindowHttpUnavailable('POLICY_WINDOW_HTTP_CONFIG_UNAVAILABLE') from None


def relay_window_current_checker(config, bearer_token):
    """One fixed direct-loopback current OIDC observation, never approval."""
    from datetime import datetime, timezone
    connection = None
    try:
        if (type(config) is not ProtectedWindowHttpConfig or type(bearer_token) is not SecretStr
                or any(os.environ.get(k) for k in _PROXY_ENV)
                or load_window_http_config(config.path) != config):
            raise ValueError()
        token = bearer_token.get_secret_value()
        if (not 1 <= len(token) <= 16384 or not token.isascii()
                or any(ord(c) <= 32 or ord(c) >= 127 for c in token)):
            raise ValueError()
        connection = _WindowHTTPConnection('127.0.0.1', 18080, timeout=3)
        connection.request('GET', '/v1/aip/model-governance-policies/renewal-checker', headers={
            'Authorization': 'Bearer '+token, 'X-Org-Id': 'org-org', 'X-Project-Id': 'dev-project',
            'Accept': 'application/json', 'Cache-Control': 'no-store'})
        token = None
        response = connection.getresponse()
        raw = response.read(MAX_BYTES+1)
        if load_window_http_config(config.path) != config:
            raise ValueError()
        if response.status in {401, 403}:
            raise WindowHttpDenied(response.status)
        if (response.status != 200 or len(raw) > MAX_BYTES
                or response.getheader('Content-Type', '').split(';')[0].strip().lower() != 'application/json'
                or response.getheader('Content-Encoding', 'identity') != 'identity'):
            raise ValueError()
        value = _object(raw)
        if (set(value) != {'schemaVersion', 'tenant', 'subject', 'tokenKind', 'role', 'evaluatedAt',
                'approvalVerified', 'activationEligible'} or type(value['evaluatedAt']) is not str):
            raise ValueError()
        result = BudgetPolicyRenewalCheckerView.model_validate(value)
        age = (datetime.now(timezone.utc)-result.evaluated_at).total_seconds()
        if not 0 <= age <= 30:
            raise ValueError()
        return result
    except WindowHttpDenied:
        raise
    except Exception:
        raise WindowHttpUnavailable('POLICY_WINDOW_CURRENT_CHECKER_UNAVAILABLE') from None
    finally:
        if connection is not None:
            connection.close()


def _window_http_route(path, method):
    if type(path) is not str or not path.startswith(_HTTP_PREFIX+'/'):
        raise WindowHttpRejected(404, 'POLICY_WINDOW_HTTP_ROUTE_NOT_FOUND')
    tail = path[len(_HTTP_PREFIX):]
    if tail in {'/status', '/requests'}:
        route, allowed = ('status',) if tail == '/status' else ('history',), 'GET'
    elif tail[1:] in COMMANDS:
        route, allowed = ('operation', tail[1:]), 'POST'
    elif match := re.fullmatch(r'/requests/(propose|decide|revoke|consume)/([A-Za-z0-9][A-Za-z0-9._:-]{0,119})', tail):
        route, allowed = ('request', match[1], match[2]), 'GET'
    else:
        raise WindowHttpRejected(404, 'POLICY_WINDOW_HTTP_ROUTE_NOT_FOUND')
    if method != allowed:
        raise WindowHttpRejected(405, 'POLICY_WINDOW_HTTP_METHOD_NOT_ALLOWED')
    return route


def _window_http_headers(scope, config):
    try:
        if (scope.get('scheme') != 'http' or scope.get('server') != ('127.0.0.1', HTTP_PORT)
                or not scope.get('client') or scope['client'][0] != '127.0.0.1'
                or scope.get('query_string') or scope.get('raw_path') != scope['path'].encode('ascii')
                or len(scope['headers']) > 64):
            raise ValueError()
        headers = {}
        total = 0
        for raw_key, raw_value in scope['headers']:
            key, value = raw_key.decode('ascii').lower(), raw_value.decode('latin-1')
            total += len(raw_key)+len(raw_value)
            if (key in headers or key in {'forwarded', 'cookie'} or key.startswith('x-forwarded-')
                    or total > 32768 or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                raise ValueError()
            headers[key] = value
    except Exception:
        raise WindowHttpRejected(400, 'POLICY_WINDOW_HTTP_HEADERS_INVALID') from None
    if headers.get('host') != f'127.0.0.1:{HTTP_PORT}':
        raise WindowHttpRejected(400, 'POLICY_WINDOW_HTTP_HOST_INVALID')
    if headers.get('origin') != config.web_origin:
        raise WindowHttpRejected(403, 'POLICY_WINDOW_HTTP_ORIGIN_DENIED')
    if scope['method'] == 'OPTIONS':
        return headers, None
    if headers.get('x-org-id') != 'org-org' or headers.get('x-project-id') != 'dev-project':
        raise WindowHttpRejected(403, 'POLICY_WINDOW_HTTP_TENANT_DENIED')
    auth = headers.get('authorization', '')
    if (not auth.startswith('Bearer ') or not 1 <= len(auth[7:]) <= 16384
            or not auth[7:].isascii() or any(ord(c) <= 32 or ord(c) >= 127 for c in auth[7:])):
        raise WindowHttpRejected(401, 'POLICY_WINDOW_HTTP_BEARER_REQUIRED')
    return headers, SecretStr(auth[7:])


def _window_http_command(operation, body):
    try:
        command = COMMANDS[operation].model_validate(body)
        if type(body) is not dict or set(body) != set(command.canonical_payload()):
            raise ValueError()
        return command
    except Exception:
        raise WindowHttpRejected(400, 'POLICY_WINDOW_HTTP_EXACT_COMMAND_REQUIRED') from None


def _window_http_flags():
    return dict(approvalVerified=False, activationEligible=False, nativeWriteAllowed=False, runtimeAdmissionAllowed=False)


class WindowHttpController:
    """Serial isolated parent; it never changes the formal management API."""
    def __init__(self, config):
        self.config = config
        self._lock = threading.RLock()
        self.transport = (WindowTransport(WindowTransportJournal(config.journal_directory), config.process_gateway.path)
            if config.process_gateway is not None else None)

    def _available(self, write=False):
        if load_window_http_config(self.config.path) != self.config:
            raise WindowHttpUnavailable('POLICY_WINDOW_HTTP_CONFIG_DRIFTED')
        if write and (not self.config.writer_enabled or self.transport is None):
            raise WindowHttpUnavailable('POLICY_WINDOW_HTTP_WRITER_CLOSED')

    def dispatch(self, route, body, token):
        with self._lock:
            self._available()
            checker = relay_window_current_checker(self.config, token)
            # A current checker observation is not the new budget decision.
            self._available(route[0] == 'operation')
            flags = _window_http_flags()
            if route[0] == 'status':
                return dict(schemaVersion='aos.budget-policy-window.gateway-status/v1',
                    tenant=dict(orgId='org-org', projectId='dev-project'), subject=checker.subject,
                    writerEnabled=self.config.writer_enabled, **flags)
            if self.transport is None:
                raise WindowHttpUnavailable('POLICY_WINDOW_HTTP_HISTORY_UNAVAILABLE')
            if route[0] == 'history':
                return dict(schemaVersion='aos.budget-policy-window.request-index/v1',
                    requests=self.transport.journal.history(checker.subject), **flags)
            operation = route[1]
            issuer_token = token if operation in {'decide', 'revoke'} else None
            if route[0] == 'request':
                observation = self.transport.reconcile(operation, route[2], checker.subject, bearer_token=issuer_token)
            else:
                command = _window_http_command(operation, body)
                request = self.transport._request(operation, command, issuer_token, 'execute')
                observation = self.transport.execute(request, checker.subject)
            return dict(schemaVersion='aos.budget-policy-window.gateway-observation/v1', observation=observation, **flags)

    def close(self):
        with self._lock:
            if self.transport is not None:
                self.transport.close()


class WindowGatewayApp:
    def __init__(self, config):
        self.config = config
        self.controller = WindowHttpController(config)

    async def __call__(self, scope, receive, send):
        import asyncio
        if scope['type'] == 'lifespan':
            while True:
                message = await receive()
                if message['type'] == 'lifespan.startup':
                    await send({'type':'lifespan.startup.complete'})
                elif message['type'] == 'lifespan.shutdown':
                    await asyncio.to_thread(self.controller.close)
                    await send({'type':'lifespan.shutdown.complete'})
                    return
        if scope['type'] != 'http':
            return
        status, preflight = 200, False
        response_headers = [(b'cache-control', b'no-store'), (b'pragma', b'no-cache'),
            (b'x-content-type-options', b'nosniff'), (b'vary', b'Origin')]
        try:
            requested_method = scope['method']
            if requested_method != 'OPTIONS':
                route = _window_http_route(scope['path'], requested_method)
            headers, bearer = _window_http_headers(scope, self.config)
            if requested_method == 'OPTIONS':
                if load_window_http_config(self.config.path) != self.config:
                    raise WindowHttpUnavailable('POLICY_WINDOW_HTTP_CONFIG_DRIFTED')
                desired = headers.get('access-control-request-method')
                if desired not in {'GET', 'POST'}:
                    raise WindowHttpRejected(403, 'POLICY_WINDOW_HTTP_PREFLIGHT_DENIED')
                _window_http_route(scope['path'], desired)
                requested_headers = [h.strip().lower() for h in headers.get('access-control-request-headers', '').split(',') if h.strip()]
                if (not requested_headers or len(set(requested_headers)) != len(requested_headers)
                        or set(requested_headers)-{'authorization', 'content-type', 'x-org-id', 'x-project-id'}):
                    raise WindowHttpRejected(403, 'POLICY_WINDOW_HTTP_PREFLIGHT_DENIED')
                # Reuse the GET body boundary for OPTIONS: no business input.
                read_scope = dict(scope, method='GET')
                await _read_http_body(read_scope, headers, receive)
                preflight, status = True, 204
                response_headers += [(b'access-control-allow-methods', desired.encode('ascii')),
                    (b'access-control-allow-headers', ','.join(sorted(requested_headers)).encode('ascii')),
                    (b'access-control-max-age', b'0')]
                value = None
            else:
                body = await _read_http_body(scope, headers, receive)
                # Exact wire shape is checked before any current-checker relay.
                if route[0] == 'operation':
                    _window_http_command(route[1], body)
                value = await asyncio.to_thread(self.controller.dispatch, route, body, bearer)
        except WindowHttpRejected as error:
            status, code = error.status, error.code
        except RenewalHttpRejected as error:
            status, code = error.status, 'POLICY_WINDOW_HTTP_BODY_INVALID'
        except WindowHttpDenied as error:
            status, code = error.status, 'POLICY_WINDOW_HTTP_CHECKER_DENIED'
        except WindowTransportConflict:
            status, code = 409, 'POLICY_WINDOW_HTTP_INTENT_CONFLICT'
        except WindowTransportUnknown:
            status, code = 409, 'POLICY_WINDOW_HTTP_OUTCOME_UNKNOWN_READONLY_RECONCILE'
        except Exception:
            status, code = 503, 'POLICY_WINDOW_HTTP_UNAVAILABLE'
        if status not in {200, 204}:
            value = dict(schemaVersion='aos.budget-policy-window.gateway-error/v1', code=code, **_window_http_flags())
        raw = b'' if preflight else json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
        if len(raw) > 2*1024*1024:
            status = 503
            raw = json.dumps(dict(code='POLICY_WINDOW_HTTP_RESPONSE_BOUND_EXCEEDED', **_window_http_flags()), separators=(',', ':')).encode()
        # Never reflect a supplied origin. Only the fixed deployed Web can read.
        if (b'origin', self.config.web_origin.encode()) in scope.get('headers', []) and (b'host', f'127.0.0.1:{HTTP_PORT}'.encode()) in scope.get('headers', []):
            response_headers.append((b'access-control-allow-origin', self.config.web_origin.encode()))
        response_headers += [(b'content-type', b'application/json; charset=utf-8'), (b'content-length', str(len(raw)).encode())]
        await send({'type':'http.response.start', 'status':status, 'headers':response_headers})
        await send({'type':'http.response.body', 'body':raw})


def create_window_gateway(config_path):
    return WindowGatewayApp(load_window_http_config(Path(config_path)))


def serve_main(argv=None):
    try:
        with redirect_stdout(_Discard()), redirect_stderr(_Discard()):
            parser = argparse.ArgumentParser()
            parser.add_argument('--config', required=True, type=Path)
            args = parser.parse_args(argv)
            app = create_window_gateway(args.config)
    except (Exception, SystemExit):
        print('POLICY_WINDOW_GATEWAY_STARTUP_BLOCKED', file=sys.stderr, flush=True)
        return 2
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=HTTP_PORT, workers=1, access_log=False,
        log_config=None, log_level='critical', proxy_headers=False, server_header=False)
    return 0


class _Discard(io.TextIOBase):
    def write(self, value):
        return len(value)

    def flush(self):
        pass


def main(argv=None):
    # This entry owns its serial process only. Never call main inside an API.
    original_level = logging.root.manager.disable
    try:
        with redirect_stdout(_Discard()), redirect_stderr(_Discard()):
            logging.disable(sys.maxsize)
            parser = argparse.ArgumentParser()
            parser.add_argument('--config', required=True, type=Path)
            args = parser.parse_args(argv)
            request = decode_window_request(sys.stdin.buffer.read(MAX_BYTES+1))
            config = load_gateway_config(args.config)
            _fresh_enabled(config)
            service = WindowService(config.service, config.attempt_directory)
            response = _frame(request, service.execute(request), reconciliation=request.mode == 'reconcile')
        print(json.dumps(response, ensure_ascii=False, separators=(',', ':'), allow_nan=False), flush=True)
        return 0
    except (Exception, SystemExit):
        print('POLICY_WINDOW_PRIVATE_PROCESS_BLOCKED', file=sys.stderr, flush=True)
        return 2
    finally:
        logging.disable(original_level)


if __name__ == '__main__':
    raise SystemExit(main())
