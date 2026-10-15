"""Run existing Workshop tests, typecheck and production CSS build privately."""
from pathlib import Path
import datetime, hashlib, json, os, subprocess

R=Path.cwd()
E=R/'.evidence/qyh-price-visual-filter-sizing-20261015'
report=json.loads((E/'candidate-source-r1.json').read_text())
source=Path(report['source'])
css='apps/web/src/styles/45-ecommerce-workshop.css'
before=hashlib.sha256((R/css).read_bytes()).hexdigest()
assert before==report['cssSha']
assert json.loads((E/'green-metrics-r1.json').read_text())['allPass']
for n,sha in report['manifest'].items():assert hashlib.sha256((source/n).read_bytes()).hexdigest()==sha
config=E/'private/frozen-verification-config-r1.ts'
with config.open('x') as f:
    f.write('import base from '+json.dumps(str(source/'apps/web/vite.config.ts'))+';\nexport default {...base,cacheDir:'+json.dumps(str(E/'private/verification-cache-r1'))+',envDir:'+json.dumps(str(E/'private/no-env'))+',test:{...base.test,cache:false}};\n')
node='/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node'
commands={
    'workshop-cumulative-r1':[node,'node_modules/vitest/vitest.mjs','run','src/components/workshop','src/api/ecommerceWorkshop','--config',str(config),'--no-cache'],
    'web-typecheck-r1':[node,'node_modules/typescript/bin/tsc','--noEmit'],
    'web-production-build-r1':[node,'node_modules/vite/bin/vite.js','build','--config',str(config)],
}
env={k:v for k,v in os.environ.items() if not k.startswith(('AOS_','PG','VITE_','OPENAI_'))}
env.update(CI='1',NO_COLOR='1')
results={}
started=datetime.datetime.now(datetime.timezone.utc).isoformat()
for name,command in commands.items():
    with (E/(name+'.log')).open('x') as f:
        p=subprocess.run(command,cwd=source/'apps/web',env=env,stdout=f,stderr=subprocess.STDOUT)
    results[name]={'returncode':p.returncode,'command':command,'logSha':hashlib.sha256((E/(name+'.log')).read_bytes()).hexdigest()}
after=hashlib.sha256((R/css).read_bytes()).hexdigest()
assert before==after
for n,sha in report['manifest'].items():assert hashlib.sha256((source/n).read_bytes()).hexdigest()==sha
with (E/'source-verification-r1.json').open('x') as f:json.dump({'baseHead':report['head'],'cssBefore':before,'cssAfter':after,'onlyOneOwnedCSSOverlay':True,'originalComponentUnchanged':True,'noUserDirtyCopied':True,'privateBuildAndCache':True,'results':results,'startedAt':started,'finishedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'originalServicesTouched':False},f,indent=2)
print(json.dumps({k:v['returncode'] for k,v in results.items()}))
assert all(v['returncode']==0 for v in results.values())
