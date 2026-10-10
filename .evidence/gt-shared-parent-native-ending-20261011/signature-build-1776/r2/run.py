"""Reproduce original verifier, never install it or invoke database functions."""
import hashlib,json,pathlib,shutil,subprocess
B=pathlib.Path(__file__).resolve().parent
R=next(p for p in B.parents if (p/'services/aos-api/postgres-extensions/aos_admission_end').is_dir())
P=R/'services/aos-api/postgres-extensions/aos_ed25519'
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
expected='6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'
archive_sha='f6d077142737920858ce958ccdb75c6ee137a63b5b0853c70693d401ac7e3471'
def save(name,data):(B/name).open('x').write(json.dumps(data,indent=2)+'\n')
def command(*args):return subprocess.check_output(args,timeout=30)
info=json.loads(command('docker','inspect',lab['name']))[0]
assert info['Id']==lab['container_id'] and info['Image']==lab['image'] and info['State']['Running']
installed_path='/usr/local/lib/postgresql/aos_ed25519.so'
assert command('docker','exec',lab['name'],'sha256sum',installed_path).decode().split()[0]==expected
source=B/'frozen-source';source.mkdir();hashes={}
for name in ('aos_ed25519.c','Makefile','aos_ed25519.control','aos_ed25519--1.0.sql','Dockerfile'):
    raw=(P/name).read_bytes();hashes[name]=hashlib.sha256(raw).hexdigest();(source/name).open('xb').write(raw)
archive=R/'.evidence/gt-shared-parent-native-ending-20261011/backend-source-audit-r1/postgresql-16.14.tar.bz2'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==archive_sha
history=command('docker','history','--no-trunc','--format','{{json .CreatedBy}}',lab['image']).decode().splitlines()
image=json.loads(command('docker','image','inspect',lab['image']))[0]
env=[x for x in image['Config'].get('Env',[]) if x.startswith(('PG_VERSION=','PG_MAJOR=','PG_SHA256='))]
assert 'PG_VERSION=16.14' in env and 'PG_SHA256='+archive_sha in env and any(archive_sha in x for x in history)
save('input-manifest.json',dict(source_hashes=hashes,base_image=lab['image'],original_installed_sha256=expected,pg_archive_sha256=archive_sha,whitelisted_pg_environment=env,image_history_command_hashes=[hashlib.sha256(x.encode()).hexdigest() for x in history],archive_hash_in_history=True,signed_build_provenance_proved=False))
base='aos-precommit-probe-20261009-base:exact@'+lab['image']
save('build-intent.json',dict(context=str(source),dockerfile_sha256=hashes['Dockerfile'],base_image=base,network='default',original_recipe_unchanged=True))
with (B/'build.log').open('xb') as log:
    result=subprocess.run(['docker','build','--network','default','--build-arg','PG_BASE_IMAGE='+base,'--iidfile',str(B/'image-id.txt'),str(source)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
save('build-terminal.json',dict(exit_code=result.returncode))
if result.returncode!=0:raise RuntimeError('BUILD_FAILED: preserve diagnostics; no runtime or network retry')
new_image=(B/'image-id.txt').read_text().strip();save('artifact-create-intent.json',dict(image=new_image,network='none',never_start=True))
container=command('docker','create','--network','none',new_image).decode().strip();save('artifact-created.json',dict(container=container,never_started=True))
extract=B/'artifacts';extract.mkdir();files={}
for name,path in [('aos_ed25519.so',installed_path),('aos_ed25519.control','/usr/local/share/postgresql/extension/aos_ed25519.control'),('aos_ed25519--1.0.sql','/usr/local/share/postgresql/extension/aos_ed25519--1.0.sql')]:
    command('docker','cp',container+':'+path,str(extract/name));raw=(extract/name).read_bytes();observed=hashlib.sha256(raw).hexdigest();original=command('docker','exec',lab['name'],'cat',path)
    files[name]=dict(rebuilt_sha256=observed,installed_sha256=hashlib.sha256(original).hexdigest(),bytes_equal=raw==original)
for name,digest in hashes.items():assert hashlib.sha256((P/name).read_bytes()).hexdigest()==digest
assert command('docker','exec',lab['name'],'sha256sum',installed_path).decode().split()[0]==expected
state=json.loads(command('docker','inspect',container))[0]['State'];assert state['Status']=='created' and not state['Running'] and state['StartedAt'].startswith('0001-')
out=dict(files=files,source_and_original_binary_unchanged=True,original_recipe_unchanged=True,never_started_artifact_container=True,exact_binary_reproduced=files['aos_ed25519.so']['bytes_equal'],trusted_signed_build_provenance_proved=False,all_five_components_provenance_proved=False,formal_database_changed=False,full_task_delivered=False,execution_allowed=False)
save('verification.json',out);print(json.dumps(out))
