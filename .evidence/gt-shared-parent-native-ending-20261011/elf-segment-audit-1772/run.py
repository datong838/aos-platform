"""Current isolated ELF audit. Only immutable file/header facts, no arm or effects."""
import json,hashlib,pathlib,struct,subprocess
import psycopg
from psycopg import sql
B=pathlib.Path(__file__).resolve().parent;R=B.parents[2];s=json.loads((B.parent/'mapping-identity-1771/spec.json').read_text());l=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());owner='aos_physical_capacity_occupation_owner'
def save(name,value):(B/name).open('x').write(json.dumps(value,indent=2)+'\n')
def docker(*args):return subprocess.check_output(['docker',*args])
def parse_elf(raw,header_address):
 assert 64<=len(raw)<=256*1024*1024 and raw[:7]==b'\x7fELF\x02\x01\x01'
 h=struct.unpack_from('<16sHHIQQQIHHHHHH',raw);kind,machine,version=h[1:4];phoff=h[5];ehsize,phentsize,phnum=h[8:11]
 assert kind in (2,3) and machine==183 and version==1 and ehsize==64 and phentsize==56 and 0<phnum<=256
 assert phoff>=64 and phoff+phnum*56<=len(raw)
 ph=[]
 for i in range(phnum):
  ptype,flags,offset,vaddr,paddr,filesz,memsz,align=struct.unpack_from('<IIQQQQQQ',raw,phoff+i*56)
  assert offset+filesz<=len(raw) and filesz<=memsz
  ph.append(dict(type=ptype,flags=flags,offset=offset,vaddr=vaddr,filesz=filesz,memsz=memsz,align=align))
 explicit=[p for p in ph if p['type']==6];assert len(explicit)<=1
 if explicit:phv=explicit[0]['vaddr'];assert explicit[0]['offset']==phoff and explicit[0]['filesz']>=phnum*56
 else:
  containing=[p for p in ph if p['type']==1 and p['offset']<=phoff and phoff+phnum*56<=p['offset']+p['filesz']];assert len(containing)==1
  phv=containing[0]['vaddr']+phoff-containing[0]['offset']
 bias=header_address-phv;assert bias>=0
 dynamic=[]
 for p in ph:
  if p['type']!=2:continue
  assert p['filesz']%16==0
  ended=False
  for at in range(p['offset'],p['offset']+p['filesz'],16):
   tag,value=struct.unpack_from('<qQ',raw,at)
   if tag==0:ended=True;break
   dynamic.append((tag,value))
  assert ended
 textrel=any(tag==22 or tag==30 and value&4 for tag,value in dynamic)
 loads=[p for p in ph if p['type']==1];assert loads
 readonly=[]
 for i,p in enumerate(loads):
  assert not (p['flags']&1 and p['flags']&2)
  if p['flags']&4 and not p['flags']&2 and p['filesz']:
   readonly.append(dict(load_index=i,flags=p['flags'],offset=p['offset'],vaddr=p['vaddr'],filesz=p['filesz'],memsz=p['memsz'],memory_start=hex(bias+p['vaddr']),disk_segment_sha256=hashlib.sha256(raw[p['offset']:p['offset']+p['filesz']]).hexdigest()))
 return dict(elf_class='ELF64LE',machine=machine,type=kind,program_header_offset=phoff,program_header_count=phnum,load_bias=hex(bias),text_relocations=textrel,readonly_loads=readonly,writable_load_count=sum(bool(p['flags']&2) for p in loads),gnu_relro_count=sum(p['type']==0x6474e552 for p in ph))
st=json.loads(docker('inspect',l['name']))[0];assert st['Id']==l['container_id'] and st['Image']==l['image'] and st['State']['Running']
p=R/'services/aos-api/postgres-extensions/aos_admission_end'
for name,h in s['source_hashes'].items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==h
assert docker('exec',l['name'],'sha256sum',s['library']).decode().split()[0]==s['library_sha256']
params=dict(host='127.0.0.1',port=l['port'],user='aos_app',dbname=s['database'],passfile=l['passfile'],connect_timeout=5)
with psycopg.connect(**params) as c:
 assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==l['cluster']
 original=c.execute("SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid='aos_admission_native_private.pending_relations()'::regprocedure").fetchone()
 for fn in ['loaded_module_paths','loaded_module_file_facts','loaded_module_mapping_facts']:assert c.execute('SELECT to_regprocedure(%s)',('aos_admission_native_private.'+fn+'()',)).fetchone()[0] is None
 flags=c.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(owner,)).fetchone();assert not any(flags)
 pid=c.execute('SELECT pg_backend_pid()').fetchone()[0];xid=c.execute('SELECT pg_current_xact_id()::text').fetchone()[0];save('attempt.json',dict(pid=pid,xid=xid,library=s['library'],no_arm=True,no_source_execution=True))
 ddl=(p/'aos_admission_end--0.1.sql').read_text().split('-- Supported loader observation, never a caller-supplied package allowlist.',1)[1];c.execute(ddl.replace("'MODULE_PATHNAME'",sql.Literal(s['library']).as_string(c)),prepare=False)
 c.execute('SET LOCAL ROLE '+owner)
 disk={f['path']:f for f in c.execute('SELECT aos_admission_native_private.loaded_module_file_facts()').fetchone()[0]['files']}
 mapping=c.execute('SELECT aos_admission_native_private.loaded_module_mapping_facts()').fetchone()[0]
 rows=[];native_probe=None
 for f in mapping['files']:
  if f['virtual']:continue
  raw=docker('exec',l['name'],'cat',f['path']);assert hashlib.sha256(raw).hexdigest()==disk[f['path']]['sha256']
  layout=parse_elf(raw,int(f['headerAddress'],16));rows.append(dict(path=f['path'],sha256=disk[f['path']]['sha256'],header_address=f['headerAddress'],**layout))
  if f['path']==s['library']:
   # The public program-header address refers to immutable ELF metadata only.
   expected=raw[layout['program_header_offset']:layout['program_header_offset']+64]
   command=['docker','exec',l['name'],'dd','if=/proc/'+str(pid)+'/mem','bs=64','skip='+str(int(f['headerAddress'],16)),'count=64','iflag=skip_bytes,count_bytes','status=none']
   probe=subprocess.run(command,capture_output=True,timeout=5)
   native_probe=dict(exit_code=probe.returncode,bytes=len(probe.stdout),stderr=probe.stderr.decode(errors='replace'),expected_sha256=hashlib.sha256(expected).hexdigest(),observed_sha256=hashlib.sha256(probe.stdout).hexdigest(),header_bytes_match=probe.returncode==0 and probe.stdout==expected)
 assert rows and any('libicudata' in row['path'] for row in rows)
 save('current-layouts.json',dict(pid=pid,modules=rows,virtual_modules=[f for f in mapping['files'] if f['virtual']],memory_header_oracle=native_probe,source_provenance=False,immutable_lifecycle=False))
 c.rollback()
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT pg_xact_status(%s::xid8)',(xid,)).fetchone()[0]=='aborted'
 for fn in ['loaded_module_paths','loaded_module_file_facts','loaded_module_mapping_facts']:assert c.execute('SELECT to_regprocedure(%s)',('aos_admission_native_private.'+fn+'()',)).fetchone()[0] is None
 assert c.execute("SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid='aos_admission_native_private.pending_relations()'::regprocedure").fetchone()==original
 assert c.execute('SELECT count(*) FROM pg_stat_activity WHERE pid=%s',(pid,)).fetchone()[0]==0
 assert c.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(owner,)).fetchone()==flags
assert docker('exec',l['name'],'sha256sum',s['library']).decode().split()[0]==s['library_sha256']
summary=dict(module_count=len(rows),readonly_segment_count=sum(len(r['readonly_loads']) for r in rows),text_relocation_modules=[r['path'] for r in rows if r['text_relocations']],data_only_module_included=True,memory_header_oracle=native_probe,xid_aborted=True,new_interfaces_absent=True,original_pending_exact=True,backend_closed=True,full_task_delivered=False,execution_allowed=False,formal_database_changed=False)
save('verification.json',summary);print(json.dumps({k:summary[k] for k in ('module_count','readonly_segment_count','text_relocation_modules','memory_header_oracle','xid_aborted','execution_allowed')}))
