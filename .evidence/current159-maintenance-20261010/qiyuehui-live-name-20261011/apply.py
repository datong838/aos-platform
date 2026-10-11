"""One exact authorized maintenance CAS; an existing intent is never replayed."""
import hashlib
import json
from pathlib import Path

from prepare import R, ROOT, M, inspect, write

intent = R / 'apply-intent.json'
assert not intent.exists(), 'Existing intent: read-only reconciliation required'
before = json.loads((R / 'before.json').read_text())
backup = json.loads((R / 'backup-manifest.json').read_text())
assert backup['outcome'] == 'FRESH_BACKUP_BASELINE_EXACT_NO_WRITE' and backup['tableCount'] == 626
assert inspect() == before
fingerprint = json.loads((R / 'fingerprint-before.json').read_text())
assert M.fingerprint(M.SOURCE) == fingerprint
sql = (ROOT / 'qyh-org-name-maintenance-20261011/proposed-name-update.sql').read_text()
write('apply-intent.json', {'database': M.DB, 'container': M.SOURCE,
                          'cluster': before['cluster'], 'sqlSha256': hashlib.sha256(sql.encode()).hexdigest(),
                          'humanAuthorization': '2026-10-11 full Qiyuehui restoration and domain correction',
                          'expectedOldName': before['name'], 'expectedNewName': '栖月汇商贸有限公司'})
try:
    result = M.psql(M.SOURCE, M.DB, sql)
except Exception as exc:
    write('apply-terminal.json', {'outcome': 'UNKNOWN_RECONCILE_ONLY', 'errorType': type(exc).__name__})
    raise
write('apply-terminal.json', {'outcome': 'SQL_RETURNED_SUCCESS', 'exactlyOne': result == '1'})
assert result == '1'
after = inspect()
assert after['name'] == '栖月汇商贸有限公司'
assert all(after[k] == before[k] for k in before if k not in {'name', 'updatedAt'})
after_fingerprint = M.fingerprint(M.SOURCE)
old = {x['table']: x for x in fingerprint}
new = {x['table']: x for x in after_fingerprint}
assert old.keys() == new.keys()
changed = [name for name in old if old[name] != new[name]]
assert changed == ['public.meta_org']
assert old['public.meta_org']['rows'] == new['public.meta_org']['rows']
write('after.json', after)
write('fingerprint-after.json', after_fingerprint)
write('result.json', {'outcome': 'LIVE_QIYUEHUI_ORG_NAME_RESTORED', 'database': M.DB,
                      'tables': 626, 'changedTables': changed, 'otherOrgRowFieldsUnchanged': True,
                      'historyVolumeAttachedToApi': False, 'eightWorkbenchAccepted': False})
print('LIVE_QIYUEHUI_ORG_NAME_RESTORED')
