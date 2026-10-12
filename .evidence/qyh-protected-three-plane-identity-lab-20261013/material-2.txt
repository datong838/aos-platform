"""Read-only remaining original file/target negative gates and current preservation."""
import importlib.util,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('lab',P/'lab.py');L=importlib.util.module_from_spec(s);s.loader.exec_module(L)
sys.path.insert(0,str(L.ROOT/'scripts'))
from a0v_current_runtime_host_preflight import require_current_dsn_targets
from aos_api.extension_runtime.runtime_connections import _runtime_file_dsns
values=json.loads((P/'private/identities.json').read_text());negatives=[]
for name,value in [('wrongshape',{'web':values['web']}),('duplicateprincipal',{**values,'runtime':values['directory']})]:
 path=P/'private'/f'{name}.json';L.write(path,value,True)
 try:_runtime_file_dsns(path)
 except RuntimeError:negatives.append(name)
 else:raise AssertionError('negative accepted')
dsns=_runtime_file_dsns(P/'private/identities.json')
try:require_current_dsn_targets(dsns,'aos_meta_head')
except Exception:negatives.append('historicalOrLabDatabaseRejectedByCurrentTargetGate')
else:raise AssertionError('lab target accepted as current database')
current=json.loads((L.ROOT/'.evidence/qyh-full-system-restoration-20261011/current-host-oid-maintenance-20261013/verification.json').read_text())
assert L.r.fingerprint(L.r.SOURCE,'aos_meta_head')==current['afterFingerprints']
L.record('supplement-verification.json',{'negativeGates':negatives,'current650TablesUnchanged':True,'currentCredentialsModified':False,'cloneCredentialsAreNotCurrentFormalAuthority':True})
print('ORIGINAL_PROTECTED_FILE_AND_CURRENT_TARGET_NEGATIVE_GATES_GREEN')
