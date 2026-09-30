"""Explicit private config and read-only readiness; never business authorization."""
import json
import os
from pathlib import Path
import stat

from aos_api.tenant_scope import TenantScope
from aos_api.aip_network_consumer_connection import ConsumerDatabaseConfig, connect_consumer
from aos_api.aip_network_consumer_process import ConsumerProcessConfig
from aos_api.aip_network_consumer_service import _function_gate
from aos_api.aip_network_issuer_attempt import _private_directory_fd
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.aip_network_issuer_ipc import _unique_pairs, _invalid_constant


class ConsumerConfigBlocked(ValueError):
    pass


def _read_private_config(path: str | Path):
    directory_fd = file_fd = None
    try:
        path = Path(path)
        if not path.is_absolute():
            raise ValueError('absolute config required')
        directory_fd = _private_directory_fd(path.parent)
        file_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                          dir_fd=directory_fd)
        before = os.fstat(file_fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                or stat.S_IMODE(before.st_mode) != 0o600 or not 0 < before.st_size <= 16384):
            raise ValueError('private config required')
        raw = os.read(file_fd, 16385)
        after = os.fstat(file_fd)
        if (len(raw) != before.st_size or len(raw) > 16384
                or (before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_mode, before.st_uid)
                != (after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_mode, after.st_uid)):
            raise ValueError('config changed during read')
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs,
                          parse_constant=_invalid_constant)
        return data
    except Exception:
        raise ConsumerConfigBlocked('CONSUMER_PRIVATE_CONFIG_INVALID') from None
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if directory_fd is not None:
            os.close(directory_fd)


def load_consumer_config(path: str | Path) -> ConsumerProcessConfig:
    try:
        data = _read_private_config(path)
        if (type(data) is not dict or set(data) != {'schemaVersion', 'socketPath', 'apiUid',
                'consumerUid', 'ipcGid', 'database', 'attemptDirectory', 'maxConnections', 'acceptTimeout'}
                or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1
                or type(data['database']) is not dict
                or set(data['database']) != {'host', 'port', 'database', 'passfile'}
                or data['consumerUid'] != os.geteuid()):
            raise ValueError('exact config required')
        database = ConsumerDatabaseConfig(**data['database'])
        return ConsumerProcessConfig(socket_path=data['socketPath'], api_uid=data['apiUid'],
            consumer_uid=data['consumerUid'], ipc_gid=data['ipcGid'], database=database,
            attempt_directory=data['attemptDirectory'], max_connections=data['maxConnections'],
            accept_timeout=data['acceptTimeout'])
    except Exception:
        raise ConsumerConfigBlocked('CONSUMER_PRIVATE_CONFIG_INVALID') from None


def preflight_consumer(config: ConsumerProcessConfig, scope: TenantScope) -> dict[str, bool]:
    try:
        if (type(config) is not ConsumerProcessConfig or type(scope) is not TenantScope
                or config.consumer_uid != os.geteuid() or config.ipc_gid != os.getegid()):
            raise ValueError('exact OS identity required')
        config.__post_init__()
        _require_external_oidc_config()
        directory = config.socket_path.parent.lstat()
        if (not stat.S_ISDIR(directory.st_mode) or stat.S_IMODE(directory.st_mode) != 0o750
                or directory.st_uid != config.consumer_uid or directory.st_gid != config.ipc_gid):
            raise ValueError('private socket directory required')
        try:
            config.socket_path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise ValueError('socket path occupied')
        fd = _private_directory_fd(config.attempt_directory)
        os.close(fd)
        with connect_consumer(config.database, scope, read_only=True) as conn:
            for signature, volatility in (
                ('public.aip_consume_network_activation_a0v_120(text,text,text,text)', 'v'),
                ('public.aip_reconcile_network_receipt_a0v_121(text,text,text,text)', 's'),
                ('public.aip_consume_network_as_actor_a0v_122(text,text,text,text,text,text,text,text)', 'v'),
                ('public.aip_reconcile_network_as_actor_a0v_122(text,text,text,text,text,text,text,text)', 's'),
                ('public.aip_claim_network_delivery_a0v_123(text,text,text,uuid)', 'v'),
                ('public.aip_finish_network_delivery_a0v_123(text,text,text,text,uuid)', 'v'),
            ):
                _function_gate(conn, signature, volatility)
        return {'ready': True, 'businessAuthorized': False}
    except Exception:
        raise ConsumerConfigBlocked('CONSUMER_READ_ONLY_PREFLIGHT_BLOCKED') from None
