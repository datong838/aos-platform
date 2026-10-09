"""Owned new bounded lab on an already-running VM; preserves every old resource."""
import hashlib,json,os,secrets,socket,subprocess,tempfile,time
from pathlib import Path
from datetime import datetime,timezone
import psycopg

R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
CTX='desktop-linux';D=['docker','--context',CTX]
NAME='aos-source-desktop-shm-20261009';VOL=NAME+'-data'
IMAGE='sha256:1a726528ec4ec3dfebf104148d3c6ae329828bfd228c305bb3e0e1e582ee074b'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip().startswith('007902dbf')
def call(args):return subprocess.check_output(args,text=True).strip()
states=json.loads(call(D+['inspect']+call(D+['ps','-aq']).splitlines()))
before=[{'Id':x['Id'],'name':x['Name'],'started':x['State']['StartedAt'],'mounts':x['Mounts'],'ports':x['HostConfig']['PortBindings']} for x in states]
assert not call(D+['ps','-a','--filter','name=^/'+NAME+'$','--format','{{.ID}}'])
assert VOL not in call(D+['volume','ls','-q']).splitlines()
with socket.socket() as p:p.bind(('127.0.0.1',5441))
storage=(B/'storage-probe.log').read_text();available_bytes=int(storage.splitlines()[-1].split()[3]);assert available_bytes>30000000000
assert os.statvfs(B).f_bavail*os.statvfs(B).f_frsize>2000000000
(B/'preflight.json').write_text(json.dumps({'available_bytes':available_bytes,'old_containers':before,'image':IMAGE,'port':5441,'new_volume':VOL,'external_mount':'/Volumes/NVME2T','external_docker_location_source':'user statement; protected Docker settings not read','full386_next_not_passed':True},indent=2)+'\n')
attempt={'observed_at':datetime.now(timezone.utc).isoformat(),'name':NAME,'volume':VOL,'context':CTX,'memory':805306368,'no_swap':True,'no_old_resources_modified':True}
with (B/'create-attempt-r2.json').open('x') as f:json.dump(attempt,f,indent=2)
IMAGE='sha256:bcdf34e61bae2345234063d6fa3dd31dbd89b9dd97d9a669b59edc0f1212d883'
assert call(D+['image','inspect',IMAGE,'--format','{{.Id}}'])==IMAGE
assert json.loads((R/'.evidence/gt-source-desktop-native-lab-20261009/image-equivalence.json').read_text())['config_exact']
secret_dir=Path('/Users/ddt/.aos-lab-secrets')/NAME;secret_dir.mkdir(mode=0o700);os.chmod(secret_dir,0o700)
pw=secrets.token_urlsafe(40);secret=secret_dir/'postgres-password';pf=secret_dir/'pgpass'
for path,value in [(secret,pw),(pf,'127.0.0.1:5441:*:aos_app:'+pw+'\n')]:
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,value.encode());os.close(fd)
del pw
assert call(D+['volume','create','--driver','local','--label','aos.scope=test-only','--label','aos.task=gt-source-desktop-shm-lab-20261009',VOL])==VOL
(B/'volume-created.json').write_text(call(D+['volume','inspect',VOL]))
subprocess.run(D+['run','--name',NAME+'-volume-init','--user','0:0','--memory','32m','--memory-swap','32m','--mount','type=volume,src='+VOL+',dst=/newdata','--entrypoint','sh',IMAGE,'-c',f'chown {os.getuid()}:{os.getgid()} /newdata && chmod 0700 /newdata'],check=True,stdout=subprocess.DEVNULL)
identity=call(D+['run','-d','--name',NAME,'--label','aos.scope=test-only','--user',f'{os.getuid()}:{os.getgid()}',
    '--shm-size','256m','--cpus','1','--memory','768m','--memory-swap','768m','--pids-limit','128',
    '--mount','type=volume,src='+VOL+',dst=/var/lib/postgresql/data',
    '--mount',f'type=bind,src={secret},dst=/run/aos-postgres-password,readonly',
    '-e','POSTGRES_USER=aos_app','-e','POSTGRES_DB=aos_meta','-e','POSTGRES_PASSWORD_FILE=/run/aos-postgres-password',
    '-e','POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256','-p','127.0.0.1:5441:5432',IMAGE,'postgres','-c','shared_buffers=16MB','-c','max_connections=30'])
(B/'container-id.json').write_text(json.dumps({'container_id':identity})+'\n')
for _ in range(30):
    try:
        with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname='aos_meta',passfile=str(pf),connect_timeout=1) as c:
            c.execute('SET TRANSACTION READ ONLY');cluster=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0];break
    except psycopg.OperationalError:time.sleep(.5)
else:raise RuntimeError('new lab unavailable; reconcile exact container, do not recreate')
state=json.loads(call(D+['inspect',NAME]))[0];assert state['Id']==identity and state['Image']==IMAGE and state['HostConfig']['Memory']==805306368
after=json.loads(call(D+['inspect']+[x['Id'] for x in before]));assert [{'Id':x['Id'],'name':x['Name'],'started':x['State']['StartedAt'],'mounts':x['Mounts'],'ports':x['HostConfig']['PortBindings']} for x in after]==before
lab={'name':NAME,'context':CTX,'container_id':identity,'image':IMAGE,'cluster':cluster,'port':5441,'volume':VOL,'passfile':str(pf),'memory_bytes':805306368,'old_resources_unchanged':True,'shm_bytes':268435456,'volume_options':{},'external_mount':'/Volumes/NVME2T'}
(B/'lab.json').write_text(json.dumps(lab,indent=2)+'\n');print(json.dumps({'name':NAME,'cluster':cluster,'port':5441,'old_resources_unchanged':True}))

for ctx,items in json.loads((B/'resource-baseline.json').read_text()).items():
 for item in items:
  now=json.loads(call(['docker','--context',ctx,'inspect',item['Id']]))[0]
  assert now['State']['StartedAt']==item['started'] and now['Mounts']==item['mounts'] and now['HostConfig']['PortBindings']==item['ports']
print('All pre-existing resources on both engines unchanged')
