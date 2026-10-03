"""Bounded isolated BI issuer listener with original scoped Plan services."""

from __future__ import annotations

import math
import os
import re
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from aos_api.aip_bi_plan_issuer_connection import (
    BIIssuerDatabaseConfig, connect_bi_issuer_read_only, connect_bi_issuer_write,
)
from aos_api.aip_bi_plan_issuer_ipc import serve_one_bi_issuer_connection
from aos_api.aip_bi_plan_issuer_service import dispatch_bi_issuer_command
from aos_api.aip_production_contract_store import (
    SignedBIPlanReceiptReader, SignedBIPlanRebindReceiptReader,
)
from aos_api.aip_responsibility_template_authority import (
    ActiveBIBusinessResolver, ApprovedBIPreparationResolver,
)
from aos_api.ecommerce_business_investigation_aip_authority import (
    SignedBIPlanActiveRebindService, SignedBIPlanPreparationService,
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


def build_bi_issuer_dispatcher(
    config: BIIssuerProcessConfig, *, release_root: Path,
    trust_roots, source_alias: str,
):
    """Bind the original Plan services and Receipt readers to one exact issuer DB identity."""
    try:
        if type(config) is not BIIssuerProcessConfig:
            raise ValueError()
        config.__post_init__()
        root = Path(release_root)
        if (not root.is_absolute() or root.is_symlink() or not root.is_dir()
                or type(source_alias) is not str
                or re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,80}", source_alias) is None
                or not callable(getattr(trust_roots, "snapshot", None))):
            raise ValueError()
        root = root.resolve(strict=True)
    except Exception:
        raise BIIssuerProcessBlocked("BI_ISSUER_SIGNED_SOURCE_REQUIRED") from None

    def require_scope(scope: TenantScope) -> None:
        if type(scope) is not TenantScope or scope != config.scope:
            raise BIIssuerProcessBlocked("BI_ISSUER_PROCESS_SCOPE_REQUIRED")

    def read_connection(scope: TenantScope):
        require_scope(scope)
        return connect_bi_issuer_read_only(config.database, scope)

    def write_connection(scope: TenantScope):
        require_scope(scope)
        return connect_bi_issuer_write(config.database, scope)

    resolver_options = dict(
        connect_factory=read_connection,
        registry_connect_factory=lambda: read_connection(config.scope),
        release_root=root, trust_roots=trust_roots, source_alias=source_alias,
        registry_prepared_transaction=True, restricted_bi_scope=config.scope,
    )
    prepare_service = SignedBIPlanPreparationService(
        connect_factory=write_connection,
        preparation_resolver=ApprovedBIPreparationResolver(**resolver_options),
    )
    rebind_service = SignedBIPlanActiveRebindService(
        connect_factory=write_connection,
        active_resolver=ActiveBIBusinessResolver(**resolver_options),
    )
    prepare_reader = SignedBIPlanReceiptReader(
        connect_factory=read_connection, restricted_bi_scope=config.scope,
    )
    rebind_reader = SignedBIPlanRebindReceiptReader(
        connect_factory=read_connection, restricted_bi_scope=config.scope,
    )

    def dispatch(command):
        if (command.org_id, command.project_id) != config.scope.key:
            raise BIIssuerProcessBlocked("BI_ISSUER_PROCESS_SCOPE_REQUIRED")
        return dispatch_bi_issuer_command(
            command, attempt_directory=config.attempt_directory,
            prepare_service=prepare_service, rebind_service=rebind_service,
            prepare_receipt_reader=prepare_reader,
            rebind_receipt_reader=rebind_reader,
        )

    return dispatch


def run_bi_issuer_process(
    config: BIIssuerProcessConfig, *, release_root: Path,
    trust_roots, source_alias: str,
) -> dict[str, int]:
    """Accept a bounded number of private requests; never replay an unknown write."""
    dispatch = build_bi_issuer_dispatcher(
        config, release_root=release_root,
        trust_roots=trust_roots, source_alias=source_alias,
    )
    accepted = processed = 0
    with bi_issuer_listener(config) as listener:
        listener.settimeout(config.accept_timeout)
        for _ in range(config.max_connections):
            try:
                conn, _ = listener.accept()
            except TimeoutError:
                break
            accepted += 1
            try:
                processed += int(serve_one_bi_issuer_connection(
                    conn, api_uid=config.api_uid, issuer_uid=config.issuer_uid,
                    expected_scope=config.scope, dispatch=dispatch,
                ))
            finally:
                conn.close()
    return {"accepted": accepted, "processed": processed}
