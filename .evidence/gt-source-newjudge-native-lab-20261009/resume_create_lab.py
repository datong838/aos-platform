import hashlib,json,os,secrets,socket,subprocess,time,tarfile
from pathlib import Path
import psycopg
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
CTX='colima-aos-extension';D=['docker','--context',CTX]
NAME='aos-source-newjudge-native-20261009';VOL=NAME+'-data'
def call(args):return subprocess.check_output(args,text=True).strip()
copy=json.loads((B/'image-copy.json').read_text());archive=Path(copy['archive'])
assert hashlib.sha256(archive.read_bytes()).hexdigest()==copy['sha256']
with tarfile.open(archive) as tar:
 index=json.load(tar.extractfile('index.json'));assert index['manifests'][0]['digest']==copy['image']
 manifest_bytes=tar.extractfile('blobs/sha256/'+copy['image'].split(':')[1]).read();assert 'sha256:'+hashlib.sha256(manifest_bytes).hexdigest()==copy['image']
 manifest=json.loads(manifest_bytes);IMAGE=manifest['config']['digest']
 config_bytes=tar.extractfile('blobs/sha256/'+IMAGE.split(':')[1]).read();assert 'sha256:'+hashlib.sha256(config_bytes).hexdigest()==IMAGE
 config=json.loads(config_bytes)
 imported=json.loads(call(D+['image','inspect',IMAGE]))[0]
 assert imported['Id']==IMAGE and imported['RootFS']['Layers']==config['rootfs']['diff_ids']
 assert imported['Config']==config['config']
 source=json.loads(call(['docker','--context','colima-aos-a0v-test-only','image','inspect',copy['image']]))[0]
 assert source['RootFS']==imported['RootFS'] and source['Config']==imported['Config'] and source['Architecture']==imported['Architecture']
before=json.loads((B/'preflight.json').read_text())['old_containers']
assert not call(D+['ps','-a','--filter','name=^/'+NAME+'$','--format','{{.ID}}'])
assert VOL not in call(D+['volume','ls','-q']).splitlines()
assert not (Path('/Users/ddt/.aos-lab-secrets')/NAME).exists()
with socket.socket() as p:p.bind(('127.0.0.1',5436))
(B/'image-provenance-reconciliation.json').write_text(json.dumps({'source_oci_manifest':copy['image'],'loaded_docker_config':IMAGE,'archive_sha256':copy['sha256'],'config_and_rootfs_exact':True,'original_load_effect_reconciled':True,'no_volume_container_or_secret_before_resume':True},indent=2)+'\n')
with (B/'create-resume-attempt.json').open('x') as f:json.dump({'phase':'first volume and credential creation','image':IMAGE,'no_repeated_image_load':True},f)
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
