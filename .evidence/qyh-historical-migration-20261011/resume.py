import ast,hashlib,io,json,subprocess,tarfile,zipfile
from pathlib import Path
R=Path(__file__).resolve().parent
tree=ast.parse((R/'migrate.py').read_text())
prefix=[]
for node in tree.body:
    if isinstance(node,ast.If):break
    prefix.append(node)
env={'__file__':str(R/'resume.py')}
exec(compile(ast.Module(body=prefix,type_ignores=[]),str(R/'resume.py'),'exec'),env)
m=env['m'];TARGET=env['TARGET'];CID=env['CID'];TOOL=env['TOOL'];VOLUME=env['VOLUME'];target=env['target'];read_identity=env['read_identity']
DEP='qyh-historical-migration-deps-20261011'
assert not (R/'deps-intent.json').exists(),'Existing resume attempt; readonly reconcile, no replay'
identity=read_identity();assert identity['version']=='a0v_092' and identity['cluster']=='7695294217975042088'
baseline=json.loads((R.parent/'qyh-historical-full-restore-20261011'/'source-before.json').read_text())
assert m.fingerprint(TARGET)==baseline and m.fingerprint(m.SOURCE)==baseline
old=json.loads((R/'93-terminal.json').read_text());assert old['exit']==1 and "No module named 'fastapi'" in old['stderr']
wheels=R.parents[2]/'aos-recovery/current157-fac006c02b6e/migration-tool-image/api-wheels'
names=('fastapi','starlette','anyio','annotated_doc','idna','exceptiongroup')
wheel_hashes={};files={}
for name in names:
    matches=list(wheels.glob(name+'-*.whl'));assert len(matches)==1
    path=matches[0];raw=path.read_bytes();wheel_hashes[path.name]=hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for item in archive.infolist():
            if item.is_dir():continue
            assert not Path(item.filename).is_absolute() and '..' not in Path(item.filename).parts
            files[item.filename]=archive.read(item)
buffer=io.BytesIO()
with tarfile.open(fileobj=buffer,mode='w') as archive:
    for name,raw in files.items():
        item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o644;archive.addfile(item,io.BytesIO(raw))
assert subprocess.run(['docker','--context',m.CTX,'volume','inspect',DEP],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
m.record('deps-intent.json',{'volume':DEP,'cachedWheels':wheel_hashes,'baseTool':TOOL,'targetUnchangedAt092':True,'basePydanticUnchanged':True})
m.run(['docker','--context',m.CTX,'volume','create','--label','aos.task=qyh-historical-migration-20261011',DEP])
extract="import sys,tarfile;tarfile.open(fileobj=sys.stdin.buffer,mode='r|').extractall('/deps',filter='data')"
p=subprocess.run(['docker','--context',m.CTX,'run','-i','--pull','never','--name','qyh-historical-deps-freeze-20261011','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=volume,source='+DEP+',target=/deps',TOOL,'python','-c',extract],input=buffer.getvalue(),capture_output=True,timeout=120)
m.record('deps-terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode()});assert p.returncode==0
deps={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()};m.record('deps-manifest.json',deps)
manifest=json.loads((R/'code-manifest.json').read_text())
program=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='program' for t in n.targets))
program=program.replace("sys.path.insert(0,'/code/services/aos-api')","sys.path.insert(0,'/deps');sys.path.insert(0,'/code/services/aos-api')")
program=program.replace("manifest=json.loads(sys.stdin.buffer.read()); step=meta['step']","payload=json.loads(sys.stdin.buffer.read()); manifest=payload['code']; step=meta['step']\nfor path,digest in payload['deps'].items():assert hashlib.sha256((Path('/deps')/path).read_bytes()).hexdigest()==digest,path")
for number in range(93,160):
    x=target();before=read_identity();assert before['cluster']==identity['cluster'] and before['version']=='a0v_'+str(number-1).zfill(3)
    label=str(number)+'-r2';assert not (R/(label+'-intent.json')).exists(),'Existing step attempt; reconcile'
    args=['docker','--context',m.CTX,'run','-i','--pull','never','--name','qyh-historical-step-'+str(number)+'-r2-20261011','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','-e','PYTHONDONTWRITEBYTECODE=1','--mount','type=bind,source='+x['GraphDriver']['Data']['MergedDir']+'/var/run/postgresql,target=/pgsocket,readonly','--mount','type=volume,source='+VOLUME+',target=/code,readonly','--mount','type=volume,source='+DEP+',target=/deps,readonly',TOOL,'python','-c',program,json.dumps({'step':number,'cluster':identity['cluster']})]
    m.record(label+'-intent.json',{'before':before,'programSha256':hashlib.sha256(program.encode()).hexdigest(),'targetId':CID,'codeVolume':VOLUME,'depsVolume':DEP})
    p=subprocess.run(args,input=json.dumps({'code':manifest,'deps':deps}).encode(),capture_output=True,timeout=180)
    m.record(label+'-terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode(errors='replace'),'stdout':p.stdout.decode(errors='replace')})
    after=read_identity();m.record(label+'-identity.json',after)
    assert p.returncode==0,'Migration failed; preserve and reconcile'
    assert after['version']=='a0v_'+str(number).zfill(3)
    current=m.fingerprint(TARGET);lookup={v['table']:v for v in current}
    changed=[v['table'] for v in baseline if v['table']!='public.alembic_version' and lookup.get(v['table'])!=v]
    m.record(label+'-data.json',{'oldTablesChecked':len(baseline)-1,'changed':changed,'newTables':[v['table'] for v in current if v['table'] not in {b['table'] for b in baseline}]})
    assert not changed,'Historical data drift; no automatic exemption'
    print(json.dumps({'step':number,'historicalTablesUnchanged':True}),flush=True)
assert m.fingerprint(m.SOURCE)==baseline
m.record('result.json',{'outcome':'ORIGINAL67_HISTORICAL_MIGRATION_STEPS_COMMITTED_OLD_DATA_PRESERVED','target':read_identity(),'steps':67,'oldTablesChecked':len(baseline)-1,'sourceUnchanged':True,'businessExecution':False,'catalogAndReadinessFinalReviewPending':True})
print(json.dumps({'outcome':'ORIGINAL67_HISTORICAL_MIGRATION_STEPS_COMMITTED_OLD_DATA_PRESERVED'}),flush=True)
