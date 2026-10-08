from pathlib import Path
import json,subprocess,hashlib,importlib.util,sys
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
result=json.loads((B/'native-r3-result.json').read_text());assert result['pytest_exit']==0
checks=json.loads((B/'existing-call-immutability.json').read_text());assert checks['direct_target_call_constraint_tested'] and len(checks['checks'])==4
assert {v['operation']:v['sqlstate'] for v in checks['checks']}==dict(update='42501',delete='42501',truncate='55006',joint_constraint='23514')
readback=json.loads((B/'independent-readback.json').read_text());assert readback['xact_state']=='aborted' and readback['test_only_probe_count']==0 and readback['old_resources_unchanged']
files=[str(p.relative_to(R)) for p in sorted(B.iterdir()) if p.is_file() and p.name not in ('delivery.json','context-sync-1614.json','evidence-commit.json','stage-files.json')]
for suffix in ('r1','r2','r3'):
 for folder,prefix in (('gt-atomic-model-admission-20261008','source-newjudge-target-call-immutable-'+suffix+'-'),('gt-judge-call-authority-20261008','target-call-immutable-'+suffix+'-')):
  files.extend(str(p.relative_to(R)) for p in sorted((R/'.evidence'/folder).glob(prefix+'*.json')))
files=sorted(set(files));(B/'stage-files.json').write_text(json.dumps(files,indent=2)+'\n')
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).strip()
subprocess.run(['git','add','--',*files,str((B/'stage-files.json').relative_to(R))],cwd=R,check=True)
staged=set(subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).splitlines());assert staged<=set(files)|{str((B/'stage-files.json').relative_to(R))}
subprocess.run(['git','commit','-m','test(aip): prove Target call row immutability and dedicated commit gate'],cwd=R,check=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();(B/'evidence-commit.json').write_text(json.dumps(dict(head=head,product_changed=False),indent=2)+'\n')
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);a=m.load_authority();assert a['project_revision']=='AOS-001613'
d=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='TARGET_CALL_IMMUTABILITY_AND_DEDICATED_COMMIT_GATE_NATIVE_GREEN_ADMISSION_PENDING',changed_files=['aos-platform/.evidence/'+B.name],commits=[head],verification=['Actual original Source/SCRAM/current approved Target/newJudge/complete plan/Target Intent and call; existing UPDATE DELETE42501, pending-eventTRUNCATE55006, empty-table customTRUNCATE42501, exact newcall joint_constraint23514','Full original native1PASS92.62s regression; actualcallerCOMMIT rejected, independent aborted/prepared0/Source1/NOLOGIN/member0/no temporary probes/31old resources unchanged'],risks=['No product code changes, actual inflight ledger/risk allocation/unknown/final deadline/transport/Usage still pending','R1 exact truncate error mismatch and R2 original50s deadline failures retained; no deadline expansion or formal effects'],blockers=[]);(B/'delivery.json').write_text(json.dumps(d,indent=2)+'\n')
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary='Actual existing trusted Target call row UPDATE/DELETE refused42501, TRUNCATE with pending deferred events refused55006, empty table original BEFORE TRUNCATE trigger42501 separately proven; exact newcall require_joint_finalization IMMEDIATE refused23514 independent of oldparent constraint. R1 expected wrong truncate error FAIL62.56s and R2 repeated validation hit genuine Judge50s deadline FAIL66.65s preserved; only specialized test corrected and duplicate1613 negative repetition removed, no expiry extension/product changes. R3 full original native1PASS92.62s regression, precise replays unchanged; independent callerxid aborted/four preparations0/Source1/NOLOGIN/member0/temp probes0/31old resources unchanged. No actualadmission/finalizer/transport/fees/unknown/lastdeadline or Goal completion; five parentTasks ACTIVE; actual ledger safe preparation next.')])
orig=m.atomic_write_text
def safe(path,text,**kw):
 if str(path).startswith('/Users/ddt/.codex/memories/'):return
 return orig(path,text,**kw)
m.atomic_write_text=safe;sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=f,sha256=hashlib.sha256((R/f).read_bytes()).hexdigest()) for f in files]
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008']
for task in tasks:
 folder=R/'.evidence'/task;cp=json.loads((folder/'checkpoint.json').read_text());prior='.evidence/'+task+'/trusted-target-call-reference-1613.json';ref='.evidence/'+task+'/target-call-immutability-reference-1614.json';(R/ref).write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,execution_allowed=False,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs),indent=2)+'\n');cp.update(authority_revision=r['project_revision'],step='trusted-target-call-immutability-native-green-actual-occupation-ledger-next');cp['evidence_files']=[ref if f==prior else f for f in cp['evidence_files']];(folder/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
v=m.validate_installation();status=m.memory_status();assert v['status']=='GREEN';assert all(x['status']=='CURRENT' for x in status['projections'] if x['consistency']=='strong')
spec=importlib.util.spec_from_file_location('wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');w=importlib.util.module_from_spec(spec);sys.modules[spec.name]=w;spec.loader.exec_module(w)
for task in tasks:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2','.evidence/'+task+'/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文')
(B/'context-sync-1614.json').write_text(json.dumps(dict(revision=r['project_revision'],head=head,sync=sync,validation=v,status=status,all_five_checkpoint_bindings='PASS'),ensure_ascii=False,indent=2)+'\n')
print(r['project_revision'],'GREEN; five checkpoints PASS')
