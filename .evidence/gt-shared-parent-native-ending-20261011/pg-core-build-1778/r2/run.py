"""Controlled whole upstream build; no runtime installation or execution."""
import hashlib,io,json,pathlib,re,shlex,shutil,subprocess,tarfile
B=pathlib.Path(__file__).resolve().parent
R=next(p for p in B.parents if (p/'services/aos-api').is_dir())
BASE='sha256:bcdf34e61bae2345234063d6fa3dd31dbd89b9dd97d9a669b59edc0f1212d883'
LAB='aos-source-desktop-shm-20261009'
def cmd(*args):return subprocess.check_output(args,timeout=30)
def save(n,d):(B/n).open('x').write(json.dumps(d,indent=2)+'\n')
info=json.loads(cmd('docker','inspect',LAB))[0]
assert info['Image']==BASE and info['Id']=='8d2a50eb82cd8e5a8feea0ee647ad63090edb685416c777fcf9deafa9b877d3f' and info['State']['Running']
archive=R/'.evidence/gt-shared-parent-native-ending-20261011/backend-source-audit-r1/postgresql-16.14.tar.bz2'
raw=archive.read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='f6d077142737920858ce958ccdb75c6ee137a63b5b0853c70693d401ac7e3471'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:bz2') as t:
    for m in t.getmembers():
        p=pathlib.PurePosixPath(m.name)
        assert not p.is_absolute() and '..' not in p.parts and p.parts[0]=='postgresql-16.14' and (m.isfile() or m.isdir())
flags=shlex.split(cmd('docker','exec',LAB,'pg_config','--configure').decode())
history=cmd('docker','history','--no-trunc','--format','{{json .CreatedBy}}',BASE).decode().splitlines()
dependency=[];matched=[]
for line in history:
    text=json.loads(line)
    match=re.search(r'--virtual\s+\.build-deps\s+(.*?)(?:;|&&)',text)
    if match and 'PG_VERSION' in text:
        dependency=re.findall(r'[a-zA-Z0-9.+_-]+',match.group(1));matched.append(hashlib.sha256(line.encode()).hexdigest())
assert dependency and dependency[0]=='DOCKER_PG_LLVM_DEPS'
env=json.loads(cmd('docker','image','inspect',BASE))[0]['Config']['Env']
llvm=next(x.split('=',1)[1].split() for x in env if x.startswith('DOCKER_PG_LLVM_DEPS='))
assert llvm==['llvm21-dev','clang21'];dependency=llvm+dependency[1:]
assert all(re.fullmatch(r'[a-zA-Z0-9.+_-]+',x) for x in dependency)
paths={'postgres':'/usr/local/bin/postgres','plpgsql.so':'/usr/local/lib/postgresql/plpgsql.so','pgcrypto.so':'/usr/local/lib/postgresql/pgcrypto.so','pg_config.h':'/usr/local/include/postgresql/server/pg_config.h','pg_config_ext.h':'/usr/local/include/postgresql/server/pg_config_ext.h','probes.h':'/usr/local/include/postgresql/server/utils/probes.h'}
original={n:hashlib.sha256(cmd('docker','exec',LAB,'cat',p)).hexdigest() for n,p in paths.items()}
shutil.copyfile(archive,B/'postgresql-16.14.tar.bz2')
(B/'configure-flags.json').open('x').write(json.dumps(flags))
build='''import pathlib,json,subprocess,tarfile
root=pathlib.Path('/build/source');root.mkdir()
with tarfile.open('/build/postgresql-16.14.tar.bz2') as t:t.extractall(root)
src=root/'postgresql-16.14';p=src/'src/include/pg_config_manual.h';s=p.read_text();old='#define DEFAULT_PGSOCKET_DIR  "/tmp"';new='#define DEFAULT_PGSOCKET_DIR "/var/run/postgresql"';assert s.count(old)==1;p.write_text(s.replace(old,new))
sdk=pathlib.Path('/usr/local/include');park=pathlib.Path('/build/preexisting-sdk');assert sdk.is_dir() and not park.exists();sdk.rename(park)
try:
    subprocess.run(['./configure',*json.loads(pathlib.Path('/build/configure-flags.json').read_text())],cwd=src,check=True)
finally:
    park.rename(sdk)
global_text=(src/'src/Makefile.global').read_text();include_lines=[x for x in global_text.splitlines() if x.startswith(('INCLUDES =','CPPFLAGS ='))];print(json.dumps({'preexisting_include_parked_only_during_configure':True,'sdk_restored':sdk.is_dir(),'generated_include_lines':include_lines}))
subprocess.run(['make','-j2','world-bin'],cwd=src,check=True)
'''
(B/'build.py').open('x').write(build)
recipe='FROM aos-precommit-probe-20261009-base:exact@'+BASE+' AS build\nRUN apk add --no-cache '+' '.join(dependency)+'\nWORKDIR /build\nCOPY postgresql-16.14.tar.bz2 configure-flags.json build.py ./\nRUN python3 /build/build.py\nFROM scratch\n'
outputs={'postgres':'src/backend/postgres','plpgsql.so':'src/pl/plpgsql/src/plpgsql.so','pgcrypto.so':'contrib/pgcrypto/pgcrypto.so','pg_config.h':'src/include/pg_config.h','pg_config_ext.h':'src/include/pg_config_ext.h','probes.h':'src/include/utils/probes.h'}
for n,p in outputs.items():recipe+='COPY --from=build /build/source/postgresql-16.14/'+p+' /artifacts/'+n+'\n'
(B/'Dockerfile').open('x').write(recipe)
save('input-manifest.json',dict(base_image=BASE,archive_sha256=sha,configure_flags=flags,build_dependencies=dependency,history_command_hashes=matched,original_artifact_hashes=original,build_script_sha256=hashlib.sha256(build.encode()).hexdigest(),socket_patch_only=True,whole_image_recipe_replayed=False))
save('build-intent.json',dict(network='default',timeout_seconds=1200,jobs=2,never_install=True,never_start=True,dockerfile_sha256=hashlib.sha256(recipe.encode()).hexdigest()))
try:
    with (B/'build.log').open('xb') as log:
        result=subprocess.run(['docker','build','--network','default','--iidfile',str(B/'image-id.txt'),str(B)],stdout=log,stderr=subprocess.STDOUT,timeout=1200)
except subprocess.TimeoutExpired:
    save('build-terminal.json',dict(status='timeout_unknown_build_outcome',no_replay=True));raise
save('build-terminal.json',dict(exit_code=result.returncode))
if result.returncode:raise RuntimeError('BUILD_FAILED preserve evidence no retry')
image=(B/'image-id.txt').read_text().strip();save('artifact-create-intent.json',dict(image=image,never_start=True,network='none'))
c=cmd('docker','create','--network','none','--entrypoint','/never-execute',image).decode().strip();save('artifact-created.json',dict(container=c));(B/'artifacts').mkdir();files={}
for n,p in paths.items():
    cmd('docker','cp',c+':/artifacts/'+n,str(B/'artifacts'/n));rebuilt=(B/'artifacts'/n).read_bytes();current=cmd('docker','exec',LAB,'cat',p);assert hashlib.sha256(current).hexdigest()==original[n]
    files[n]=dict(rebuilt_sha256=hashlib.sha256(rebuilt).hexdigest(),installed_sha256=original[n],bytes_equal=rebuilt==current)
i=json.loads(cmd('docker','inspect',c))[0];assert not i['State']['Running'] and i['State']['Status']=='created' and not i['Mounts']
save('verification.json',dict(files=files,never_started=True,no_mounts=True,original_artifacts_unchanged=True,signed_source_build_provenance=False,full_task_delivered=False,execution_allowed=False));print(json.dumps(files))
