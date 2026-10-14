from pathlib import Path,PurePosixPath
import io,json,hashlib,os,subprocess,tarfile
E=Path(__file__).resolve().parent;R=E.parents[1];HEAD='1627a39050cc5e8c88f223c56eb870f085091dd9'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==HEAD
source=E/'private'/('creator-closure-web-'+HEAD);out=E/'creator-closure-web-source.json';assert not source.exists() and not out.exists()
proof=json.loads((R/'.evidence/qyh-creator-closure-readonly-client-20261015/source-verification-r3.json').read_text());hashes=proof['sourceAfter'];assert all(x['returncode']==0 for x in proof['results'].values())
raw=subprocess.check_output(['git','archive',HEAD,'apps/web','packages/ontology-sdk','packages/ui-kit'],cwd=R);members={}
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
 for item in archive.getmembers():
  p=PurePosixPath(item.name);assert not p.is_absolute() and '..' not in p.parts and (item.isfile() or item.isdir())
  if item.isfile() and not any(x.startswith('.env') for x in p.parts):members[item.name]=archive.extractfile(item).read()
assert all(hashlib.sha256(members[f]).hexdigest()==h for f,h in hashes.items())
with (E/'creator-closure-web-freeze-intent.json').open('x') as f:json.dump({'head':HEAD,'source':str(source),'fileCount':len(members),'dirtyCopied':False,'credentialsCopied':False},f,indent=2);f.flush();os.fsync(f.fileno())
source.mkdir(parents=True,mode=0o700)
for name,body in members.items():
 p=source/name;p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);p.write_bytes(body);p.chmod(0o600)
manifest={name:hashlib.sha256(body).hexdigest() for name,body in members.items()};assert {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}==manifest
(source/'apps/web/node_modules').symlink_to(R/'apps/web/node_modules',target_is_directory=True)
with out.open('x') as f:json.dump({'head':HEAD,'source':str(source),'manifest':manifest,'sourceHashes':hashes,'port':18434,'apiTarget':'http://127.0.0.1:18080','processEffects':False},f,indent=2)
print({'head':HEAD,'fileCount':len(manifest),'processEffects':False})
