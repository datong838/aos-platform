import hashlib,importlib.util,io,json,os,subprocess,sys,tarfile,time
from pathlib import Path
R=Path(__file__).resolve().parent;REPO=R.parents[1]
s=importlib.util.spec_from_file_location('readonly_tools',R.parent/'qyh-org-name-maintenance-20261011'/'prepare.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
m.R=R;m.DB='aos_meta_head'
TARGET='aos-qyh-history-restore-20261011';CID='ccaaaa4655a86f0beba1bcbcce8891def8146abfd55b3561c5872be53791216e'
TOOL='sha256:2376642dd6f7f8645411408371ea354046448d7b65f182dba762fb4df1f10312'
VOLUME='qyh-historical-migration-code-20261011'
private=R/'private';private.mkdir(exist_ok=True,mode=0o700);os.chmod(private,0o700)
def target():
    x=json.loads(m.run(['docker','--context',m.CTX,'inspect',TARGET]))[0]
    assert x['Id']==CID and x['State']['Running'] and x['Image']==m.IMAGE
    assert x['HostConfig']['NetworkMode']=='none' and not x['HostConfig']['PortBindings'] and not x['Mounts']
    return x
def read_identity():
    return json.loads(m.psql(TARGET,m.DB,"BEGIN READ ONLY; SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'database',current_database(),'version',(SELECT version_num FROM alembic_version)); COMMIT;"))
if (R/'freeze-intent.json').exists():raise RuntimeError('Existing migration attempt; readonly reconciliation required, no automatic replay')
assert json.loads((R.parent/'qyh-historical-restore-catalog-20261011'/'result.json').read_text())['outcome']=='HISTORICAL_RESTORE_CATALOG_BASELINE_VERIFIED'
x=target();identity=read_identity();assert identity['version']=='a0v_092' and identity['database']==m.DB and identity['cluster']!='7683855731447750695'
baseline=m.fingerprint(TARGET);source_before=m.fingerprint(m.SOURCE)
assert baseline==source_before==json.loads((R.parent/'qyh-historical-full-restore-20261011'/'source-before.json').read_text())
head=m.run(['git','-C',str(REPO),'rev-parse','HEAD']).decode().strip()
archive=m.run(['git','-C',str(REPO),'archive',head,'services/aos-api'])
path=private/'committed-source.tar';path.write_bytes(archive);os.chmod(path,0o600)
manifest={}
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    for member in tar.getmembers():
        if member.isfile():manifest[member.name]=hashlib.sha256(tar.extractfile(member).read()).hexdigest()
        elif not member.isdir():raise RuntimeError('Unexpected source artifact type')
chain=json.loads((R.parent/'qyh-historical-full-restore-20261011'/'migration-path.json').read_text())['steps']
assert len(chain)==67
for step in chain:assert manifest[str(Path(step['file']).resolve().relative_to(REPO))]==step['sha256']
assert subprocess.run(['docker','--context',m.CTX,'volume','inspect',VOLUME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
m.record('freeze-intent.json',{'head':head,'volume':VOLUME,'tool':TOOL,'archiveSha256':hashlib.sha256(archive).hexdigest(),'target':identity,'containerId':CID,'sourceWrites':False})
m.run(['docker','--context',m.CTX,'volume','create','--label','aos.task=qyh-historical-migration-20261011',VOLUME])
extract="import sys,tarfile;tarfile.open(fileobj=sys.stdin.buffer,mode='r|').extractall('/code',filter='data')"
p=subprocess.run(['docker','--context',m.CTX,'run','-i','--pull','never','--name','qyh-historical-code-freeze-20261011','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=volume,source='+VOLUME+',target=/code',TOOL,'python','-c',extract],input=archive,capture_output=True,timeout=120)
m.record('freeze-terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode(errors='replace')});assert p.returncode==0
m.record('code-manifest.json',manifest)
program='''import os,sys,json,hashlib
from pathlib import Path
from sqlalchemy import create_engine
from alembic.config import Config
from alembic import command
assert not os.environ.get('AOS_DATABASE_URL')
os.environ['AOS_DOTENV_DISABLED']='1'
sys.path.insert(0,'/code/services/aos-api')
meta=json.loads(sys.argv[1]); manifest=json.loads(sys.stdin.buffer.read()); step=meta['step']
assert 93<=step<=159
for path,digest in manifest.items():assert hashlib.sha256((Path('/code')/path).read_bytes()).hexdigest()==digest,path
cfg=Config('/code/services/aos-api/alembic.ini');cfg.set_main_option('script_location','/code/services/aos-api/alembic')
cfg.set_main_option('sqlalchemy.url','postgresql+psycopg://aos_app@/aos_meta_head?host=/pgsocket')
engine=create_engine(cfg.get_main_option('sqlalchemy.url'))
try:
 with engine.begin() as connection:
  raw=connection.connection.driver_connection
  assert raw.execute('SELECT system_identifier::text,current_database(),inet_server_addr() FROM pg_control_system()').fetchone()==(meta['cluster'],'aos_meta_head',None)
  assert raw.execute('SELECT version_num FROM alembic_version').fetchall()==[('a0v_'+str(step-1).zfill(3),)]
  cfg.attributes['connection']=connection;command.upgrade(cfg,'a0v_'+str(step).zfill(3))
  assert raw.execute('SELECT version_num FROM alembic_version').fetchall()==[('a0v_'+str(step).zfill(3),)]
 print(json.dumps({'step':step,'committed':True,'cluster':meta['cluster']}),flush=True)
finally:engine.dispose()
'''
for number in range(93,160):
    x=target();before=read_identity();assert before['cluster']==identity['cluster'] and before['version']=='a0v_'+str(number-1).zfill(3)
    args=['docker','--context',m.CTX,'run','-i','--pull','never','--name','qyh-historical-step-'+str(number)+'-20261011','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','512m','-e','PYTHONDONTWRITEBYTECODE=1','--mount','type=bind,source='+x['GraphDriver']['Data']['MergedDir']+'/var/run/postgresql,target=/pgsocket,readonly','--mount','type=volume,source='+VOLUME+',target=/code,readonly',TOOL,'python','-c',program,json.dumps({'step':number,'cluster':identity['cluster']})]
    m.record(str(number)+'-intent.json',{'before':before,'programSha256':hashlib.sha256(program.encode()).hexdigest(),'volume':VOLUME,'targetId':CID})
    started=time.monotonic();p=subprocess.run(args,input=json.dumps(manifest).encode(),capture_output=True,timeout=180)
    m.record(str(number)+'-terminal.json',{'exit':p.returncode,'seconds':time.monotonic()-started,'stderr':p.stderr.decode(errors='replace'),'stdout':p.stdout.decode(errors='replace')})
    after=read_identity();m.record(str(number)+'-identity.json',after)
    assert p.returncode==0,'Migration failed; preserve target and terminal'
    assert after['version']=='a0v_'+str(number).zfill(3)
    current=m.fingerprint(TARGET);lookup={v['table']:v for v in current}
    changed=[v['table'] for v in baseline if v['table']!='public.alembic_version' and lookup.get(v['table'])!=v]
    m.record(str(number)+'-data.json',{'oldTablesChecked':len(baseline)-1,'changed':changed,'newTables':[v['table'] for v in current if v['table'] not in {b['table'] for b in baseline}]})
    assert not changed,'Historical data drift; no automatic exemption'
    print(json.dumps({'step':number,'version':after['version'],'historicalTablesUnchanged':True}),flush=True)
assert m.fingerprint(m.SOURCE)==source_before
m.record('result.json',{'outcome':'ORIGINAL67_HISTORICAL_MIGRATION_STEPS_COMMITTED_OLD_DATA_PRESERVED','target':read_identity(),'codeHead':head,'steps':67,'oldTablesChecked':len(baseline)-1,'sourceUnchanged':True,'businessExecution':False,'catalogAndReadinessFinalReviewPending':True})
print(json.dumps({'outcome':'ORIGINAL67_HISTORICAL_MIGRATION_STEPS_COMMITTED_OLD_DATA_PRESERVED','sourceWrites':False}),flush=True)
