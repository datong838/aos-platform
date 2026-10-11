import ast,hashlib,json,subprocess
from pathlib import Path
from preservation import check,baseline
R=Path(__file__).resolve().parent;tree=ast.parse((R/'migrate.py').read_text());prefix=[]
for node in tree.body:
    if isinstance(node,ast.If):break
    prefix.append(node)
env={'__file__':str(R/'resume_r3.py')};exec(compile(ast.Module(body=prefix,type_ignores=[]),str(R/'resume_r3.py'),'exec'),env)
m=env['m'];TARGET=env['TARGET'];CID=env['CID'];TOOL=env['TOOL'];VOLUME=env['VOLUME'];target=env['target'];read_identity=env['read_identity']
DEP='qyh-historical-migration-deps-20261011'
identity=read_identity();assert identity['version']=='a0v_117' and identity['cluster']=='7695294217975042088'
assert check(117)['historicalRowsUnchanged'] and m.fingerprint(m.SOURCE)==baseline
manifest=json.loads((R/'code-manifest.json').read_text());deps=json.loads((R/'deps-manifest.json').read_text())
program=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='program' for t in n.targets))
program=program.replace("sys.path.insert(0,'/code/services/aos-api')","sys.path.insert(0,'/deps');sys.path.insert(0,'/code/services/aos-api')")
program=program.replace("manifest=json.loads(sys.stdin.buffer.read()); step=meta['step']","payload=json.loads(sys.stdin.buffer.read()); manifest=payload['code']; step=meta['step']\nfor path,digest in payload['deps'].items():assert hashlib.sha256((Path('/deps')/path).read_bytes()).hexdigest()==digest,path")
for number in range(118,160):
    x=target();before=read_identity();assert before['cluster']==identity['cluster'] and before['version']=='a0v_'+str(number-1).zfill(3)
    label=str(number)+'-r3';assert not (R/(label+'-intent.json')).exists(),'Existing step attempt; reconcile'
    args=['docker','--context',m.CTX,'run','-i','--pull','never','--name','qyh-historical-step-'+str(number)+'-r3-20261011','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','-e','PYTHONDONTWRITEBYTECODE=1','--mount','type=bind,source='+x['GraphDriver']['Data']['MergedDir']+'/var/run/postgresql,target=/pgsocket,readonly','--mount','type=volume,source='+VOLUME+',target=/code,readonly','--mount','type=volume,source='+DEP+',target=/deps,readonly',TOOL,'python','-c',program,json.dumps({'step':number,'cluster':identity['cluster']})]
    m.record(label+'-intent.json',{'before':before,'programSha256':hashlib.sha256(program.encode()).hexdigest(),'targetId':CID,'metadataExpectationsSha256':hashlib.sha256((R/'metadata-expectations.json').read_bytes()).hexdigest()})
    p=subprocess.run(args,input=json.dumps({'code':manifest,'deps':deps}).encode(),capture_output=True,timeout=180)
    m.record(label+'-terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode(errors='replace'),'stdout':p.stdout.decode(errors='replace')})
    after=read_identity();m.record(label+'-identity.json',after);assert p.returncode==0,'Migration failed; preserve and reconcile'
    assert after['version']=='a0v_'+str(number).zfill(3)
    data=check(number);m.record(label+'-data.json',data)
    print(json.dumps({'step':number,'historicalRowsUnchanged':True,'reviewedMetadataAdditions':len(data['originalMigrationMetadataAdditions'])}),flush=True)
assert m.fingerprint(m.SOURCE)==baseline
m.record('result.json',{'outcome':'ORIGINAL67_HISTORICAL_MIGRATION_STEPS_COMMITTED_EXISTING_ROWS_PRESERVED','target':read_identity(),'steps':67,'oldTablesChecked':len(baseline)-1,'sourceUnchanged':True,'reviewedMetadataAdditions':16,'businessExecution':False,'catalogAndReadinessFinalReviewPending':True})
print(json.dumps({'outcome':'ORIGINAL67_HISTORICAL_MIGRATION_STEPS_COMMITTED_EXISTING_ROWS_PRESERVED'}),flush=True)
