from pathlib import Path
import zlib,tarfile,io,gzip,json,hashlib,base64,subprocess,uuid
B=Path(__file__).resolve().parent;N=B.parent
raw=(N/'package-signature-1811/original.apk').read_bytes();lock=json.loads((N/'build-dependency-lock-1809/dependency-lock.json').read_text());positive=json.loads((N/'package-signature-1811/result.json').read_text());assert hashlib.sha256(raw).hexdigest()==positive['sha256']
z=zlib.decompressobj(31);signature=z.decompress(raw)+z.flush();assert z.eof;rest=z.unused_data
with tarfile.open(fileobj=io.BytesIO(signature)) as t:
 entries=t.getmembers();assert len(entries)==1 and entries[0].name.startswith('.SIGN.RSA.') and entries[0].size==512
 offset=entries[0].offset_data
changed=bytearray(signature);changed[offset]^=1
bad=gzip.compress(bytes(changed),mtime=0)+rest
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(bad[:len(bad)-len(rest)]))) as t:assert [(m.name,m.size) for m in t.getmembers()]==[(m.name,m.size) for m in entries]
z=zlib.decompressobj(31);z.decompress(rest);assert z.eof;control=rest[:len(rest)-len(z.unused_data)]
identity='Q1'+base64.b64encode(hashlib.sha1(control).digest()).decode();installed=next(p for p in lock['packages'] if p['name']=='binutils');assert identity==installed['apk_checksum']
(B/'wrong-signature.apk').open('xb').write(bad)
def docker(*args):return subprocess.check_output(['docker','--context','desktop-linux',*args],text=True).strip()
name='aos-apk-signature-negative-'+uuid.uuid4().hex
(B/'intent.json').open('x').write(json.dumps({'name':name,'image':lock['image'],'entrypoint':'/sbin/apk'}))
cid=docker('create','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=bind,src='+str(B/'wrong-signature.apk')+',dst=/tmp/input.apk,readonly','--entrypoint','/sbin/apk',lock['image'],'verify','/tmp/input.apk')
p=subprocess.run(['docker','--context','desktop-linux','start','-a',cid],capture_output=True,text=True,timeout=30);info=json.loads(docker('inspect',cid))[0]
assert info['State']['Status']=='exited'
r={'container':cid,'image':info['Image'],'exit_code':info['State']['ExitCode'],'stdout':p.stdout,'stderr':p.stderr,'control_and_payload_unchanged':True,'signature_bytes_changed':1,'installed_control_checksum_matches':True,'installed_checksum':identity,'original_sha256':hashlib.sha256(raw).hexdigest(),'negative_sha256':hashlib.sha256(bad).hexdigest(),'independent_key_trust':False,'execution_authorized':False}
(B/'result.json').open('x').write(json.dumps(r,indent=2)+'\n');print(json.dumps(r));assert r['exit_code']!=0 and 'signature' in (p.stdout+p.stderr).lower()
