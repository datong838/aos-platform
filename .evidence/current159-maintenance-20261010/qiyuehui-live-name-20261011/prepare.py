"""Fresh backup/read-only reconciliation for the explicitly authorized name CAS."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

R = Path(__file__).resolve().parent
ROOT = R.parents[1]
SPEC = importlib.util.spec_from_file_location("qyh_previous_name_preparation", ROOT / "qyh-org-name-maintenance-20261011/prepare.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
PRIVATE = R / "private"


def write(name, value):
    (R / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def inspect():
    item = json.loads(M.run(["docker", "--context", M.CTX, "inspect", "--format",
                            '{"Image":{{json .Image}},"Mounts":{{json .Mounts}}}', M.SOURCE]))
    assert item["Image"] == M.IMAGE
    assert any(x.get("Name") == "aos-a0v-recovery-pg-data" and x["Destination"] == "/var/lib/postgresql/data" for x in item["Mounts"])
    sql = """BEGIN READ ONLY; SELECT json_build_object(
      'cluster',(SELECT system_identifier::text FROM pg_control_system()),
      'schema',(SELECT version_num FROM alembic_version),
      'rows',(SELECT count(*) FROM meta_org WHERE id='org-org'),
      'name',(SELECT name FROM meta_org WHERE id='org-org'),
      'updatedAt',(SELECT updated_at::text FROM meta_org WHERE id='org-org'),
      'otherRowFields',(SELECT md5((to_jsonb(t)-'name'-'updated_at')::text) FROM meta_org t WHERE id='org-org'),
      'activeOtherConnections',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND state='active' AND pid<>pg_backend_pid())); COMMIT;"""
    result = json.loads(M.psql(M.SOURCE, M.DB, sql))
    assert result['cluster'] == '7683855731447750695' and result['schema'] == 'a0v_159' and result['rows'] == 1 and result['activeOtherConnections'] == 0
    return result


if __name__ == '__main__':
    assert not (R / 'backup-manifest.json').exists(), 'Existing result: reconcile only'
    before = inspect()
    assert before['name'] == 'org-org' and before['updatedAt'] == '2026-10-05 02:21:26.625638+00'
    fingerprint = M.fingerprint(M.SOURCE)
    baseline = json.loads((ROOT / 'qyh-org-name-maintenance-20261011/source-fingerprint-after-backup.json').read_text())
    assert fingerprint == baseline, 'Original full-restore baseline changed; re-evaluate before CAS'
    write('before.json', before)
    write('fingerprint-before.json', fingerprint)
    PRIVATE.mkdir(mode=0o700)
    for name, args in [('current.dump', ['pg_dump', '-U', 'aos_app', '-d', M.DB, '-Fc']),
                       ('globals.sql', ['pg_dumpall', '-U', 'aos_app', '--globals-only', '--no-role-passwords'])]:
        file = PRIVATE / name
        fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            result = subprocess.run(['docker', '--context', M.CTX, 'exec', M.SOURCE] + args,
                                    stdout=stream, stderr=subprocess.PIPE, timeout=180)
            assert result.returncode == 0, 'Backup failed; no mutation permitted'
    manifest = {}
    for path in sorted(PRIVATE.iterdir()):
        copy = PRIVATE / (path.name + '.second-copy')
        shutil.copyfile(path, copy)
        os.chmod(copy, 0o600)
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        assert hashlib.sha256(copy.read_bytes()).hexdigest() == expected
        manifest[path.name] = {'sha256': expected, 'bytes': path.stat().st_size, 'secondCopyChecksumMatches': True}
    assert M.fingerprint(M.SOURCE) == fingerprint and inspect() == before
    write('backup-manifest.json', {'outcome': 'FRESH_BACKUP_BASELINE_EXACT_NO_WRITE', 'tableCount': len(fingerprint), 'files': manifest, 'independentRestoreBaselineAlreadyVerified': True})
    print('FRESH_BACKUP_BASELINE_EXACT_NO_WRITE')
