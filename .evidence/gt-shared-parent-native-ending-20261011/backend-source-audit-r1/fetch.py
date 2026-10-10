import hashlib,json,tarfile,urllib.request
from pathlib import Path
B=Path(__file__).resolve().parent
url='https://ftp.postgresql.org/pub/source/v16.14/postgresql-16.14.tar.bz2'
archive=B/'postgresql-16.14.tar.bz2'
checksum=urllib.request.urlopen(url+'.sha256',timeout=30).read().decode('ascii');expected=checksum.split()[0]
with urllib.request.urlopen(url,timeout=30) as inp,archive.open('xb') as out:
 while True:
  data=inp.read(1024*1024)
  if not data:break
  out.write(data)
actual=hashlib.sha256(archive.read_bytes()).hexdigest();assert actual==expected
count=0
with tarfile.open(archive,'r:bz2') as tar:
 for entry in tar:
  parts=Path(entry.name).parts
  if not entry.isfile() or len(parts)<3 or parts[0]!='postgresql-16.14' or parts[1] not in ('src','contrib') or not entry.name.endswith(('.c','.h')):continue
  assert all(p not in ('..','') for p in parts)
  target=B/'source'/Path(*parts[1:]);target.parent.mkdir(parents=True,exist_ok=True)
  target.open('xb').write(tar.extractfile(entry).read());count+=1
(B/'source-identity.json').open('x').write(json.dumps(dict(url=url,sha256=actual,published_sha256=expected,regular_c_header_files=count,version='16.14',installed_binary_reproducible_provenance=False,formal_database_changed=False),indent=2)+'\n');print(actual,count)
