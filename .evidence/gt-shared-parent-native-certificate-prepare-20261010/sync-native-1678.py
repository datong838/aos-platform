from pathlib import Path
import importlib.util,sys,json,hashlib,subprocess
B=Path(__file__).resolve().parent;R=B.parents[1]
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001677'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
n=json.loads((B/'native-r8/result-r8.json').read_text());assert n['pytest_exit']==0 and n['old_files_unchanged']
for p,h in n['file_hashes'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
v8=json.loads((B/'independent-core-readback-r8.json').read_text());assert v8['whole_node_passed'] and not v8['execution_allowed'] and v8['verifier_permissions']['direct_c'] is False
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],
 completed=a['completed']+['Same native physical SERIAL v3 executor-set metadata necessary gate: 337 DB-denied pure PASS1.29s and fresh full original native R8 PASS136.36s. Four certificate/root originals same xid38002/pid53829, five direct SQL negative cases, caught post-write Python savepoint cleanup, actual risk COMMIT refusal; independent READONLY aborted/9 risk-metadata tables zero, exact four SQL bodies/closed ACL/12 source hashes. Source pinned original C ACL preserved by narrow pure verifier delegation; runtime/Model direct C/schema grants absent.'],
 incomplete=a['incomplete']+['Tasks9/10 ACTIVE without Delivery: replay version/canary/other caller/old domain/withdrawal/final expiry dedicated real matrix pending. Same-caller staging observation is not trusted Root, finaljoint/WALACK/transport or formal business chain. R1-R7 actual failures retained; R6/7 core success did not make their whole Source adjacent nodes PASS, R7 exact C ACL drift corrected without weakening Source audit. Historical summary beforeimages and Prime UNKNOWN unchanged.'],
 next_steps=['Continue registered native executor-set/prepare Tasks: add exact savepoint replay-version and canary/non-native caller matrix, then genuine withdrawal/final expiry and independent formal Root/final joint route; no standalone metadata COMMIT workaround or Source ACL widening.']+a['next_steps'],
 source_commits={**a['source_commits'],'shared-parent-native-certificate-prepare-necessary':head},
 evidence=a['evidence']+[dict(type='checkpoint',path=str(B/'review-1677.md'),summary='337 pure/fresh complete native R8; same caller staging/cleanup/COMMIT denial, Source C ACL preserved; full Task/Root/business pending')])
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010','gt-shared-parent-certificate-identity-20261010','gt-shared-description-origin-reader-20261010','gt-shared-parent-native-executor-set-20261010',B.name]
extra=[str((B/p).relative_to(R)) for p in ['review-1677.md','implementation-plan.md','native-r8/result-r8.json','native-r8/native-same-transaction-prepare-proof.json','native-r8/native-description-proof.json','independent-core-readback-r8.json','pure-result-r4.json','source-verifier-acl-root-cause-r7.json']]
for task in tasks:
 root=R/'.evidence'/task;cp=json.loads((root/'checkpoint.json').read_text());old=cp['evidence_files'][-1]
 path=root/'current-native-certificate-reference-1678.json';refs=[old]+extra
 body=dict(authority_revision=r['project_revision'],task=task,head=head,execution_allowed=False,root_provenance_verified=False,same_caller_metadata_necessary_verified=True,full_task_delivered=False,historical_fixture_restored=False,references=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in refs])
 path.open('x').write(json.dumps(body,indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='same-native-v3-certificate-metadata-necessary-green-replay-canary-withdrawal-final-expiry-matrix-next')
 cp['evidence_files'][-1]=str(path.relative_to(R));(root/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text
m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);v=m.validate_installation();assert v['status']=='GREEN'
(B/'context-sync-1678.json').write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,installation=v,memory_write_skipped=True,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False),indent=2)+'\n')
print(r['project_revision'],v['status'],head)
