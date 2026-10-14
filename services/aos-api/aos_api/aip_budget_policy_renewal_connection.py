"""Protected deployment provenance and purpose-only renewal connections.

No provisioning, DDL, shared DSN, password environment or implicit enablement.
The operator-controlled configuration and signed package are the deployment TCB.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

import psycopg
from psycopg.rows import dict_row

from aos_api.aip_budget_policy_renewal_identity import CheckerBinding, _database_identity
from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore, _CALLERS

ROOT = Path(__file__).resolve().parents[3]
PACKAGE_FILES = (
    'scripts/a0v_qyh_restored_http.py', 'scripts/a0v_current_preview_http.py',
    *('services/aos-api/aos_api/aip_budget_policy_renewal_'+name for name in
      ('contracts.py','identity.py','store.py','authority.sql','connection.py',
       'service.py','process.py','schema.json')),
    'services/aos-api/alembic/versions/a0v_162_budget_policy_renewal.py',
)
_HASH = re.compile(r'^[0-9a-f]{64}$')
_FORBIDDEN_ENV = ('PGPASSWORD','PGSERVICE','PGSERVICEFILE','PGOPTIONS','PGHOSTADDR',
                  'PGSSLMODE','PGPASSFILE','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY',
                  'http_proxy','https_proxy','all_proxy')


class RenewalConnectionBlocked(ValueError):
    pass


def _private_bytes(path, *, maximum=65536):
    try:
        path = Path(path)
        parent = path.parent.lstat()
        if (not path.is_absolute() or path.resolve(strict=True) != path
                or not stat.S_ISDIR(parent.st_mode)
                or parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) != 0o700):
            raise ValueError()
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                    or stat.S_IMODE(before.st_mode) != 0o600 or not 0 < before.st_size <= maximum):
                raise ValueError()
            raw = stream.read(maximum+1)
            after = os.fstat(stream.fileno())
        if len(raw)>maximum or (before.st_size,before.st_mtime_ns,before.st_ino) != (after.st_size,after.st_mtime_ns,after.st_ino):
            raise ValueError()
        return raw
    except (OSError,ValueError,TypeError):
        raise RenewalConnectionBlocked('RENEWAL_PRIVATE_CONFIG_REQUIRED') from None


def _unique(pairs):
    value = {}
    for key,item in pairs:
        if key in value:
            raise ValueError()
        value[key] = item
    return value


@dataclass(frozen=True)
class PurposeProfile:
    purpose: str
    host: str
    port: int
    database: str
    user: str
    passfile: Path
    passfile_sha256: str
    manifest_sha256: str


@dataclass(frozen=True)
class ProtectedRenewalConfig:
    path: Path
    content_sha256: str
    enabled: bool
    identity_path: Path
    identity_sha256: str
    binding: CheckerBinding
    profiles: tuple[PurposeProfile, ...]
    package_sources: tuple[tuple[str,str], ...]

    def profile(self, purpose):
        matches = [p for p in self.profiles if p.purpose == purpose]
        if len(matches) != 1:
            raise RenewalConnectionBlocked('RENEWAL_PURPOSE_REQUIRED')
        return matches[0]


def _original_oidc_loader():
    """Import audited definition modules only, never their main/maintenance."""
    for name in ('a0v_current_preview_http','a0v_qyh_restored_http'):
        path = ROOT/'scripts'/(name+'.py')
        existing = sys.modules.get(name)
        if existing is not None:
            if Path(existing.__file__).resolve() != path.resolve():
                raise RenewalConnectionBlocked('RENEWAL_LOADER_SOURCE_REQUIRED')
            continue
        spec = importlib.util.spec_from_file_location(name,path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(name,None)
            raise RenewalConnectionBlocked('RENEWAL_LOADER_SOURCE_REQUIRED') from None
    return sys.modules['a0v_qyh_restored_http'].load_management_oidc_config


def load_protected_config(path):
    raw = _private_bytes(path)
    try:
        value = json.loads(raw,object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        fields = {'schemaVersion','orgId','projectId','enabled','identityConfigPath',
                  'identityConfigSha256','profiles','packageSources'}
        if (type(value) is not dict or set(value)!=fields
                or value['schemaVersion']!='aos.budget-policy-renewal.private/v1'
                or value['orgId']!='org-org' or value['projectId']!='dev-project'
                or type(value['enabled']) is not bool
                or type(value['packageSources']) is not dict
                or set(value['packageSources'])!=set(PACKAGE_FILES)):
            raise ValueError()
        for relative,digest in value['packageSources'].items():
            source = ROOT/relative
            if (type(digest) is not str or not _HASH.fullmatch(digest)
                    or source.is_symlink() or not source.is_file()
                    or hashlib.sha256(source.read_bytes()).hexdigest()!=digest):
                raise ValueError()
        identity_path = Path(value['identityConfigPath'])
        identity_raw = _private_bytes(identity_path,maximum=16384)
        digest = hashlib.sha256(identity_raw).hexdigest()
        if digest != value['identityConfigSha256']:
            raise ValueError()
        environment = _original_oidc_loader()(identity_path)
        # Detect a replacement between the audited loader and this provenance read.
        if hashlib.sha256(_private_bytes(identity_path,maximum=16384)).hexdigest()!=digest:
            raise ValueError()
        binding = CheckerBinding('6f31cfdc-a26c-4f1f-ad6b-95a8559cc657',digest,
                                 tuple(sorted(environment.items())))
        if type(value['profiles']) is not dict or set(value['profiles'])!=set(_CALLERS):
            raise ValueError()
        profiles=[]
        for purpose,item in value['profiles'].items():
            if (type(item) is not dict or set(item)!=
                    {'host','port','database','user','passfile','passfileSha256','manifestSha256'}
                    or item['host'] not in {'127.0.0.1','localhost','::1'}
                    or type(item['port']) is not int or not 1<=item['port']<=65535
                    or type(item['database']) is not str
                    or re.fullmatch('[A-Za-z0-9_]{1,63}',item['database']) is None
                    or item['user']!=_CALLERS[purpose]
                    or any(type(item[k]) is not str or not _HASH.fullmatch(item[k])
                           for k in ('passfileSha256','manifestSha256'))):
                raise ValueError()
            passfile=Path(item['passfile'])
            password_raw=_private_bytes(passfile,maximum=16384)
            if hashlib.sha256(password_raw).hexdigest()!=item['passfileSha256']:
                raise ValueError()
            # Exact single connection credential, no wildcard/service fallback.
            escaped_host=item['host'].replace('\\','\\\\').replace(':','\\:')
            prefix=f"{escaped_host}:{item['port']}:{item['database']}:{item['user']}:".encode()
            if (not password_raw.startswith(prefix) or b'\n' in password_raw.rstrip(b'\n')
                    or not password_raw[len(prefix):].strip()):
                raise ValueError()
            profiles.append(PurposeProfile(purpose,item['host'],item['port'],item['database'],
                item['user'],passfile,item['passfileSha256'],item['manifestSha256']))
        # Cross-purpose credentials must address exactly the same database/seal.
        if len({(p.host,p.port,p.database,p.manifest_sha256) for p in profiles})!=1:
            raise ValueError()
        return ProtectedRenewalConfig(Path(path),hashlib.sha256(raw).hexdigest(),value['enabled'],
            identity_path,digest,binding,tuple(sorted(profiles,key=lambda p:p.purpose)),
            tuple(sorted(value['packageSources'].items())))
    except Exception:
        raise RenewalConnectionBlocked('RENEWAL_PRIVATE_CONFIG_REQUIRED') from None


@contextmanager
def open_purpose_connection(config,purpose,read_only):
    if type(config) is not ProtectedRenewalConfig or type(read_only) is not bool:
        raise RenewalConnectionBlocked('RENEWAL_PROTECTED_CONNECTION_REQUIRED')
    fresh=load_protected_config(config.path)
    if fresh!=config or not fresh.enabled or any(os.environ.get(k) for k in _FORBIDDEN_ENV):
        raise RenewalConnectionBlocked('RENEWAL_CONFIG_CLOSED_OR_DRIFTED')
    profile=fresh.profile(purpose)
    os.environ.update(dict(fresh.binding.validated_oidc_environment))
    conn=None
    try:
        try:
            conn=psycopg.connect(host=profile.host,port=profile.port,dbname=profile.database,
                user=profile.user,passfile=str(profile.passfile),connect_timeout=5,
                options='-c statement_timeout=5000 -c lock_timeout=1000')
            store=RenewalAuthorityStore(conn,checker_binding=fresh.binding)
            with conn.transaction():
                conn.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY')
                conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
                _database_identity(conn,purpose)
                with conn.cursor(row_factory=dict_row) as cur:
                    seal=cur.execute("SELECT obj_description('public.aip_budget_policy_renewal_proposal'::regclass,'pg_class') AS seal").fetchone()['seal']
                    if not isinstance(seal,str) or hashlib.sha256(seal.encode()).hexdigest()!=profile.manifest_sha256:
                        raise RenewalConnectionBlocked('RENEWAL_DEPLOYED_MANIFEST_DRIFT')
                    store._verify_native_manifest(cur)
        except RenewalConnectionBlocked:
            raise
        except Exception:
            raise RenewalConnectionBlocked('RENEWAL_PURPOSE_CONNECTION_UNAVAILABLE') from None
        conn.read_only=read_only
        # Operation exceptions, especially unknown COMMIT, retain their identity.
        yield conn
    finally:
        if conn is not None:
            conn.close()
