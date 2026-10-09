"""Owned new bounded lab on an already-running VM; preserves every old resource."""
import hashlib,json,os,secrets,socket,subprocess,tempfile,time
from pathlib import Path
from datetime import datetime,timezone
import psycopg

R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
CTX='colima-aos-extension';D=['docker','--context',CTX]
NAME='aos-source-root-native-20261009';VOL=NAME+'-data'
IMAGE='sha256:1a726528ec4ec3dfebf104148d3c6ae329828bfd228c305bb3e0e1e582ee074b'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()=='455b74ea10487e5fa1be0392d14ef6ef4499cb9c'
def call(args):return subprocess.check_output(args,text=True).strip()
states=json.loads(call(D+['inspect']+call(D+['ps','-aq']).splitlines()))
before=[{'Id':x['Id'],'name':x['Name'],'started':x['State']['StartedAt'],'mounts':x['Mounts'],'ports':x['HostConfig']['PortBindings']} for x in states]
assert not call(D+['ps','-a','--filter','name=^/'+NAME+'$','--format','{{.ID}}'])
assert VOL not in call(D+['volume','ls','-q']).splitlines()
with socket.socket() as p:p.bind(('127.0.0.1',5437))
mem=call(['colima','ssh','--profile','aos-extension','--','cat','/proc/meminfo'])
available=int(next(x.split()[1] for x in mem.splitlines() if x.startswith('MemAvailable:')))
assert available>1048576
(B/'preflight.json').write_text(json.dumps({'available_kib':available,'old_containers':before,'image':IMAGE,'port':5437,'new_volume':VOL},indent=2)+'\n')
attempt={'observed_at':datetime.now(timezone.utc).isoformat(),'name':NAME,'volume':VOL,'context':CTX,'memory':805306368,'no_swap':True,'no_old_resources_modified':True}
with (B/'create-attempt.json').open('x') as f:json.dump(attempt,f,indent=2)
assert call(D+['image','inspect',IMAGE,'--format','{{.Id}}'])==IMAGE
secret_dir=Path('/Users/ddt/.aos-lab-secrets')/NAME;secret_dir.mkdir(mode=0o700);os.chmod(secret_dir,0o700)
pw=secrets.token_urlsafe(40);secret=secret_dir/'postgres-password';pf=secret_dir/'pgpass'
for path,value in [(secret,pw),(pf,'127.0.0.1:5437:*:aos_app:'+pw+'\n')]:
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,value.encode());os.close(fd)
del pw
root_dir='/var/lib/aos-test-labs/'+NAME
assert subprocess.run(['colima','ssh','--profile','aos-extension','--','sudo','test','-e',root_dir]).returncode==1
root_free=int(call(['colima','ssh','--profile','aos-extension','--','df','-P','-B1','/var/tmp']).splitlines()[-1].split()[3]);assert root_free>5000000000
subprocess.run(['colima','ssh','--profile','aos-extension','--','sudo','install','-d','-m','0700','-o','100000','-g','100000',root_dir],check=True)
(B/'root-directory-created.json').write_text(json.dumps({'path':root_dir,'free_before':root_free,'original_data_volume_unchanged':True}))
assert call(D+['volume','create','--driver','local','--opt','type=none','--opt','o=bind','--opt','device='+root_dir,'--label','aos.scope=test-only','--label','aos.task=gt-source-root-native-lab-20261009',VOL])==VOL
(B/'volume-created.json').write_text(call(D+['volume','inspect',VOL]))
subprocess.run(D+['run','--name',NAME+'-volume-init','--user','0:0','--memory','32m','--memory-swap','32m','--mount','type=volume,src='+VOL+',dst=/newdata','--entrypoint','sh',IMAGE,'-c',f'chown {os.getuid()}:{os.getgid()} /newdata && chmod 0700 /newdata'],check=True,stdout=subprocess.DEVNULL)
identity=call(D+['run','-d','--name',NAME,'--label','aos.scope=test-only','--user',f'{os.getuid()}:{os.getgid()}',
    '--cpus','1','--memory','768m','--memory-swap','768m','--pids-limit','128',
    '--mount','type=volume,src='+VOL+',dst=/var/lib/postgresql/data',
    '--mount',f'type=bind,src={secret},dst=/run/aos-postgres-password,readonly',
    '-e','POSTGRES_USER=aos_app','-e','POSTGRES_DB=aos_meta','-e','POSTGRES_PASSWORD_FILE=/run/aos-postgres-password',
    '-e','POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256','-p','127.0.0.1:5437:5432',IMAGE,'postgres','-c','shared_buffers=16MB','-c','max_connections=30'])
(B/'container-id.json').write_text(json.dumps({'container_id':identity})+'\n')
for _ in range(30):
    try:
        with psycopg.connect(host='127.0.0.1',port=5437,user='aos_app',dbname='aos_meta',passfile=str(pf),connect_timeout=1) as c:
            c.execute('SET TRANSACTION READ ONLY');cluster=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0];break
    except psycopg.OperationalError:time.sleep(.5)
else:raise RuntimeError('new lab unavailable; reconcile exact container, do not recreate')
state=json.loads(call(D+['inspect',NAME]))[0];assert state['Id']==identity and state['Image']==IMAGE and state['HostConfig']['Memory']==805306368
after=json.loads(call(D+['inspect']+[x['Id'] for x in before]));assert [{'Id':x['Id'],'name':x['Name'],'started':x['State']['StartedAt'],'mounts':x['Mounts'],'ports':x['HostConfig']['PortBindings']} for x in after]==before
lab={'name':NAME,'context':CTX,'container_id':identity,'image':IMAGE,'cluster':cluster,'port':5437,'volume':VOL,'passfile':str(pf),'memory_bytes':805306368,'old_resources_unchanged':True,'root_directory':root_dir}
(B/'lab.json').write_text(json.dumps(lab,indent=2)+'\n');print(json.dumps({'name':NAME,'cluster':cluster,'port':5437,'old_resources_unchanged':True}))
