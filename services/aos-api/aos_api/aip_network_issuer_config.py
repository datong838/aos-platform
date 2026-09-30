"""Private issuer process config and read-only structural startup checks."""
import os
from pathlib import Path
import stat

from aos_api.tenant_scope import TenantScope
from aos_api.aip_network_consumer_config import _read_private_config
from aos_api.aip_network_issuer_connection import IssuerDatabaseConfig, connect_issuer_read_only
from aos_api.aip_network_issuer_process import IssuerProcessConfig
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.aip_network_issuer_attempt import _private_directory_fd


class IssuerConfigBlocked(ValueError):
    pass


def load_issuer_config(path: str | Path) -> IssuerProcessConfig:
    try:
        data = _read_private_config(path)
        if (type(data) is not dict or set(data) != {'schemaVersion', 'socketPath', 'apiUid',
                'issuerUid', 'ipcGid', 'database', 'scope', 'attemptDirectory', 'maxConnections', 'acceptTimeout'}
                or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1
                or type(data['database']) is not dict
                or set(data['database']) != {'host', 'port', 'database', 'passfile'}
                or type(data['scope']) is not dict or set(data['scope']) != {'orgId', 'projectId'}):
            raise ValueError()
        return IssuerProcessConfig(socket_path=data['socketPath'], api_uid=data['apiUid'],
            issuer_uid=data['issuerUid'], ipc_gid=data['ipcGid'],
            database=IssuerDatabaseConfig(**data['database']),
            scope=TenantScope(data['scope']['orgId'], data['scope']['projectId']),
            attempt_directory=data['attemptDirectory'], max_connections=data['maxConnections'],
            accept_timeout=data['acceptTimeout'])
    except Exception:
        raise IssuerConfigBlocked('ISSUER_PRIVATE_CONFIG_INVALID') from None


def preflight_issuer(config: IssuerProcessConfig, expected_scope: TenantScope) -> dict[str, bool]:
    try:
        if (type(config) is not IssuerProcessConfig or type(expected_scope) is not TenantScope
                or config.scope != expected_scope):
            raise ValueError()
        config.__post_init__()
        _require_external_oidc_config()
        directory = config.socket_path.parent.lstat()
        if (not stat.S_ISDIR(directory.st_mode) or stat.S_IMODE(directory.st_mode) != 0o750
                or directory.st_uid != config.issuer_uid or directory.st_gid != config.ipc_gid):
            raise ValueError()
        try:
            config.socket_path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise ValueError()
        fd = _private_directory_fd(config.attempt_directory)
        os.close(fd)
        with connect_issuer_read_only(config.database, config.scope) as conn:
            for table, guard in (
                ('aip_action_approval_event', 'aip_network_approval_event_guard_a0v_118'),
                ('aip_action_proposal', 'aip_network_proposal_guard_a0v_118'),
            ):
                row = conn.execute('''SELECT t.tgenabled,t.tgtype,p.prosecdef,p.proconfig
                    FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid
                    WHERE t.tgrelid=to_regclass(%s) AND t.tgname=%s
                      AND t.tgfoid=to_regprocedure(%s) AND NOT t.tgisinternal''',
                    ('public.'+table, guard, 'public.'+guard+'()')).fetchone()
                if (row is None or row['tgenabled'] != 'O' or row['tgtype'] != 31
                        or row['prosecdef'] or row['proconfig'] != ['search_path=pg_catalog']):
                    raise ValueError()
        return {'ready': True, 'businessAuthorized': False}
    except Exception:
        raise IssuerConfigBlocked('ISSUER_READ_ONLY_PREFLIGHT_BLOCKED') from None
