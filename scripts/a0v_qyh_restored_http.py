#!/usr/bin/env python3
"""Read-only HTTP attachment preflight for the preserved Qiyuehui cluster.

This stage has no serve/write command. It can inspect an exact current
installation through the original release reader; OIDC, current configuration,
process switching and browser acceptance remain separate gates.
"""
from __future__ import annotations
import argparse
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
SELECTED_VERSIONS = {'domain.ecommerce.core': '1.4.3',
    'platform.ecommerce.niushop': '1.23.2', 'solution.ecommerce.growth': '1.13.0',
    'solution.ecommerce.operations-base': '1.2.2'}

class RestorationBlocked(RuntimeError):
    pass

def require_identity(observed, *, code_head):
    if any(observed.get(k) != v for k,v in EXPECTED.items()):
        raise RestorationBlocked('RESTORED_IDENTITY_DRIFT')
    if observed['schema'] != code_head:
        raise RestorationBlocked('RESTORED_CODE_SCHEMA_DRIFT')

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

def preflight(identity_file):
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
    require_identity(observed,code_head=previous._code_schema_head())
    report = inventory_report(observed, inventory)
    report['limitedLoginVerified'] = True
    report['volume'] = VOLUME
    report['databaseStartedAt'] = container['State']['StartedAt']
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

def select_current_installation(*, identity_file, bundle_root, trust_roots_file, installation_id):
    report = preflight(identity_file)
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

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-identity-file',type=Path,required=True)
    parser.add_argument('--current-installation')
    parser.add_argument('--bundle-root',type=Path)
    parser.add_argument('--trust-roots-file',type=Path)
    args = parser.parse_args()
    values = (args.current_installation, args.bundle_root, args.trust_roots_file)
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
    main()
