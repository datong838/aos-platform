"""Finite accept loop for one configured tenant; no deployment authority implied."""
from contextlib import contextmanager
from dataclasses import dataclass
import math
import os
from pathlib import Path

from aos_api.tenant_scope import TenantScope
from aos_api.aip_network_issuer_connection import (
    IssuerDatabaseConfig, connect_issuer_read_only, connect_issuer_decision,
)
from aos_api.aip_network_issuer_ipc import (
    IssuerProtocolBlocked, open_private_issuer_listener, serve_one_issuer_connection,
)
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.aip_network_issuer_attempt import _private_directory_fd
from aos_api.aip_private_listener import owned_private_listener


@dataclass(frozen=True)
class IssuerProcessConfig:
    socket_path: Path
    api_uid: int
    issuer_uid: int
    ipc_gid: int
    database: IssuerDatabaseConfig
    scope: TenantScope
    attempt_directory: Path
    max_connections: int = 1
    accept_timeout: float = 5.0

    def __post_init__(self):
        try:
            if (type(self.database) is not IssuerDatabaseConfig or type(self.scope) is not TenantScope
                    or any(type(v) is not int or v <= 0 for v in (self.api_uid, self.issuer_uid, self.ipc_gid))
                    or self.api_uid == self.issuer_uid or self.issuer_uid != os.geteuid()
                    or self.ipc_gid != os.getegid()
                    or type(self.max_connections) is not int or not 1 <= self.max_connections <= 64
                    or type(self.accept_timeout) not in (int, float)
                    or not math.isfinite(self.accept_timeout) or not 0 < self.accept_timeout <= 30):
                raise ValueError()
            path, attempt = Path(self.socket_path), Path(self.attempt_directory)
            if not path.is_absolute() or not attempt.is_absolute() or not self.database.passfile.is_absolute():
                raise ValueError()
            self.scope.__post_init__()
            self.database.__post_init__()
            object.__setattr__(self, 'socket_path', path)
            object.__setattr__(self, 'attempt_directory', attempt)
        except Exception:
            raise IssuerProtocolBlocked('ISSUER_PROCESS_CONFIG_REQUIRED') from None


@contextmanager
def issuer_listener(config: IssuerProcessConfig):
    if type(config) is not IssuerProcessConfig:
        raise IssuerProtocolBlocked('ISSUER_PROCESS_CONFIG_REQUIRED')
    config.__post_init__()
    try:
        _require_external_oidc_config()
        fd = _private_directory_fd(config.attempt_directory)
        os.close(fd)
    except Exception:
        raise IssuerProtocolBlocked('ISSUER_PROCESS_PREFLIGHT_REQUIRED') from None
    with owned_private_listener(config.socket_path, service_uid=config.issuer_uid,
            ipc_gid=config.ipc_gid, blocked=IssuerProtocolBlocked,
            error_code='ISSUER_SOCKET_DIRECTORY_REQUIRED',
            open_listener=lambda: open_private_issuer_listener(config.socket_path,
                api_uid=config.api_uid, issuer_uid=config.issuer_uid, ipc_gid=config.ipc_gid,
                credential_file=config.database.passfile)) as listener:
        yield listener


def run_issuer_process(config: IssuerProcessConfig) -> dict[str, int]:
    accepted = processed = 0
    def decision_connection(scope):
        if type(scope) is not TenantScope or scope != config.scope:
            raise IssuerProtocolBlocked('ISSUER_PROCESS_SCOPE_REQUIRED')
        return connect_issuer_decision(config.database, config.scope)
    with issuer_listener(config) as listener:
        listener.settimeout(config.accept_timeout)
        for _ in range(config.max_connections):
            try:
                conn, _ = listener.accept()
            except TimeoutError:
                break
            accepted += 1
            try:
                processed += int(serve_one_issuer_connection(conn,
                    api_uid=config.api_uid, issuer_uid=config.issuer_uid,
                    attempt_directory=config.attempt_directory, expected_database=config.database.database,
                    expected_scope=config.scope,
                    read_connect_factory=lambda: connect_issuer_read_only(config.database, config.scope),
                    decision_connect_factory=decision_connection))
            finally:
                conn.close()
    return {'accepted': accepted, 'processed': processed}
