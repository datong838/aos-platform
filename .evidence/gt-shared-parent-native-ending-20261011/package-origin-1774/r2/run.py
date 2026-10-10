"""Current isolated package audit. No package install, Source, arm or effect."""
import base64,hashlib,json,pathlib,struct,subprocess
import psycopg
from psycopg import sql
B=pathlib.Path(__file__).resolve().parent
R=next(p for p in B.parents if (p/'services/aos-api/postgres-extensions/aos_admission_end').is_dir())
spec=json.loads((B.parent.parent/'readonly-native-1773/spec.json').read_text())
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
P=R/'services/aos-api/postgres-extensions/aos_admission_end'
def save(name,data):(B/name).open('x').write(json.dumps(data,indent=2)+'\n')
def docker(*args):return subprocess.check_output(['docker',*args],timeout=20)
def libraries(raw):
    assert 64<=len(raw)<=256*1024*1024 and raw[:7]==b'\x7fELF\x02\x01\x01'
    h=struct.unpack_from('<16sHHIQQQIHHHHHH',raw);shoff,entsize,count=h[6],h[11],h[12]
    assert entsize==64 and 0<count<=4096 and shoff+count*entsize<=len(raw)
    sections=[struct.unpack_from('<IIQQQQIIQQ',raw,shoff+i*entsize) for i in range(count)]
    imports=[]
    for section in sections:
        if section[1]!=11:continue
        assert section[9]==24 and section[5]%24==0 and section[4]+section[5]<=len(raw) and section[6]<count
        strings=sections[section[6]];assert strings[1]==3 and strings[4]+strings[5]<=len(raw)
        for at in range(section[4],section[4]+section[5],24):
            name,info,other,index,value,size=struct.unpack_from('<IBBHQQ',raw,at)
            if index!=0 or name==0:continue
            assert name<strings[5]
            begin=strings[4]+name;end=raw.find(b'\0',begin,strings[4]+strings[5]);assert end>=begin and end-begin<=4096
            imports.append(raw[begin:end].decode('ascii'))
    phoff,phsize,phcount=h[5],h[9],h[10]
    assert phsize==56 and 0<phcount<=256 and phoff+phcount*phsize<=len(raw)
    ph=[struct.unpack_from('<IIQQQQQQ',raw,phoff+i*phsize) for i in range(phcount)]
    needed=[];strv=None;strsize=None
    for p in ph:
        if p[0]!=2:continue
        assert p[2]+p[5]<=len(raw) and p[5]%16==0
        ended=False
        for at in range(p[2],p[2]+p[5],16):
            tag,value=struct.unpack_from('<qQ',raw,at)
            if tag==0:ended=True;break
            if tag==1:needed.append(value)
            if tag==5:strv=value
            if tag==10:strsize=value
        assert ended
    names=[]
    if needed:
        assert strv is not None and strsize is not None
        containing=[p for p in ph if p[0]==1 and p[3]<=strv and strv+strsize<=p[3]+p[5]];assert len(containing)==1
        p=containing[0];start=p[2]+strv-p[3];assert start+strsize<=len(raw)
        for offset in needed:
            assert offset<strsize
            end=raw.find(b'\0',start+offset,start+strsize);assert end>=start+offset and end-start-offset<=4096
            names.append(raw[start+offset:end].decode('ascii'))
    interesting=[x for x in imports if x in ('dlopen','dlmopen','dlsym','dlclose','RegisterXactCallback','RegisterSubXactCallback','UnregisterXactCallback','UnregisterSubXactCallback')]
    return {'dynamic_needed':names,'undefined_symbol_count':len(imports),'loader_callback_imports':sorted(set(interesting)),'indirect_registration_absence_proved':False}
info=json.loads(docker('inspect',lab['name']))[0]
assert info['Id']==lab['container_id'] and info['Image']==lab['image'] and info['State']['Running']
for name,digest in spec['source_hashes'].items():assert hashlib.sha256((P/name).read_bytes()).hexdigest()==digest
assert docker('exec',lab['name'],'sha256sum',spec['library']).decode().split()[0]==spec['library_sha256']
installed=docker('exec',lab['name'],'cat','/lib/apk/db/installed');assert len(installed)<=16*1024*1024
owners={}
for block in installed.decode().split('\n\n'):
    metadata={};directory=None;name=None;checks={}
    for line in block.splitlines():
        if ':' not in line:continue
        kind,value=line.split(':',1)
        if kind in ('P','V','A','o','C'):metadata[kind]=value
        if kind=='F':directory=value
        if kind=='R':name=value
        if kind=='Z':
            assert directory is not None and name is not None
            path='/'+directory.lstrip('/')+'/'+name;assert path not in owners
            owners[path]={'package':dict(metadata),'installed_checksum':value}
params=dict(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=spec['database'],passfile=lab['passfile'],connect_timeout=5)
with psycopg.connect(**params) as c:
    assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
    original=c.execute("SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid='aos_admission_native_private.pending_relations()'::regprocedure").fetchone()
    functions=['loaded_module_paths','loaded_module_file_facts','loaded_module_mapping_facts','loaded_module_readonly_facts']
    for fn in functions:assert c.execute('SELECT to_regprocedure(%s)',('aos_admission_native_private.'+fn+'()',)).fetchone()[0] is None
    pid=c.execute('SELECT pg_backend_pid()').fetchone()[0];xid=c.execute('SELECT pg_current_xact_id()::text').fetchone()[0]
    save('attempt.json',dict(pid=pid,xid=xid,no_arm=True,no_source=True,library=spec['library']))
    ddl=(P/'aos_admission_end--0.1.sql').read_text().split('-- Supported loader observation, never a caller-supplied package allowlist.',1)[1]
    c.execute(ddl.replace("'MODULE_PATHNAME'",sql.Literal(spec['library']).as_string(c)),prepare=False)
    c.execute("SELECT digest(''::text,'sha256')");assert c.execute("SELECT aos_ed25519.verify(''::bytea,''::bytea,''::bytea)").fetchone()[0] is False
    c.execute('DO LANGUAGE plpgsql $$BEGIN NULL;END$$')
    c.execute('SET LOCAL ROLE aos_physical_capacity_occupation_owner')
    facts=c.execute('SELECT aos_admission_native_private.loaded_module_readonly_facts()').fetchone()[0]
    assert facts['readonlyLoadedBytesVerified'] and not facts['executionAllowed']
    status=docker('exec',lab['name'],'cat',f'/proc/{pid}/status').decode()
    identity={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in status.splitlines() if line.startswith(('Uid:','Gid:','Groups:'))}
    rows=[]
    for f in facts['files']:
        if f['virtual']:continue
        path=f['path'];assert path.startswith('/') and '\n' not in path and '\t' not in path
        raw=docker('exec',lab['name'],'cat',path);assert len(raw)<=256*1024*1024
        digest=hashlib.sha256(raw).hexdigest();owned=owners.get(path)
        if owned:
            owned=dict(owned);checksum=owned['installed_checksum']
            observed='Q1'+base64.b64encode(hashlib.sha1(raw).digest()).decode() if checksum.startswith('Q1') else None
            owned.update(installed_checksum_matches=observed==checksum if observed is not None else None,checksum_is_trusted_signature=False)
        paths=[path,*map(str,pathlib.PurePosixPath(path).parents)]
        checks=[]
        for target in paths:
            metadata=docker('exec',lab['name'],'stat','-c','%u %g %a %d %i',target).decode().strip()
            result=subprocess.run(['docker','exec',lab['name'],'sh','-c','test -w "$1"','sh',target],capture_output=True,timeout=5);assert result.returncode in (0,1)
            checks.append(dict(path=target,stat=metadata,writable_by_container_identity=result.returncode==0))
        rows.append(dict(path=path,sha256=digest,bytes=len(raw),apk=owned,elf=libraries(raw),file_and_ancestors=checks))
    save('current-package.json',dict(modules=rows,virtual_modules=[x for x in facts['files'] if x['virtual']],backend_identity=identity,container_exec_identity=docker('exec',lab['name'],'id').decode().strip(),readonly_native_facts=facts,installed_apk_database_sha256=hashlib.sha256(installed).hexdigest(),readonly_rootfs=info['HostConfig']['ReadonlyRootfs'],image_id=info['Image'],image_repo_digests=json.loads(docker('image','inspect',info['Image']))[0]['RepoDigests'],repo_digest_is_signature=False))
    c.rollback()
with psycopg.connect(**params) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert c.execute('SELECT pg_xact_status(%s::xid8)',(xid,)).fetchone()[0]=='aborted'
    assert c.execute('SELECT count(*) FROM pg_stat_activity WHERE pid=%s',(pid,)).fetchone()[0]==0
    for fn in functions:assert c.execute('SELECT to_regprocedure(%s)',('aos_admission_native_private.'+fn+'()',)).fetchone()[0] is None
    assert c.execute("SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid='aos_admission_native_private.pending_relations()'::regprocedure").fetchone()==original
    for role in ['aos_physical_capacity_occupation_owner','aos_provider_capacity_issuer','aos_provider_capacity_occupation','aos_model_eval_issuer_owner','aos_capacity_publication_owner']:
        flags=c.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(role,)).fetchone();assert flags is not None and not any(flags)
        assert c.execute('SELECT count(*) FROM pg_auth_members WHERE member=%s::regrole OR roleid=%s::regrole',(role,role)).fetchone()[0]==0
    c.rollback()
for path,digest in {spec['library']:spec['library_sha256'],spec['foreign_library']:spec['foreign_library_sha256'],'/usr/local/lib/postgresql/aos_ed25519.so':'6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'}.items():assert docker('exec',lab['name'],'sha256sum',path).decode().split()[0]==digest
out=dict(module_count=len(rows),apk_owned_count=sum(r['apk'] is not None for r in rows),apk_checksum_matches=sum(r['apk'] is not None and r['apk']['installed_checksum_matches'] is True for r in rows),unowned_modules=[r['path'] for r in rows if r['apk'] is None],writable_files=[r['path'] for r in rows if r['file_and_ancestors'][0]['writable_by_container_identity']],loader_callback_import_modules=[r['path'] for r in rows if r['elf']['loader_callback_imports']],readonly_rootfs=info['HostConfig']['ReadonlyRootfs'],original_metadata_exact=True,five_owners_closed=True,xid_aborted=True,backend_gone=True,new_interfaces_absent=True,original_binaries_exact=True,package_source_build_provenance_proved=False,immutable_lifecycle_proved=False,formal_database_changed=False,execution_allowed=False,full_task_delivered=False)
save('verification.json',out);print(json.dumps(out))
