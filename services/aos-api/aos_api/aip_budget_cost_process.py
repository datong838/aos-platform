"""Finite private budget-issuer process; no provisioning or shared API secrets."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import struct

from aos_api.aip_budget_cost_connection import BudgetCostDatabaseConfig, BudgetCostConnectionFactory
from aos_api.aip_budget_cost_issuer import (
    BudgetCostIssuer, BudgetCostIssuerCommand, BudgetCostIssuerBlocked, _authenticate, _proposal,
)
from aos_api.aip_budget_activation_store import _member
from aos_api.aip_budget_cost_preflight import require_budget_schema
from aos_api.aip_network_issuer_attempt import (
    AttemptReceipt, AttemptAlreadyRecorded, AttemptConflict, AttemptUnknown,
    _private_directory_fd, _reserve_attempt_receipt,
)
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.aip_network_issuer_ipc import (
    MAX_ISSUER_FRAME_BYTES, _unique_pairs, _invalid_constant, read_issuer_frame,
    require_issuer_peer, open_private_issuer_listener,
)
from aos_api.aip_private_listener import owned_private_listener
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class BudgetCostProcessConfig:
    database: BudgetCostDatabaseConfig
    scope: TenantScope
    socket_path: Path
    attempt_directory: Path
    api_uid: int
    issuer_uid: int
    ipc_gid: int
    max_connections: int = 1
    accept_timeout: float = 5.0

    def __post_init__(self):
        try:
            if (type(self.database) is not BudgetCostDatabaseConfig or type(self.scope) is not TenantScope
                    or any(type(v) is not int or v <= 0 for v in (self.api_uid, self.issuer_uid, self.ipc_gid))
                    or self.api_uid == self.issuer_uid or self.issuer_uid != os.geteuid()
                    or self.ipc_gid != os.getegid()
                    or type(self.max_connections) is not int or not 1 <= self.max_connections <= 64
                    or type(self.accept_timeout) not in (int, float)
                    or not math.isfinite(self.accept_timeout) or not 0 < self.accept_timeout <= 30):
                raise ValueError()
            for name in ('socket_path', 'attempt_directory'):
                value = Path(getattr(self, name))
                if not value.is_absolute():
                    raise ValueError()
                if name == 'socket_path' and (len(os.fsencode(value)) > 103 or '\0' in str(value)):
                    raise ValueError('macOS Unix socket path exceeds kernel limit')
                object.__setattr__(self, name, value)
            self.database.__post_init__()
            self.scope.__post_init__()
        except Exception:
            raise BudgetCostIssuerBlocked('BUDGET_COST_PROCESS_CONFIG_REQUIRED') from None


def admitted_factory(config):
    base = BudgetCostConnectionFactory(config.database, config.scope)
    @contextmanager
    def connect(scope, read_only):
        with base(scope, read_only) as conn:
            require_budget_schema(conn)
            yield conn
    return connect


def decode_budget_request(raw):
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_ISSUER_FRAME_BYTES:
            raise ValueError()
        frame = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs,
                           parse_constant=_invalid_constant)
        if (type(frame) is not dict or set(frame) != {'schemaVersion', 'method', 'payload'}
                or type(frame['schemaVersion']) is not int or frame['schemaVersion'] != 1
                or frame['method'] not in ('execute_once', 'inquiry') or type(frame['payload']) is not dict):
            raise ValueError()
        command = BudgetCostIssuerCommand.model_validate(frame['payload'])
        return frame['method'], command
    except Exception:
        raise BudgetCostIssuerBlocked('BUDGET_COST_WIRE_INVALID') from None


def dispatch_budget_request(config, method, command):
    if type(config) is not BudgetCostProcessConfig:
        raise BudgetCostIssuerBlocked('BUDGET_COST_PROCESS_CONFIG_REQUIRED')
    config.__post_init__()
    c, principal, scope = _authenticate(command)
    if scope != config.scope or method not in ('execute_once', 'inquiry'):
        raise BudgetCostIssuerBlocked('BUDGET_COST_PROCESS_SCOPE_REQUIRED')
    factory = admitted_factory(config)
    issuer = BudgetCostIssuer(factory)
    if method == 'inquiry':
        return issuer.inquire(c)
    # Authenticate/current membership before reserving any local attempt. This
    # read does not replace the write transaction's later authority revalidation.
    with factory(scope, True) as conn:
        _member(conn, scope, principal.subject, label='REVIEWER', lock=False)
        _, proposal = _proposal(conn, scope, c)
        if (principal.subject not in {proposal.maker_subject, proposal.checker_subject}
                or (c.operation == 'decide' and principal.subject != proposal.checker_subject)):
            raise BudgetCostIssuerBlocked('BUDGET_COST_REVIEWER_REQUIRED')
    namespace = 'budget-cost/v1/' + hashlib.sha256(json.dumps(
        [principal.subject, c.operation], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    receipt = AttemptReceipt(c.org_id, c.project_id, c.proposal_id,
                             c.idempotency_key, c.request_hash, principal.subject)
    try:
        _reserve_attempt_receipt(config.attempt_directory, receipt, namespace=namespace)
    except AttemptAlreadyRecorded:
        return issuer.inquire(c)
    except AttemptConflict:
        return {'status': 'conflict'}
    except AttemptUnknown:
        return {'status': 'unresolved'}
    try:
        issuer.execute(c)
    except Exception:
        # Includes post-commit readback failure: never execute a second time.
        pass
    try:
        return issuer.inquire(c)
    except Exception:
        return {'status': 'unresolved'}


def serve_budget_connection(conn, config):
    response = {'schemaVersion': 1, 'status': 'blocked', 'code': 'BUDGET_COST_REQUEST_BLOCKED'}
    processed = False
    try:
        require_issuer_peer(conn, api_uid=config.api_uid, issuer_uid=config.issuer_uid)
        method, command = decode_budget_request(read_issuer_frame(conn))
        if (command.org_id, command.project_id) != config.scope.key:
            raise BudgetCostIssuerBlocked('BUDGET_COST_PROCESS_SCOPE_REQUIRED')
        response = {'schemaVersion': 1, **dispatch_budget_request(config, method, command)}
        processed = True
    except Exception:
        # Never return bearer tokens, raw SQL, tenant data or exception text.
        pass
    try:
        body = json.dumps(response, separators=(',', ':')).encode()
        conn.settimeout(5)
        conn.sendall(struct.pack('>I', len(body)) + body)
    except OSError:
        processed = False
    finally:
        conn.close()
    return processed


@contextmanager
def budget_listener(config):
    if type(config) is not BudgetCostProcessConfig:
        raise BudgetCostIssuerBlocked('BUDGET_COST_PROCESS_CONFIG_REQUIRED')
    config.__post_init__()
    _require_external_oidc_config()
    fd = _private_directory_fd(config.attempt_directory)
    os.close(fd)
    with admitted_factory(config)(config.scope, True):
        pass
    with owned_private_listener(config.socket_path, service_uid=config.issuer_uid,
            ipc_gid=config.ipc_gid, blocked=BudgetCostIssuerBlocked,
            error_code='BUDGET_COST_SOCKET_DIRECTORY_REQUIRED',
            open_listener=lambda: open_private_issuer_listener(config.socket_path,
                api_uid=config.api_uid, issuer_uid=config.issuer_uid, ipc_gid=config.ipc_gid,
                credential_file=config.database.passfile)) as listener:
        yield listener


def run_budget_process(config):
    accepted = processed = 0
    with budget_listener(config) as listener:
        listener.settimeout(config.accept_timeout)
        for _ in range(config.max_connections):
            try:
                conn, _ = listener.accept()
            except TimeoutError:
                break
            accepted += 1
            try:
                processed += int(serve_budget_connection(conn, config))
            finally:
                conn.close()
    return {'accepted': accepted, 'processed': processed}
