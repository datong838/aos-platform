#!/usr/bin/env python3
"""Read-only HTTP attachment preflight for the preserved Qiyuehui cluster.

This stage deliberately has no serve/write command. Signature/current release,
OIDC, installation configuration and browser acceptance remain separate gates.
"""
from __future__ import annotations
import argparse
import json
import os
import stat
import subprocess
from pathlib import Path
import a0v_current_preview_http as previous

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'qyh-restored-pg-20261011'
CONTEXT = 'colima-aos-extension'
VOLUME = 'aos-qyh-history159-prepared-data-20261011'
IMAGE = 'sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
EXPECTED = {'database': 'aos_meta_head', 'cluster': '7695302940039200809',
    'schema': 'a0v_159', 'orgId': 'org-org', 'orgName': '栖月汇商贸有限公司',
    'projectId': 'dev-project', 'tables': 647}

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

def preflight(identity_file):
    data = json.loads(_private(identity_file).read_text())
    if (set(data) != {'host','port','dbname','user','pgpassfile'}
        or data['host'] != '127.0.0.1' or type(data['port']) is not int
        or data['port'] != 18446 or data['dbname'] != EXPECTED['database']
        or data['user'] != 'qyh_restored_api_login'):
        raise RestorationBlocked('RESTORED_LOGIN_TARGET_DRIFT')
    data['pgpassFile'] = str(_private(Path(data.pop('pgpassfile'))))
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

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-identity-file',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(preflight(args.api_identity_file),ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
