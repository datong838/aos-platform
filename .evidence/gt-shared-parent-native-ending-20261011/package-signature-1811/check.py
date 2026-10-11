import json,hashlib,subprocess,urllib.request,uuid
from pathlib import Path
B=Path(__file__).resolve().parent
lock=json.loads((B.parent/'build-dependency-lock-1809/dependency-lock.json').read_text());av=json.loads((B.parent/'package-availability-1810/result.json').read_text());p=next(p for p in av['packages'] if p['name']=='binutils');url=next(x['url'] for x in p['checks'] if x.get('status')==200)
with urllib.request.urlopen(url,timeout=30) as response:raw=response.read(8*1024*1024+1)
assert 0<len(raw)<=8*1024*1024
(B/'original.apk').open('xb').write(raw);bad=raw[:-1]+bytes([raw[-1]^1]);(B/'tampered.apk').open('xb').write(bad)
def docker(*args):return subprocess.check_output(['docker','--context','desktop-linux',*args],text=True).strip()
assert json.loads(docker('image','inspect',lock['image']))[0]['Id']==lock['image']
results=[]
for case in ['original','tampered']:
 name='aos-apk-verify-'+uuid.uuid4().hex
 (B/(case+'-intent.json')).open('x').write(json.dumps({'name':name,'image':lock['image'],'entrypoint':'/sbin/apk','arguments':['verify','/tmp/input.apk']}))
 cid=docker('create','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','/sbin/apk',lock['image'],'verify','/tmp/input.apk')
 docker('cp',str(B/(case+'.apk')),cid+':/tmp/input.apk')
 process=subprocess.run(['docker','--context','desktop-linux','start','-a',cid],text=True,capture_output=True,timeout=30)
 info=json.loads(docker('inspect',cid))[0]
 assert info['State']['Status']=='exited' and info['Config']['Entrypoint']==['/sbin/apk']
 results.append({'case':case,'container':cid,'exit_code':info['State']['ExitCode'],'stdout':process.stdout,'stderr':process.stderr,'readonly':info['HostConfig']['ReadonlyRootfs'],'network':info['HostConfig']['NetworkMode'],'mounts':info['Mounts']})
r={'package':p['name'],'version':p['version'],'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'cases':results,'independent_key_trust':False,'execution_authorized':False}
(B/'result.json').open('x').write(json.dumps(r,indent=2)+'\n')
print(json.dumps(r))
assert results[0]['exit_code']==0 and results[1]['exit_code']!=0
