"""Private durable file creation only; callers authenticate and validate bodies."""
import os


def create_private_request_file(directory_fd, filename, raw):
    """True only after file AND directory fsync; False means already exists.

    A failed or partial file is retained for inquiry, never deleted or retried.
    """
    if (type(filename) is not str or '/' in filename or filename in ('', '.', '..')
            or type(raw) is not bytes or not 0 < len(raw) <= 4096):
        raise ValueError('private request file input required')
    try:
        fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory_fd)
    except FileExistsError:
        return False
    try:
        os.fchmod(fd, 0o600)
        written = 0
        while written < len(raw):
            count = os.write(fd, raw[written:])
            if count <= 0:
                raise OSError('partial persistence')
            written += count
        os.fsync(fd)
        os.fsync(directory_fd)
        return True
    finally:
        os.close(fd)
