import hashlib,json,pathlib,shutil,subprocess
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
(out/'probe.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='inputs'}))
