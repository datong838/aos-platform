from pathlib import Path,PurePosixPath
import datetime,hashlib,io,json,os,subprocess,tarfile
E=Path(__file__).resolve().parent;R=E.parents[1];NODE='/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node'
files=['apps/web/src/api/ecommerceWorkshop/parser.ts','apps/web/src/api/ecommerceWorkshop/threeModuleClosureClient.test.ts','apps/web/src/api/ecommerceWorkshop/contracts.ts'];before={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in files};head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();assert head=='53d572ba3265d77835a49ee92441c7ce26ea7faa'
source=E/'private/frozen-web-candidate-r3';assert not source.exists();members={}
raw=subprocess.check_output(['git','archive',head,'apps/web','packages/ontology-sdk','packages/ui-kit'],cwd=R)
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
 for item in archive.getmembers():
  p=PurePosixPath(item.name);assert not p.is_absolute() and '..' not in p.parts and (item.isfile() or item.isdir())
  if item.isfile() and not any(x.startswith('.env') for x in p.parts):members[item.name]=archive.extractfile(item).read()
for p in files:members[p]=(R/p).read_bytes()
source.mkdir(parents=True,mode=0o700)
for name,body in members.items():
 p=source/name;p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);p.write_bytes(body);p.chmod(0o600)
(source/'apps/web/node_modules').symlink_to(R/'apps/web/node_modules',target_is_directory=True)
commands={'web-cumulative-r3':[NODE,'node_modules/vitest/vitest.mjs','run','src/components/workshop','src/api/ecommerceWorkshop'],'web-typecheck-r3':[NODE,'node_modules/typescript/bin/tsc','--noEmit']};result={};at=datetime.datetime.now(datetime.timezone.utc).isoformat()
for name,cmd in commands.items():
 with (E/(name+'.log')).open('x') as f:p=subprocess.run(cmd,cwd=source/'apps/web',env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=f,stderr=subprocess.STDOUT)
 result[name]={'returncode':p.returncode,'command':cmd,'logSha':hashlib.sha256((E/(name+'.log')).read_bytes()).hexdigest()}
after={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in files};assert before==after
with (E/'source-verification-r3.json').open('x') as f:json.dump({'baseHead':head,'sourceBefore':before,'sourceAfter':after,'onlyThreeOwnedOverlays':True,'noUserDirtyCopied':True,'results':result,'at':at,'finishedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'serviceEffects':False},f,indent=2)
print({k:v['returncode'] for k,v in result.items()});assert all(v['returncode']==0 for v in result.values())
