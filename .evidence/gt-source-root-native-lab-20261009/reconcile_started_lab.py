import json,subprocess,time
from pathlib import Path
import psycopg
B=Path(__file__).resolve().parent;D=['docker','--context','colima-aos-extension'];CTX='colima-aos-extension';NAME='aos-source-root-native-20261009';VOL=NAME+'-data';IMAGE='sha256:1a726528ec4ec3dfebf104148d3c6ae329828bfd228c305bb3e0e1e582ee074b';identity='8384eef7b29dabf3629ba31c8ab18beab011a2f86cddffe96c0907be73024ec5';pf=Path('/Users/ddt/.aos-lab-secrets')/NAME/'pgpass'
def call(args):return subprocess.check_output(args,text=True).strip()
before=json.loads((B/'preflight.json').read_text())['old_containers']
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
