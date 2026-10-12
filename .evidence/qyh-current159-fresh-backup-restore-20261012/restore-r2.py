"""Full native restore on a new isolated DB, retaining earlier failed attempts."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

OUT = Path(__file__).resolve().parent
DOCKER = ['docker', '--context', 'colima-aos-extension']
SOURCE = 'qyh-restored-pg-20261011'
LAB = 'qyh-current159-exact-restore-20261012'
DB = 'qyh_current159_full_restore_r2_20261012'


def save(name, value):
    with (OUT / name).open('x') as stream:
        json.dump(value, stream, indent=2)


def sql(container, database, query):
    return subprocess.check_output(DOCKER + ['exec', '-i', container, 'psql', '-X', '-qAt', '-v',
        'ON_ERROR_STOP=1', '-U', 'aos_app', '-d', database],
        input='BEGIN READ ONLY; ' + query + ' COMMIT;', text=True)


def module(name):
    spec = importlib.util.spec_from_file_location(name, OUT / 'backup_restore.py')
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def schema(container, database, filename):
    result = subprocess.run(DOCKER + ['exec', container, 'pg_dump', '--schema-only', '-U', 'aos_app', '-d', database],
                            capture_output=True)
    assert result.returncode == 0
    fd = os.open(OUT / 'private' / filename, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(result.stdout)
    return b'\n'.join(line for line in result.stdout.splitlines()
                      if not line.startswith((b'\\restrict ', b'\\unrestrict ')))


def sequences(container, database):
    names = json.loads(sql(container, database, "SELECT coalesce(json_agg(json_build_object('schema',n.nspname,'name',c.relname) ORDER BY n.nspname,c.relname),'[]') FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='S' AND n.nspname NOT IN ('pg_catalog','information_schema');"))
    result = {}
    for row in names:
        qualified = '.'.join('"' + row[k].replace('"', '""') + '"' for k in ('schema', 'name'))
        result[row['schema'] + '.' + row['name']] = json.loads(sql(container, database,
            'SELECT json_build_object(\'last_value\',last_value,\'is_called\',is_called) FROM ' + qualified + ';'))
    return result


def roles(container):
    return json.loads(sql(container, 'postgres', """SELECT json_build_object(
    'roles',(SELECT json_agg(row_to_json(r) ORDER BY r.rolname) FROM
      (SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls,rolconnlimit,rolvaliduntil,rolconfig
       FROM pg_roles WHERE rolname NOT LIKE 'pg_%') r),
    'members',(SELECT coalesce(json_agg(row_to_json(g) ORDER BY g.role,g.member,g.grantor),'[]') FROM
      (SELECT r.rolname AS role,u.rolname AS member,z.rolname AS grantor,m.admin_option,m.inherit_option,m.set_option
       FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid JOIN pg_roles u ON u.oid=m.member JOIN pg_roles z ON z.oid=m.grantor
       WHERE r.rolname NOT LIKE 'pg_%' AND u.rolname NOT LIKE 'pg_%') g));"""))


def main():
    assert not (OUT / 'full-restore-r2-intent.json').exists(), 'Reconcile prior r2, never replay'
    lab = json.loads(subprocess.check_output(DOCKER + ['inspect', LAB]))[0]
    old = json.loads((OUT / 'exact-lab-created.json').read_text())
    assert lab['Id'] == old['containerId'] and lab['State']['Running']
    assert lab['HostConfig']['NetworkMode'] == 'none' and not lab['HostConfig']['PortBindings']
    assert lab['Mounts'][0]['Name'] == 'aos-qyh-current159-exact-restore-20261012'
    assert sql(LAB, 'aos_meta_head', "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%';").strip() == '0'
    assert sql(LAB, 'postgres', "SELECT count(*) FROM pg_database WHERE datname='" + DB + "';").strip() == '0'
    baseline = json.loads((OUT / 'current-baseline.json').read_text())
    fresh = module('current_source_native_fingerprint')
    assert fresh.source_fingerprint() == baseline and len(baseline) == 647
    expected = json.loads((OUT / 'backup-terminal.json').read_text())['backupSHA256']
    archive = OUT / 'private' / 'copy' / 'current.dump'
    for path in [archive, OUT / 'private' / 'current.dump']:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    before_roles = roles(SOURCE)
    assert roles(LAB) == before_roles
    before_sequences = sequences(SOURCE, 'aos_meta_head')
    before_schema = schema(SOURCE, 'aos_meta_head', 'source-schema-r2.sql')
    save('full-restore-r2-intent.json', {'ownedContainerId': lab['Id'], 'ownedDatabase': DB,
        'backupSHA256': expected, 'oldFailedDatabaseTables': 0, 'sourceTables': 647,
        'singleTransaction': True, 'networkNone': True, 'realDatabaseMigrated': False})
    subprocess.run(DOCKER + ['exec', LAB, 'createdb', '-U', 'aos_app', '-O', 'aos_app', DB],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    save('full-restore-r2-created.json', {'ownedDatabase': DB, 'createdSuccessfully': True})
    log = OUT / 'private' / 'full-restore-r2.log'
    fd = os.open(log, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as stream, archive.open('rb') as input_stream:
        result = subprocess.run(DOCKER + ['exec', '-i', '-e', 'PGOPTIONS=-c session_replication_role=replica', LAB,
            'pg_restore', '--single-transaction', '--exit-on-error', '-U', 'aos_app', '-d', DB],
            stdin=input_stream, stdout=stream, stderr=stream)
    save('full-restore-r2-terminal.json', {'exitCode': result.returncode, 'ownedDatabase': DB})
    assert result.returncode == 0, 'Full restore failed; diagnose retained private log and reconcile'
    restored = module('isolated_restore_native_fingerprint')
    restored.current_sql = lambda query: sql(LAB, DB, query)
    assert restored.source_fingerprint() == baseline
    after_schema = schema(LAB, DB, 'restored-schema-r2.sql')
    schema_equal = after_schema == before_schema
    sequence_equal = sequences(LAB, DB) == before_sequences
    role_equal = roles(LAB) == before_roles
    source_equal = fresh.source_fingerprint() == baseline
    save('full-restore-r2-comparison.json', {'all647TableDataHashesAndCountsMatch': True,
        'fullSchemaSQLIncludingOwnersACLsEqual': schema_equal,
        'sourceSchemaSHA256': hashlib.sha256(before_schema).hexdigest(),
        'restoredSchemaSHA256': hashlib.sha256(after_schema).hexdigest(),
        'sequencesEqual': sequence_equal, 'sequenceCount': len(before_sequences),
        'nonSystemRoleFlagsAndUserMembershipGrantorsEqual': role_equal,
        'roleCount': len(before_roles['roles']), 'userMembershipCount': len(before_roles['members']),
        'source647TableFingerprintsUnchanged': source_equal, 'actualRealMigration': False,
        'formalIdentityAndEightWorkbenchesAccepted': False})
    assert schema_equal and sequence_equal and role_equal and source_equal, 'Comparison failure; source unchanged, no migration'
    print(json.dumps({'independentFullRestoreTables': 647, 'schemaOwnersACLsEqual': True,
                      'sequencesEqual': True, 'sourceUnchanged': True, 'realMigration': False}), flush=True)


if __name__ == '__main__':
    main()
