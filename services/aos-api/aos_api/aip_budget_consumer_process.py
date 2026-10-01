"""Explicit finite private budget consumer; readiness is not business authority."""
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
import sys

from aos_api.aip_budget_consumer_connection import BudgetConsumerConfig, connect_budget_consumer
from aos_api.aip_budget_consumer_service import BudgetConsumerRequest, consume_budget_once, inquire_budget
from aos_api.aip_private_process import (
    validate_private_process, decode_private_request, serve_private_connection, run_private_process,
)
from aos_api.aip_private_listener import owned_private_listener
from aos_api.aip_network_issuer_attempt import _private_directory_fd
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.aip_network_issuer_ipc import open_private_issuer_listener
from aos_api.aip_network_consumer_config import _read_private_config
from aos_api.tenant_scope import TenantScope


class BudgetConsumerProcessBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class BudgetConsumerProcessConfig:
    database: BudgetConsumerConfig
    scope: TenantScope
    socket_path: Path
    attempt_directory: Path
    api_uid: int
    consumer_uid: int
    ipc_gid: int
    max_connections: int = 1
    accept_timeout: float = 5.0

    def __post_init__(self):
        validate_private_process(self, database_type=BudgetConsumerConfig,
            service_uid=self.consumer_uid, blocked=BudgetConsumerProcessBlocked,
            error_code='BUDGET_CONSUMER_PROCESS_CONFIG_REQUIRED')
        if self.scope.key != ('org-org', 'dev-project'):
            raise BudgetConsumerProcessBlocked('BUDGET_CONSUMER_PROCESS_CONFIG_REQUIRED')


def decode_consumer_request(raw):
    return decode_private_request(raw, request_type=BudgetConsumerRequest,
        blocked=BudgetConsumerProcessBlocked, error_code='BUDGET_CONSUMER_WIRE_INVALID')


def dispatch_consumer_request(config, method, request):
    if type(config) is not BudgetConsumerProcessConfig or type(request) is not BudgetConsumerRequest:
        raise BudgetConsumerProcessBlocked('BUDGET_CONSUMER_PROCESS_INPUT_REQUIRED')
    config.__post_init__()
    if (request.org_id, request.project_id) != config.scope.key or method not in ('execute_once', 'inquiry'):
        raise BudgetConsumerProcessBlocked('BUDGET_CONSUMER_PROCESS_SCOPE_REQUIRED')
    if method == 'inquiry':
        return inquire_budget(request, config.database)
    return consume_budget_once(request, config.database, config.attempt_directory)


def serve_consumer_connection(conn, config):
    return serve_private_connection(conn, api_uid=config.api_uid, service_uid=config.consumer_uid,
        scope=config.scope, decode=decode_consumer_request,
        dispatch=lambda method, request: dispatch_consumer_request(config, method, request),
        error_code='BUDGET_CONSUMER_REQUEST_BLOCKED')


def preflight_budget_consumer(config):
    try:
        if type(config) is not BudgetConsumerProcessConfig:
            raise ValueError()
        config.__post_init__()
        _require_external_oidc_config()
        parent = config.socket_path.parent.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or stat.S_IMODE(parent.st_mode) != 0o750
                or parent.st_uid != config.consumer_uid or parent.st_gid != config.ipc_gid):
            raise ValueError()
        try:
            config.socket_path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise ValueError()
        fd = _private_directory_fd(config.attempt_directory)
        os.close(fd)
        with connect_budget_consumer(config.database, config.scope, read_only=True):
            pass
    except Exception:
        raise BudgetConsumerProcessBlocked('BUDGET_CONSUMER_STARTUP_BLOCKED') from None
    return {'ready': True, 'businessAuthorized': False}


@contextmanager
def consumer_listener(config):
    preflight_budget_consumer(config)
    with owned_private_listener(config.socket_path, service_uid=config.consumer_uid,
            ipc_gid=config.ipc_gid, blocked=BudgetConsumerProcessBlocked,
            error_code='BUDGET_CONSUMER_SOCKET_DIRECTORY_REQUIRED',
            open_listener=lambda: open_private_issuer_listener(config.socket_path,
                api_uid=config.api_uid, issuer_uid=config.consumer_uid, ipc_gid=config.ipc_gid,
                credential_file=config.database.passfile)) as listener:
        yield listener


def run_budget_consumer(config):
    return run_private_process(config, listener_factory=consumer_listener, serve=serve_consumer_connection)


def load_budget_consumer_config(path):
    try:
        data = _read_private_config(path)
        if (type(data) is not dict or set(data) != {'schemaVersion', 'tenant', 'socketPath',
                'apiUid', 'consumerUid', 'ipcGid', 'database', 'attemptDirectory', 'maxConnections', 'acceptTimeout'}
                or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1
                or type(data['tenant']) is not dict or set(data['tenant']) != {'orgId', 'projectId'}
                or type(data['database']) is not dict
                or set(data['database']) != {'host', 'port', 'database', 'passfile'}):
            raise ValueError()
        return BudgetConsumerProcessConfig(BudgetConsumerConfig(**data['database']),
            TenantScope(data['tenant']['orgId'], data['tenant']['projectId']),
            data['socketPath'], data['attemptDirectory'], data['apiUid'], data['consumerUid'],
            data['ipcGid'], data['maxConnections'], data['acceptTimeout'])
    except Exception:
        raise BudgetConsumerProcessBlocked('BUDGET_CONSUMER_PRIVATE_CONFIG_INVALID') from None


def main(argv=None):
    # Reuse the parser which deliberately never echoes invalid option values.
    from aos_api.aip_network_consumer_cli import _Parser, _Once
    parser = _Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--mode', choices=('check', 'serve'), required=True, action=_Once)
    parser.add_argument('--config', required=True, action=_Once)
    try:
        args = parser.parse_args(argv)
    except ValueError:
        print('BUDGET_CONSUMER_ENTRY_ARGUMENTS_INVALID', file=sys.stderr)
        return 2
    try:
        config = load_budget_consumer_config(args.config)
        if args.mode == 'check':
            result = {'mode': 'check', **preflight_budget_consumer(config)}
        else:
            result = {'mode': 'serve', **run_budget_consumer(config), 'businessAuthorized': False}
    except Exception:
        print('BUDGET_CONSUMER_ENTRY_BLOCKED', file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
