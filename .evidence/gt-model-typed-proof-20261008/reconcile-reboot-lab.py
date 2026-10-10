"""Read back already-created lab; never replay any create or init operation."""
import hashlib,json,subprocess,sys
from pathlib import Path
import psycopg
E=Path(__file__).resolve().parent;J=E/'reboot-lab-create';sys.path.insert(0,str(E));from reboot_resource_review import require_same
intent=json.loads((J/'intent.json').read_text());identity=json.loads((J/'container-created.json').read_text())['id'];assert identity=='64350ecc88aa446cc0a5694a3398155f4b123bbe6633d5ab24b84a46fc0de849'
assert json.loads((J/'init-terminal.json').read_text())['exit']==0
for ctx,old in intent['before'].items():
 now={x['Id']:x for x in json.loads(subprocess.check_output(['docker','--context',ctx,'inspect',*[z['Id'] for z in old]],text=True))}
 for before in old:
  x=now[before['Id']];require_same(before,dict(Id=x['Id'],started=x['State']['StartedAt'],mounts=x['Mounts'],ports=x['HostConfig']['PortBindings']))
x=json.loads(subprocess.check_output(['docker','--context','desktop-linux','inspect',identity],text=True))[0];h=x['HostConfig'];assert x['State']['Running'] and x['Image']==intent['image'] and h['ShmSize']==2**30 and h['Memory']==h['MemorySwap']==2**31
assert [z['Name'] for z in x['Mounts'] if z['Type']=='volume']==[intent['volume']]
assert h['PortBindings']=={'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'5442'}]} and x['Config']['Labels']['aos.scope']=='test-only' and x['Config']['Labels']['aos.task']==intent['task']
pf=Path('/Users/ddt/.aos-lab-secrets')/intent['name']/'pgpass';assert pf.stat().st_mode&0o077==0
with psycopg.connect(host='127.0.0.1',port=5442,user='aos_app',dbname='aos_meta',passfile=str(pf)) as c:
 c.read_only=True;cluster=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0];assert cluster not in ('7683855731447750695','7694680278363095064')
 assert c.execute("SELECT current_setting('fsync'),current_setting('synchronous_commit')").fetchone()==('on','on');c.rollback()
lab=dict(context='desktop-linux',name=intent['name'],container_id=identity,image=intent['image'],cluster=cluster,port=5442,volume=intent['volume'],passfile=str(pf),shm_bytes=2**30,memory_bytes=2**31,original_resources_unchanged=True,task=intent['task'])
(J/'reconciled-terminal.json').open('x').write(json.dumps(lab,indent=2)+'\n');(E/'reboot-lab.json').open('x').write(json.dumps(lab,indent=2)+'\n');print(json.dumps({k:lab[k] for k in ('container_id','cluster','original_resources_unchanged')}))
