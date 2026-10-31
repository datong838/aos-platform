"""Strict private config loader for the isolated guard policy issuer process."""
from dataclasses import dataclass
import os
from pathlib import Path
import stat

from aos_api.aip_guard_policy_issuer_connection import GuardIssuerDatabaseConfig, connect_guard_issuer
from aos_api.aip_guard_policy_issuer_process import GuardIssuerProcessConfig
from aos_api.aip_network_consumer_config import _read_private_config
from aos_api.aip_network_issuer_attempt import _private_directory_fd
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.tenant_scope import TenantScope


class GuardIssuerConfigBlocked(ValueError):
    pass


@dataclass(frozen=True)
class LoadedGuardIssuerConfig:
    process: GuardIssuerProcessConfig
    database: GuardIssuerDatabaseConfig


def load_guard_issuer_config(path: str | Path):
    try:
        data = _read_private_config(path)
        if (type(data) is not dict or set(data) != {"schemaVersion", "socketPath", "credentialFile",
                "apiUid", "issuerUid", "ipcGid", "database", "scope", "attemptDirectory",
                "maxConnections", "acceptTimeout"} or data["schemaVersion"] != 1
                or type(data["database"]) is not dict
                or set(data["database"]) != {"host", "port", "database", "passfile"}
                or type(data["scope"]) is not dict
                or set(data["scope"]) != {"orgId", "projectId"}):
            raise ValueError()
        database = GuardIssuerDatabaseConfig(**data["database"])
        process = GuardIssuerProcessConfig(socket_path=data["socketPath"], credential_file=data["credentialFile"],
            api_uid=data["apiUid"], issuer_uid=data["issuerUid"], ipc_gid=data["ipcGid"],
            scope=TenantScope(data["scope"]["orgId"], data["scope"]["projectId"]),
            attempt_directory=data["attemptDirectory"], expected_database=database.database,
            max_connections=data["maxConnections"], accept_timeout=data["acceptTimeout"])
        return LoadedGuardIssuerConfig(process, database)
    except Exception:
        raise GuardIssuerConfigBlocked("GUARD_ISSUER_PRIVATE_CONFIG_INVALID") from None


def preflight_guard_issuer(config):
    try:
        if type(config) is not LoadedGuardIssuerConfig:
            raise ValueError()
        process = config.process
        process.__post_init__()
        if process.issuer_uid != os.geteuid() or process.ipc_gid != os.getegid():
            raise ValueError()
        _require_external_oidc_config()
        directory = process.socket_path.parent.lstat()
        if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != process.issuer_uid
                or directory.st_gid != process.ipc_gid or stat.S_IMODE(directory.st_mode) != 0o750):
            raise ValueError()
        try:
            process.socket_path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise ValueError()
        fd = _private_directory_fd(process.attempt_directory)
        os.close(fd)
        with connect_guard_issuer(config.database, process.scope, True):
            pass
        return {"ready": True, "businessAuthorized": False}
    except Exception:
        raise GuardIssuerConfigBlocked("GUARD_ISSUER_READ_ONLY_PREFLIGHT_BLOCKED") from None
