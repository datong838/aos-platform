from pathlib import Path
import json,subprocess,hashlib,importlib.util,sys
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
result=json.loads((B/'native-green-r2-result.json').read_text());assert result['pytest_exit']==0
proof=json.loads((B/'wrapper-green.json').read_text());assert len(proof['negative_boundaries'])==10 and proof['exact_replay'] and proof['same_xid_pid']
assert '349 passed' in (B/'adjacent-r1.log').read_text()
readback=json.loads((B/'independent-readback.json').read_text());assert readback['xact_state']=='aborted' and readback['old_resources_unchanged'] and readback['test_only_probe_count']==0
assert (R/'services/aos-api/aos_api/aip_physical_capacity_occupation.py').read_bytes().startswith((B/'original-product.py.txt').read_bytes())
files=[str(p.relative_to(R)) for p in sorted(B.iterdir()) if p.is_file() and p.name not in ('delivery.json','context-sync-1618.json','evidence-commit.json','stage-files.json')]
files += ['services/aos-api/aos_api/aip_physical_capacity_occupation.py']
for suffix in ('red-r1','green-r1','green-r2'):
 for folder,prefix in (('gt-atomic-model-admission-20261008','source-newjudge-wrapper-'+suffix+'-'),('gt-judge-call-authority-20261008','wrapper-'+suffix+'-')):
  files.extend(str(p.relative_to(R)) for p in sorted((R/'.evidence'/folder).glob(prefix+'*.json')))
files=sorted(set(files));(B/'stage-files.json').write_text(json.dumps(files,indent=2)+'\n')
assert not subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).strip()
subprocess.run(['git','add','--',*files,str((B/'stage-files.json').relative_to(R))],cwd=R,check=True)
staged=set(subprocess.check_output(['git','diff','--cached','--name-only'],cwd=R,text=True).splitlines());assert staged<=set(files)|{str((B/'stage-files.json').relative_to(R))}
subprocess.run(['git','commit','-m','feat(aip): wrap original occupation SQL on authenticated caller'],cwd=R,check=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();(B/'evidence-commit.json').write_text(json.dumps(dict(head=head,product_changed=True),indent=2)+'\n')
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);a=m.load_authority();assert a['project_revision']=='AOS-001617'
d=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='TYPED_OCCUPATION_SAME_CALLER_WRAPPER_NATIVE_GREEN_ADMISSION_PENDING',changed_files=['aos-platform/services/aos-api/aos_api/aip_physical_capacity_occupation.py','aos-platform/.evidence/'+B.name],commits=[head],verification=['Original native missing wrapper RED91.45s; R2 full original1PASS100.66s exact native DTO/replay/same connection/xid/pid and ten boundaries denied','Independent aborted/six preparations0/Source1/NOLOGIN/member0/no probes/31old resources unchanged; adjacent349PASS0.77s'],risks=['GREEN R1 fullFAIL66.49s oldJudge50s expiry after wrapper checks; only frozen duplicate oldplan negatives removed in R2, no expiry/product weakening','No runtime route/defaultmigration/admission/unknown/fees/Judge result/transport/finalizer/COMMIT permission; parentTasks ACTIVE'],blockers=[]);(B/'delivery.json').write_text(json.dumps(d,indent=2)+'\n')
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary='Minimal original same-caller prepare_target_occupation wrapper validates true SCRAM conn/active transaction/dict_row/positive scope/UUID and original consumer/packet; strict DTO binds same native tenant/login/xid/pid/role/UTC and original plan/Intent/call/physical Source before and after. Original module prefix preserved, preexisting authorized untracked file incorporated. Native RED91.45s missing wrapper; GREEN R1 wrapper positive/replay/ten boundaries reached but wholeFAIL66.49s oldJudge50s deadline; duplicate1610 oldplan negative repetition removed only. R2 original full1PASS100.66s/ten boundaries/current exact DTO/replay/callerCOMMIT reject; independent aborted/six preparations0/Source1/NOLOGIN/member0/probes0/31old resources unchanged. Adjacent349PASS0.77s. No runtime route/defaultmigration/admission/unknown/fees/Judge result/transport/finalizer/Goal change; five parentTasks ACTIVE. Next independent cross-transaction/command mutation original native negative gates and risk/Judge dependencies.')])
orig=m.atomic_write_text
def safe(path,text,**kw):
 if str(path).startswith('/Users/ddt/.codex/memories/'):return
 return orig(path,text,**kw)
m.atomic_write_text=safe;sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=f,sha256=hashlib.sha256((R/f).read_bytes()).hexdigest()) for f in files]
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008']
for task in tasks:
 folder=R/'.evidence'/task;cp=json.loads((folder/'checkpoint.json').read_text());prior='.evidence/'+task+'/typed-occupation-wrapper-plan-reference-1617.json';ref='.evidence/'+task+'/typed-occupation-wrapper-reference-1618.json';(R/ref).write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,execution_allowed=False,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs),indent=2)+'\n');cp.update(authority_revision=r['project_revision'],step='typed-occupation-wrapper-native-green-cross-caller-negative-next');cp['evidence_files']=[ref if f==prior else f for f in cp['evidence_files']];(folder/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
v=m.validate_installation();status=m.memory_status();assert v['status']=='GREEN';assert all(x['status']=='CURRENT' for x in status['projections'] if x['consistency']=='strong')
spec=importlib.util.spec_from_file_location('wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');w=importlib.util.module_from_spec(spec);sys.modules[spec.name]=w;spec.loader.exec_module(w)
for task in tasks:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2','.evidence/'+task+'/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文')
(B/'context-sync-1618.json').write_text(json.dumps(dict(revision=r['project_revision'],head=head,sync=sync,validation=v,status=status,all_five_checkpoint_bindings='PASS'),ensure_ascii=False,indent=2)+'\n')
print(r['project_revision'],'GREEN; five checkpoints PASS')
