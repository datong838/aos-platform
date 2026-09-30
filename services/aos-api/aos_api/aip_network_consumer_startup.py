"""Load API-owned client configuration only; never start a consumer or authorize work."""
import os

from aos_api.aip_network_consumer_config import _read_private_config
from aos_api.aip_network_consumer_application import ConsumerApplicationConfig
from aos_api.aip_network_consumer_client import ConsumerEndpoint
from aos_api.aip_network_issuer_auth import _require_external_oidc_config


class ConsumerStartupBlocked(RuntimeError):
    pass


def configured_api_consumer() -> ConsumerApplicationConfig | None:
    path = os.environ.get('AOS_NETWORK_CONSUMER_API_CONFIG')
    if path is None or path == '':
        return None
    try:
        data = _read_private_config(path)
        if (type(data) is not dict or set(data) != {'schemaVersion', 'socketPath', 'apiUid',
                'consumerUid', 'ipcGid', 'apiAttemptDirectory'}
                or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1):
            raise ValueError()
        _require_external_oidc_config()
        return ConsumerApplicationConfig(ConsumerEndpoint(data['socketPath'], data['apiUid'],
            data['consumerUid'], data['ipcGid']), data['apiAttemptDirectory'])
    except Exception:
        raise ConsumerStartupBlocked('CONSUMER_API_STARTUP_BLOCKED') from None
