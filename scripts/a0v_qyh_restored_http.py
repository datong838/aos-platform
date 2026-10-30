#!/usr/bin/env python3
"""Read-only HTTP attachment preflight for the preserved Qiyuehui cluster.

Default operation inspects an exact current installation through the original
release reader. Explicit limited serving additionally requires formal OIDC and
an independently verified frozen API source; Host and all workers remain off.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID
import a0v_current_preview_http as previous

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'qyh-restored-pg-20261011'
CONTEXT = 'colima-aos-extension'
VOLUME = 'aos-qyh-history159-prepared-data-20261011'
IMAGE = 'sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
EXPECTED = {'database': 'aos_meta_head', 'cluster': '7695302940039200809',
    'schema': 'a0v_159', 'orgId': 'org-org', 'orgName': '栖月汇商贸有限公司',
    'projectId': 'dev-project', 'tables': 647}
# Physical contracts for independently rehearsed migrations of this preserved
# cluster. Unknown revisions must be reviewed before the attachment gate opens.
SCHEMA_TABLE_COUNTS = {'a0v_159': 647, 'a0v_160': 650, 'a0v_161': 650, 'a0v_163': 658}
SELECTED_VERSIONS = {'domain.ecommerce.core': '1.4.3',
    'platform.ecommerce.niushop': '1.23.2', 'solution.ecommerce.growth': '1.13.0',
    'solution.ecommerce.operations-base': '1.2.2'}
LIMITED_PORT = 18080

class RestorationBlocked(RuntimeError):
    pass


def load_management_oidc_config(path):
    """Private exact local identity routing; never accept credentials here."""
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate key')
            value[key] = item
        return value
    try:
        path = Path(path)
        parent = path.parent.lstat()
        if (not path.is_absolute() or not stat.S_ISDIR(parent.st_mode)
                or parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) != 0o700):
            raise ValueError('private parent required')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as source:
            before = os.fstat(source.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                    or stat.S_IMODE(before.st_mode) != 0o600 or not 0 < before.st_size <= 16384):
                raise ValueError('private ordinary configuration required')
            raw = source.read(16385)
            after = os.fstat(source.fileno())
        if len(raw) > 16384 or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('configuration changed')
        value = json.loads(raw, object_pairs_hook=unique)
        fields = {'schemaVersion','issuer','audience','clientId','jwksUrl','tokenUrl','clockSkewSeconds'}
        issuer = 'http://127.0.0.1:18448/realms/qyh-local'
        if (type(value) is not dict or set(value) != fields
                or value['schemaVersion'] != 'aos.local-management-oidc/v1'
                or value['issuer'] != issuer or value['audience'] != 'aos-api'
                or value['clientId'] != 'aos-api'
                or value['jwksUrl'] != issuer + '/protocol/openid-connect/certs'
                or value['tokenUrl'] != issuer + '/protocol/openid-connect/token'
                or type(value['clockSkewSeconds']) is not int
                or not 0 <= value['clockSkewSeconds'] <= 5):
            raise ValueError('exact local identity contract required')
        return {'AOS_AUTH_ALLOW_DEV':'0', 'AOS_AUTH_EXTERNAL_ONLY':'1',
            'AOS_OIDC_ISSUER':issuer, 'AOS_OIDC_AUDIENCE':'aos-api',
            'AOS_OIDC_CLIENT_ID':'aos-api', 'AOS_OIDC_JWKS_URL':value['jwksUrl'],
            'AOS_OIDC_ISSUERS':'', 'AOS_OIDC_JWKS_URLS':'',
            'AOS_OIDC_TOKEN_URL':value['tokenUrl'], 'AOS_OIDC_TOKEN_ALG':'RS256',
            'AOS_OIDC_LEEWAY_SECONDS':str(value['clockSkewSeconds'])}
    except (OSError, ValueError, TypeError, KeyError):
        raise RestorationBlocked('RESTORED_LOCAL_OIDC_PRIVATE_EXACT_CONFIG_REQUIRED') from None


class ReadOnlyManagementApp:
    """Local inspection only; product authentication and tenant checks still run."""
    def __init__(self, app, *, allow_password_login=False):
        self.app = app
        self.allow_password_login = allow_password_login is True

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            await send({'type': 'websocket.close', 'code': 1008})
            return
        login = (self.allow_password_login and scope['type'] == 'http'
                 and scope['method'] == 'POST' and scope['path'] == '/v1/auth/token')
        if scope['type'] == 'http' and scope['method'] not in {'GET', 'HEAD', 'OPTIONS'} and not login:
            body = b'{"code":"RESTORED_MANAGEMENT_READ_ONLY","message":"Management inspection is read only."}'
            await send({'type': 'http.response.start', 'status': 405,
                        'headers': [(b'content-type', b'application/json'), (b'cache-control', b'no-store')]})
            await send({'type': 'http.response.body', 'body': body})
            return
        await self.app(scope, receive, send)

def require_identity(observed, *, code_head, management_readonly=False,
                     pending_renewal_absent=False):
    if type(management_readonly) is not bool or type(pending_renewal_absent) is not bool:
        raise RestorationBlocked('RESTORED_READONLY_COMPATIBILITY_INVALID')
    if any(observed.get(k) != v for k,v in EXPECTED.items()
           if k not in {'schema', 'tables'}):
        raise RestorationBlocked('RESTORED_IDENTITY_DRIFT')
    tables = SCHEMA_TABLE_COUNTS.get(observed.get('schema'))
    if tables is None or observed.get('tables') != tables:
        raise RestorationBlocked('RESTORED_IDENTITY_DRIFT')
    if observed['schema'] != code_head:
        if not (management_readonly and pending_renewal_absent
                and observed['schema']=='a0v_161' and code_head=='a0v_162'):
            raise RestorationBlocked('RESTORED_CODE_SCHEMA_DRIFT')
        # Only the independently delivered closed candidate may remain pending.
        # Never infer that a future or modified migration is safe to bypass.
        pins={
            'services/aos-api/alembic/versions/a0v_162_budget_policy_renewal.py':
                '9426ad5bc3b027e02c21f1317fec603576b541200982460e310567e11f32f761',
            'services/aos-api/aos_api/aip_budget_policy_renewal_authority.sql':
                'febed109685624c872fbc68d307a81c44b90f405cd8e7d2fefa30503a63cead5',
        }
        try:
            if any((ROOT/name).is_symlink() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest
                   for name,digest in pins.items()):
                raise OSError()
        except OSError:
            raise RestorationBlocked('RESTORED_PENDING_CANDIDATE_SOURCE_DRIFT') from None

def inventory_report(identity, inventory):
    return {'outcome': 'RESTORED_HTTP_ATTACHMENT_INVENTORY_ONLY',
        'identity': identity, 'inventory': inventory, 'apiStartAuthorized': False,
        'eightWorkbenchesVerified': False, 'runtimeHostEnabled': False,
        'remainingGates': ['current signed release and installation',
                          'current configuration and formal identity',
                          'API/Web restart and eight-page browser acceptance']}

def _private(path):
    if path.is_symlink() or not path.is_file():
        raise RestorationBlocked('RESTORED_IDENTITY_FILE_INVALID')
    s = path.stat()
    if stat.S_IMODE(s.st_mode) != 0o600 or s.st_uid != os.getuid():
        raise RestorationBlocked('RESTORED_IDENTITY_FILE_PERMISSION')
    return path.resolve(strict=True)

def _identity_parameters(identity_file):
    data = json.loads(_private(identity_file).read_text())
    if (set(data) != {'host','port','dbname','user','pgpassfile'}
        or data['host'] != '127.0.0.1' or type(data['port']) is not int
        or data['port'] != 18446 or data['dbname'] != EXPECTED['database']
        or data['user'] != 'qyh_restored_api_login'):
        raise RestorationBlocked('RESTORED_LOGIN_TARGET_DRIFT')
    data['pgpassFile'] = str(_private(Path(data.pop('pgpassfile'))))
    return data

def preflight(identity_file, *, management_readonly=False, source_candidate=None):
    frozen_code_head = None
    if source_candidate is not None:
        if management_readonly is not True:
            raise RestorationBlocked('RESTORED_FROZEN_SCHEMA_READONLY_REQUIRED')
        frozen_code_head = _readonly_candidate_schema_head(source_candidate)
    data = _identity_parameters(identity_file)
    previous._verify_limited_login(data)
    proc = subprocess.run(['docker','--context',CONTEXT,'inspect','--format',
        '{"Image":{{json .Image}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}},"State":{{json .State}}}',TARGET],
        check=True,capture_output=True,timeout=30)
    container = json.loads(proc.stdout)
    if (container['Image'] != IMAGE or not container['State']['Running']
        or len(container['Mounts']) != 1 or container['Mounts'][0].get('Name') != VOLUME
        or container['Ports'].get('5432/tcp') != [{'HostIp':'127.0.0.1','HostPort':'18446'}]):
        raise RestorationBlocked('RESTORED_CONTAINER_DRIFT')
    # Native cluster control metadata needs local maintenance access. This
    # subprocess has a literal READ ONLY query, never service credentials.
    sql = """BEGIN READ ONLY; SELECT json_build_object(
      'database',current_database(),
      'cluster',(SELECT system_identifier::text FROM pg_control_system()),
      'schema',(SELECT version_num FROM alembic_version),
      'pendingRenewalAbsent',to_regclass('public.aip_budget_policy_renewal_proposal') IS NULL
        AND to_regclass('public.aip_budget_policy_renewal_decision') IS NULL
        AND to_regclass('public.aip_budget_policy_renewal_receipt') IS NULL
        AND NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname LIKE 'aos_budget_renewal_%'),
      'orgId',(SELECT id FROM meta_org WHERE id='org-org'),
      'orgName',(SELECT name FROM meta_org WHERE id='org-org'),
      'projectId',(SELECT project_id FROM meta_workspace WHERE project_id='dev-project' AND org_id='org-org'),
      'tables',(SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%'),
      'inventory',json_build_object(
        'installations',(SELECT count(*) FROM bundle_installation WHERE org_id='org-org' AND project_id='dev-project'),
        'configurations',(SELECT count(*) FROM extension_runtime_configuration WHERE org_id='org-org' AND project_id='dev-project'),
        'bindings',(SELECT count(*) FROM extension_runtime_binding WHERE org_id='org-org' AND project_id='dev-project'),
        'enabledBindings',(SELECT count(*) FROM extension_runtime_binding WHERE org_id='org-org' AND project_id='dev-project' AND enabled)));
      COMMIT;"""
    proc = subprocess.run(['docker','--context',CONTEXT,'exec','-i',TARGET,
        'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','aos_app','-d','aos_meta_head'],
        input=sql.encode(),check=True,capture_output=True,timeout=30)
    observed = json.loads(proc.stdout)
    inventory = observed.pop('inventory')
    pending_absent=observed.pop('pendingRenewalAbsent')
    code_head = (frozen_code_head if frozen_code_head is not None
                 else previous._code_schema_head())
    require_identity(observed,code_head=code_head,management_readonly=management_readonly,
                     pending_renewal_absent=pending_absent)
    report = inventory_report(observed, inventory)
    report['limitedLoginVerified'] = True
    report['volume'] = VOLUME
    report['databaseStartedAt'] = container['State']['StartedAt']
    report['codeSchema']=code_head
    report['pendingCodeCandidateNotApplied']=observed['schema']!=code_head
    return report

def require_selected_installation(view, *, installation_id):
    try:
        exact_id = str(UUID(installation_id))
    except (ValueError, TypeError, AttributeError):
        raise RestorationBlocked('RESTORED_INSTALLATION_ID_INVALID') from None
    if (view.scope != ('org-org', 'dev-project') or view.installation_id != exact_id
        or view.authorization != 'EVIDENCE_ONLY_NO_START'):
        raise RestorationBlocked('RESTORED_INSTALLATION_SCOPE_OR_AUTHORITY_DRIFT')
    versions = {(r.publisher, r.bundle_id): r.version for r in view.releases}
    if (len(view.releases) != 4 or len(versions) != 4
        or versions != {('aos', bid): version for bid, version in SELECTED_VERSIONS.items()}):
        raise RestorationBlocked('RESTORED_SELECTED_RELEASE_SET_DRIFT')
    return {'installationId': exact_id, 'installationRevision': view.current_revision,
        'etagVersion': view.etag_version, 'growthVersion': SELECTED_VERSIONS['solution.ecommerce.growth'],
        'releases': [{'publisher': r.publisher, 'id': r.bundle_id, 'version': r.version,
                      'contentHash': r.content_hash} for r in view.releases],
        'authorization': 'CURRENT_INSTALLATION_EVIDENCE_ONLY_NO_START',
        'apiStartAuthorized': False, 'runtimeHostEnabled': False,
        'currentConfigurationVerified': False, 'eightWorkbenchesVerified': False}

def select_current_installation(*, identity_file, bundle_root, trust_roots_file, installation_id,
                                management_readonly=False, source_candidate=None):
    if type(management_readonly) is not bool:
        raise RestorationBlocked('RESTORED_READONLY_COMPATIBILITY_INVALID')
    if source_candidate is not None:
        if management_readonly is not True:
            raise RestorationBlocked('RESTORED_FROZEN_SCHEMA_READONLY_REQUIRED')
        report = preflight(identity_file, management_readonly=True,
                           source_candidate=source_candidate)
    else:
        report = (preflight(identity_file,management_readonly=True) if management_readonly is True
                  else preflight(identity_file))
    parameters = _identity_parameters(identity_file)
    sys.path.insert(0, str(ROOT / 'services/aos-api'))
    from psycopg import connect
    from psycopg.rows import dict_row
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.extension_runtime.current_installation_release_evidence import (
        CurrentReleaseEvidenceBlocked, read_current_installation_release_evidence,
    )
    from aos_api.tenant_scope import TenantScope
    trust = FileTrustRootProvider(trust_roots_file).snapshot()
    loader = ManifestLoader({'a0v-canonical': bundle_root, 'a0v-qyh-current': bundle_root,
                             'a0v-current': bundle_root}, trust_roots=trust)

    @contextmanager
    def factory():
        with connect(host=parameters['host'], port=parameters['port'],
                     dbname=parameters['dbname'], user=parameters['user'],
                     passfile=parameters['pgpassFile'], row_factory=dict_row) as conn:
            conn.read_only = True
            yield conn
    try:
        view = read_current_installation_release_evidence(connect_factory=factory,
            scope=TenantScope('org-org', 'dev-project'), installation_id=installation_id,
            release_policy=ReleasePolicy(trust_roots=trust), loader=loader)
    except CurrentReleaseEvidenceBlocked as exc:
        raise RestorationBlocked('RESTORED_CURRENT_RELEASE_REJECTED:' + str(exc)) from None
    selected = require_selected_installation(view, installation_id=installation_id)
    return {**report, 'outcome': 'RESTORED_CURRENT_INSTALLATION_EVIDENCE_ONLY',
            'currentInstallation': selected}

def require_api_source_candidate(report_path):
    task = ROOT / '.evidence/qyh-full-system-restoration-20261011'
    if (report_path.is_symlink() or not report_path.is_file()
        or report_path.resolve().parent != task.resolve()
        or report_path.stat().st_uid != os.getuid()):
        raise RestorationBlocked('RESTORED_API_SOURCE_CANDIDATE_INVALID')
    report = json.loads(report_path.read_text())
    head = report.get('head', '')
    if (type(head) is not str or len(head) != 40
        or any(c not in '0123456789abcdef' for c in head)
        or report.get('outcome') != 'CURRENT_M1_API_SOURCE_CANDIDATE_FROZEN_NO_START'):
        raise RestorationBlocked('RESTORED_API_SOURCE_CANDIDATE_INVALID')
    source = task / 'private' / ('api-source-' + head)
    if report.get('source') != str(source) or source.resolve() != source or not source.is_dir():
        raise RestorationBlocked('RESTORED_API_SOURCE_CANDIDATE_INVALID')
    manifest_path = _private(source.parent / ('api-manifest-' + head + '.json'))
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != report.get('manifestSha256'):
        raise RestorationBlocked('RESTORED_API_SOURCE_MANIFEST_DRIFT')
    manifest = json.loads(raw)
    observed = {}
    for path in [source, *source.rglob('*')]:
        mode = stat.S_IMODE(path.stat().st_mode)
        if (path.is_symlink() or path.stat().st_uid != os.getuid()
            or (not path.is_file() and not path.is_dir())
            or mode != (0o600 if path.is_file() else 0o700)):
            raise RestorationBlocked('RESTORED_API_SOURCE_PERMISSION_DRIFT')
        if path.is_file():
            observed[str(path.relative_to(source))] = hashlib.sha256(path.read_bytes()).hexdigest()
    if observed != manifest or len(observed) != report.get('fileCount'):
        raise RestorationBlocked('RESTORED_API_SOURCE_FILES_DRIFT')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, timeout=30)
    if git('branch', '--show-current').strip() != b'm1' or git('rev-parse', '--show-object-format').strip() != b'sha1':
        raise RestorationBlocked('RESTORED_API_SOURCE_BRANCH_OR_FORMAT_DRIFT')
    tree = git('ls-tree', '-rz', 'HEAD', '--', 'services/aos-api',
               'scripts/a0v_current_preview_http.py', 'scripts/a0v_qyh_restored_http.py')
    api_paths = set()
    for item in tree.split(b'\0'):
        if not item:
            continue
        metadata, raw_path = item.split(b'\t', 1)
        mode, kind, oid = metadata.split()
        name = raw_path.decode('utf-8')
        if mode not in {b'100644', b'100755'} or kind != b'blob' or name not in manifest:
            raise RestorationBlocked('RESTORED_CURRENT_API_SOURCE_DRIFT')
        data = (source / name).read_bytes()
        actual_oid = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest().encode()
        if actual_oid != oid:
            raise RestorationBlocked('RESTORED_CURRENT_API_SOURCE_DRIFT')
        if name.startswith('services/aos-api/'):
            api_paths.add(name)
    if not api_paths or api_paths != {p for p in manifest if p.startswith('services/aos-api/')}:
        raise RestorationBlocked('RESTORED_CURRENT_API_SOURCE_DRIFT')
    if Path(previous.__file__).read_bytes() != (source / 'scripts/a0v_current_preview_http.py').read_bytes():
        raise RestorationBlocked('RESTORED_CURRENT_STARTUP_FLAGS_SOURCE_DRIFT')
    return source


def _readonly_candidate_schema_head(report_path):
    """Compare the database with the exact committed source that will run."""
    source = require_api_source_candidate(report_path)
    # Startup inspection must not mutate the frozen source it validates.
    original_bytecode_flag = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        config = previous.Config()
        config.set_main_option('script_location', str(source / 'services/aos-api/alembic'))
        heads = previous.ScriptDirectory.from_config(config).get_heads()
    except Exception:
        raise RestorationBlocked('RESTORED_FROZEN_CODE_SCHEMA_UNAVAILABLE') from None
    finally:
        sys.dont_write_bytecode = original_bytecode_flag
    if len(heads) != 1 or not isinstance(heads[0], str) or not heads[0]:
        raise RestorationBlocked('RESTORED_FROZEN_CODE_SCHEMA_UNAVAILABLE')
    return heads[0]

def prepare_limited_launch(*, identity_file, bundle_root, trust_roots_file,
                           installation_id, source_candidate):
    # Existing authentication gate runs before any DB or process action.
    try:
        previous._require_external_oidc()
    except previous.PreviewBlocked as exc:
        raise RestorationBlocked(str(exc)) from None
    if not previous._port_free(LIMITED_PORT):
        raise RestorationBlocked('RESTORED_HTTP_PORT_OCCUPIED')
    source = require_api_source_candidate(source_candidate)
    report = select_current_installation(identity_file=identity_file,
        bundle_root=bundle_root, trust_roots_file=trust_roots_file,
        installation_id=installation_id)
    identity = _identity_parameters(identity_file)
    from psycopg.conninfo import make_conninfo
    forbidden = {'AOS_DATABASE_URL', 'PGPASSWORD', 'PGPASSFILE', 'PGHOST', 'PGPORT', 'PGOPTIONS',
        'PGDATABASE', 'PGUSER', 'PGSERVICE', 'PGSERVICEFILE', 'PYTHONPATH', 'PYTHONHOME'}
    environment = {k:v for k,v in os.environ.items() if k not in forbidden}
    environment.update(previous.FLAGS)
    environment.update({'AOS_AUTH_ALLOW_DEV': '0', 'AOS_AUTH_EXTERNAL_ONLY': '1',
        'AOS_REST_CONNECTOR_MOCK': '0', 'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHONPATH': str(source / 'services/aos-api'),
        'PGPASSFILE': identity['pgpassFile'],
        'AOS_DATABASE_URL': make_conninfo(host=identity['host'], port=identity['port'],
            dbname=identity['dbname'], user=identity['user']),
        'AOS_BUNDLE_ROOT': str(bundle_root.resolve(strict=True)),
        'AOS_BUNDLE_TRUST_ROOTS_FILE': str(trust_roots_file.resolve(strict=True))})
    command = [sys.executable, '-m', 'uvicorn', 'aos_api.main:app', '--host',
        '127.0.0.1', '--port', str(LIMITED_PORT), '--workers', '1',
        '--no-access-log', '--log-level', 'warning']
    public = {'outcome': 'RESTORED_HTTP_LIMITED_STARTING', 'database': EXPECTED['database'],
        'installationId': report['currentInstallation']['installationId'],
        'port': LIMITED_PORT, 'runtimeAuthorized': False, 'workersEnabled': 0,
        'eightPagesAccepted': False, 'migrationMode': 'disabled',
        'currentConfigurationVerified': False, 'formalOwnerVerified': False}
    return command, environment, public

def serve_limited(**arguments):
    command, environment, public = prepare_limited_launch(**arguments)
    print(json.dumps(public, ensure_ascii=False), flush=True)
    os.chdir(Path(environment['PYTHONPATH']).parents[1])
    os.execve(sys.executable, command, environment)


def installed_readonly_environment(installation_id, *, management_oidc_config):
    """Explicit viewing selection; never a runtime-start or approval flag."""
    if installation_id is None:
        return {}
    from uuid import UUID
    try:
        if not isinstance(installation_id, str) or str(UUID(installation_id)) != installation_id:
            raise ValueError('Canonical UUID required')
    except (ValueError, TypeError, AttributeError):
        raise RestorationBlocked('INSTALLED_READONLY_SELECTION_INVALID') from None
    if management_oidc_config is None:
        raise RestorationBlocked('INSTALLED_READONLY_REAL_LOGIN_REQUIRED')
    return {'AOS_INSTALLED_READONLY_CATALOG': json.dumps({
        'installationId': installation_id, 'orgId': 'org-org', 'projectId': 'dev-project'})}


def serve_management_readonly(*, identity_file, bundle_root, trust_roots_file, source_candidate,
                              management_oidc_config=None, installed_readonly_installation=None):
    """Attach preserved local management data without enabling formal execution."""
    if not previous._port_free(LIMITED_PORT):
        raise RestorationBlocked('RESTORED_HTTP_PORT_OCCUPIED')
    source = require_api_source_candidate(source_candidate)
    oidc_environment = load_management_oidc_config(management_oidc_config) if management_oidc_config is not None else None
    readonly_catalog_environment = installed_readonly_environment(
        installed_readonly_installation, management_oidc_config=management_oidc_config)
    if installed_readonly_installation is not None:
        select_current_installation(identity_file=identity_file, bundle_root=bundle_root,
            trust_roots_file=trust_roots_file, installation_id=installed_readonly_installation,
            management_readonly=True, source_candidate=source_candidate)
    preflight(identity_file,management_readonly=True, source_candidate=source_candidate)
    identity = _identity_parameters(identity_file)
    from psycopg import connect
    from psycopg.conninfo import make_conninfo
    dsn = make_conninfo(host=identity['host'], port=identity['port'],
        dbname=identity['dbname'], user=identity['user'],
        options='-c default_transaction_read_only=on')
    with connect(dsn, passfile=identity['pgpassFile']) as conn:
        if conn.execute('SHOW transaction_read_only').fetchone() != ('on',):
            raise RestorationBlocked('RESTORED_MANAGEMENT_DATABASE_NOT_READONLY')
    # Never inherit separate protected command/owner/provider identities.
    environment = {k: v for k, v in os.environ.items()
                   if not k.startswith(('AOS_', 'PG')) and k not in {'PYTHONPATH', 'PYTHONHOME'}}
    environment.update(previous.FLAGS)
    environment.update({'AOS_AUTH_ALLOW_DEV': '1', 'AOS_AUTH_EXTERNAL_ONLY': '0',
        'AOS_REST_CONNECTOR_MOCK': '0', 'PYTHONDONTWRITEBYTECODE': '1',
        'PGPASSFILE': identity['pgpassFile'], 'AOS_DATABASE_URL': dsn,
        'AOS_BUNDLE_ROOT': str(bundle_root.resolve(strict=True)),
        'AOS_BUNDLE_TRUST_ROOTS_FILE': str(trust_roots_file.resolve(strict=True))})
    environment.update(readonly_catalog_environment)
    environment['PYTHONPATH'] = os.pathsep.join([str(source / 'services/aos-api'), str(source / 'scripts')])
    if oidc_environment is not None:
        environment.update(oidc_environment)
        environment['AOS_LOCAL_MANAGEMENT_OIDC_CONFIG'] = str(management_oidc_config)
    print(json.dumps({'outcome': 'RESTORED_LOCAL_MANAGEMENT_READONLY_STARTING',
        'port': LIMITED_PORT, 'databaseReadOnly': True, 'mutationRequestsAllowed': False,
        'passwordLoginRequestsAllowed': oidc_environment is not None,
        'formalIdentityVerified': False, 'runtimeAuthorized': False, 'eightPagesAccepted': False}), flush=True)
    os.chdir(source)
    command = management_command()
    os.execve(sys.executable, command, environment)


def management_command():
    # Schema preflight imports migration modules. A fresh interpreter prevents
    # those working-tree imports from contaminating frozen API source loading.
    return [sys.executable, '-m', 'uvicorn',
            'a0v_qyh_restored_http:management_app', '--factory', '--host', '127.0.0.1',
            '--port', str(LIMITED_PORT), '--workers', '1', '--no-access-log', '--log-level', 'warning']


def management_app():
    config = os.environ.get('AOS_LOCAL_MANAGEMENT_OIDC_CONFIG')
    if config:
        os.environ.update(load_management_oidc_config(config))
    from aos_api.main import app
    api_file = Path(sys.modules['aos_api.main'].__file__).resolve()
    if api_file != Path.cwd() / 'services/aos-api/aos_api/main.py':
        raise RestorationBlocked('RESTORED_MANAGEMENT_SOURCE_IMPORT_DRIFT')
    if config and os.environ.get('AOS_INSTALLED_READONLY_CATALOG'):
        routes = __import__('aos_api.routers.ecommerce_workshop',
                            fromlist=['get_ecommerce_workshop_read_catalog'])
        installed = __import__('aos_api.ecommerce_installed_readonly_catalog',
                               fromlist=['build_installed_readonly_catalog'])
        app.dependency_overrides[routes.get_ecommerce_workshop_read_catalog] = (
            installed.build_installed_readonly_catalog)
    return ReadOnlyManagementApp(app, allow_password_login=bool(config))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-identity-file',type=Path,required=True)
    parser.add_argument('--current-installation')
    parser.add_argument('--bundle-root',type=Path)
    parser.add_argument('--trust-roots-file',type=Path)
    parser.add_argument('--serve-limited', action='store_true')
    parser.add_argument('--serve-management-readonly', action='store_true')
    parser.add_argument('--management-oidc-config', type=Path)
    parser.add_argument('--installed-readonly-installation')
    parser.add_argument('--source-candidate', type=Path)
    args = parser.parse_args()
    if args.management_oidc_config is not None and not args.serve_management_readonly:
        parser.error('local management OIDC requires explicit management readonly serving')
    if args.installed_readonly_installation is not None and not args.serve_management_readonly:
        parser.error('installed readonly selection requires management readonly serving')
    values = (args.current_installation, args.bundle_root, args.trust_roots_file)
    if args.serve_management_readonly:
        if (args.serve_limited or args.current_installation is not None
            or args.bundle_root is None or args.trust_roots_file is None or args.source_candidate is None):
            parser.error('management inspection requires bundle root, trust roots, source candidate; no runtime installation or limited start')
        serve_management_readonly(identity_file=args.api_identity_file, bundle_root=args.bundle_root,
            trust_roots_file=args.trust_roots_file, source_candidate=args.source_candidate,
            management_oidc_config=args.management_oidc_config,
            installed_readonly_installation=args.installed_readonly_installation)
        return
    if args.serve_limited:
        if any(value is None for value in values) or args.source_candidate is None:
            parser.error('limited start requires current installation, bundle root, trust roots and source candidate')
        serve_limited(identity_file=args.api_identity_file, bundle_root=args.bundle_root,
            trust_roots_file=args.trust_roots_file, installation_id=args.current_installation,
            source_candidate=args.source_candidate)
        return
    if args.source_candidate is not None:
        parser.error('source candidate requires explicit limited start')
    if any(value is not None for value in values):
        if any(value is None for value in values):
            parser.error('current installation, bundle root and trust roots are required together')
        report = select_current_installation(identity_file=args.api_identity_file,
            bundle_root=args.bundle_root, trust_roots_file=args.trust_roots_file,
            installation_id=args.current_installation)
    else:
        report = preflight(args.api_identity_file)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    try:
        main()
    except RestorationBlocked as exc:
        print(json.dumps({'outcome': 'RESTORED_HTTP_STARTUP_REJECTED', 'reason': str(exc),
            'apiStarted': False, 'runtimeAuthorized': False}, ensure_ascii=False), flush=True)
        raise SystemExit(2)
