"""Isolated PGXS source comparison; never install or start PostgreSQL."""
import hashlib,io,json,pathlib,subprocess,tarfile
B=pathlib.Path(__file__).resolve().parent
R=next(p for p in B.parents if (p/'services/aos-api').is_dir())
BASE='sha256:bcdf34e61bae2345234063d6fa3dd31dbd89b9dd97d9a669b59edc0f1212d883'
LAB='aos-source-desktop-shm-20261009'
def save(name,data):(B/name).open('x').write(json.dumps(data,indent=2)+'\n')
def cmd(*args):return subprocess.check_output(args,timeout=30)
original=json.loads(cmd('docker','inspect',LAB))[0]
assert original['Image']==BASE and original['Id']=='8d2a50eb82cd8e5a8feea0ee647ad63090edb685416c777fcf9deafa9b877d3f' and original['State']['Running']
installed='/usr/local/lib/postgresql/pgcrypto.so'
old=cmd('docker','exec',LAB,'cat',installed);old_sha=hashlib.sha256(old).hexdigest()
archive=R/'.evidence/gt-shared-parent-native-ending-20261011/backend-source-audit-r1/postgresql-16.14.tar.bz2'
raw=archive.read_bytes();archive_sha=hashlib.sha256(raw).hexdigest()
assert archive_sha=='f6d077142737920858ce958ccdb75c6ee137a63b5b0853c70693d401ac7e3471'
source=B/'frozen-source';hashes={}
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:bz2') as t:
    for m in t.getmembers():
        prefix='postgresql-16.14/contrib/pgcrypto/'
        if not m.name.startswith(prefix):continue
        name=m.name[len(prefix):]
        if not name or '/' in name:continue
        assert m.isfile() and name not in ('.','..')
        contents=t.extractfile(m).read();(source/name).open('xb').write(contents);hashes[name]=hashlib.sha256(contents).hexdigest()
assert 'Makefile' in hashes and 'pgcrypto.c' in hashes
recipe='''FROM aos-precommit-probe-20261009-base:exact@'''+BASE+''' AS build
RUN apk add --no-cache build-base openssl-dev zlib-dev
COPY frozen-source /build/pgcrypto
RUN make -C /build/pgcrypto USE_PGXS=1 with_llvm=no && pg_config --version && apk info -v libcrypto3 openssl-dev zlib-dev && cc --version
FROM aos-precommit-probe-20261009-base:exact@'''+BASE+'''
COPY --from=build /build/pgcrypto/pgcrypto.so /artifacts/pgcrypto.so
COPY --from=build /build/pgcrypto/pgcrypto.control /artifacts/pgcrypto.control
'''
(B/'Dockerfile').open('x').write(recipe)
save('input-manifest.json',dict(base_image=BASE,archive_sha256=archive_sha,source_hashes=hashes,original_pgcrypto_sha256=old_sha,upstream_makefile_unchanged=True,build_mode='USE_PGXS=1 with_llvm=no',exact_original_whole_image_recipe=False))
save('build-intent.json',dict(context=str(B),network='default',timeout_seconds=300,dockerfile_sha256=hashlib.sha256(recipe.encode()).hexdigest(),no_install=True,no_pg_start=True))
with (B/'build.log').open('xb') as log:
    result=subprocess.run(['docker','build','--network','default','--iidfile',str(B/'image-id.txt'),str(B)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
save('build-terminal.json',dict(exit_code=result.returncode))
if result.returncode:raise RuntimeError('BUILD_FAILED preserve diagnostics; no retry')
newimage=(B/'image-id.txt').read_text().strip();save('artifact-create-intent.json',dict(image=newimage,network='none',never_start=True))
c=cmd('docker','create','--network','none',newimage).decode().strip();save('artifact-created.json',dict(container=c))
files={};(B/'artifacts').mkdir()
for name,path in [('pgcrypto.so',installed),('pgcrypto.control','/usr/local/share/postgresql/extension/pgcrypto.control')]:
    cmd('docker','cp',c+':/artifacts/'+name,str(B/'artifacts'/name));rebuilt=(B/'artifacts'/name).read_bytes();current=cmd('docker','exec',LAB,'cat',path)
    files[name]=dict(rebuilt_sha256=hashlib.sha256(rebuilt).hexdigest(),installed_sha256=hashlib.sha256(current).hexdigest(),bytes_equal=rebuilt==current)
assert hashlib.sha256(cmd('docker','exec',LAB,'cat',installed)).hexdigest()==old_sha
for name,digest in hashes.items():assert hashlib.sha256((source/name).read_bytes()).hexdigest()==digest
i=json.loads(cmd('docker','inspect',c))[0];assert i['State']['Status']=='created' and not i['State']['Running'] and i['State']['StartedAt'].startswith('0001-')
mounts=[dict(type=x['Type'],name=x.get('Name'),destination=x['Destination'],rw=x['RW']) for x in i['Mounts']]
save('verification.json',dict(files=files,source_and_original_binary_unchanged=True,never_started=True,artifact_mounts=mounts,exact_pgcrypto_reproduced=files['pgcrypto.so']['bytes_equal'],trusted_source_build_provenance=False,formal_database_changed=False,full_task_delivered=False,execution_allowed=False))
print(json.dumps(files))
