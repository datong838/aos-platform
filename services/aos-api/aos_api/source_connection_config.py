"""Strict executable source configuration; never performs a connection or logs inputs."""
from typing import Any

_FIELDS = frozenset({
    'sshHost', 'sshPort', 'sshUser', 'sshPassword', 'sshKeyRef',
    'dbHost', 'dbPort', 'database', 'username', 'password', 'secretRef',
})
_REQUIRED = ('sshHost', 'sshUser', 'dbHost', 'database', 'username')


def normalize_source_connection_config(connector: str, value: Any) -> dict[str, Any]:
    """Validate the supported connector without echoing secret input on failure."""
    def invalid() -> None:
        raise ValueError('SOURCE_CONNECTION_CONFIG_INVALID')

    if connector != 'jdbc-mysql-ssh' or type(value) is not dict:
        invalid()
    if any(type(key) is not str or key not in _FIELDS for key in value):
        invalid()
    result = dict(value)
    for key in _REQUIRED:
        if key not in result:
            invalid()
    for key, item in result.items():
        if key in {'sshPort', 'dbPort'}:
            if type(item) is not int or not 1 <= item <= 65535:
                invalid()
        elif type(item) is not str or not item or len(item) > 16384 or '\x00' in item:
            invalid()
        elif key not in {'sshPassword', 'password'} and (item != item.strip() or not item.strip()):
            invalid()
    for password, reference in (('sshPassword', 'sshKeyRef'), ('password', 'secretRef')):
        if (password in result) == (reference in result):
            invalid()
    result.setdefault('sshPort', 22)
    result.setdefault('dbPort', 3306)
    result['connector_type'] = connector
    return result
