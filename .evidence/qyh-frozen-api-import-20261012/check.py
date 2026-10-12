"""Fresh original app factory import; all attempted DB/network effects fail closed."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('restored',ROOT/'scripts/a0v_qyh_restored_http.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
receipt=ROOT/'.evidence/qyh-full-system-restoration-20261011/latest-api-skill-snapshot-20261012.json'
source=original.require_api_source_candidate(receipt)
report=json.loads(receipt.read_text())
assert not (OUT/'result.json').exists()
environment={k:os.environ[k] for k in ('PATH','LANG','TZ') if k in os.environ}
environment.update(report['startupFlags'])
environment.update({'AOS_AUTH_ALLOW_DEV':'1','AOS_AUTH_EXTERNAL_ONLY':'0',
    'PYTHONPATH':os.pathsep.join([str(source/'services/aos-api'),str(source/'scripts')]),
    'PYTHONDONTWRITEBYTECODE':'1','AOS_DATABASE_URL':'postgresql://aos_app@127.0.0.1:1/unavailable'})
child=r'''
import json,pathlib,socket,sys
import psycopg
attempts={'database':0,'network':0}
def database(*args,**kwargs):
    attempts['database']+=1
    raise RuntimeError('import attempted database connection')
def network(*args,**kwargs):
    attempts['network']+=1
    raise RuntimeError('import attempted network connection')
psycopg.connect=database
psycopg.Connection.connect=database
psycopg.AsyncConnection.connect=database
socket.socket.connect=network
socket.socket.connect_ex=network
socket.create_connection=network
try:
    import a0v_qyh_restored_http
    app=a0v_qyh_restored_http.management_app()
    root=pathlib.Path.cwd()/'services/aos-api'
    modules=[]
    for name,module in sys.modules.items():
        if name=='aos_api' or name.startswith('aos_api.'):
            path=getattr(module,'__file__',None)
            if path:
                assert pathlib.Path(path).resolve().is_relative_to(root), 'worktree import contamination'
                modules.append(name)
    assert attempts=={'database':0,'network':0}
    outcome={'imported':True,'originalManagementFactoryUsed':True,'moduleCount':len(modules),
        'modules':sorted(modules),'attempts':attempts,'lifespanCalled':False,'serverStarted':False}
except Exception as error:
    outcome={'imported':False,'errorType':type(error).__name__,'missingModule':getattr(error,'name',None),
        'attempts':attempts,'lifespanCalled':False,'serverStarted':False}
print(json.dumps(outcome))
sys.exit(0 if outcome['imported'] else 1)
'''
result=subprocess.run([sys.executable,'-c',child],cwd=source,env=environment,
    capture_output=True,text=True,timeout=30)
(OUT/'import.stdout.log').write_text(result.stdout)
(OUT/'import.stderr.log').write_text(result.stderr)
outcome=json.loads(result.stdout.splitlines()[-1])
outcome.update(sourceHead=report['head'],originalSourceGatePassed=True,exitCode=result.returncode,
    currentServiceChanged=False,formalIdentityVerified=False,eightWorkbenchesAccepted=False)
with (OUT/'result.json').open('x') as stream:json.dump(outcome,stream,indent=2)
print(json.dumps({k:v for k,v in outcome.items() if k!='modules'}))
if result.returncode:raise SystemExit(result.returncode)
