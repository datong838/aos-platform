"""New owned native lab: no old resource restart/deletion, no preview writes."""
import hashlib,importlib.util,json,os,secrets,socket,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
import psycopg
E=Path(__file__).resolve().parent;R=E.parents[1];J=E/'reboot-lab-create';J.mkdir(mode=0o700)
NAME='aos-model-native-shm-20261010';VOL=NAME+'-data';IMAGE='sha256:bcdf34e61bae2345234063d6fa3dd31dbd89b9dd97d9a669b59edc0f1212d883';PORT=5442;D=['docker','--context','desktop-linux']
def call(args):return subprocess.check_output(args,text=True).strip()
def save(name,value):
 with os.fdopen(os.open(J/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as out:json.dump(value,out,indent=2);out.flush();os.fsync(out.fileno())
s=importlib.util.spec_from_file_location('model_lab_memory',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks/gt-model-typed-proof-20261008.json').read_text());assert m.load_authority()['project_revision']=='AOS-001701' and t['status']=='ACTIVE' and t['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
assert [x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==t['task_id']]==[t]
assert not call(D+['ps','-a','--filter','name=^/'+NAME+'$','--format','{{.ID}}']) and VOL not in call(D+['volume','ls','-q']).splitlines()
assert call(D+['image','inspect',IMAGE,'--format','{{.Id}}'])==IMAGE
assert int(call(D+['info','--format','{{.MemTotal}}']))>=7*1024**3
assert os.statvfs('/Volumes/NVME2T').f_bavail*os.statvfs('/Volumes/NVME2T').f_frsize>30*1024**3
with socket.socket() as sock:sock.bind(('127.0.0.1',PORT))
def resources():
 result={}
 for ctx in ('desktop-linux','colima-aos-extension'):
  ids=call(['docker','--context',ctx,'ps','-aq']).splitlines()
  result[ctx]=[{'Id':x['Id'],'started':x['State']['StartedAt'],'mounts':x['Mounts'],'ports':x['HostConfig']['PortBindings']} for x in json.loads(call(['docker','--context',ctx,'inspect',*ids]))]
 return result
before=resources();save('intent.json',{'before':before,'name':NAME,'volume':VOL,'image':IMAGE,'port':PORT,'shm':1024**3,'memory':2*1024**3,'no_swap':True,'task':t['task_id']})
secret_dir=Path('/Users/ddt/.aos-lab-secrets')/NAME;secret_dir.mkdir(mode=0o700);secret=secret_dir/'postgres-password';pf=secret_dir/'pgpass';pw=secrets.token_urlsafe(40)
for path,value in ((secret,pw),(pf,f'127.0.0.1:{PORT}:*:aos_app:'+pw+'\n')):
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as out:out.write(value)
del pw
assert call(D+['volume','create','--driver','local','--label','aos.scope=test-only','--label','aos.task='+t['task_id'],VOL])==VOL;save('volume-created.json',json.loads(call(D+['volume','inspect',VOL])))
p=subprocess.run(D+['run','--name',NAME+'-volume-init','--user','0:0','--network','none','--memory','32m','--memory-swap','32m','--mount','type=volume,src='+VOL+',dst=/newdata,volume-nocopy','--entrypoint','sh',IMAGE,'-c',f'test ! -e /newdata/PG_VERSION && test -z "$(ls -A /newdata)" && chown {os.getuid()}:{os.getgid()} /newdata && chmod 0700 /newdata'],capture_output=True);save('init-terminal.json',{'exit':p.returncode});assert p.returncode==0
identity=call(D+['run','-d','--name',NAME,'--label','aos.scope=test-only','--label','aos.task='+t['task_id'],'--user',f'{os.getuid()}:{os.getgid()}','--shm-size','1g','--cpus','1','--memory','2g','--memory-swap','2g','--pids-limit','128','--mount','type=volume,src='+VOL+',dst=/var/lib/postgresql/data,volume-nocopy','--mount',f'type=bind,src={secret},dst=/run/aos-postgres-password,readonly','-e','POSTGRES_USER=aos_app','-e','POSTGRES_DB=aos_meta','-e','POSTGRES_PASSWORD_FILE=/run/aos-postgres-password','-e','POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256','-p',f'127.0.0.1:{PORT}:5432',IMAGE,'postgres','-c','shared_buffers=16MB','-c','max_connections=30']);save('container-created.json',{'id':identity})
for _ in range(40):
 try:
  with psycopg.connect(host='127.0.0.1',port=PORT,user='aos_app',dbname='aos_meta',passfile=str(pf),connect_timeout=1) as c:
   c.read_only=True;cluster=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0];assert c.execute('SELECT current_setting(\'fsync\'),current_setting(\'synchronous_commit\')').fetchone()==('on','on');c.rollback();break
 except psycopg.OperationalError:time.sleep(.5)
else:raise RuntimeError('new lab readiness unknown; reconcile original ID without replay')
x=json.loads(call(D+['inspect',NAME]))[0];assert x['Id']==identity and x['Image']==IMAGE and x['HostConfig']['ShmSize']==1024**3 and x['HostConfig']['Memory']==2*1024**3 and x['HostConfig']['MemorySwap']==2*1024**3
for ctx,entries in before.items():
 after={x['Id']:x for x in resources()[ctx]}
 assert all(after[z['Id']]==z for z in entries)
lab={'context':'desktop-linux','name':NAME,'container_id':identity,'image':IMAGE,'cluster':cluster,'port':PORT,'volume':VOL,'passfile':str(pf),'shm_bytes':1024**3,'memory_bytes':2*1024**3,'original_resources_unchanged':True,'task':t['task_id']};save('terminal.json',lab);(E/'reboot-lab.json').open('x').write(json.dumps(lab,indent=2)+'\n');print(json.dumps({k:lab[k] for k in ('name','container_id','cluster','port','original_resources_unchanged')}))
