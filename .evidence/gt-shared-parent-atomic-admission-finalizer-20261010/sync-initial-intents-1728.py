from pathlib import Path
import importlib.util,sys,json,subprocess
R=Path.cwd();N=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001727'
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
v=json.loads((N/'initial-intents-verification-1727.json').read_text());db=v['component_readback']['database']
assert v['postnative_metadata_pass']==17 and not v['whole_fixture_pass']
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],completed=a['completed']+[f'Isolated first Target Intent/unique Judge awaiting-result dependency component: native Source/two original holds/four signatures/current Suite and actual input bytes accepted; byte tamper rejected; actual COMMIT denied and independent aborted caller/zero rows/parent holds in {db}. Original14 SQL outputs byte exact, adjacent336 PASS and post-native metadata17 PASS. Component only; no complete admission or formal Root.'],incomplete=a['incomplete']+['1727 initial Intent whole original Source adjacent remains RED: r1 missing test helper corrected using fresh attempt; r2 expired Source and r3 current consumer required after complete-end rejected COMMIT; signed supplier cleanup also expired. Preserve all failures, no TTL extension or old attempt replay. Formal Colima aos-extension stopped after reboot; registered signed API159 process present, Web5173 absent; no restart in continuation.'],next_steps=['Diagnose full original Source lifecycle and added verification cost after rejected complete COMMIT without extending authority TTL or removing original regressions; use fresh isolated cases, preserve component/whole distinction.','Continue complete shared admission ending, whole physical/current-window risk and old unknown cutover; actual Target result/Judge consumer and formal first chain remain pending.']+a['next_steps'],source_commits={**a['source_commits'],'shared-initial-target-judge-dependency-component':head},evidence=a['evidence']+[dict(type='checkpoint',path=str(N/'initial-intents-verification-1727.json'),summary='Initial Intent component native rollback/readback only, whole Source RED retained'),dict(type='checkpoint',path=str(N/'initial-intents-review-1727.json'),summary='Exact three files and kernel preservation review, formal recovery read-only observation')])
for task in (N.name,'gt-atomic-model-admission-20261008'):
 p=R/'.evidence'/task/'checkpoint.json';cp=json.loads(p.read_text());cp.update(authority_revision=r['project_revision'],step='initial-intents-component-native-readback-pass-whole-source-red-diagnosis-next')
 refs=[x for x in cp['evidence_files'] if 'context-sync' not in x and 'context-delivery' not in x]
 for f in (N/'initial-intents-verification-1727.json',N/'initial-intents-review-1727.json'):
  rel=str(f.relative_to(R))
  if rel not in refs:refs.append(rel)
 assert len(refs)<=32
 cp['evidence_files']=refs;p.write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text;m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);validation=m.validate_installation();assert validation['status']=='GREEN'
(N/'initial-intents-context-sync-1728.json').write_text(json.dumps({'authority_revision':r['project_revision'],'head':head,'installation':validation,'retained_database':db,'component_only':True,'whole_source_adjacent_pass':False,'full_task_delivered':False,'goal_complete':False,'codex_memories_write_skipped':True},indent=2)+'\n')
print(r['project_revision'],validation['status'],db)
