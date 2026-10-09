import json,os,subprocess,time
from pathlib import Path
import psycopg
B=Path(__file__).resolve().parent;D=['docker','--context','colima-aos-extension'];CTX='colima-aos-extension'
NAME='aos-source-root-native-20261009';VOL=NAME+'-data';IMAGE='sha256:1a726528ec4ec3dfebf104148d3c6ae329828bfd228c305bb3e0e1e582ee074b'
secret=Path('/Users/ddt/.aos-lab-secrets')/NAME/'postgres-password';pf=secret.parent/'pgpass'
def call(args):return subprocess.check_output(args,text=True).strip()
assert not call(D+['ps','-a','--filter','name=^/'+NAME+'$','--format','{{.ID}}'])
assert json.loads(call(D+['inspect',NAME+'-volume-init']))[0]['State']['ExitCode']==0
assert secret.stat().st_mode&0o077==0 and pf.stat().st_mode&0o077==0
before=json.loads((B/'preflight.json').read_text())['old_containers']
with (B/'create-file-copy-attempt.json').open('x') as f:json.dump({'cause':'VM does not mount private host directory','method':'copy private0600 file into first stopped owned container, then start','never_plaintext_env_or_args':True},f)
identity=call(D+['create','--name',NAME,'--label','aos.scope=test-only','--user',f'{os.getuid()}:{os.getgid()}',
    '--cpus','1','--memory','768m','--memory-swap','768m','--pids-limit','128',
    '--mount','type=volume,src='+VOL+',dst=/var/lib/postgresql/data',
    '-e','POSTGRES_USER=aos_app','-e','POSTGRES_DB=aos_meta','-e','POSTGRES_PASSWORD_FILE=/run/aos-postgres-password',
    '-e','POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256','-p','127.0.0.1:5437:5432',IMAGE,'postgres','-c','shared_buffers=16MB','-c','max_connections=30'])
subprocess.run(D+['cp',str(secret),identity+':/run/aos-postgres-password'],check=True)
subprocess.run(D+['start',identity],check=True,stdout=subprocess.DEVNULL)
(B/'container-id.json').write_text(json.dumps({'container_id':identity})+'\n')
for _ in range(30):
    try:
        with psycopg.connect(host='127.0.0.1',port=5437,user='aos_app',dbname='aos_meta',passfile=str(pf),connect_timeout=1) as c:
            c.execute('SET TRANSACTION READ ONLY');cluster=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0];break
    except psycopg.OperationalError:time.sleep(.5)
else:raise RuntimeError('new lab unavailable; reconcile exact container, do not recreate')
state=json.loads(call(D+['inspect',NAME]))[0];assert state['Id']==identity and state['Image']==IMAGE and state['HostConfig']['Memory']==805306368
after=json.loads(call(D+['inspect']+[x['Id'] for x in before]));assert [{'Id':x['Id'],'name':x['Name'],'started':x['State']['StartedAt'],'mounts':x['Mounts'],'ports':x['HostConfig']['PortBindings']} for x in after]==before
lab={'name':NAME,'context':CTX,'container_id':identity,'image':IMAGE,'cluster':cluster,'port':5437,'volume':VOL,'passfile':str(pf),'memory_bytes':805306368,'old_resources_unchanged':True,'root_directory':'/var/lib/aos-test-labs/'+NAME}
(B/'lab.json').write_text(json.dumps(lab,indent=2)+'\n');print(json.dumps({'name':NAME,'cluster':cluster,'port':5437,'old_resources_unchanged':True}))
