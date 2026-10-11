import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

B = Path(__file__).resolve().parent
R = B.parents[2]
F = B.parent / 'planstate-catalog-1802'
sys.path[:0] = [str(R / 'services/aos-api'), str(F)]
from catalog_fixture_restore import original_family_restoration_statements

statements = original_family_restoration_statements()
binding = json.loads((F / 'fixture-restoration-binding.json').read_text())
assert [hashlib.sha256(s.encode()).hexdigest() for s in statements] == binding['fixed_statements_sha256']
expected = {}
for statement in statements:
    match = re.fullmatch(r'CREATE OR REPLACE FUNCTION (\S+) RETURNS void LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS \$profile\$(.*)\$profile\$;', statement, re.S)
    if match:
        expected[match[1]] = match[2]
prior = json.loads((F / 'independent-readback.json').read_text())
snapshot = {r['oid']: r for r in json.loads((F / 'in-transaction-functions.json').read_text())['functions']}
changed = [r for r in prior['observed_functions'] if r['changed_after_cleanup']]
assert len(changed) == 3
lab = json.loads((R / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
c = json.loads(subprocess.check_output(['docker', '--context', lab['context'], 'inspect', lab['name']], text=True))[0]
assert c['Id'] == lab['container_id'] and c['Image'] == lab['image'] and c['State']['Running']
proofs = []
with psycopg.connect(host='127.0.0.1', port=lab['port'], user='aos_app',
                     dbname=prior['database'], passfile=lab['passfile'], row_factory=dict_row) as conn:
    conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
    assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == lab['cluster']
    for function in changed:
        signature = function['signature']
        assert signature in expected
        row = conn.execute('SELECT prosrc,proowner::regrole::text AS owner,proacl::text AS acl,proconfig,prosecdef FROM pg_proc WHERE oid=%s', (function['oid'],)).fetchone()
        assert row['prosrc'] == expected[signature]
        assert all(row[k] == snapshot[function['oid']][k] for k in ('owner', 'acl', 'proconfig', 'prosecdef'))
        proofs.append(dict(signature=signature, restored_body_exact=True,
                           owner_acl_config_unchanged=True,
                           restored_sha256=hashlib.sha256(row['prosrc'].encode()).hexdigest()))
    for function in prior['cleanup_changed_functions']:
        assert conn.execute('SELECT to_regprocedure(%s) AS function', (function['signature'],)).fetchone()['function'] is None
    conn.rollback()
sources = [R / 'services/aos-api/tests/aip/test_physical_capacity_occupation_pg.py',
           R / 'services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py']
drop_locations = []
for function in prior['cleanup_changed_functions']:
    name = function['signature'].split('(')[0].split('.')[-1]
    hits = []
    for source in sources:
        for number, line in enumerate(source.read_text().splitlines(), 1):
            if 'DROP FUNCTION' in line and name + '(' in line:
                hits.append(dict(path=str(source.relative_to(R)), line=number))
    assert hits
    drop_locations.append(dict(signature=function['signature'], declared_drop_locations=hits))
result = dict(restoration_statement_hashes_match=True, exact_body_proofs=proofs,
              absent_functions=drop_locations,
              source_hashes={str(s.relative_to(R)): hashlib.sha256(s.read_bytes()).hexdigest() for s in sources},
              database_writes=False, runtime_immutability_proved=False, execution_allowed=False)
(B / 'result.json').open('x').write(json.dumps(result, indent=2) + '\n')
print('Three exact restored bodies and unchanged owner/ACL/config verified; three absent functions have declared DROP paths.')
