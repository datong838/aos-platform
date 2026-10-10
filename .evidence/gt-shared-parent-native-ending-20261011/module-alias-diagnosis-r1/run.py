import hashlib,json,subprocess,uuid
from pathlib import Path
import psycopg
from psycopg import sql
B=Path(__file__).resolve().parent;R=B.parents[2];l=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());u=uuid.uuid4().hex;lib='/tmp/aos_module_diag_'+u+'.so';ns='test_owned_module_diag_'+u
image=(B/'image-id.txt').read_text().strip();aid=subprocess.check_output(['docker','create','--network','none',image],text=True).strip();(B/'attempt.json').open('x').write(json.dumps(dict(artifact=aid,library=lib,schema=ns,test_only=True)))
subprocess.run(['docker','cp',aid+':/aos_admission_end.so',str(B/'diag.so')],check=True);subprocess.run(['docker','cp',str(B/'diag.so'),l['name']+':'+lib],check=True)
with psycopg.connect(host='127.0.0.1',port=l['port'],user='aos_app',dbname='aos_test_05f1a1dcd51f_ti4_test',passfile=l['passfile']) as c:
 assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==l['cluster']
 c.execute('CREATE SCHEMA '+ns+' AUTHORIZATION aos_app')
 c.execute(sql.SQL('CREATE FUNCTION '+ns+".raw() RETURNS text[] AS {},'aos_test_raw_module_names' LANGUAGE c VOLATILE SET search_path=pg_catalog").format(sql.Literal(lib)));c.execute('REVOKE ALL ON FUNCTION '+ns+'.raw() FROM PUBLIC')
 raw=c.execute('SELECT '+ns+'.raw()').fetchone()[0]
 canonical=[subprocess.check_output(['docker','exec',l['name'],'readlink','-f',p or '/proc/'+str(c.execute('SELECT pg_backend_pid()').fetchone()[0])+'/exe'],text=True).strip() if p!='linux-vdso.so.1' else 'virtual:linux-vdso.so.1' for p in raw]
 duplicates={p:[raw[i] for i,v in enumerate(canonical) if v==p] for p in canonical if canonical.count(p)>1}
 c.rollback()
 with psycopg.connect(host='127.0.0.1',port=l['port'],user='aos_app',dbname='aos_test_05f1a1dcd51f_ti4_test',passfile=l['passfile']) as other:
  other.execute('SET TRANSACTION READ ONLY');assert other.execute('SELECT to_regnamespace(%s)',(ns,)).fetchone()[0] is None
(B/'result.json').open('x').write(json.dumps(dict(raw_names=raw,canonical_names=canonical,duplicates=duplicates,diagnostic_schema_absent_after_rollback=True,library_sha256=hashlib.sha256((B/'diag.so').read_bytes()).hexdigest(),full_admission=False),indent=2)+'\n');print(json.dumps(duplicates))
