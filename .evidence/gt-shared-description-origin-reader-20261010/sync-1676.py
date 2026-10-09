from pathlib import Path
import importlib.util,sys,json,hashlib,subprocess
B=Path(__file__).resolve().parent;R=B.parents[1]
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001675'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
n=json.loads((B/'native-r2/result-r2.json').read_text());assert n['pytest_exit']==0 and n['old_files_unchanged']
for p,h in n['file_hashes'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],
 completed=a['completed']+['Original physical full shared-parent description native same-caller readonly necessary bridge, with canonical full row/hash/origin and before-after Source/Owner currentness. 334 DB-denied pure PASS; new independent 300s authentication native full node R2 PASS with 7 negatives, original actual COMMIT rejection and independent aborted/4 risk tables zero; SQL body/hash/closed ACL exact. No issuer/root or execution grant.'],
 incomplete=a['incomplete']+['Dedicated new origin-reader real wait across Source/approval expiry and withdrawal race matrix remains pending; adjacent guard race is not its substitute. Original native risk row observed only within its caller transaction; independent issuer metadata cannot become same-caller joint. Root bootstrap/identity bridge/real token/WAL-ACK/transport/formal natural chain remain pending. R1 complete-node authentication expiry and teardown failure retained, fresh R2 does not extend old authentication; historical two summary before-images and Prime unknown unchanged.'],
 next_steps=['Continue registered original-description reader real post-wait Source/approval expiry and withdrawal matrix; then same native caller identity/certificate necessary bridge under original ordered locks, preserving independent trusted-root provenance and final joint boundaries.']+a['next_steps'],
 source_commits={**a['source_commits'],'shared-parent-native-description-origin-reader':head},
 evidence=a['evidence']+[dict(type='checkpoint',path=str(B/'review.md'),summary='334 pure/fresh full native and exact original caller row; 7 negatives and independent ABORTED/zero risk; dedicated expiry races and same-caller identity/root/joint pending')])
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010','gt-shared-parent-certificate-identity-20261010',B.name]
extra=[str((B/p).relative_to(R)) for p in ['review.md','pure-result.json','native-r2/result-r2.json','native-r2/native-origin-reader-proof.json','native-r2/new-authentication-window.json','independent-readback-r2.json','failure-readback-r1.json']]
for task in tasks:
 root=R/'.evidence'/task;cp=json.loads((root/'checkpoint.json').read_text());old=cp['evidence_files'][-1]
 assert old.endswith('current-shared-identity-reference-1675.json') or (task==B.name and old.endswith('task.json'))
 path=root/'current-shared-origin-reference-1676.json';refs=[old]+extra
 body=dict(authority_revision=r['project_revision'],task=task,head=head,execution_allowed=False,executors_authenticated=False,issuer_metadata_current=False,root_provenance_verified=False,original_native_row_observed=True,physical_description_origin_authenticated=False,full_task_delivered=False,historical_fixture_restored=False,references=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in refs])
 path.write_text(json.dumps(body,indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='native-original-description-reader-necessary-green-dedicated-source-expiry-and-identity-bridge-next')
 cp['evidence_files'][-1]=str(path.relative_to(R));(root/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text
m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);v=m.validate_installation();assert v['status']=='GREEN'
(B/'context-sync-1676.json').write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,installation=v,memory_write_skipped=True,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False),indent=2)+'\n')
print(r['project_revision'],v['status'],head)
