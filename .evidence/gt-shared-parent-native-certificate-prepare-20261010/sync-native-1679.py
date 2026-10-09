from pathlib import Path
import importlib.util,sys,json,hashlib,subprocess
B=Path(__file__).resolve().parent;R=B.parents[1]
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001678'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
n=json.loads((B/'native-r11/result-r11.json').read_text());assert n['pytest_exit']==0 and n['old_files_unchanged']
for p,h in n['file_hashes'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
v8=json.loads((B/'independent-core-readback-r11.json').read_text());assert v8['whole_node_passed'] and not v8['execution_allowed'] and v8['verifier_permissions']['direct_c'] is False
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],
 completed=a['completed']+['Native replay identityVersion necessary gate: actual R9 RED, two-line reader change, 337 DB-denied pure PASS1.30s and final full native R11 PASS138.76s. Four persisted originals replayed same caller with identity versions 2-to-2 and unchanged complete metadata; canary and runtime direct verifier denied. External assertions prevent wrapped hook failures from false PASS. Independent READONLY risk ABORTED, nine tables zero, exact SQL/closed C ACL/current 12 hashes; actual COMMIT refused.'],
 incomplete=a['incomplete']+['Tasks9/10 ACTIVE without Delivery: other caller/old domain/withdrawal/dedicated final expiry matrix still pending. Replay occurs in controlled rollback savepoint and fresh full Python success uses independent new signed originals, no old TTL extension. Formal Root/finaljoint/WALACK/business pending; historical beforeimages and Prime UNKNOWN unchanged.'],
 next_steps=['Continue registered Tasks9/10 with dedicated genuine certificate final-expiry termination and separate fresh full adjacent positive; other-caller/old-domain/withdrawal and formal Root/finaljoint remain independent. No Source ACL widening or standalone metadata COMMIT workaround.']+a['next_steps'],
 source_commits={**a['source_commits'],'shared-parent-native-replay-version-boundaries-necessary':head},
 evidence=a['evidence']+[dict(type='checkpoint',path=str(B/'review-1678.md'),summary='337 pure/final full native R11; real replay version stability/canary/runtime denial, same caller cleanup/COMMIT refusal; formal Task/Root/business pending')])
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010','gt-shared-parent-certificate-identity-20261010','gt-shared-description-origin-reader-20261010','gt-shared-parent-native-executor-set-20261010',B.name]
extra=[str((B/p).relative_to(R)) for p in ['review-1678.md','implementation-plan.md','native-r11/result-r11.json','native-r11/native-same-transaction-prepare-proof.json','native-r11/native-description-proof.json','independent-core-readback-r11.json','pure-result-r6.json','lease-renewal-1678.json']]
for task in tasks:
 root=R/'.evidence'/task;cp=json.loads((root/'checkpoint.json').read_text());old=cp['evidence_files'][-1]
 path=root/'current-native-certificate-reference-1679.json';refs=[old]+extra
 body=dict(authority_revision=r['project_revision'],task=task,head=head,execution_allowed=False,root_provenance_verified=False,same_caller_metadata_necessary_verified=True,full_task_delivered=False,historical_fixture_restored=False,references=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in refs])
 path.open('x').write(json.dumps(body,indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='native-replay-version-boundaries-necessary-green-dedicated-real-final-expiry-next')
 cp['evidence_files'][-1]=str(path.relative_to(R));(root/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text
m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);v=m.validate_installation();assert v['status']=='GREEN'
(B/'context-sync-1679.json').write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,installation=v,memory_write_skipped=True,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False),indent=2)+'\n')
print(r['project_revision'],v['status'],head)
