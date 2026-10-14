from pathlib import Path
import datetime,hashlib,json,subprocess
Q=Path(__file__).resolve().parent;R=Q.parents[1];WEB=R/'apps/web';NODE='/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node'
files=['apps/web/src/components/workshop/CreatorGrowthPage.tsx','apps/web/src/components/workshop/CreatorGrowthPage.test.tsx']
def hashes():return {f:hashlib.sha256((R/f).read_bytes()).hexdigest() for f in files}
before=hashes();at=datetime.datetime.now(datetime.timezone.utc).isoformat();results={}
for label,cmd in [('cumulative-r2',[NODE,'node_modules/vitest/vitest.mjs','run','src/components/workshop','src/api/ecommerceWorkshop/creatorWorkflowClient.test.ts']),('typecheck-r2',[NODE,'node_modules/typescript/bin/tsc','--noEmit','-p','tsconfig.json'])]:
 with (Q/(label+'.log')).open('x') as out:res=subprocess.run(cmd,cwd=WEB,stdout=out,stderr=subprocess.STDOUT)
 results[label]={'returncode':res.returncode,'command':cmd,'logSha256':hashlib.sha256((Q/(label+'.log')).read_bytes()).hexdigest()}
after=hashes();assert before==after
(Q/'source-verification-r2.json').write_text(json.dumps({'at':at,'finishedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sourceBefore':before,'sourceAfter':after,'results':results,'originalRuntimeTouched':False},indent=2));assert all(v['returncode']==0 for v in results.values())
print({'sourceEqual':before==after,'checks':{k:v['returncode'] for k,v in results.items()}})
