"""Exact committed Web freeze; no process signal or service start."""
from pathlib import Path,PurePosixPath
import datetime,hashlib,io,json,os,subprocess,tarfile
E=Path(__file__).resolve().parent;R=E.parents[1]
lease=json.loads((R.parent/'docs/palantier/AOS项目开发上下文/memory/receipts/tasks'/f'{E.name}.json').read_text())
assert lease['owner']=='codex-01a13484-f019-7d82-94ce-812396db9124' and lease['base_revision']=='AOS-002030'
assert datetime.datetime.fromisoformat(lease['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();assert head=='ce1f8258c863a2dae3baddadb1b5d2fa9557ea3d'
source=E/'private'/('web-source-'+head);out=E/'creator-workflow-web-source.json';intent=E/'creator-workflow-web-freeze-intent.json'
assert not source.exists() and not out.exists() and not intent.exists(),'existing operation: reconcile only'
ui=R/'.evidence/qyh-creator-workflow-read-failure-ui-20261014';quality=json.loads((ui/'complete-code-review-manifest.json').read_text())
for v in ['r1','r2']:
 r=json.loads((ui/f'code-review-result-{v}.json').read_text());c=json.loads((ui/f'code-review-consumption-{v}.json').read_text());assert r['result']['verdict']=='PASS' and c['status']=='CONSUMED_MATERIAL_REVIEW' and c['result_sha256']==hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()
raw=subprocess.check_output(['git','archive',head,'apps/web','packages/ontology-sdk','packages/ui-kit'],cwd=R,timeout=60);members={}
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
 for item in archive.getmembers():
  rel=PurePosixPath(item.name);assert not rel.is_absolute() and '..' not in rel.parts and (item.isfile() or item.isdir())
  if not item.isfile():continue
  if any(part.startswith('.env') for part in rel.parts):continue  # Exclude even committed example env files.
  members[item.name]=archive.extractfile(item).read()
assert all(hashlib.sha256(members[f]).hexdigest()==h for f,h in quality['sourceHashes'].items())
def save(path,value):
 with path.open('x') as f:os.chmod(path,0o600);json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
save(intent,dict(head=head,source=str(source),fileCount=len(members),processEffects=False,dirtyCopied=False,credentialsCopied=False))
source.mkdir(parents=True,mode=0o700)
for name,data in members.items():
 p=source/name;p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);p.write_bytes(data);p.chmod(0o600)
manifest={name:hashlib.sha256(data).hexdigest() for name,data in members.items()}
assert {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}==manifest
(source/'apps/web/node_modules').symlink_to(R/'apps/web/node_modules',target_is_directory=True)
save(out,dict(head=head,source=str(source),manifest=manifest,port=18434,apiTarget='http://127.0.0.1:18080',processEffects=False,dirtyCopied=False,credentialsCopied=False,qualitySourceHashes=quality['sourceHashes']))
print(dict(head=head,fileCount=len(manifest),sourceFrozen=True,processEffects=False))
