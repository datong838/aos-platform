"""Retained native functions vs frozen original SQL; read-only, no replay."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

R = Path.cwd()
E = Path(__file__).resolve().parent
sys.path.insert(0, str(R / 'services/aos-api'))
from aos_api import aip_shared_parent_certificate_prepare as api

before = json.loads((E / 'original-sql-beforeimage.json').read_text())['statements']
assert list(api.shared_parent_certificate_prepare_statements()) == before
lab = json.loads((R / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
item = json.loads(subprocess.check_output(['docker', '--context', lab['context'], 'inspect', lab['name']]))[0]
assert item['Id'] == lab['container_id'] and item['Image'] == lab['image'] and item['State']['Running']
for key in ('PGPASSWORD', 'PGPASSFILE', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS'):
    os.environ.pop(key, None)
functions = []
with psycopg.connect(host='127.0.0.1', port=lab['port'], user='aos_app', dbname='aos_test_05f1a1dcd51f_ti4_test', passfile=lab['passfile'], row_factory=dict_row) as conn:
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert conn.execute('SELECT system_identifier::text AS value FROM pg_control_system()').fetchone()['value'] == lab['cluster']
    for signature, tag, owner, grants in ((api.MANIFEST, 'manifest', api.OWNER, {api.ISSUER_OWNER}), (api.VERIFY, 'verify', api.SOURCE_OWNER, {api.ISSUER_OWNER}), (api.FUNCTION, 'prepare', api.ISSUER_OWNER, {'aos_runtime'})):
        statement = next(x for x in before if x.startswith('CREATE FUNCTION ' + signature.split('(')[0] + '('))
        body = re.search(r'\$' + tag + r'\$(.*?)\$' + tag + r'\$', statement, re.S)[1]
        row = conn.execute('SELECT prosrc,pg_get_userbyid(proowner) AS owner,prosecdef,proconfig,proacl::text AS acl FROM pg_proc WHERE oid=%s::regprocedure', (signature,)).fetchone()
        assert row['prosrc'] == body and row['owner'] == owner and row['prosecdef'] and row['proconfig'] == ['search_path=pg_catalog'], signature
        acl = conn.execute("SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS grantee,a.privilege_type,a.is_grantable FROM pg_proc p CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s::regprocedure", (signature,)).fetchall()
        assert {x['grantee'] for x in acl} == grants | {owner}
        assert all(x['privilege_type'] == 'EXECUTE' and (x['grantee'] == owner or x['is_grantable'] is False) for x in acl)
        functions.append({'signature': signature, 'body_sha256': hashlib.sha256(body.encode()).hexdigest(), 'owner': owner, 'acl': row['acl'], 'original_body_and_permissions_exact': True})
    native = conn.execute("SELECT p.probin,p.prosrc,p.provolatile,p.proisstrict,p.prosecdef,l.lanname,pg_get_userbyid(p.proowner) AS owner FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang WHERE n.nspname='aos_ed25519' AND p.proname='verify' AND p.proargtypes='17 17 17'::oidvector").fetchone()
    assert native == {'probin': '$libdir/aos_ed25519', 'prosrc': 'aos_ed25519_verify', 'provolatile': 'i', 'proisstrict': True, 'prosecdef': False, 'lanname': 'c', 'owner': 'aos_ed25519_owner'}
    conn.rollback()
result = {'status': 'ORIGINAL_CERTIFICATE_SQL_NATIVE_BODIES_AND_ACL_EXACT', 'task': E.name, 'authority': 'AOS-001717', 'cluster': lab['cluster'], 'readonly': True, 'original_sql_statements_exact': len(before), 'functions': functions, 'native_verifier_catalog': native, 'formal_root_provenance_verified': False, 'database_writes': False, 'full_new_admission_pass': False}
with (E / 'native-readback.json').open('x') as out:
    json.dump(result, out, indent=2)
    out.write('\n')
print('13 original SQL statements, three installed bodies/ACL and native C verifier exact; no writes')
