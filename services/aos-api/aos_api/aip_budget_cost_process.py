"""Finite private budget-issuer process; no provisioning or shared API secrets."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

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
    open_private_issuer_listener,
)
from aos_api.aip_private_listener import owned_private_listener
from aos_api.tenant_scope import TenantScope
from aos_api.aip_private_process import (
    validate_private_process, decode_private_request, serve_private_connection, run_private_process,
)


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
        validate_private_process(self, database_type=BudgetCostDatabaseConfig,
            service_uid=self.issuer_uid, blocked=BudgetCostIssuerBlocked,
            error_code='BUDGET_COST_PROCESS_CONFIG_REQUIRED')


def admitted_factory(config):
    base = BudgetCostConnectionFactory(config.database, config.scope)
    @contextmanager
    def connect(scope, read_only):
        with base(scope, read_only) as conn:
            require_budget_schema(conn)
            yield conn
    return connect


def decode_budget_request(raw):
    return decode_private_request(raw, request_type=BudgetCostIssuerCommand,
        blocked=BudgetCostIssuerBlocked, error_code='BUDGET_COST_WIRE_INVALID')


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
    return serve_private_connection(conn, api_uid=config.api_uid, service_uid=config.issuer_uid,
        scope=config.scope, decode=decode_budget_request,
        dispatch=lambda method, command: dispatch_budget_request(config, method, command),
        error_code='BUDGET_COST_REQUEST_BLOCKED')


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
    return run_private_process(config, listener_factory=budget_listener, serve=serve_budget_connection)
