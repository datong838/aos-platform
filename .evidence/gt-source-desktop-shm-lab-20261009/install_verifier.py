import json,subprocess,hashlib,os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
REPO=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;lab=json.loads((OUT/'lab.json').read_text());prefix=['docker','--context',lab['context']]
state=json.loads(subprocess.check_output(prefix+['inspect',lab['name']],text=True))[0];assert state['Id']==lab['container_id'] and state['State']['Running']
sharedir=subprocess.check_output(prefix+['exec',lab['name'],'pg_config','--sharedir'],text=True).strip()
pkglibdir=subprocess.check_output(prefix+['exec',lab['name'],'pg_config','--pkglibdir'],text=True).strip()
assert sharedir=='/usr/local/share/postgresql' and pkglibdir=='/usr/local/lib/postgresql'
files=['aos_ed25519--1.0.sql','aos_ed25519.control'];hashes={}
for f in files:
 data=subprocess.check_output(prefix+['exec',lab['name'],'cat',sharedir+'/extension/'+f]);assert data==(REPO/'services/aos-api/postgres-extensions/aos_ed25519'/f).read_bytes();hashes[f]=hashlib.sha256(data).hexdigest()
binary=subprocess.check_output(prefix+['exec',lab['name'],'sha256sum',pkglibdir+'/aos_ed25519.so'],text=True).split()[0]
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname='template1',passfile=lab['passfile'],row_factory=dict_row) as c:
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 assert c.execute("SELECT to_regprocedure('aos_ed25519.verify(bytea,bytea,bytea)') AS f").fetchone()['f'] is None
 assert c.execute("SELECT count(*) AS n FROM pg_roles WHERE rolname='aos_ed25519_owner'").fetchone()['n']==0
 with (OUT/'verifier-install-attempt.json').open('x') as h:json.dump({'cluster':lab['cluster'],'database':'template1','SQL':'CREATE EXTENSION aos_ed25519','file_hashes':hashes,'image_binary_sha256':binary},h)
 c.execute('CREATE EXTENSION aos_ed25519')
 role=c.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='aos_ed25519_owner'").fetchone();assert all(x is False for x in role.values())
 catalog=c.execute("SELECT p.prosrc,p.probin,p.proisstrict,p.prosecdef,p.provolatile,p.proparallel,l.lanname,e.extname,n.nspowner=p.proowner AS same_owner FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang JOIN pg_depend d ON d.objid=p.oid AND d.classid='pg_proc'::regclass AND d.deptype='e' JOIN pg_extension e ON e.oid=d.refobjid WHERE p.oid='aos_ed25519.verify(bytea,bytea,bytea)'::regprocedure").fetchone();assert catalog==dict(prosrc='aos_ed25519_verify',probin='$libdir/aos_ed25519',proisstrict=True,prosecdef=False,provolatile='i',proparallel='s',lanname='c',extname='aos_ed25519',same_owner=True)
 key=Ed25519PrivateKey.generate();raw=b'isolated-original-C-verifier-no-trust';sig=key.sign(raw);pub=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
 assert c.execute('SELECT aos_ed25519.verify(%s,%s,%s) AS valid',(sig,raw,pub)).fetchone()['valid'] is True
 assert c.execute('SELECT aos_ed25519.verify(%s,%s,%s) AS valid',(sig,raw+b'bad',pub)).fetchone()['valid'] is False
 c.commit()
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname='template1',passfile=lab['passfile']) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute("SELECT extversion FROM pg_extension WHERE extname='aos_ed25519'").fetchone()[0]=='1.0'
result={'cluster':lab['cluster'],'database':'template1','original_control_SQL_match':hashes,'image_binary_sha256':binary,'catalog':catalog,'owner_role':role,'real_signature_positive':True,'tampered_signature_rejected':True,'committed':True,'no_source_trust_or_business_authority':True};(OUT/'verifier-install.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
