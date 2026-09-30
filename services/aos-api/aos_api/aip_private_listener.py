"""Owned Unix socket lifecycle shared by isolated services."""
from contextlib import contextmanager
import os
import stat


def _identity(info):
    return info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode


@contextmanager
def owned_private_listener(path, *, service_uid, ipc_gid, open_listener, blocked, error_code):
    try:
        directory_fd = os.open(path.parent,
                               os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        raise blocked(error_code) from None
    listener = None
    created = None
    directory = os.fstat(directory_fd)
    try:
        if (directory.st_uid != service_uid or directory.st_gid != ipc_gid
                or stat.S_IMODE(directory.st_mode) != 0o750):
            raise blocked(error_code)
        listener = open_listener()
        created = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
        yield listener
    finally:
        if listener is not None:
            listener.close()
        try:
            if created is not None:
                current = os.stat(path.name, dir_fd=directory_fd, follow_symlinks=False)
                if (stat.S_ISSOCK(current.st_mode) and current.st_uid == service_uid
                        and _identity(current) == _identity(created)
                        and _identity(os.fstat(directory_fd)) == _identity(directory)
                        and _identity(path.parent.lstat()) == _identity(directory)):
                    os.unlink(path.name, dir_fd=directory_fd)
        except OSError:
            # Unknown or replaced paths are retained for explicit reconciliation.
            pass
        finally:
            os.close(directory_fd)
