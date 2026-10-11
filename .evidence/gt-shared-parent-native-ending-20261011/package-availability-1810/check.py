import concurrent.futures,json,urllib.request,urllib.error,time
from pathlib import Path
B=Path(__file__).resolve().parent
lock=json.loads((B.parent/'build-dependency-lock-1809/dependency-lock.json').read_text())
repos=(B.parent/'build-dependency-lock-1809/repositories.txt').read_text().splitlines()
assert len(repos)==2 and all(x.startswith('https://dl-cdn.alpinelinux.org/alpine/v3.24/') for x in repos)
def check(p):
 results=[]
 for repo in repos:
  url=repo+'/'+p['architecture']+'/'+p['name']+'-'+p['version']+'.apk'
  try:
   with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=15) as r:results.append({'url':url,'status':r.status,'length':r.headers.get('Content-Length')})
  except urllib.error.HTTPError as e:results.append({'url':url,'status':e.code})
  except Exception as e:results.append({'url':url,'error_type':type(e).__name__})
  if results[-1].get('status')==200:break
 return {'name':p['name'],'version':p['version'],'checks':results,'available':any(x.get('status')==200 for x in results)}
start=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:rows=list(pool.map(check,lock['packages']))
r={'image':lock['image'],'packages':rows,'available':sum(x['available'] for x in rows),'total':len(rows),'elapsed_seconds':round(time.monotonic()-start,2),'signatures_verified':False,'downloads_or_installs':False}
(B/'result.json').open('x').write(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='packages'}))
