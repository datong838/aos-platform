"""Prepare committed startup source only; no database or service executor."""
import hashlib, io, json, os, tarfile
from pathlib import Path, PurePosixPath

PATHS = ('services/aos-api/aos_api', 'services/aos-api/alembic',
         'services/aos-api/alembic.ini', 'scripts', 'bundles/candidates/ecommerce')

def require(value, reason):
    if not value:
        raise ValueError(reason)

def archive_files(raw):
    files = {}
    seen = set()
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive:
            name = member.name
            path = PurePosixPath(name)
            require(not path.is_absolute() and name == str(path)
                    and all(x not in ('..', '.', '') for x in name.split('/')),
                    'UNSAFE_ARCHIVE_PATH')
            require(name not in seen, 'DUPLICATE_ARCHIVE_ENTRY')
            seen.add(name)
            require(member.isdir() or member.isfile(), 'REGULAR_FILES_ONLY')
            if member.isdir():
                require(any(name == p or name.startswith(p + '/') or p.startswith(name + '/') for p in PATHS),
                        'ARCHIVE_DIRECTORY_SCOPE_DRIFT')
                continue
            require(any(name == p or name.startswith(p + '/') for p in PATHS),
                    'ARCHIVE_SCOPE_DRIFT')
            files[name] = archive.extractfile(member).read()
    require(files, 'EMPTY_ARCHIVE')
    return files

def manifest(files):
    return {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}

def require_migration_subset(files, original):
    observed = manifest({name: raw for name, raw in files.items()
                         if any(name == p or name.startswith(p + '/') for p in PATHS[:3])})
    require(observed == original, 'FROZEN_MIGRATION_BYTES_DRIFT')

def verify(root, expected):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), 'PRIVATE_ROOT_REQUIRED')
    require(root.stat().st_uid == os.getuid() and root.stat().st_mode & 0o077 == 0,
            'EXPORTED_ROOT_PERMISSIONS')
    observed = {}
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'EXPORTED_LINK_FORBIDDEN')
        require(path.stat().st_uid == os.getuid() and path.stat().st_mode & 0o077 == 0,
                'EXPORTED_PERMISSIONS_DRIFT')
        if path.is_file():
            observed[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            require(path.is_dir(), 'EXPORTED_SPECIAL_FILE_FORBIDDEN')
    require(observed == expected, 'EXPORTED_MANIFEST_DRIFT')
    return True

def materialize(raw, root, expected):
    files = archive_files(raw)
    require(manifest(files) == expected, 'ARCHIVE_MANIFEST_DRIFT')
    root = Path(root)
    require(not root.exists() and not root.is_symlink(), 'EXISTING_DESTINATION_RECONCILE_ONLY')
    parent = root.parent
    require(parent.is_dir() and not parent.is_symlink()
            and parent.resolve() == parent and parent.stat().st_uid == os.getuid()
            and parent.stat().st_mode & 0o077 == 0, 'PRIVATE_PARENT_REQUIRED')
    root.mkdir(mode=0o700)
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    verify(root, expected)
    descriptor = os.open(root, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return {'status': 'COMMITTED_STARTUP_SOURCE_MATERIALIZED', 'files': len(files),
            'archive_sha256': hashlib.sha256(raw).hexdigest(),
            'manifest_sha256': hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest(),
            'database_effects': 0, 'service_start_attempted': False}
