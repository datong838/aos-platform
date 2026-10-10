"""Two fixed-input relinks in a new isolated builder; never execute postgres."""
import hashlib,json,pathlib,subprocess
B=pathlib.Path(__file__).resolve().parent
R=next(p for p in B.parents if (p/'services/aos-api').is_dir())
C=R/'.evidence/gt-shared-parent-native-ending-20261011/pg-core-build-1778/r3'
def save(n,d):(B/n).open('x').write(json.dumps(d,indent=2)+'\n')
def cmd(*a):return subprocess.check_output(a,timeout=30)
v=json.loads((C/'verification.json').read_text());assert json.loads((C/'build-terminal.json').read_text())['exit_code']==0
manifest=json.loads((C/'input-manifest.json').read_text());assert hashlib.sha256((C/'build.py').read_bytes()).hexdigest()==manifest['build_script_sha256']
expected=v['files']['postgres']['rebuilt_sha256'];save('sdk-export-intent.json',dict(context=str(C),target='build',network='default',expected_core_sha256=expected,original_source_script_sha256=manifest['build_script_sha256']))
with (B/'sdk-export.log').open('xb') as log:
    result=subprocess.run(['docker','build','--target','build','--network','default','--iidfile',str(B/'sdk-image-id.txt'),'-t','aos-pg-core-sdk-1779:exact',str(C)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
save('sdk-export-terminal.json',dict(exit_code=result.returncode))
if result.returncode:raise RuntimeError('SDK_EXPORT_FAILED preserve state no retry')
sdk=(B/'sdk-image-id.txt').read_text().strip();save('sdk-image.json',dict(image=sdk))
(B/'reference.json').open('x').write(json.dumps(dict(expected_core_sha256=expected)))
probe='''import hashlib,json,pathlib,shutil,subprocess
src=pathlib.Path('/build/source/postgresql-16.14');out=pathlib.Path('/probe-output');out.mkdir();core=src/'src/backend/postgres'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected=json.loads(pathlib.Path('/probe/reference.json').read_text())['expected_core_sha256'];assert sha(core)==expected
inputs={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file() and p.suffix in ('.o','.a')};assert inputs
versions={n:subprocess.check_output([n,'--version']).decode().splitlines()[0] for n in ['gcc','ld']}
tools={n:sha(pathlib.Path(shutil.which(n)).resolve()) for n in ['gcc','ld','ar']}
shutil.copyfile(core,out/'first-postgres');hashes=[sha(core)]
for i in (1,2):
    core.unlink();subprocess.run(['make','-j2','-C',str(src/'src/backend'),'postgres'],check=True);shutil.copyfile(core,out/('relink'+str(i)+'-postgres'));hashes.append(sha(core))
after={str(p.relative_to(src)):sha(p) for p in src.rglob('*') if p.is_file() and p.suffix in ('.o','.a')};assert inputs==after
pkg=pathlib.Path('/lib/apk/db/installed').read_bytes();(out/'apk-installed').write_bytes(pkg)
result=dict(fixed_object_and_archive_inputs=len(inputs),inputs=inputs,input_hashes_unchanged=True,compiler_linker_versions=versions,tool_binary_sha256=tools,apk_db_sha256=hashlib.sha256(pkg).hexdigest(),three_core_sha256=hashes,three_outputs_raw_equal=len(set(hashes))==1,no_pg_execution=True,historical_linker_provenance=False)
(out/'probe.json').write_text(json.dumps(result,indent=2)+'\\n');print(json.dumps({k:v for k,v in result.items() if k!='inputs'}))
'''
(B/'relink.py').open('x').write(probe)
recipe='FROM aos-pg-core-sdk-1779:exact@'+sdk+' AS probe\nCOPY relink.py reference.json /probe/\nRUN python3 /probe/relink.py\nFROM scratch\nCOPY --from=probe /probe-output /artifacts\n';(B/'Dockerfile').open('x').write(recipe)
save('probe-build-intent.json',dict(sdk_image=sdk,network='none',predetermined_relinks=2,script_sha256=hashlib.sha256(probe.encode()).hexdigest()))
with (B/'build.log').open('xb') as log:
    result=subprocess.run(['docker','build','--network','none','--iidfile',str(B/'image-id.txt'),str(B)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
save('probe-build-terminal.json',dict(exit_code=result.returncode))
if result.returncode:raise RuntimeError('PROBE_BUILD_FAILED preserve diagnostics')
image=(B/'image-id.txt').read_text().strip();save('artifact-create-intent.json',dict(image=image,network='none',never_start=True))
c=cmd('docker','create','--network','none','--entrypoint','/never-execute',image).decode().strip();save('artifact-created.json',dict(container=c));(B/'artifacts').mkdir()
for n in ['first-postgres','relink1-postgres','relink2-postgres','probe.json','apk-installed']:cmd('docker','cp',c+':/artifacts/'+n,str(B/'artifacts'/n))
i=json.loads(cmd('docker','inspect',c))[0];assert not i['State']['Running'] and i['State']['Status']=='created' and not i['Mounts']
p=json.loads((B/'artifacts/probe.json').read_text());old=cmd('docker','exec','aos-source-desktop-shm-20261009','cat','/usr/local/bin/postgres');assert hashlib.sha256(old).hexdigest()==v['files']['postgres']['installed_sha256']
save('verification.json',dict(three_hashes=p['three_core_sha256'],three_raw_equal=p['three_outputs_raw_equal'],input_hashes_unchanged=p['input_hashes_unchanged'],original_core_sha256=hashlib.sha256(old).hexdigest(),never_started=True,no_mounts=True,original_binary_reproduced=False,full_task_delivered=False,execution_allowed=False));print(json.dumps(p['three_core_sha256']))
