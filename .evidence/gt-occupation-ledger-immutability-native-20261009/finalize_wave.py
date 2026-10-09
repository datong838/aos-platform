from pathlib import Path
import json,subprocess,hashlib,importlib.util,sys
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
result=json.loads((B/'native-green-r2-result.json').read_text());assert result['pytest_exit']==0
checks=json.loads((B/'existing-ledger-immutability.json').read_text());assert len(checks['checks'])==6 and checks['exact_readback_after_each']
assert all(v['sqlstate']==('55006' if v['operation']=='truncate' else '42501') for v in checks['checks'])
assert all(v['sqlstate']=='42501' for v in json.loads((B/'empty-truncate.json').read_text()))
readback=json.loads((B/'independent-readback.json').read_text());assert readback['xact_state']=='aborted' and readback['test_only_probe_count']==0 and readback['old_resources_unchanged']
files=[str(p.relative_to(R)) for p in sorted(B.iterdir()) if p.is_file() and p.name not in ('delivery.json','context-sync-1616.json','evidence-commit.json','stage-files.json')]
for suffix in ('r1','r2'):
 for folder,prefix in (('gt-atomic-model-admission-20261008','source-newjudge-ledger-immutable-'+suffix+'-'),('gt-judge-call-authority-20261008','ledger-immutable-'+suffix+'-')):
  files.extend(str(p.relative_to(R)) for p in sorted((R/'.evidence'/folder).glob(prefix+'*.json')))
files=sorted(set(files));(B/'stage-files.json').write_text(json.dumps(files,indent=2)+'\n')
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).strip()
subprocess.run(['git','add','--',*files,str((B/'stage-files.json').relative_to(R))],cwd=R,check=True)
staged=set(subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).splitlines());assert staged<=set(files)|{str((B/'stage-files.json').relative_to(R))}
subprocess.run(['git','commit','-m','test(aip): verify occupation root and event immutability'],cwd=R,check=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();(B/'evidence-commit.json').write_text(json.dumps(dict(head=head,product_changed=False),indent=2)+'\n')
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);a=m.load_authority();assert a['project_revision']=='AOS-001615'
d=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='OCCUPATION_ROOT_EVENT_IMMUTABILITY_NATIVE_GREEN_ACTUAL_ADMISSION_PENDING',changed_files=['aos-platform/.evidence/'+B.name],commits=[head],verification=['Original actual root/event UPDATE/DELETE42501, pending-event TRUNCATE55006, empty root+event explicit TRUNCATE and event-alone custom trigger42501; exact readback after every savepoint','Full original native regression PASS; independent xidaborted/six preparation tables0/Source1/NOLOGIN/member0/temp probes0/31old resources unchanged'],risks=['No product code changes or actual admission/fees/Usage/Judge result/transport/finalizer','R1 single root TRUNCATE hit original FK0A000 before trigger; only explicit two-table test changed, no CASCADE/TTL expansion; failure retained'],blockers=[]);(B/'delivery.json').write_text(json.dumps(d,indent=2)+'\n')
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary='Existing occupation root and first event native immutable UPDATE/DELETE42501, pending deferred-eventTRUNCATE55006; empty explicit root+event TRUNCATE and independent event TRUNCATE original custom42501. R1 FAIL20.42s original root referencing FK0A000 before trigger; only test changed to exact two-table TRUNCATE, no CASCADE/product/expiry change. R2 full native regression PASS and exact same rows/hashes after every savepoint; independent aborted/six preparationtables0/Source1/NOLOGIN/member0/temp probes0/31old resources unchanged. Five parentTasks ACTIVE, no actual admission/lifecycle/fees/transport/finalizer/Goal completion. Next strict nonexecuting root/event typed boundary; Judge input remains awaiting true Target result, never substitute original input hash.')])
orig=m.atomic_write_text
def safe(path,text,**kw):
 if str(path).startswith('/Users/ddt/.codex/memories/'):return
 return orig(path,text,**kw)
m.atomic_write_text=safe;sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=f,sha256=hashlib.sha256((R/f).read_bytes()).hexdigest()) for f in files]
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008']
for task in tasks:
 folder=R/'.evidence'/task;cp=json.loads((folder/'checkpoint.json').read_text());prior='.evidence/'+task+'/actual-admission-investigation-reference-1615.json';ref='.evidence/'+task+'/occupation-ledger-immutability-reference-1616.json';(R/ref).write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,execution_allowed=False,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs),indent=2)+'\n');cp.update(authority_revision=r['project_revision'],step='occupation-root-event-immutability-native-green-strict-preparation-type-next');cp['evidence_files']=[ref if f==prior else f for f in cp['evidence_files']];(folder/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
v=m.validate_installation();status=m.memory_status();assert v['status']=='GREEN';assert all(x['status']=='CURRENT' for x in status['projections'] if x['consistency']=='strong')
spec=importlib.util.spec_from_file_location('wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');w=importlib.util.module_from_spec(spec);sys.modules[spec.name]=w;spec.loader.exec_module(w)
for task in tasks:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2','.evidence/'+task+'/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文')
(B/'context-sync-1616.json').write_text(json.dumps(dict(revision=r['project_revision'],head=head,sync=sync,validation=v,status=status,all_five_checkpoint_bindings='PASS'),ensure_ascii=False,indent=2)+'\n')
print(r['project_revision'],'GREEN; five checkpoints PASS')
