from pathlib import Path
import subprocess,json,tarfile,io,hashlib
B=Path(__file__).resolve().parent;old=json.loads((B.parent/'build-dependency-lock-1809/dependency-lock.json').read_text());new=json.loads((B/'extraction.json').read_text());cmd=['docker','--context','desktop-linux']
def snapshot(cid,path):
 raw=subprocess.check_output(cmd+['cp','-L',cid+':'+path,'-']);result={}
 with tarfile.open(fileobj=io.BytesIO(raw)) as t:
  for m in t:
   key=m.name
   assert key not in result
   result[key]={'type':m.type.decode(),'mode':m.mode,'link':m.linkname,'sha256':hashlib.sha256(t.extractfile(m).read()).hexdigest() if m.isfile() else None}
 return result
for r in [old,new]:
 info=json.loads(subprocess.check_output(cmd+['inspect',r['container']],text=True))[0];assert info['Image']==r['image'] and info['State']['Status']=='created'
checks=[]
for path in ['/usr/bin/gcc','/usr/bin/ld','/usr/bin/ar','/usr/include','/usr/local/include']:
 a=snapshot(old['container'],path);b=snapshot(new['container'],path)
 differences=[k for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)]
 checks.append({'path':path,'reference_entries':len(a),'rebuilt_entries':len(b),'differences':differences,'equal':not differences,'reference_manifest_sha256':hashlib.sha256(json.dumps(a,sort_keys=True).encode()).hexdigest(),'rebuilt_manifest_sha256':hashlib.sha256(json.dumps(b,sort_keys=True).encode()).hexdigest()})
result={'checks':checks,'containers_never_started':True,'full_source_build_trust':False,'execution_authorized':False}
(B/'material-result.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert all(r['equal'] for r in checks)
