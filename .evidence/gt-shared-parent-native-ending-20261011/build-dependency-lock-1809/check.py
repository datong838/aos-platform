from pathlib import Path
import hashlib,json,subprocess,uuid
B=Path(__file__).resolve().parent
sdk=json.loads((B.parent/'pg-linker-probe-1779/sdk-image.json').read_text())['image']
def docker(*args):return subprocess.check_output(['docker','--context','desktop-linux',*args],text=True).strip()
assert json.loads(docker('image','inspect',sdk))[0]['Id']==sdk
name='aos-sdk-lock-'+uuid.uuid4().hex
(B/'intent.json').open('x').write(json.dumps({'image':sdk,'name':name,'never_start':True}))
cid=docker('create','--name',name,'--network','none',sdk,'/never-start')
for source,target in [('/lib/apk/db/installed','installed.txt'),('/etc/apk/repositories','repositories.txt')]:
 docker('cp',cid+':'+source,str(B/target))
raw=(B/'installed.txt').read_bytes(); packages=[];seen=set()
for block in raw.decode().split('\n\n'):
 fields={}
 for line in block.splitlines():
  if len(line)>2 and line[1]==':' and line[0] in 'PVACo':
   assert line[0] not in fields
   fields[line[0]]=line[2:]
 if not fields:continue
 assert all(fields.get(k) for k in 'PVAC')
 assert fields['P'] not in seen;seen.add(fields['P'])
 packages.append({'name':fields['P'],'version':fields['V'],'architecture':fields['A'],'apk_checksum':fields['C'],'origin':fields.get('o')})
assert packages
info=json.loads(docker('inspect',cid))[0]
assert info['State']['Status']=='created' and info['State']['Pid']==0 and info['Image']==sdk
result={'image':sdk,'container':cid,'never_started':True,'mounts':info['Mounts'],'installed_database_sha256':hashlib.sha256(raw).hexdigest(),'repository_configuration_sha256':hashlib.sha256((B/'repositories.txt').read_bytes()).hexdigest(),'packages':sorted(packages,key=lambda p:p['name']),'package_count':len(packages),'independent_package_signatures_verified':False,'historical_source_build_trust':False,'execution_authorized':False}
(B/'dependency-lock.json').open('x').write(json.dumps(result,indent=2)+'\n')
print(json.dumps({'packages':len(packages),'never_started':True,'mount_count':len(info['Mounts']),'signed_trust':False}))
