"""Isolated file lifetime negative/positive. Never install or invoke a PG module."""
import hashlib,json,pathlib,subprocess,uuid
B=pathlib.Path(__file__).resolve().parent
R=next(p for p in B.parents if (p/'services/aos-api/postgres-extensions/aos_admission_end').is_dir())
def save(name,value):(B/name).open('x').write(json.dumps(value,indent=2)+'\n')
def command(*args,timeout=30):return subprocess.check_output(args,timeout=timeout)
profile=json.loads((B.parent.parent/'package-origin-1774/r2/current-package.json').read_text())
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
info=json.loads(command('docker','inspect',lab['name']))[0]
assert info['Id']==lab['container_id'] and info['Image']==lab['image'] and info['State']['Running']
assert len(profile['modules'])==27 and profile['image_id']==lab['image']
pack=B/'pack';pack.mkdir();manifest=[];expected={}
for row in profile['modules']:
    raw=command('docker','exec',lab['name'],'cat',row['path'])
    assert hashlib.sha256(raw).hexdigest()==row['sha256'] and len(raw)==row['bytes']<=256*1024*1024
    name=row['sha256']+'.bin';assert name not in expected
    (pack/name).open('xb').write(raw);manifest.append(row['sha256']+'  '+name);expected[name]=row['sha256']
(pack/'SHA256SUMS').open('x').write('\n'.join(manifest)+'\n')
save('input-manifest.json',dict(source_profile=str((B.parent.parent/'package-origin-1774/r2/current-package.json').relative_to(R)),source_profile_sha256=hashlib.sha256((B.parent.parent/'package-origin-1774/r2/current-package.json').read_bytes()).hexdigest(),base_image=lab['image'],byte_files=expected,source_build_provenance_proved=False))
native=next(r['sha256']+'.bin' for r in profile['modules'] if r['path'].startswith('/tmp/aos_admission_modules_'))
(B/'Dockerfile').open('x').write('FROM aos-precommit-probe-20261009-base:exact@'+lab['image']+' AS substrate\nFROM scratch\nCOPY --from=substrate /bin/busybox /bin/busybox\nCOPY --from=substrate /lib/ld-musl-aarch64.so.1 /lib/ld-musl-aarch64.so.1\nCOPY pack /opt/aos-native-package\nCOPY probe.sh /opt/aos-native-package/probe.sh\nRUN ["/bin/busybox","sh","-c","/bin/busybox ln -s ld-musl-aarch64.so.1 /lib/libc.musl-aarch64.so.1; for c in sh sha256sum sed chmod id mv; do /bin/busybox ln -s busybox /bin/$c; done; /bin/busybox mkdir /opt/aos-native-package-owned; /bin/busybox cp /opt/aos-native-package/'+native+' /opt/aos-native-package-owned/fixture.bin; /bin/busybox chown 501:20 /opt/aos-native-package-owned/fixture.bin; /bin/busybox chmod 444 /opt/aos-native-package-owned/fixture.bin"]\nUSER 501:20\nENTRYPOINT ["/bin/sh","/opt/aos-native-package/probe.sh"]\n')
save('build-intent.json',dict(base=lab['image'],context=str(B),network='none',no_original_file_or_volume_changes=True))
with (B/'build.log').open('xb') as log:
    subprocess.run(['docker','build','--network','none','--iidfile',str(B/'image-id.txt'),str(B)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
image=(B/'image-id.txt').read_text().strip();results={}
assert not json.loads(command('docker','image','inspect',image))[0]['Config'].get('Volumes')
for mode in ('mutable','protected'):
    name='aos-native-lifetime-'+mode+'-'+uuid.uuid4().hex[:12]
    args=['docker','create','--name',name,'--network','none','--user','501:20','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','128m','--cpus','1','--pids-limit','32']
    if mode=='protected':args+=['--read-only']
    args += [image,mode]
    save(mode+'-create-intent.json',dict(name=name,image=image,args=args,no_pg_process=True,no_original_mounts=True))
    container=command(*args).decode().strip();save(mode+'-created.json',dict(container=container,name=name))
    save(mode+'-start-intent.json',dict(container=container))
    result=subprocess.run(['docker','start','-a',container],capture_output=True,timeout=20)
    after=json.loads(command('docker','inspect',container))[0]
    save(mode+'-terminal.json',dict(container=container,state=after['State'],exit_code=result.returncode,stdout=result.stdout.decode(),stderr=result.stderr.decode(),readonly_rootfs=after['HostConfig']['ReadonlyRootfs'],mounts=after['Mounts'],user=after['Config']['User'],cap_drop=after['HostConfig']['CapDrop'],security_opt=after['HostConfig']['SecurityOpt'],network=after['HostConfig']['NetworkMode']))
    assert not after['State']['Running'] and after['State']['ExitCode']==result.returncode==0
    assert not after['Mounts'] and after['Config']['User']=='501:20' and after['HostConfig']['NetworkMode']=='none'
    assert after['HostConfig']['CapDrop']==['ALL'] and 'no-new-privileges' in after['HostConfig']['SecurityOpt']
    assert after['HostConfig']['ReadonlyRootfs']==(mode=='protected')
    marker=b'OWNER_CHMOD_THEN_WRITE_SUCCEEDED' if mode=='mutable' else b'OWNER_AND_PACKAGE_WRITE_CHMOD_RENAME_DENIED'
    assert marker in result.stdout and b'PACKAGE27_HASHES_UNCHANGED' in result.stdout
    copy=B/(mode+'-fixture.bin');command('docker','cp',container+':/opt/aos-native-package-owned/fixture.bin',str(copy))
    original=(pack/native).read_bytes();assert copy.read_bytes()==(original+b'X' if mode=='mutable' else original)
    diff=command('docker','diff',container).decode();save(mode+'-filesystem-diff.json',dict(diff=diff))
    if mode=='protected':assert not diff.strip()
    results[mode]=dict(container=container,terminal=True,expected_marker=True,fixture_bytes_expected=True,readonly_rootfs=after['HostConfig']['ReadonlyRootfs'])
for row in profile['modules']:
    assert hashlib.sha256(command('docker','exec',lab['name'],'cat',row['path'])).hexdigest()==row['sha256']
out=dict(status='ISOLATED_FILE_SUBSTRATE_GREEN',cases=results,package_byte_files=27,original27_module_hashes_exact=True,chmod_only_insufficient_proved=True,readonly_rootfs_file_write_chmod_rename_denied=True,no_pg_process_started=True,no_original_volumes_or_mounts=True,mapped_memory_immutable_proved=False,signed_source_build_provenance_proved=False,formal_root_issued=False,full_task_delivered=False,execution_allowed=False)
save('verification.json',out);print(json.dumps(out))
