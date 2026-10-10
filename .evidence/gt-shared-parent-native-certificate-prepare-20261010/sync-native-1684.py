from pathlib import Path
import importlib.util,sys,json,hashlib,subprocess
B=Path(__file__).resolve().parent;R=B.parents[1]
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001683'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
v=json.loads((B/'joint-finalizer-current-audit-1683.json').read_text());assert v['identity']['readonly']=='on' and not v['actual_event_queue_proven'] and not v['execution_allowed'] and not v['finalizer_implemented']
for p,h in v['input_hashes'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],
 completed=a['completed']+['Original joint finalizer current dependency audit: R22 owned retained DB READONLY catalog 37 application/105 internal deferred entries, exact source eight hashes and static call order; three risk tables have direct unconditional deny guards, target Intent has FK execution_intent -> case_input_binding -> parent_debit rather than its own deferred deny. R1/R2 wrong direct-guard/FK assumptions failed and preserved, R3 current two-hop catalog assertion passed. Catalog is not actual event queue, product unchanged/no business effect.'],
 incomplete=a['incomplete']+['Prior assertion that all four risk tables each have their own deferred deny trigger corrected: only parent_debit/plan_risk/shared_description directly guarded in R22; target Intent indirect same-caller parent guard must be proven per complete joint protocol. Full installed constraint dependency closure/actual event queue/finalizer/WAL ACK/trusted Root/business still pending.'],
 next_steps=['Continue scoped complete joint end-protocol design: map actual written relations and recursive FK/trigger dependencies to exact installed catalog/Owners/body hashes and native caller; register exact product Task/Lease before implementing a fail-closed dependency validator. Do not bypass current deny guards or infer event queue from catalog.']+a['next_steps'],
 source_commits={**a['source_commits'],'shared-parent-native-joint-dependency-audit':head},
 evidence=a['evidence']+[dict(type='checkpoint',path=str(B/'joint-finalizer-audit-review-1683.md'),summary='Current READONLY catalog and two-hop Intent dependencies; previous direct guard claim corrected; actual joint event queue/finalizer pending')])
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010','gt-shared-parent-certificate-identity-20261010','gt-shared-description-origin-reader-20261010','gt-shared-parent-native-executor-set-20261010',B.name]
extra=[str((B/p).relative_to(R)) for p in ['joint-finalizer-audit-plan-1683.md','joint-finalizer-audit-review-1683.md','joint-finalizer-current-audit-1683.json','joint-finalizer-audit-failure-r1-1683.json','joint-finalizer-audit-failure-r2-1683.json']]
for task in tasks:
 root=R/'.evidence'/task;cp=json.loads((root/'checkpoint.json').read_text());old=cp['evidence_files'][-1]
 path=root/'current-native-certificate-reference-1684.json';refs=[old]+extra
 body=dict(authority_revision=r['project_revision'],task=task,head=head,execution_allowed=False,root_provenance_verified=False,same_caller_metadata_necessary_verified=True,full_task_delivered=False,historical_fixture_restored=False,references=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in refs])
 path.open('x').write(json.dumps(body,indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='joint-finalizer-readonly-dependency-audit-guard-claims-corrected-actual-event-closure-next')
 cp['evidence_files'][-1]=str(path.relative_to(R));(root/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text
m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);v=m.validate_installation();assert v['status']=='GREEN'
(B/'context-sync-1684.json').write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,installation=v,memory_write_skipped=True,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False),indent=2)+'\n')
print(r['project_revision'],v['status'],head)
