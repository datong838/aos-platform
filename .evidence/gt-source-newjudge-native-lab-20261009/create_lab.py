"""Owned new bounded lab on an already-running VM; preserves every old resource."""
import hashlib,json,os,secrets,socket,subprocess,tempfile,time
from pathlib import Path
from datetime import datetime,timezone
import psycopg

R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
CTX='colima-aos-extension';D=['docker','--context',CTX]
NAME='aos-source-newjudge-native-20261009';VOL=NAME+'-data'
IMAGE='sha256:a0eb61b312f90f7c5891afc088edc2824ae8eae1dd21ab8ba0e3ef78b1027eb8'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()=='a1a814a45f5840cef235ca3b57bcea08f5f5b5f8'
def call(args):return subprocess.check_output(args,text=True).strip()
states=json.loads(call(D+['inspect']+call(D+['ps','-aq']).splitlines()))
before=[{'Id':x['Id'],'name':x['Name'],'started':x['State']['StartedAt'],'mounts':x['Mounts'],'ports':x['HostConfig']['PortBindings']} for x in states]
assert not call(D+['ps','-a','--filter','name=^/'+NAME+'$','--format','{{.ID}}'])
assert VOL not in call(D+['volume','ls','-q']).splitlines()
with socket.socket() as p:p.bind(('127.0.0.1',5436))
mem=call(['colima','ssh','--profile','aos-extension','--','cat','/proc/meminfo'])
available=int(next(x.split()[1] for x in mem.splitlines() if x.startswith('MemAvailable:')))
assert available>1048576
(B/'preflight.json').write_text(json.dumps({'available_kib':available,'old_containers':before,'image':IMAGE,'port':5436,'new_volume':VOL},indent=2)+'\n')
attempt={'observed_at':datetime.now(timezone.utc).isoformat(),'name':NAME,'volume':VOL,'context':CTX,'memory':805306368,'no_swap':True,'no_old_resources_modified':True}
with (B/'create-attempt.json').open('x') as f:json.dump(attempt,f,indent=2)
if subprocess.run(D+['image','inspect',IMAGE],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
    archive=Path(tempfile.gettempdir())/'aos-source-newjudge-exact-image-20261009.tar'
    assert not archive.exists()
    subprocess.run(['docker','--context','colima-aos-a0v-test-only','save','-o',str(archive),IMAGE],check=True)
    os.chmod(archive,0o600)
    subprocess.run(D+['load','-i',str(archive)],check=True,stdout=subprocess.DEVNULL)
    (B/'image-copy.json').write_text(json.dumps({'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'image':IMAGE,'downloaded':False},indent=2)+'\n')
assert call(D+['image','inspect',IMAGE,'--format','{{.Id}}'])==IMAGE
secret_dir=Path('/Users/ddt/.aos-lab-secrets')/NAME;secret_dir.mkdir(mode=0o700);os.chmod(secret_dir,0o700)
pw=secrets.token_urlsafe(40);secret=secret_dir/'postgres-password';pf=secret_dir/'pgpass'
for path,value in [(secret,pw),(pf,'127.0.0.1:5436:*:aos_app:'+pw+'\n')]:
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,value.encode());os.close(fd)
del pw
assert call(D+['volume','create','--label','aos.scope=test-only','--label','aos.task=gt-source-newjudge-native-lab-20261009',VOL])==VOL
subprocess.run(D+['run','--name',NAME+'-volume-init','--user','0:0','--memory','32m','--memory-swap','32m','--mount','type=volume,src='+VOL+',dst=/newdata','--entrypoint','sh',IMAGE,'-c',f'chown {os.getuid()}:{os.getgid()} /newdata && chmod 0700 /newdata'],check=True,stdout=subprocess.DEVNULL)
identity=call(D+['run','-d','--name',NAME,'--label','aos.scope=test-only','--user',f'{os.getuid()}:{os.getgid()}',
    '--cpus','1','--memory','768m','--memory-swap','768m','--pids-limit','128',
    '--mount','type=volume,src='+VOL+',dst=/var/lib/postgresql/data',
    '--mount',f'type=bind,src={secret},dst=/run/aos-postgres-password,readonly',
    '-e','POSTGRES_USER=aos_app','-e','POSTGRES_DB=aos_meta','-e','POSTGRES_PASSWORD_FILE=/run/aos-postgres-password',
    '-e','POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256','-p','127.0.0.1:5436:5432',IMAGE,'postgres','-c','shared_buffers=16MB','-c','max_connections=30'])
(B/'container-id.json').write_text(json.dumps({'container_id':identity})+'\n')
for _ in range(30):
    try:
        with psycopg.connect(host='127.0.0.1',port=5436,user='aos_app',dbname='aos_meta',passfile=str(pf),connect_timeout=1) as c:
            c.execute('SET TRANSACTION READ ONLY');cluster=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0];break
    except psycopg.OperationalError:time.sleep(.5)
else:raise RuntimeError('new lab unavailable; reconcile exact container, do not recreate')
state=json.loads(call(D+['inspect',NAME]))[0];assert state['Id']==identity and state['Image']==IMAGE and state['HostConfig']['Memory']==805306368
after=json.loads(call(D+['inspect']+[x['Id'] for x in before]));assert [{'Id':x['Id'],'name':x['Name'],'started':x['State']['StartedAt'],'mounts':x['Mounts'],'ports':x['HostConfig']['PortBindings']} for x in after]==before
lab={'name':NAME,'context':CTX,'container_id':identity,'image':IMAGE,'cluster':cluster,'port':5436,'volume':VOL,'passfile':str(pf),'memory_bytes':805306368,'old_resources_unchanged':True}
(B/'lab.json').write_text(json.dumps(lab,indent=2)+'\n');print(json.dumps({'name':NAME,'cluster':cluster,'port':5436,'old_resources_unchanged':True}))
