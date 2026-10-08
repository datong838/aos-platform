import os,json,secrets,subprocess,sys,importlib.util,socket,time
from pathlib import Path
from datetime import datetime,timezone
import psycopg
REPO=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;NAME='aos-native-joint-memory-20261009';IMAGE='sha256:a0eb61b312f90f7c5891afc088edc2824ae8eae1dd21ab8ba0e3ef78b1027eb8';PREFIX=['docker','--context','colima-aos-a0v-test-only']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()=='986bf81ea5bac9169f066266677d9a5cb0a30112'
s=importlib.util.spec_from_file_location('mc',REPO/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m);assert m.load_authority()['project_revision']=='AOS-001596'
t=m.read_json(m.DEFAULT_PATHS.receipts_path/'tasks'/'gt-native-joint-fresh-lab-20261009.json');assert [x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x.get('task_id')==t['task_id']]==[t];assert datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
assert not subprocess.check_output(PREFIX+['ps','-a','--filter','name=^/'+NAME+'$','--format','{{.ID}}'],text=True).strip()
with socket.socket() as probe:probe.bind(('127.0.0.1',5435))
mem=subprocess.check_output(PREFIX+['exec','aos-capacity-publication-scram-20261006','cat','/proc/meminfo'],text=True);available=int(next(x.split()[1] for x in mem.splitlines() if x.startswith('MemAvailable:')));assert available>768*1024
secret_dir=Path('/Users/ddt/.aos-lab-secrets')/NAME;assert not secret_dir.exists();secret_dir.mkdir(parents=True,mode=0o700);os.chmod(secret_dir,0o700)
pw=secrets.token_urlsafe(40);secret=secret_dir/'postgres-password';fd=os.open(secret,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,pw.encode());os.close(fd)
passfile=secret_dir/'pgpass';fd=os.open(passfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,('127.0.0.1:5435:*:aos_app:'+pw+'\n').encode());os.close(fd);del pw
with (OUT/'create-attempt.json').open('x') as h:json.dump({'name':NAME,'image':IMAGE,'port':5435,'data':'separate tmpfs256MiB','memory_limit':'384MiB','secret_not_in_evidence':True},h)
cmd=PREFIX+['run','-d','--name',NAME,'--user',f'{os.getuid()}:{os.getgid()}','--memory','384m','--memory-swap','384m','--pids-limit','128','--tmpfs',f'/var/lib/postgresql/data:rw,size=256m,uid={os.getuid()},gid={os.getgid()},mode=0700','--mount',f'type=bind,src={secret},dst=/run/aos-postgres-password,readonly','-e','POSTGRES_USER=aos_app','-e','POSTGRES_DB=aos_meta','-e','POSTGRES_PASSWORD_FILE=/run/aos-postgres-password','-e','POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256','-p','127.0.0.1:5435:5432',IMAGE,'postgres','-c','shared_buffers=16MB','-c','max_connections=30']
r=subprocess.run(cmd,text=True,capture_output=True);assert r.returncode==0,r.stderr
identity=r.stdout.strip();(OUT/'container-id.json').write_text(json.dumps({'container_id':identity,'name':NAME})+'\n')
healthy=False
for _ in range(30):
 try:
  with psycopg.connect(host='127.0.0.1',port=5435,user='aos_app',dbname='aos_meta',passfile=str(passfile),connect_timeout=1) as c:
   c.execute('SET TRANSACTION READ ONLY');cluster=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0];version=c.execute('SHOW server_version').fetchone()[0];healthy=True;break
 except psycopg.OperationalError:time.sleep(.5)
assert healthy,'new test lab health failed, inspect same container; no repeat run'
state=json.loads(subprocess.check_output(PREFIX+['inspect',NAME],text=True))[0];assert state['Id']==identity and state['State']['Running'] and state['HostConfig']['Memory']==384*1024*1024
assert '/var/lib/postgresql/data' in state['HostConfig']['Tmpfs'];assert cluster!='7693564235776004128'
result={'name':NAME,'container_id':identity,'image':state['Image'],'port':5435,'cluster':cluster,'server_version':version,'data_tmpfs':state['HostConfig']['Tmpfs'],'memory_bytes':state['HostConfig']['Memory'],'passfile':str(passfile),'existing_lab_and_formal_untouched':True,'ephemeral_only':True,'observed_at':datetime.now(timezone.utc).isoformat()};(OUT/'lab.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
