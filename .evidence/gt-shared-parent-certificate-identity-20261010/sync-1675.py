from pathlib import Path
import importlib.util,sys,json,hashlib,subprocess
B=Path(__file__).resolve().parent;R=B.parents[1]
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001674'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
n=json.loads((B/'native-r6/result-r6.json').read_text());assert n['pytest_exit']==0 and n['old_files_unchanged']
for p,h in n['file_hashes'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],
 completed=a['completed']+['Separate private immutable v3 shared-parent certificate identity metadata gate: persisted canonical full manifest/root/certificate, original global identity withdrawal, root-certificate-identity locks and post-wait real-time verification. 333 DB-denied pure PASS; full fresh native node R6 PASS/20 negatives; registration savepoint failure followed by actual caller COMMIT leaves no binding/version change, real dual wait graph frozen. Necessary isolated metadata only, no execution permission.'],
 incomplete=a['incomplete']+['V3 identity metadata does not authenticate root bootstrap provenance or current native physical prepared description/caller. Final current Source/approval/joint, actual token and strict WAL/ACK/transport remain pending. R1/R2/R5 failures retained; R3/R4 historical source frozen; historical two summary before-images unavailable and Prime unknown unchanged.'],
 next_steps=['Investigate registered current physical prepared-description row/caller necessary bridge and trusted-root bootstrap provenance without granting execution; actual token and final joint retain real-input and strict-time dependencies.']+a['next_steps'],
 source_commits={**a['source_commits'],'shared-parent-v3-identity-metadata':head},
 evidence=a['evidence']+[dict(type='checkpoint',path=str(B/'review.md'),summary='333 pure/full native 20 negatives and real registration-failure COMMIT zero binding; private metadata only, bootstrap/native physical origin/joint remain pending, no Delivery')])
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010',B.name]
extra=[str((B/p).relative_to(R)) for p in ['review.md','pure-result.json','native-r6/result-r6.json','native-r6/native-identity-proof.json','native-r6/dual-wait-graph.json','independent-readback-r6.json']]
for task in tasks:
 root=R/'.evidence'/task;cp=json.loads((root/'checkpoint.json').read_text());old=cp['evidence_files'][-1]
 assert old.endswith('current-shared-certificate-reference-1674.json') or (task==B.name and old.endswith('task.json'))
 path=root/'current-shared-identity-reference-1675.json';refs=[old]+extra
 body=dict(authority_revision=r['project_revision'],task=task,head=head,execution_allowed=False,executors_authenticated=False,issuer_metadata_current=False,root_provenance_verified=False,physical_description_origin_authenticated=False,full_task_delivered=False,historical_fixture_restored=False,references=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in refs])
 path.write_text(json.dumps(body,indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='v3-identity-metadata-necessary-green-native-physical-origin-root-provenance-next')
 cp['evidence_files'][-1]=str(path.relative_to(R));(root/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text
m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);v=m.validate_installation();assert v['status']=='GREEN'
(B/'context-sync-1675.json').write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,installation=v,memory_write_skipped=True,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False),indent=2)+'\n')
print(r['project_revision'],v['status'],head)
