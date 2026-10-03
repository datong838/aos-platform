"""Start gate for one isolated BI issuer listener; no business dispatch here."""

from __future__ import annotations

import math
import os
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from aos_api.aip_bi_plan_issuer_connection import (
    BIIssuerDatabaseConfig, connect_bi_issuer_read_only,
)
from aos_api.aip_network_issuer_attempt import _private_directory_fd
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.aip_network_issuer_ipc import open_private_issuer_listener
from aos_api.aip_private_listener import owned_private_listener
from aos_api.tenant_scope import TenantScope


class BIIssuerProcessBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class BIIssuerProcessConfig:
    socket_path: Path
    api_uid: int
    issuer_uid: int
    ipc_gid: int
    database: BIIssuerDatabaseConfig
    scope: TenantScope
    attempt_directory: Path
    max_connections: int = 1
    accept_timeout: float = 5.0

    def __post_init__(self) -> None:
        try:
            if (type(self.database) is not BIIssuerDatabaseConfig
                    or type(self.scope) is not TenantScope
                    or any(type(v) is not int or v <= 0
                           for v in (self.api_uid, self.issuer_uid, self.ipc_gid))
                    or self.api_uid == self.issuer_uid
                    or self.issuer_uid != os.geteuid()
                    or self.ipc_gid != os.getegid()
                    or type(self.max_connections) is not int
                    or not 1 <= self.max_connections <= 64
                    or type(self.accept_timeout) not in (int, float)
                    or not math.isfinite(self.accept_timeout)
                    or not 0 < self.accept_timeout <= 30):
                raise ValueError()
            socket_path, attempt = Path(self.socket_path), Path(self.attempt_directory)
            if (not socket_path.is_absolute() or not attempt.is_absolute()
                    or not self.database.passfile.is_absolute()):
                raise ValueError()
            self.scope.__post_init__()
            self.database.__post_init__()
            object.__setattr__(self, "socket_path", socket_path)
            object.__setattr__(self, "attempt_directory", attempt)
        except Exception:
            raise BIIssuerProcessBlocked("BI_ISSUER_PROCESS_CONFIG_REQUIRED") from None


@contextmanager
def bi_issuer_listener(config: BIIssuerProcessConfig):
    """Read-only preflight before the kernel-visible socket can exist."""
    try:
        if type(config) is not BIIssuerProcessConfig:
            raise ValueError()
        config.__post_init__()
        _require_external_oidc_config()
        directory_fd = _private_directory_fd(config.attempt_directory)
        os.close(directory_fd)
        with connect_bi_issuer_read_only(config.database, config.scope) as conn:
            conn.execute("SELECT 1")
    except Exception:
        raise BIIssuerProcessBlocked("BI_ISSUER_PROCESS_PREFLIGHT_REQUIRED") from None
    with ExitStack() as stack:
        try:
            listener = stack.enter_context(owned_private_listener(
                config.socket_path, service_uid=config.issuer_uid,
                ipc_gid=config.ipc_gid, blocked=BIIssuerProcessBlocked,
                error_code="BI_ISSUER_SOCKET_DIRECTORY_REQUIRED",
                open_listener=lambda: open_private_issuer_listener(
                    config.socket_path, api_uid=config.api_uid,
                    issuer_uid=config.issuer_uid, ipc_gid=config.ipc_gid,
                    credential_file=config.database.passfile)))
        except Exception:
            raise BIIssuerProcessBlocked("BI_ISSUER_LISTENER_START_BLOCKED") from None
        yield listener
