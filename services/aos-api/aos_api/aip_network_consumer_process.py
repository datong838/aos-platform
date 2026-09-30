"""Finite private consumer lifecycle; deployment supplies trusted OS/config authority."""
from contextlib import contextmanager
from dataclasses import dataclass
import math
from pathlib import Path

from aos_api.aip_private_listener import owned_private_listener
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


@contextmanager
def consumer_listener(config: ConsumerProcessConfig):
    if type(config) is not ConsumerProcessConfig:
        raise ConsumerProtocolBlocked('CONSUMER_PROCESS_CONFIG_REQUIRED')
    config.__post_init__()
    with owned_private_listener(config.socket_path, service_uid=config.consumer_uid,
            ipc_gid=config.ipc_gid, blocked=ConsumerProtocolBlocked,
            error_code='CONSUMER_SOCKET_DIRECTORY_REQUIRED',
            open_listener=lambda: open_private_consumer_listener(config.socket_path,
                api_uid=config.api_uid, consumer_uid=config.consumer_uid, ipc_gid=config.ipc_gid,
                config=config.database, attempt_directory=config.attempt_directory)) as listener:
        yield listener


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
