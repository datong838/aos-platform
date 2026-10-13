"""Create one named local tmpfs-only test PG; never touch customer PG."""
import json,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent
name='qyh-media-read-isolated-pg-20261013-r2'
base=['docker','--context','colima-aos-extension']
def run(*args):return subprocess.check_output(base+list(args),text=True).strip()
assert not (P/'isolated-pg-r2-intent.json').exists(),'existing attempt: reconcile only'
assert subprocess.run(base+['inspect',name],capture_output=True).returncode!=0
image='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
(P/'isolated-pg-r2-intent.json').write_text(json.dumps({'name':name,'image':image,'purpose':'disposable fixture only','customerDataCopied':False,'noNamedVolume':True,'host':'127.0.0.1'})+'\n')
cid=run('run','-d','--name',name,'--memory','512m','--cpus','1','--tmpfs','/var/lib/postgresql/data:rw,size=512m','-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_USER=aos_app','-e','POSTGRES_DB=postgres','-p','127.0.0.1::5432',image,'-c','shared_buffers=32MB','-c','max_connections=30')
obj=json.loads(run('inspect',cid))[0];assert obj['Id']==cid;assert not obj['Mounts'];assert obj['HostConfig']['Tmpfs']['/var/lib/postgresql/data'];port=obj['NetworkSettings']['Ports']['5432/tcp'][0];assert port['HostIp']=='127.0.0.1' and port['HostPort']!='18446'
for _ in range(50):
 if subprocess.run(base+['exec',cid,'pg_isready','-U','aos_app'],capture_output=True).returncode==0:break
 time.sleep(.2)
else:raise RuntimeError('readiness pending:reconcile same CID')
cluster=run('exec',cid,'psql','-U','aos_app','-Atc','SELECT system_identifier FROM pg_control_system()');assert cluster!='7695302940039200809'
result={'name':name,'cid':cid,'port':int(port['HostPort']),'cluster':cluster,'fixtureOnly':True,'pgdataTmpfs':True,'customerDataCopied':False}
(P/'isolated-pg-r2-started.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
