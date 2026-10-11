import importlib.util,sys,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('m',R/'prepare.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
T='aos-qyh-name-rehearsal-20261011-r3';sql=(R/'proposed-name-update.sql').read_bytes()
if (R/'proposal-test-intent.json').exists():raise RuntimeError('Prior proposal test intent; reconcile')
before=m.fingerprint(T)
# Target already contains the rehearsed new name. The unchanged proposal must fail its CAS.
args=['docker','--context',m.CTX,'exec','-i',T,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','aos_app','-d',m.DB]
negative=subprocess.run(args,input=sql,capture_output=True,timeout=30)
assert negative.returncode!=0 and b'division by zero' in negative.stderr
assert m.fingerprint(T)==before
old=json.loads((R/'rename-intent.json').read_text())['row']
quote=lambda x:"'"+x.replace("'","''")+"'"
m.record('proposal-test-intent.json',{'target':T,'negativeCASFailedClosed':True,'sourceWrites':False,'step':'restore exact old metadata only in isolated target, then run proposal once'})
m.psql(T,m.DB,"BEGIN; UPDATE ONLY meta_org SET name='org-org',updated_at="+quote(old['updatedAt'])+"::timestamptz WHERE id='org-org'; COMMIT;")
positive=subprocess.run(args,input=sql,capture_output=True,timeout=30)
assert positive.returncode==0 and positive.stdout.strip()==b'1'
after=m.fingerprint(T)
original=json.loads((R/'source-fingerprint-before.json').read_text())
assert [x['table'] for x,y in zip(original,after) if x!=y]==['public.meta_org']
assert m.fingerprint(m.SOURCE)==original
m.record('proposal-test-result.json',{'positiveExactlyOneRow':True,'negativeDivisionByZeroAborts':True,'negativeAll626FingerprintsUnchanged':True,'positiveOnlyMetaOrgChanged':True,'sourceFingerprintUnchanged':True,'sourceWrites':False})
print('Isolated exact proposal positive/negative validated; source unchanged')
