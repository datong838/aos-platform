"""User-authorized actual human metadata enrollment; guarded, never replay."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
OUT = BASE / 'human-enrollment-20261013'
SUBJECT = '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
CONTEXT = 'colima-aos-extension'
SOURCE = 'qyh-restored-pg-20261011'

def record(name, value):
    with (OUT / name).open('x') as f:
        json.dump(value, f, indent=2); f.write('\n')

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

if __name__ == '__main__':
    assert not OUT.exists(), 'Existing attempt: read-only reconciliation required'
    os.environ['AOS_DOTENV_DISABLED'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.path.insert(0, str(ROOT / 'services/aos-api'))
    from psycopg.conninfo import make_conninfo
    identity = json.loads((BASE / 'private/restored-identity.json').read_text())
    os.environ['AOS_DATABASE_URL'] = make_conninfo(host=identity['host'], port=identity['port'],
        dbname=identity['dbname'], user=identity['user'], passfile=identity['pgpassfile'])
    os.environ['AOS_TWA_STORE'] = 'pg'
    ro = load('enrollment_readonly', ROOT / '.evidence/qyh-current159-fresh-backup-restore-20261012/backup_restore.py')
    state = json.loads(subprocess.check_output(['docker', '--context', CONTEXT, 'inspect', SOURCE], text=True))[0]
    assert state['Id'] == '84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c'
    assert state['State']['Running'] and state['Mounts'][0]['Name'] == 'aos-qyh-history159-prepared-data-20261011'
    assert ro.current_sql('SELECT version_num FROM alembic_version;').strip() == 'a0v_161'
    assert ro.current_sql('SELECT system_identifier FROM pg_control_system();').strip() == '7695302940039200809'
    assert ro.current_sql('SELECT count(*) FROM extension_runtime_binding WHERE enabled OR NOT operation_fence;').strip() == '0'
    for table in ['meta_membership', 'twa_ws_member', 'twa_person_profile']:
        assert ro.current_sql("SELECT count(*) FROM " + table + " WHERE subject='" + SUBJECT + "';").strip() == '0'
    from aos_api import twa_pg, membership, person_identity
    twa_pg.load_pg_to_memory()
    next_audit = 'aud-' + str(len(membership._AUDIT) + 1)
    assert ro.current_sql("SELECT count(*) FROM twa_audit WHERE id='" + next_audit + "';").strip() == '0'
    before = ro.source_fingerprint(); assert len(before) == 650
    OUT.mkdir(mode=0o700)
    record('intent.json', {'task': 'qyh-full-system-restoration-20261011', 'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'authority': 'Human explicitly authorized local administrator account and existing restoration in current chat',
        'subject': SUBJECT, 'tenant': 'org-org/dev-project', 'role': 'admin', 'existingRowsAbsent': True,
        'containerId': state['Id'], 'volume': state['Mounts'][0]['Name'], 'serviceStart': False})
    record('before.json', before)
    private = OUT / 'private'; private.mkdir(mode=0o700)
    dump = private / 'before.dump'
    fd = os.open(dump, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        result = subprocess.run(['docker','--context',CONTEXT,'exec',SOURCE,'pg_dump','-U','aos_app','-d','aos_meta_head','-Fc'],stdout=f,stderr=subprocess.PIPE,timeout=180)
    assert result.returncode == 0, 'Backup failed; no metadata writes'
    second = private / 'before.second.dump'
    fd = os.open(second, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f: f.write(dump.read_bytes())
    digest = hashlib.sha256(dump.read_bytes()).hexdigest()
    assert hashlib.sha256(second.read_bytes()).hexdigest() == digest
    with second.open('rb') as f:
        listing = subprocess.run(['docker','--context',CONTEXT,'exec','-i',SOURCE,'pg_restore','--list'],stdin=f,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=30)
    assert listing.returncode == 0
    record('backup.json', {'sha256': digest, 'secondSha256': digest, 'bytes': dump.stat().st_size, 'archiveValid': True})
    assert ro.source_fingerprint() == before
    member = membership.upsert_member('org-org','dev-project',SUBJECT,'admin',actor_id='qyh-user-authorized-account-maintainer-20261013')
    assert member['persisted'] is True, 'Partial result: reconcile only'
    person_identity.upsert_person_profile(SUBJECT, display_name='datong838')
    for table in ['meta_membership', 'twa_ws_member']:
        assert ro.current_sql("SELECT count(*) FROM " + table + " WHERE subject='" + SUBJECT + "' AND org_id='org-org' AND project_id='dev-project' AND role='admin';").strip() == '1'
        assert ro.current_sql("SELECT count(*) FROM " + table + " WHERE subject='" + SUBJECT + "';").strip() == '1'
    assert ro.current_sql("SELECT count(*) FROM twa_person_profile WHERE subject='"+SUBJECT+"' AND display_name='datong838' AND email IS NULL AND phone IS NULL;").strip() == '1'
    assert ro.current_sql("SELECT count(*) FROM twa_audit WHERE id='"+next_audit+"' AND action='membership.upsert';").strip() == '1'
    after = ro.source_fingerprint()
    changed = [table for table in before if before[table] != after[table]]
    assert set(changed) == {'public.meta_membership','public.twa_ws_member','public.twa_person_profile','public.twa_audit'}
    assert ro.current_sql('SELECT count(*) FROM extension_runtime_binding WHERE enabled OR NOT operation_fence;').strip() == '0'
    record('after.json', after)
    record('result.json', {'outcome':'QYH_ACTUAL_LOCAL_HUMAN_MEMBERSHIP_PERSISTED','username':'datong838','subject':SUBJECT,
        'tenant':'org-org/dev-project','role':'admin','changedTables':changed,'other646TablesUnchanged':True,
        'originalServicesUsed':True,'backupTwoCopiesValid':True,'businessRuntimeOpened':False,'liveLoginAccepted':False})
    print('Actual human admin enrollment verified; other646 tables unchanged; runtime remains closed.')
