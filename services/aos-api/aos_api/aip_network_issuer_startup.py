"""Private API issuer client configuration; never starts or authorizes an issuer."""
import os

from aos_api.aip_network_consumer_config import _read_private_config
from aos_api.aip_network_issuer_application import IssuerApplicationConfig
from aos_api.aip_network_issuer_client import IssuerEndpoint
from aos_api.aip_network_issuer_auth import _require_external_oidc_config


class IssuerStartupBlocked(RuntimeError):
    pass


def configured_api_issuer() -> IssuerApplicationConfig | None:
    path = os.environ.get('AOS_NETWORK_ISSUER_API_CONFIG')
    if path is None or path == '':
        return None
    try:
        data = _read_private_config(path)
        if (type(data) is not dict or set(data) != {'schemaVersion', 'socketPath', 'apiUid',
                'issuerUid', 'ipcGid', 'apiAttemptDirectory'}
                or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1):
            raise ValueError()
        _require_external_oidc_config()
        return IssuerApplicationConfig(IssuerEndpoint(data['socketPath'], data['apiUid'],
            data['issuerUid'], data['ipcGid']), data['apiAttemptDirectory'])
    except Exception:
        raise IssuerStartupBlocked('ISSUER_API_STARTUP_BLOCKED') from None
