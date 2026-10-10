"""Verify actual retained shared preparation; never install legacy per-case debits."""
import hashlib
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

R = Path.cwd()
E = Path(__file__).resolve().parent
source = R / 'services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py'
s = importlib.util.spec_from_file_location('capacity_scope_original', source)
api = importlib.util.module_from_spec(s)
s.loader.exec_module(api)
lab = json.loads((R / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
container = json.loads(subprocess.check_output(['docker', '--context', lab['context'], 'inspect', lab['name']]))[0]
assert container['Id'] == lab['container_id'] and container['Image'] == lab['image'] and container['State']['Running']
for key in ('PGPASSWORD', 'PGPASSFILE', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS'):
    os.environ.pop(key, None)
expected = [
    (api.PLAN_RISK, 'occupation_plan_risk_statements', 'planrisk'),
    (api.SHARED_RISK_DESCRIPTION, 'occupation_shared_risk_description_statements', 'shared'),
    (api.TARGET_CALL, 'occupation_target_call_statements', 'targetcall'),
    (api.TARGET_OCCUPATION, 'occupation_target_ledger_statements', 'occupation'),
]
verified = []
with psycopg.connect(host='127.0.0.1', port=5441, user='aos_app',
                     dbname='aos_test_05f1a1dcd51f_ti4_test', passfile=lab['passfile'], row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert c.execute('SELECT system_identifier::text AS v FROM pg_control_system()').fetchone()['v'] == lab['cluster']
    for signature, generator, tag in expected:
        statement = next(x for x in getattr(api, generator)() if x.startswith('CREATE FUNCTION ' + signature.split('(')[0] + '('))
        body = re.search(r'\$' + tag + r'\$(.*?)\$' + tag + r'\$', statement, re.S)
        assert body is not None, 'exact original function delimiter required: ' + signature
        row = c.execute('SELECT prosrc,prosecdef,proconfig,pg_get_userbyid(proowner) AS owner,proacl::text AS acl FROM pg_proc WHERE oid=to_regprocedure(%s)', (signature,)).fetchone()
        frozen_original = json.loads((E / 'native-kernel-scope-readback-1716.json').read_text())['functions']
        original_acl = next(x['acl'] for x in frozen_original if x['signature'] == signature)
        assert row and row['acl'] == original_acl and row['prosrc'] == body[1] and row['owner'] == api.OWNER and row['prosecdef'] and row['proconfig'] == ['search_path=pg_catalog'], signature
        verified.append({'signature': signature, 'body_sha256': hashlib.sha256(body[1].encode()).hexdigest(), 'owner': row['owner'], 'acl': row['acl'], 'body_exact_current_generated': True})
    absent = [sig for sig in (api.DEBIT, api.JUDGE_DEBIT) if c.execute('SELECT to_regprocedure(%s) AS v', (sig,)).fetchone()['v'] is None]
    assert absent == [api.DEBIT, api.JUDGE_DEBIT]
    rows = c.execute("SELECT c.relname,t.tgname,t.tgdeferrable,t.tginitdeferred,p.prosrc,pg_get_userbyid(p.proowner) AS owner FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname='aos_physical_capacity_occupation_private' AND p.proname='reject_unfinalized_parent_debit'").fetchall()
    guards = json.loads((E / 'native-finalizer-gap-1698.json').read_text())['guards']
    frozen = {(x['table'], x['trigger']): x['body_sha256'] for x in guards}
    assert len(rows) == 7 and {(x['relname'], x['tgname']) for x in rows} == set(frozen)
    assert all(x['tgdeferrable'] and x['tginitdeferred'] and x['owner'] == api.OWNER and hashlib.sha256(x['prosrc'].encode()).hexdigest() == frozen[(x['relname'], x['tgname'])] for x in rows)
    c.rollback()
result = {'status': 'ORIGINAL_SHARED_PREPARATION_NATIVE_BODIES_EXACT', 'authority': 'AOS-001718', 'cluster': lab['cluster'], 'database': 'aos_test_05f1a1dcd51f_ti4_test', 'readonly': True, 'functions': verified, 'legacy_per_case_debits_not_installed': absent, 'original_seven_denial_guards_unchanged': True, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'full_admission_pass': False, 'database_writes': False}
with (E / 'description-kernel-native-readback-1718.json').open('x') as out:
    json.dump(result, out, indent=2)
    out.write('\n')
print('Original four shared producers match native bodies; seven reject guards exact; legacy debits not installed')
