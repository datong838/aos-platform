"""Optional private Source connections; no deployment or business authorization."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat

import psycopg
from psycopg.conninfo import conninfo_to_dict

from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseBlocked, BIIssuerDatabaseConfig
from aos_api.aip_source_issuer_connection import SourceIssuerDatabaseConfig, connect_source_issuer_write
from aos_api.db import get_dsn


_CONFIG_ENV = {
    'plan': 'AOS_PLAN_SOURCE_ISSUER_CONFIG',
    'content': 'AOS_CONTENT_SOURCE_ISSUER_CONFIG',
    'contract': 'AOS_CONTRACT_SOURCE_ISSUER_CONFIG',
}
_FIELDS = {'schemaVersion', 'purpose', 'host', 'port', 'database', 'passfile'}


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate configuration key')
        result[key] = value
    return result


def _read_config(path, purpose):
    try:
        path = Path(path)
        parent = path.parent.lstat()
        if (not path.is_absolute() or not stat.S_ISDIR(parent.st_mode)
                or parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) != 0o700):
            raise ValueError('private directory required')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as source:
            metadata = os.fstat(source.fileno())
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid()
                    or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_size > 16384):
                raise ValueError('private configuration required')
            raw = source.read(16385)
        if len(raw) > 16384:
            raise ValueError('oversize configuration')
        value = json.loads(raw, object_pairs_hook=_unique_pairs)
        if (type(value) is not dict or set(value) != _FIELDS
                or value['schemaVersion'] != 'aos.source-issuer-database/v1'
                or value['purpose'] != purpose
                or any(type(value[key]) is not str for key in ('host', 'database', 'passfile'))):
            raise ValueError('wrong configuration contract')
        database = BIIssuerDatabaseConfig(value['host'], value['port'], value['database'], Path(value['passfile']))
        target = conninfo_to_dict(get_dsn())
        current = (target.get('hostaddr') or target.get('host'),
                   int(target.get('port') or 5432), target.get('dbname'))
        if (database.host, database.port, database.database) != current:
            raise ValueError('wrong application database target')
        return SourceIssuerDatabaseConfig(purpose, database)
    except (OSError, ValueError, TypeError, psycopg.Error, BIIssuerDatabaseBlocked):
        raise BIIssuerDatabaseBlocked('SOURCE_ISSUER_PRIVATE_EXACT_CONFIG_REQUIRED') from None


def configured_source_issuer_factory(purpose):
    """Leave the original factory intact unless a purpose is explicitly configured."""
    if purpose not in _CONFIG_ENV:
        raise BIIssuerDatabaseBlocked('SOURCE_ISSUER_PURPOSE_REQUIRED')
    path = os.getenv(_CONFIG_ENV[purpose], '').strip()
    if not path:
        return None

    @contextmanager
    def connection(scope):
        config = _read_config(path, purpose)
        with connect_source_issuer_write(config, scope) as conn:
            yield conn

    return connection
