from pathlib import Path
import importlib.util,sys,json,hashlib,subprocess
B=Path(__file__).resolve().parent;R=B.parents[1]
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001676'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
n=json.loads((B/'native-r8/result-r8.json').read_text());assert n['pytest_exit']==0 and n['old_files_unchanged']
for p,h in n['file_hashes'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],
 completed=a['completed']+['Native same-caller original-description read post-row authentication expiry necessary gate: 334 DB-denied pure PASS and full fresh native R8 PASS159.66s, 8 negatives including actual expired-signature final Source rejection after real row/typed parsing in same xid/pid. Independent READONLY ABORTED/4 risk tables zero, exact SQL/closed ACL/frozen hashes. Product unchanged; no execution or trusted-root grant.'],
 incomplete=a['incomplete']+['Dedicated SourceTTL/approval withdrawal real race matrix and v3 same-caller identity bridge remain pending; real-time auth barrier is not PG row lock wait. R3/R4 full node approval expiry failures and R5/R6 preflight/R7 missing helper failures retained and reconciled, R8 fresh success does not extend old original deadlines. Root provenance/finaljoint/WAL-ACK/transport/formal business chain, historical summary beforeimages and Prime unknown unchanged.'],
 next_steps=['Continue registered v3 same native occupation caller identity/certificate original metadata readonly bridge; first file-level plan/Task/Lease and RED, preserve old v1/v2 and separate trusted-root/final-joint authority.']+a['next_steps'],
 source_commits={**a['source_commits'],'shared-parent-native-description-post-row-auth-expiry':head},
 evidence=a['evidence']+[dict(type='checkpoint',path=str(B/'expiry-review-1676.md'),summary='334 pure/fresh full native R8 actual post-row auth expiry; readonly aborted/zero risk/closed ACL; same-caller v3 identity and trusted-root/finaljoint pending')])
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010','gt-shared-parent-certificate-identity-20261010',B.name]
extra=[str((B/p).relative_to(R)) for p in ['expiry-review-1676.md','expiry-pure-result-r5-1676.json','native-r8/result-r8.json','native-r8/post-row-auth-expiry-proof.json','native-r8/native-origin-reader-proof.json','independent-readback-r8-expiry.json','failure-readback-r3.json','failure-readback-r4.json','failure-readback-r7.json','native-r5/preflight-failure.json','same-caller-identity-routing-audit-1676.json']]
for task in tasks:
 root=R/'.evidence'/task;cp=json.loads((root/'checkpoint.json').read_text());old=cp['evidence_files'][-1]
 assert old.endswith('current-shared-origin-reference-1676.json')
 path=root/'current-shared-expiry-reference-1677.json';refs=[old]+extra
 body=dict(authority_revision=r['project_revision'],task=task,head=head,execution_allowed=False,executors_authenticated=False,issuer_metadata_current=False,root_provenance_verified=False,original_native_row_observed=True,physical_description_origin_authenticated=False,full_task_delivered=False,historical_fixture_restored=False,references=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in refs])
 path.write_text(json.dumps(body,indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='native-description-post-row-auth-expiry-necessary-green-same-caller-v3-identity-bridge-next')
 cp['evidence_files'][-1]=str(path.relative_to(R));(root/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text
m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);v=m.validate_installation();assert v['status']=='GREEN'
(B/'context-sync-1677.json').write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,installation=v,memory_write_skipped=True,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False),indent=2)+'\n')
print(r['project_revision'],v['status'],head)
