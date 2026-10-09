from pathlib import Path
import json,subprocess,hashlib,importlib.util,sys
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
result=json.loads((B/'native-green-r1-result.json').read_text());assert result['pytest_exit']==0
checks=json.loads((B/'ledger-green.json').read_text());assert len(checks['dml_denials'])==10 and len(checks['dedicated_constraints'])==2
readback=json.loads((B/'independent-readback.json').read_text());assert readback['xact_state']=='aborted' and readback['test_only_probe_count']==0 and readback['old_resources_unchanged']
assert '318 passed' in (B/'adjacent-r1.log').read_text()
files=[str(p.relative_to(R)) for p in sorted(B.iterdir()) if p.is_file() and p.name not in ('delivery.json','context-sync-1615.json','evidence-commit.json','stage-files.json')]
files += ['services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py','.evidence/gt-atomic-model-admission-20261008/renewals-ledger-1614.json']
for suffix in ('red-r1','green-r1'):
 for folder,prefix in (('gt-atomic-model-admission-20261008','source-newjudge-ledger-'+suffix+'-'),('gt-judge-call-authority-20261008','ledger-'+suffix+'-')):
  files.extend(str(p.relative_to(R)) for p in sorted((R/'.evidence'/folder).glob(prefix+'*.json')))
files=sorted(set(files));(B/'stage-files.json').write_text(json.dumps(files,indent=2)+'\n')
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).strip()
subprocess.run(['git','add','--',*files,str((B/'stage-files.json').relative_to(R))],cwd=R,check=True)
staged=set(subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).splitlines());assert staged<=set(files)|{str((B/'stage-files.json').relative_to(R))}
subprocess.run(['git','commit','-m','feat(aip): prepare immutable Target occupation root and first event'],cwd=R,check=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();(B/'evidence-commit.json').write_text(json.dumps(dict(head=head,product_changed=True),indent=2)+'\n')
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);a=m.load_authority();assert a['project_revision']=='AOS-001614'
d=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='TARGET_OCCUPATION_INITIAL_ROOT_EVENT_NATIVE_GREEN_ACTUAL_ADMISSION_PENDING',changed_files=['aos-platform/services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py','aos-platform/.evidence/'+B.name],commits=[head],verification=['Original native RED85.56s interface missing42883; GREEN95.76s actual root/event insertion exact replay and ten runtime DML denials42501, two dedicated gates23514','Actual inflight0, original debit1/tokens10000 unchanged; adjacent318PASS0.73s; independent aborted/six preparation tables0/Source1/NOLOGIN/member0/probes0/31old resources unchanged'],risks=['Preparation only; no actual admission or lifecycle/fees/Usage/finalizer/transport/firstchain','Original code prefix preserved, no default migration/formal DB effects; five parent Tasks remain ACTIVE'],blockers=[]);(B/'delivery.json').write_text(json.dumps(d,indent=2)+'\n')
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary='Trusted original Target call now derives immutable occupation root and first immutable event with server hashes/origin/parent/physical/token, prepared_only and counts_as_inflight=false; explicit isolated artifact only. Original native RED85.56s42883, GREEN95.76s actual insertion/replay/tenDML42501/two dedicated23514 and full regression; actualinflight0/debit1/tokens10000 unchanged, adjacent318PASS0.73s. Independent xidaborted/six preparationtables0/Source1/NOLOGIN/member0/temp probes0/31old resources unchanged. No actual admission/lifecycle/unknown/fees/Usage/finalizer/transport/firstchain or Goal change; five parentTasks ACTIVE. Next safe investigation global physical guard/bucket fences and trusted actual-state evidence.')])
orig=m.atomic_write_text
def safe(path,text,**kw):
 if str(path).startswith('/Users/ddt/.codex/memories/'):return
 return orig(path,text,**kw)
m.atomic_write_text=safe;sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=f,sha256=hashlib.sha256((R/f).read_bytes()).hexdigest()) for f in files]
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008']
for task in tasks:
 folder=R/'.evidence'/task;cp=json.loads((folder/'checkpoint.json').read_text());prior='.evidence/'+task+'/target-call-immutability-reference-1614.json';ref='.evidence/'+task+'/occupation-ledger-preparation-reference-1615.json';(R/ref).write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,execution_allowed=False,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs),indent=2)+'\n');cp.update(authority_revision=r['project_revision'],step='target-occupation-initial-root-event-native-green-actual-admission-lifecycle-pending');cp['evidence_files']=[ref if f==prior else f for f in cp['evidence_files']];(folder/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
v=m.validate_installation();status=m.memory_status();assert v['status']=='GREEN';assert all(x['status']=='CURRENT' for x in status['projections'] if x['consistency']=='strong')
spec=importlib.util.spec_from_file_location('wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');w=importlib.util.module_from_spec(spec);sys.modules[spec.name]=w;spec.loader.exec_module(w)
for task in tasks:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2','.evidence/'+task+'/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文')
(B/'context-sync-1615.json').write_text(json.dumps(dict(revision=r['project_revision'],head=head,sync=sync,validation=v,status=status,all_five_checkpoint_bindings='PASS'),ensure_ascii=False,indent=2)+'\n')
print(r['project_revision'],'GREEN; five checkpoints PASS')
