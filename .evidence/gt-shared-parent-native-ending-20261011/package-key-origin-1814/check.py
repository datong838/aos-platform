from pathlib import Path
import json,subprocess,tarfile,io,urllib.request,hashlib,datetime
B=Path(__file__).resolve().parent;lock=json.loads((B.parent/'build-dependency-lock-1809/dependency-lock.json').read_text())
cmd=['docker','--context','desktop-linux'];info=json.loads(subprocess.check_output(cmd+['inspect',lock['container']],text=True))[0];assert info['Image']==lock['image'] and info['State']['Status']=='created'
raw=subprocess.check_output(cmd+['cp',lock['container']+':/etc/apk/keys','-']);rows=[]
with tarfile.open(fileobj=io.BytesIO(raw)) as t:
 members=[m for m in t.getmembers() if m.isfile()];assert len(members)==2
 for m in members:
  name=Path(m.name).name;assert name in ['alpine-devel@lists.alpinelinux.org-58199dcc.rsa.pub','alpine-devel@lists.alpinelinux.org-616ae350.rsa.pub']
  local=t.extractfile(m).read();url='https://alpinelinux.org/keys/'+name
  with urllib.request.urlopen(url,timeout=20) as response:
   assert response.status==200 and response.geturl()==url
   official=response.read(8193)
  assert len(official)<=8192 and official==local
  rows.append({'name':name,'url':url,'sha256':hashlib.sha256(local).hexdigest(),'size':len(local),'official_https_bytes_equal':True})
r={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image':lock['image'],'container_never_started':True,'keys':rows,'aos_native_root_authorized':False,'whole_source_build_proven':False}
(B/'result.json').open('x').write(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
