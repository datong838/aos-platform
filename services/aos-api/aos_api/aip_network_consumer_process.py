"""Finite private consumer lifecycle; deployment supplies trusted OS/config authority."""
from contextlib import contextmanager
from dataclasses import dataclass
import math
import os
from pathlib import Path
import socket
import stat

from aos_api.aip_network_consumer_connection import ConsumerDatabaseConfig
from aos_api.aip_network_consumer_ipc import (
    ConsumerProtocolBlocked, open_private_consumer_listener, serve_one_consumer_connection,
)


@dataclass(frozen=True)
class ConsumerProcessConfig:
    socket_path: Path
    api_uid: int
    consumer_uid: int
    ipc_gid: int
    database: ConsumerDatabaseConfig
    attempt_directory: Path
    max_connections: int = 1
    accept_timeout: float = 5.0

    def __post_init__(self):
        if (type(self.database) is not ConsumerDatabaseConfig
                or any(type(v) is not int or v <= 0 for v in
                       (self.api_uid, self.consumer_uid, self.ipc_gid))
                or self.api_uid == self.consumer_uid
                or type(self.max_connections) is not int or not 1 <= self.max_connections <= 64
                or type(self.accept_timeout) not in (int, float)
                or not math.isfinite(self.accept_timeout) or not 0 < self.accept_timeout <= 30):
            raise ConsumerProtocolBlocked('CONSUMER_PROCESS_CONFIG_REQUIRED')
        try:
            path, attempt = Path(self.socket_path), Path(self.attempt_directory)
            if not path.is_absolute() or not attempt.is_absolute():
                raise ValueError('absolute paths required')
        except (TypeError, ValueError):
            raise ConsumerProtocolBlocked('CONSUMER_PROCESS_CONFIG_REQUIRED') from None
        object.__setattr__(self, 'socket_path', path)
        object.__setattr__(self, 'attempt_directory', attempt)


def _identity(info):
    return info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode


@contextmanager
def consumer_listener(config: ConsumerProcessConfig):
    if type(config) is not ConsumerProcessConfig:
        raise ConsumerProtocolBlocked('CONSUMER_PROCESS_CONFIG_REQUIRED')
    config.__post_init__()
    try:
        directory_fd = os.open(config.socket_path.parent,
                               os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        raise ConsumerProtocolBlocked('CONSUMER_SOCKET_DIRECTORY_REQUIRED') from None
    listener = None
    created = None
    directory = os.fstat(directory_fd)
    try:
        if (directory.st_uid != config.consumer_uid or directory.st_gid != config.ipc_gid
                or stat.S_IMODE(directory.st_mode) != 0o750):
            raise ConsumerProtocolBlocked('CONSUMER_SOCKET_DIRECTORY_REQUIRED')
        listener = open_private_consumer_listener(config.socket_path,
            api_uid=config.api_uid, consumer_uid=config.consumer_uid, ipc_gid=config.ipc_gid,
            config=config.database, attempt_directory=config.attempt_directory)
        created = os.stat(config.socket_path.name, dir_fd=directory_fd, follow_symlinks=False)
        yield listener
    finally:
        if listener is not None:
            listener.close()
        try:
            if created is not None:
                current = os.stat(config.socket_path.name, dir_fd=directory_fd, follow_symlinks=False)
                if (stat.S_ISSOCK(current.st_mode) and current.st_uid == config.consumer_uid
                        and _identity(current) == _identity(created)
                        and _identity(os.fstat(directory_fd)) == _identity(directory)
                        and _identity(config.socket_path.parent.lstat()) == _identity(directory)):
                    os.unlink(config.socket_path.name, dir_fd=directory_fd)
        except OSError:
            # Unknown or replaced paths are retained for explicit reconciliation.
            pass
        finally:
            os.close(directory_fd)


def run_consumer_process(config: ConsumerProcessConfig) -> dict[str, int]:
    accepted = processed = 0
    with consumer_listener(config) as listener:
        listener.settimeout(config.accept_timeout)
        for _ in range(config.max_connections):
            try:
                conn, _ = listener.accept()
            except TimeoutError:
                break
            accepted += 1
            processed += int(serve_one_consumer_connection(conn, api_uid=config.api_uid,
                consumer_uid=config.consumer_uid, config=config.database,
                attempt_directory=config.attempt_directory))
    return {'accepted': accepted, 'processed': processed}
