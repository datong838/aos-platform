from pathlib import Path
import sys,importlib.util,json,ast,os,hashlib,datetime
import psycopg
R=Path('/Users/ddt/work/projects/ai_agent');E=R/'aos-platform/.evidence/current159-maintenance-20261010';out=E/'recovery-20261011';sys.path.insert(0,str(E))
from snapshot_all import snapshot,rows
from snapshot_supplement import supplement
from dependency_review import TABLES
with (out/'plan.md').open('a') as f:f.write('\n## Post-startup full readonly comparison\nUse original snapshot_all/snapshot_supplement and exact dependency QUERY in REPEATABLE READ READ ONLY against original cluster159. Compare base/supplement/bindings to prior after-canary-refresh-full159-readonly.json without normalization or ignored fields. Private0600 snapshot, public hashes/counts/categories only; no schema/data writes.\n')
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
bootstrap=load('bootstrap',R/'aos-recovery/api159-reboot-ba05d7d655ea/source/scripts/a0v_current_preview_bootstrap.py')
tree=ast.parse((E/'review_native_dependencies.py').read_text());env={'psycopg':psycopg,'TABLES':tuple(sorted(TABLES))};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='QUERY' for x in n.targets)],type_ignores=[]),'<original-query>','exec'),env)
with psycopg.connect(**bootstrap._connection_parameters()) as c:
 c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;c.read_only=True
 cluster=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0];assert cluster=='7683855731447750695'
 value={'cluster':cluster,'base':snapshot(c,version='a0v_159'),'supplement':supplement(c,version='a0v_159'),'bindings':rows(c,env['QUERY'])};c.rollback()
basepath=R/'aos-recovery/current159-window-800a4a23804b/resume-r1/after-canary-refresh-full159-readonly.json';old=json.loads(basepath.read_text());raw=json.dumps(value,sort_keys=True).encode();normalized=json.loads(raw)
private=R/'aos-recovery/api159-reboot-ba05d7d655ea/post-browser-full-snapshot.json'
with os.fdopen(os.open(private,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(raw)
diff={k:[key for key in sorted(set(old[k])|set(normalized[k])) if old[k].get(key)!=normalized[k].get(key)] if isinstance(old[k],dict) else ['value'] for k in old if old[k]!=normalized.get(k)}
r={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cluster':cluster,'table_count':len(value['base']['tables']),'baseline_sha256':hashlib.sha256(basepath.read_bytes()).hexdigest(),'current_sha256':hashlib.sha256(raw).hexdigest(),'exact_equal':old==normalized,'difference_categories':diff,'read_only':True,'private_snapshot':str(private),'business_first_chain':False}
(out/'post-browser-snapshot-comparison.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
