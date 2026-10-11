"""Reuse original Stage fixtures on the owned clone, never connect to port18432."""
import ast,inspect,json,os,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
expected=json.loads((ROOT/'.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
actual=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect','--format','{"Id":{{json .Id}},"Mounts":{{json .Mounts}}}','qyh-source-boundary-clone-20261011'],text=True));assert actual['Id']==expected['container']['Id'] and not actual['Mounts']
os.environ['AOS_EXTENSION_PG_TEST']='1'
sys.path[:0]=[str(ROOT/'services/aos-api'),str(ROOT/'services/aos-api/tests/extension_runtime')]
import test_lifecycle_pg as legacy
source=inspect.getsource(legacy.database)
tree=ast.parse(source);changed=0
for n in ast.walk(tree):
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='psycopg' and n.func.attr=='connect':
  values={k.arg:ast.literal_eval(k.value) for k in n.keywords}
  assert values==dict(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True)
  for k in n.keywords:
   if k.arg=='port':k.value=ast.Constant(value=18431)
   if k.arg=='user':k.value=ast.Constant(value='aos_app')
  changed+=1
assert changed==1
exec(compile(ast.fix_missing_locations(tree),'original-stage-fixture-owned-clone','exec'),legacy.__dict__)
import pytest
raise SystemExit(pytest.main([str(ROOT/'services/aos-api/tests/extension_runtime/test_configuration_stage_preflight_pg.py'),str(ROOT/'services/aos-api/tests/extension_runtime/test_configuration_stage_consumer_pg.py'),'-q']))
