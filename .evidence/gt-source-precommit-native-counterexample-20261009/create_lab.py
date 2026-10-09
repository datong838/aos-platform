import hashlib,json,os,secrets,socket,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
import psycopg
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
D=['docker','--context','desktop-linux'];N='aos-precommit-probe-20261009';V=N+'-data'
def call(args):return subprocess.check_output(args,text=True).strip()
assert call(['git','rev-parse','HEAD']).startswith('701f2d13e')
assert not call(D+['ps','-aq','--filter','name=^/'+N+'$']) and V not in call(D+['volume','ls','-q']).splitlines()
with socket.socket() as probe:probe.bind(('127.0.0.1',5442))
baseline={}
for ctx in ('desktop-linux','colima-aos-a0v-test-only'):
    ids=call(['docker','--context',ctx,'ps','-aq']).splitlines()
    states=json.loads(call(['docker','--context',ctx,'inspect',*ids])) if ids else []
    baseline[ctx]=[dict(Id=x['Id'],started=x['State']['StartedAt'],mounts=x['Mounts'],ports=x['HostConfig']['PortBindings']) for x in states]
(B/'resource-baseline.json').write_text(json.dumps(baseline,indent=2))
assert (B/'build-attempt.json').exists() and not (B/'image-id.txt').exists()
assert not (Path('/Users/ddt/.aos-lab-secrets')/N).exists()
base='sha256:bcdf34e61bae2345234063d6fa3dd31dbd89b9dd97d9a669b59edc0f1212d883'
tag=N+'-base:exact'
assert call(D+['image','inspect',base,'--format','{{.Id}}'])==base
subprocess.run(D+['image','tag',base,tag],check=True)
assert call(D+['image','inspect',tag,'--format','{{.Id}}'])==base
with (B/'build-attempt-r2.json').open('x') as f:json.dump(dict(observed_at=datetime.now(timezone.utc).isoformat(),prior_build_known_exit=1,no_prior_lab_effect=True,base_image=base,base_tag=tag,dockerfile_sha256=hashlib.sha256((B/'Dockerfile').read_bytes()).hexdigest(),c_sha256=hashlib.sha256((B/'probe.c').read_bytes()).hexdigest(),only_new_test_image=True),f)
subprocess.run(D+['build','--progress','plain','--iidfile',str(B/'image-id.txt'),'-f',str(B/'Dockerfile'),str(B)],check=True)
image=(B/'image-id.txt').read_text().strip();assert call(D+['image','inspect',image,'--format','{{.Id}}'])==image
secret_dir=Path('/Users/ddt/.aos-lab-secrets')/N;secret_dir.mkdir(mode=0o700);os.chmod(secret_dir,0o700)
pw=secrets.token_urlsafe(40);secret=secret_dir/'postgres-password';pf=secret_dir/'pgpass'
for path,value in ((secret,pw),(pf,'127.0.0.1:5442:*:aos_app:'+pw+'\n')):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,value.encode());os.close(fd)
del pw
with (B/'create-attempt.json').open('x') as f:json.dump(dict(name=N,volume=V,image=image,shm_bytes=268435456,memory_bytes=805306368,nocopy=True),f)
assert call(D+['volume','create','--label','aos.scope=test-only','--label','aos.task='+B.name,V])==V
subprocess.run(D+['run','--name',N+'-volume-init','--network','none','--user','0:0','--memory','32m','--memory-swap','32m','--mount','type=volume,src='+V+',dst=/newdata,volume-nocopy','--entrypoint','sh',image,'-c',f'test ! -e /newdata/PG_VERSION && test -z "$(ls -A /newdata)" && chown {os.getuid()}:{os.getgid()} /newdata && chmod 0700 /newdata'],check=True)
identity=call(D+['run','-d','--name',N,'--label','aos.scope=test-only','--user',f'{os.getuid()}:{os.getgid()}','--shm-size','256m','--cpus','1','--memory','768m','--memory-swap','768m','--pids-limit','128','--mount','type=volume,src='+V+',dst=/var/lib/postgresql/data,volume-nocopy','--mount',f'type=bind,src={secret},dst=/run/aos-postgres-password,readonly','-e','POSTGRES_USER=aos_app','-e','POSTGRES_DB=aos_meta','-e','POSTGRES_PASSWORD_FILE=/run/aos-postgres-password','-e','POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256','-p','127.0.0.1:5442:5432',image,'postgres','-c','shared_buffers=16MB','-c','max_connections=30'])
(B/'container-id.json').write_text(json.dumps(dict(container_id=identity)))
for _ in range(40):
    try:
        with psycopg.connect(host='127.0.0.1',port=5442,user='aos_app',dbname='aos_meta',passfile=str(pf),connect_timeout=1) as c:
            c.execute('SET TRANSACTION READ ONLY');cluster=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0];break
    except psycopg.OperationalError:time.sleep(.5)
else:raise RuntimeError('Exact new lab unavailable; reconcile, never recreate unknown')
state=json.loads(call(D+['inspect',N]))[0];assert state['Id']==identity and state['Image']==image
assert state['HostConfig']['Memory']==805306368 and state['HostConfig']['ShmSize']==268435456
volume=json.loads(call(D+['volume','inspect',V]))[0];assert volume['Driver']=='local' and not volume['Options']
lab=dict(name=N,volume=V,context='desktop-linux',image=image,container_id=identity,cluster=cluster,port=5442,passfile=str(pf),memory_bytes=805306368,shm_bytes=268435456)
(B/'lab.json').write_text(json.dumps(lab,indent=2));print(json.dumps({k:lab[k] for k in ('name','cluster','port','image')}))
