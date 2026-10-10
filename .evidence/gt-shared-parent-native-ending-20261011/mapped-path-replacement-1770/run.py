"""Isolated loader/path differential; no arm, Source call or durable SQL install."""
import hashlib,json,subprocess,uuid
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[2]
spec=json.loads((B.parent/'module-file-facts-1768/spec.json').read_text())
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
def save(name,value):
 (B/name).open('x').write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def docker(*args):return subprocess.check_output(['docker',*args],text=True).strip()
def digest(path):return docker('exec',lab['name'],'sha256sum',path).split()[0]
def maps(pid,path):
 raw=docker('exec',lab['name'],'cat','/proc/'+str(pid)+'/maps')
 return [line for line in raw.splitlines() if len(line.split(maxsplit=5))==6 and line.split(maxsplit=5)[5] in (path,path+' (deleted)')]
def observation(c,path):
 facts=c.execute('SELECT aos_admission_native_private.loaded_module_file_facts() AS facts').fetchone()['facts']
 assert facts['mappedImageProvenance'] is False and facts['executionAllowed'] is False
 return next(x for x in facts['files'] if x['path']==path)
st=json.loads(docker('inspect',lab['name']))[0]
assert st['Id']==lab['container_id'] and st['Image']==lab['image'] and st['State']['Running']
assert any(x.get('Name')==lab['volume'] for x in st['Mounts'])
package=R/'services/aos-api/postgres-extensions/aos_admission_end'
for name,h in spec['source_hashes'].items():assert hashlib.sha256((package/name).read_bytes()).hexdigest()==h
assert digest(spec['library'])==spec['library_sha256']
assert digest(spec['foreign_library'])==spec['foreign_library_sha256']
signature=digest('/usr/local/lib/postgresql/aos_ed25519.so')
assert signature=='6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'
u=uuid.uuid4().hex;copied='/tmp/aos_order_mapping_'+u+'.so';replacement='/tmp/aos_order_mapping_replacement_'+u+'.so'
schema='test_owned_mapping_'+u;owner='aos_physical_capacity_occupation_owner'
params=dict(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=spec['database'],passfile=lab['passfile'],row_factory=dict_row,connect_timeout=5)
with psycopg.connect(**params) as c:
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 original=c.execute("SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid='aos_admission_native_private.pending_relations()'::regprocedure").fetchone()
 for fn in ('loaded_module_paths','loaded_module_file_facts'):
  assert c.execute('SELECT to_regprocedure(%s) AS f',('aos_admission_native_private.'+fn+'()',)).fetchone()['f'] is None
 flags=c.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(owner,)).fetchone();assert not any(flags.values())
 assert c.execute('SELECT count(*) AS n FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole',(owner,owner)).fetchone()['n']==0
 pid=c.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid'];xid=c.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
 save('attempt.json',dict(pid=pid,xid=xid,schema=schema,copied=copied,replacement=replacement,library=spec['library'],full_admission=False,foreign_arm_invoked=False))
 docker('exec',lab['name'],'cp',spec['foreign_library'],copied)
 ddl=(package/'aos_admission_end--0.1.sql').read_text().split('-- Supported loader observation, never a caller-supplied package allowlist.',1)[1]
 c.execute(ddl.replace("'MODULE_PATHNAME'",sql.Literal(spec['library']).as_string(c)),prepare=False)
 c.execute('CREATE SCHEMA '+schema+' AUTHORIZATION aos_app')
 c.execute(sql.SQL('CREATE FUNCTION '+schema+".uninvoked(oid,oid,boolean) RETURNS void AS {},'aos_test_order_arm' LANGUAGE c STRICT VOLATILE SET search_path=pg_catalog").format(sql.Literal(copied)))
 c.execute('REVOKE ALL ON FUNCTION '+schema+'.uninvoked(oid,oid,boolean) FROM PUBLIC')
 c.execute('SET LOCAL ROLE '+owner)
 pending=c.execute('SELECT aos_admission_native_private.pending_relations() AS p').fetchone()['p'];assert pending==[]
 before=observation(c,copied);initial_maps=maps(pid,copied)
 assert initial_maps and all(line.split()[4]==before['inode'] for line in initial_maps)
 save('before.json',dict(disk_fact=before,maps=initial_maps,pending=pending))
 docker('exec',lab['name'],'cp',copied,replacement)
 docker('exec',lab['name'],'sh','-c','printf "mapping-replacement-test" >> "$1"','append-test',replacement)
 replacement_sha=digest(replacement);assert replacement_sha!=before['sha256']
 save('replace-intent.json',dict(copied=copied,replacement=replacement,replacement_sha256=replacement_sha,pid=pid,xid=xid))
 docker('exec',lab['name'],'mv',replacement,copied)
 after=observation(c,copied);after_maps=maps(pid,copied)
 assert after['sha256']==replacement_sha and after['inode']!=before['inode']
 assert after_maps and all(line.endswith(' (deleted)') and line.split()[4]==before['inode'] for line in after_maps)
 assert c.execute('SELECT aos_admission_native_private.pending_relations() AS p').fetchone()['p']==pending
 save('after.json',dict(disk_fact=after,maps=after_maps,pending=pending,old_mapping_inode=before['inode'],current_path_inode=after['inode'],mapping_and_path_separated=True,disk_interface_honestly_only_disk=True))
 c.rollback()
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT pg_xact_status(%s::xid8) AS status',(xid,)).fetchone()['status']=='aborted'
 assert c.execute('SELECT to_regnamespace(%s) AS n',(schema,)).fetchone()['n'] is None
 for fn in ('loaded_module_paths','loaded_module_file_facts'):
  assert c.execute('SELECT to_regprocedure(%s) AS f',('aos_admission_native_private.'+fn+'()',)).fetchone()['f'] is None
 assert c.execute("SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid='aos_admission_native_private.pending_relations()'::regprocedure").fetchone()==original
 assert c.execute('SELECT count(*) AS n FROM pg_stat_activity WHERE pid=%s',(pid,)).fetchone()['n']==0
 assert c.execute('SELECT count(*) AS n FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole',(owner,owner)).fetchone()['n']==0
 flags2=c.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(owner,)).fetchone();assert flags2==flags
assert digest(spec['foreign_library'])==spec['foreign_library_sha256']
assert digest('/usr/local/lib/postgresql/aos_ed25519.so')==signature
assert digest(spec['library'])==spec['library_sha256']
save('independent-readback.json',dict(xid=xid,xid_aborted=True,backend_closed=True,new_schema_absent=True,new_interfaces_absent=True,original_pending_exact=True,owner_closed=True,original_binaries_exact=True,test_copy_retained=copied))
save('verification.json',dict(mapping_and_path_separation_proven=True,full_task_delivered=False,execution_allowed=False,formal_database_changed=False,foreign_arm_invoked=False,next_required='Receiver must bind actual mapped identity and image segments plus trusted immutable package lifecycle; disk SHA/stat alone are insufficient',limitations=['No private callback list or mapped page proof','No package Root/arm/Source/RI/final-clock/COMMIT acceptance']))
print(json.dumps(dict(mapping_path_separated=True,xid_aborted=True,execution_allowed=False)))
