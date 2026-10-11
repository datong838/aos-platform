"""Fixed Source issuance identities sharing the original BI transaction boundary.

This provides connections, not deployment, caller authorization, or Source ACLs.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal
from aos_api.aip_bi_plan_issuer_connection import (
    BIIssuerDatabaseBlocked, BIIssuerDatabaseConfig, _connect_bi_issuer,
)

_LOGINS = {
    'plan': 'aos_bi_plan_issuer',
    'content': 'aos_content_source_issuer',
    'contract': 'aos_contract_source_issuer',
}


@dataclass(frozen=True)
class SourceIssuerDatabaseConfig:
    purpose: Literal['plan', 'content', 'contract']
    database: BIIssuerDatabaseConfig

    def __post_init__(self):
        if (type(self.purpose) is not str or self.purpose not in _LOGINS
                or type(self.database) is not BIIssuerDatabaseConfig):
            raise BIIssuerDatabaseBlocked('SOURCE_ISSUER_EXACT_CONFIGURATION_REQUIRED')
        self.database.__post_init__()


@contextmanager
def _connection(config, scope, *, read_only):
    if type(config) is not SourceIssuerDatabaseConfig:
        raise BIIssuerDatabaseBlocked('SOURCE_ISSUER_EXACT_CONFIGURATION_REQUIRED')
    config.__post_init__()
    with _connect_bi_issuer(config.database, scope, read_only=read_only,
                            issuer_login=_LOGINS[config.purpose]) as conn:
        yield conn


def connect_source_issuer_write(config: SourceIssuerDatabaseConfig, scope):
    return _connection(config, scope, read_only=False)


def connect_source_issuer_read_only(config: SourceIssuerDatabaseConfig, scope):
    return _connection(config, scope, read_only=True)
