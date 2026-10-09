import json,subprocess,os,time
from pathlib import Path
import psycopg
B=Path(__file__).resolve().parent;D=['docker','--context','desktop-linux'];NAME='aos-source-desktop-shm-20261009';VOL=NAME+'-data';IMAGE='sha256:bcdf34e61bae2345234063d6fa3dd31dbd89b9dd97d9a669b59edc0f1212d883'
SECRET=Path('/Users/ddt/.aos-lab-secrets')/NAME/'postgres-password';PF=SECRET.parent/'pgpass'
def call(a):return subprocess.check_output(a,text=True).strip()
old=json.loads(call(D+['inspect',NAME]))[0];assert old['Id']=='52219392c3e9176ebf3c8913131c2622097cf0f99a2eb1728d4cb5a1045a983e' and not old['State']['Running'] and old['State']['ExitCode']==1
probe=json.loads(call(D+['inspect',NAME+'-volume-audit-r3']))[0];assert probe['State']['ExitCode']==0
with (B/'recover-attempt-r3.json').open('x') as f:json.dump(dict(failed_id=old['Id'],failure_terminal=True,empty_uninitialized_volume_readonly_verified=True,old_secret_not_read=True,new_pg_mount_nocopy=True),f)
subprocess.run(D+['rename',NAME,NAME+'-failed-r2'],check=True)
subprocess.run(D+['run','--name',NAME+'-volume-init-r3','--label','aos.scope=test-only','--user','0:0','--memory','32m','--memory-swap','32m','--network','none','--mount','type=volume,src='+VOL+',dst=/newdata,volume-nocopy','--entrypoint','sh',IMAGE,'-c',f'test ! -e /newdata/PG_VERSION && test -z "$(ls -A /newdata)" && chown {os.getuid()}:{os.getgid()} /newdata && chmod 0700 /newdata'],check=True)
identity=call(D+['run','-d','--name',NAME,'--label','aos.scope=test-only','--user',f'{os.getuid()}:{os.getgid()}', '--shm-size','256m','--cpus','1','--memory','768m','--memory-swap','768m','--pids-limit','128','--mount','type=volume,src='+VOL+',dst=/var/lib/postgresql/data,volume-nocopy','--mount',f'type=bind,src={SECRET},dst=/run/aos-postgres-password,readonly','-e','POSTGRES_USER=aos_app','-e','POSTGRES_DB=aos_meta','-e','POSTGRES_PASSWORD_FILE=/run/aos-postgres-password','-e','POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256','-p','127.0.0.1:5441:5432',IMAGE,'postgres','-c','shared_buffers=16MB','-c','max_connections=30'])
(B/'container-id-r3.json').write_text(json.dumps(dict(container_id=identity)))
for _ in range(40):
 try:
  with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname='aos_meta',passfile=str(PF),connect_timeout=1) as c:
   c.execute('SET TRANSACTION READ ONLY');cluster=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0];break
 except psycopg.OperationalError:time.sleep(.5)
else:raise RuntimeError('exact new container unavailable; readonly reconcile, never re-create unknown')
state=json.loads(call(D+['inspect',NAME]))[0];assert state['Id']==identity and state['Image']==IMAGE and state['HostConfig']['Memory']==805306368
for ctx,items in json.loads((B/'resource-baseline.json').read_text()).items():
 for item in items:
  now=json.loads(call(['docker','--context',ctx,'inspect',item['Id']]))[0];assert now['State']['StartedAt']==item['started'] and sorted(now['Mounts'],key=lambda x:json.dumps(x,sort_keys=True))==sorted(item['mounts'],key=lambda x:json.dumps(x,sort_keys=True)) and now['HostConfig']['PortBindings']==item['ports']
lab=dict(name=NAME,context='desktop-linux',container_id=identity,image=IMAGE,source_image_config='sha256:1a726528ec4ec3dfebf104148d3c6ae329828bfd228c305bb3e0e1e582ee074b',cluster=cluster,port=5441,volume=VOL,passfile=str(PF),memory_bytes=805306368,shm_bytes=268435456,old_resources_unchanged=True,volume_options={},external_mount='/Volumes/NVME2T')
(B/'lab.json').write_text(json.dumps(lab,indent=2));print(json.dumps(dict(name=NAME,cluster=cluster,port=5441,all_previous_resources_unchanged=True)))
