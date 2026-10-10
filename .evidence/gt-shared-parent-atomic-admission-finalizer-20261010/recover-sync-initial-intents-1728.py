from pathlib import Path
import importlib.util,sys,json,subprocess
R=Path.cwd();N=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
r=m.load_authority();assert r['project_revision']=='AOS-001728'
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();db=json.loads((N/'initial-intents-verification-1727.json').read_text())['component_readback']['database']
for task in (N.name,'gt-atomic-model-admission-20261008'):
 p=R/'.evidence'/task/'checkpoint.json';cp=json.loads(p.read_text());cp.update(authority_revision=r['project_revision'],step='initial-intents-component-native-readback-pass-whole-source-red-diagnosis-next')
 refs=[x for x in cp['evidence_files'] if 'context-sync' not in x and 'context-delivery' not in x]
 for f in (N/'initial-intents-verification-1727.json',N/'initial-intents-review-1727.json'):
  rel=str(f.relative_to(R))
  if rel not in refs:refs.append(rel)
 refs=refs[-32:]
 assert len(refs)<=32
 cp['evidence_files']=refs;p.write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text;m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);validation=m.validate_installation();assert validation['status']=='GREEN'
(N/'initial-intents-context-sync-1728.json').write_text(json.dumps({'authority_revision':r['project_revision'],'head':head,'installation':validation,'retained_database':db,'component_only':True,'whole_source_adjacent_pass':False,'full_task_delivered':False,'goal_complete':False,'codex_memories_write_skipped':True},indent=2)+'\n')
print(r['project_revision'],validation['status'],db)
