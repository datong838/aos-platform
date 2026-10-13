"""Freeze latest committed Web without starting or touching database services."""
import json,subprocess,io,tarfile,hashlib,importlib.util,sys
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];P=Path(__file__).resolve().parent
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
assert head=='ceba8ba4c63bcfa8c3690d6f05d24cb1ed6a5f08'
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
lease=[x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']=='qyh-full-system-restoration-20261011'];assert len(lease)==1 and lease[0]['status']=='ACTIVE' and datetime.fromisoformat(lease[0]['lease_expires_at'])>datetime.now(timezone.utc)
source=P/'private'/('installed-readonly-web-'+head);assert not source.exists()
report_path=P/'installed-readonly-web-20261013.json';assert not report_path.exists()
raw=subprocess.check_output(['git','archive',head,'apps/web','packages/ontology-sdk','packages/ui-kit'],cwd=R)
manifest={};source.mkdir(mode=0o700)
with tarfile.open(fileobj=io.BytesIO(raw)) as t:
 for x in t.getmembers():
  assert '..' not in Path(x.name).parts and not Path(x.name).is_absolute() and (x.isfile() or x.isdir())
  if not x.isfile() or '.env' in Path(x.name).parts:continue
  data=t.extractfile(x).read();q=source/x.name;q.parent.mkdir(parents=True,exist_ok=True,mode=0o700);q.write_bytes(data);q.chmod(0o600);manifest[x.name]=hashlib.sha256(data).hexdigest()
(source/'apps/web/node_modules').symlink_to(R/'apps/web/node_modules',target_is_directory=True)
report={'head':head,'source':str(source),'files':len(manifest),'manifest':manifest,'apiTarget':'http://127.0.0.1:18080','port':18434,'credentialsCopied':False}
report_path.write_text(json.dumps(report,indent=2)+'\n')
old=(P/'restart-20261013-032343-web.mjs').read_text();new=old.replace('restart-20261013-032343-web.json','installed-readonly-web-20261013.json').replace('restart-20261013-032343-vite-cache','installed-readonly-web-20261013-vite-cache');(P/'installed-readonly-web-20261013.mjs').write_text(new)
print('Latest committed Web frozen:',head,len(manifest),'files; no service started.')
