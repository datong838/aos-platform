"""Freeze upstream callback sources and observe one read-only isolated backend."""
import hashlib,json,re,struct,subprocess
from pathlib import Path
import psycopg
B=Path(__file__).resolve().parent;R=B.parents[2];source=B/'source';l=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
refs=[]
for f in sorted(source.rglob('*.c')):
 text=f.read_text(errors='replace')
 for num,line in enumerate(text.splitlines(),1):
  if re.search(r'\b(?:UnregisterXactCallback|RegisterXactCallback|RegisterSubXactCallback)\s*\(',line):
   refs.append(dict(path=str(f.relative_to(source)),line=num,text=line.strip(),file_sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
registrations=[r for r in refs if not r['path'].endswith('/xact.c')]
assert len(registrations)==6,registrations
st=json.loads(subprocess.check_output(['docker','inspect',l['name']]))[0];assert st['Id']==l['container_id'] and st['Image']==l['image'] and st['State']['Running']
def mapped(pid):
 raw=subprocess.check_output(['docker','exec',l['name'],'cat','/proc/'+str(pid)+'/maps'],text=True)
 paths=sorted({line.split(maxsplit=5)[5] for line in raw.splitlines() if len(line.split(maxsplit=5))==6 and 'x' in line.split()[1] and line.split(maxsplit=5)[5].startswith('/')})
 assert all(' (deleted)' not in p for p in paths)
 return paths
with psycopg.connect(host='127.0.0.1',port=l['port'],user='aos_app',dbname='aos_test_05f1a1dcd51f_ti4_test',passfile=l['passfile']) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==l['cluster']
 pid=c.execute('SELECT pg_backend_pid()').fetchone()[0];before=mapped(pid)
 c.execute('DO $$ BEGIN NULL; END $$')
 c.execute("SELECT digest(''::text,'sha256')")
 assert c.execute("SELECT aos_ed25519.verify(''::bytea,''::bytea,''::bytea)").fetchone()[0] is False
 c.execute('SET LOCAL ROLE aos_physical_capacity_occupation_owner')
 assert c.execute('SELECT aos_admission_native_private.pending_relations()').fetchone()[0]==[]
 after=mapped(pid);c.rollback()
modules=[]
for path in after:
 data=subprocess.check_output(['docker','exec',l['name'],'cat',path]);assert data[:6]==b'\x7fELF\x02\x01'
 h=struct.unpack_from('<16sHHIQQQIHHHHHH',data);sections=[struct.unpack_from('<IIQQQQIIQQ',data,h[6]+i*h[11]) for i in range(h[12])];imports=[]
 for s in sections:
  if s[1]!=11:continue
  strings=sections[s[6]];names=data[strings[4]:strings[4]+strings[5]]
  for off in range(s[4],s[4]+s[5],s[9]):
   n,info,other,index,value,size=struct.unpack_from('<IBBHQQ',data,off);name=names[n:names.find(b'\0',n)].decode()
   if index==0 and name in ('RegisterXactCallback','RegisterSubXactCallback','dlsym','dlopen'):imports.append(name)
 modules.append(dict(path=path,sha256=hashlib.sha256(data).hexdigest(),selected_imports=sorted(set(imports))))
assert any(m['path'].endswith('/plpgsql.so') and 'RegisterXactCallback' in m['selected_imports'] for m in modules)
assert not any('aos_order_' in p or 'aos_postdrain_' in p for p in after)
assert next(m['sha256'] for m in modules if m['path'].endswith('/aos_ed25519.so'))=='6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'
result=dict(authority='AOS-001748',source_identity=json.loads((B/'source-identity.json').read_text()),source_registration_references=refs,upstream_module_registration_sites=3,read_only_backend_pid=pid,executable_maps_before=before,executable_maps_after=after,mapped_module_hashes=modules,test_probe_libraries_not_loaded=True,observed_pending_empty=True,source_evaluation_or_business_effect=False,limitations=['source tag/archive is not reproducible proof of installed binary build','selected undefined ELF imports cannot rule out indirect registration through dlsym or other modules','read-only sampled backend is not full admission backend lifecycle','no private callback list enumeration, no callback last or deadline proof'],full_admission=False,execution_allowed=False,full_task_delivered=False)
(B/'verification.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps({'registration_modules':3,'loaded_executable_files':len(after),'libraries_newly_loaded':sorted(set(after)-set(before)),'full_admission':False}))
