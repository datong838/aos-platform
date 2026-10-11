from pathlib import Path
import urllib.request,zlib,tarfile,io,json,hashlib
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
B=Path(__file__).resolve().parent;diff=json.loads((B.parent/'offline-sdk-1815/result.json').read_text())['differences'];allrows=[];indexes=[]
for repo in ['main','community']:
 url='https://dl-cdn.alpinelinux.org/alpine/v3.24/'+repo+'/aarch64/APKINDEX.tar.gz'
 with urllib.request.urlopen(url,timeout=30) as response:raw=response.read(16*1024*1024+1)
 assert len(raw)<=16*1024*1024
 (B/(repo+'.tar.gz')).open('xb').write(raw)
 z=zlib.decompressobj(31);sigdata=z.decompress(raw);assert z.eof;rest=z.unused_data
 with tarfile.open(fileobj=io.BytesIO(sigdata)) as t:
  members=t.getmembers();assert len(members)==1 and members[0].name.startswith('.SIGN.RSA.')
  signature=t.extractfile(members[0]).read();keyname=members[0].name[len('.SIGN.RSA.'):]
 assert keyname in ['alpine-devel@lists.alpinelinux.org-58199dcc.rsa.pub','alpine-devel@lists.alpinelinux.org-616ae350.rsa.pub']
 with urllib.request.urlopen('https://alpinelinux.org/keys/'+keyname,timeout=20) as response:key=response.read(8192)
 serialization.load_pem_public_key(key).verify(signature,rest,padding.PKCS1v15(),hashes.SHA1())
 z=zlib.decompressobj(31);data=z.decompress(rest);assert z.eof and not z.unused_data
 with tarfile.open(fileobj=io.BytesIO(data)) as t:text=t.extractfile('APKINDEX').read().decode()
 records=[]
 for block in text.split('\n\n'):
  f={l[0]:l[2:] for l in block.splitlines() if len(l)>2 and l[1]==':' and l[0] in 'PVAC'}
  if 'P' in f:records.append(f)
 for entry in diff:
  matches=[f for f in records if all(f.get(k)==entry['before'][k] for k in 'PVC')]
  if matches:
   assert len(matches)==1;allrows.append({'name':entry['name'],'repository':repo,'index':matches[0],'original':entry['before'],'direct_install':entry['after'],'signed_package_arch':entry['signed_metadata_arch']})
 indexes.append({'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'key_sha256':hashlib.sha256(key).hexdigest(),'signature_verified':True})
assert len(allrows)==7 and len({r['name'] for r in allrows})==7 and all(r['index']==r['original'] for r in allrows)
r={'indexes':indexes,'differences':allrows,'all_seven_index_records_match_original':True,'full_sdk_reproduced':False,'execution_authorized':False}
(B/'result.json').open('x').write(json.dumps(r,indent=2)+'\n');print('Both index signatures verified; all seven original architecture records match exact signed index entries')
