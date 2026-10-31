"""Finite private issuer process. Deployment supplies the dedicated guard DB connector."""
from contextlib import contextmanager
from dataclasses import dataclass
import math
import os
from pathlib import Path

from aos_api.aip_guard_policy_issuer_ipc import serve_one_guard_issuer_connection
from aos_api.aip_network_issuer_attempt import _private_directory_fd
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.aip_network_issuer_ipc import IssuerProtocolBlocked, open_private_issuer_listener
from aos_api.aip_private_listener import owned_private_listener
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class GuardIssuerProcessConfig:
    socket_path: Path
    credential_file: Path
    api_uid: int
    issuer_uid: int
    ipc_gid: int
    scope: TenantScope
    attempt_directory: Path
    expected_database: str
    max_connections: int = 1
    accept_timeout: float = 5.0

    def __post_init__(self):
        try:
            if (type(self.scope) is not TenantScope or not self.expected_database
                    or any(type(v) is not int or v <= 0 for v in (self.api_uid, self.issuer_uid, self.ipc_gid))
                    or self.api_uid == self.issuer_uid or self.issuer_uid != os.geteuid()
                    or self.ipc_gid != os.getegid() or type(self.max_connections) is not int
                    or not 1 <= self.max_connections <= 64 or type(self.accept_timeout) not in (int, float)
                    or not math.isfinite(self.accept_timeout) or not 0 < self.accept_timeout <= 30):
                raise ValueError()
            for name in ("socket_path", "credential_file", "attempt_directory"):
                path = Path(getattr(self, name))
                if not path.is_absolute():
                    raise ValueError()
                object.__setattr__(self, name, path)
        except Exception:
            raise IssuerProtocolBlocked("GUARD_ISSUER_PROCESS_CONFIG_REQUIRED") from None


@contextmanager
def guard_issuer_listener(config):
    config.__post_init__()
    try:
        _require_external_oidc_config()
        fd = _private_directory_fd(config.attempt_directory)
        os.close(fd)
    except Exception:
        raise IssuerProtocolBlocked("GUARD_ISSUER_PROCESS_PREFLIGHT_REQUIRED") from None
    with owned_private_listener(config.socket_path, service_uid=config.issuer_uid,
            ipc_gid=config.ipc_gid, blocked=IssuerProtocolBlocked,
            error_code="GUARD_ISSUER_SOCKET_DIRECTORY_REQUIRED",
            open_listener=lambda: open_private_issuer_listener(config.socket_path,
                api_uid=config.api_uid, issuer_uid=config.issuer_uid, ipc_gid=config.ipc_gid,
                credential_file=config.credential_file)) as listener:
        yield listener


def run_guard_issuer_process(config, *, connect_factory):
    if not callable(connect_factory):
        raise IssuerProtocolBlocked("GUARD_ISSUER_CONNECTION_FACTORY_REQUIRED")
    accepted = processed = 0
    with guard_issuer_listener(config) as listener:
        listener.settimeout(config.accept_timeout)
        for _ in range(config.max_connections):
            try:
                conn, _ = listener.accept()
            except TimeoutError:
                break
            accepted += 1
            processed += int(serve_one_guard_issuer_connection(conn, api_uid=config.api_uid,
                issuer_uid=config.issuer_uid, attempt_directory=config.attempt_directory,
                expected_database=config.expected_database, expected_scope=config.scope,
                connect_factory=connect_factory))
    return {"accepted": accepted, "processed": processed}
