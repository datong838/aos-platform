from pathlib import Path
import concurrent.futures,urllib.request,json,hashlib,zlib,base64,subprocess,uuid
B=Path(__file__).resolve().parent;N=B.parent;P=B/'packages';P.mkdir()
lock=json.loads((N/'build-dependency-lock-1809/dependency-lock.json').read_text());expected={p['name']:p for p in lock['packages']};av=json.loads((N/'package-availability-1810/result.json').read_text());selected=[p for p in av['packages'] if p['available']]
def fetch(p):
 info=next(x for x in p['checks'] if x.get('status')==200);name=p['name']+'-'+p['version']+'.apk';path=P/name
 try:
  size=0;h=hashlib.sha256()
  with urllib.request.urlopen(info['url'],timeout=60) as response,path.open('xb') as out:
   while True:
    chunk=response.read(1024*1024)
    if not chunk:break
    size+=len(chunk);assert size<=80*1024*1024;h.update(chunk);out.write(chunk)
  assert size==int(info['length'])
  raw=path.read_bytes();z=zlib.decompressobj(31);z.decompress(raw);assert z.eof
  rest=z.unused_data;z=zlib.decompressobj(31);z.decompress(rest);assert z.eof
  control=rest[:len(rest)-len(z.unused_data)];identity='Q1'+base64.b64encode(hashlib.sha1(control).digest()).decode()
  assert identity==expected[p['name']]['apk_checksum']
  return {'name':p['name'],'file':name,'size':size,'sha256':h.hexdigest(),'installed_control_checksum_matches':True}
 except Exception as e:return {'name':p['name'],'file':name,'error_type':type(e).__name__,'error':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(fetch,selected))
(B/'download-result.json').open('x').write(json.dumps(rows,indent=2)+'\n')
assert len(rows)==150 and all(r.get('installed_control_checksum_matches') for r in rows)
def docker(*args):return subprocess.check_output(['docker','--context','desktop-linux',*args],text=True).strip()
name='aos-apk-batch-'+uuid.uuid4().hex
(B/'intent.json').open('x').write(json.dumps({'name':name,'image':lock['image'],'files':[r['file'] for r in rows]}))
cid=docker('create','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=bind,src='+str(P)+',dst=/packages,readonly','--entrypoint','/sbin/apk',lock['image'],'verify',*['/packages/'+r['file'] for r in rows])
r=subprocess.run(['docker','--context','desktop-linux','start','-a',cid],text=True,capture_output=True,timeout=60);info=json.loads(docker('inspect',cid))[0];assert info['State']['Status']=='exited'
result={'container':cid,'image':info['Image'],'exit_code':info['State']['ExitCode'],'stdout':r.stdout,'stderr':r.stderr,'package_count':len(rows),'all_installed_checksums_match':True,'independent_key_trust':False,'execution_authorized':False}
(B/'result.json').open('x').write(json.dumps(result,indent=2)+'\n');assert result['exit_code']==0 and len([l for l in r.stdout.splitlines() if l.endswith(': OK')])==150
print('150 exact package identities matched; 150 apk verify OK; no installation or independent root trust')
