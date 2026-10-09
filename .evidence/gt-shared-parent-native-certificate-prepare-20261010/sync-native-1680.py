from pathlib import Path
import importlib.util,sys,json,hashlib,subprocess
B=Path(__file__).resolve().parent;R=B.parents[1]
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001679'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
n=json.loads((B/'native-r15/result-r15.json').read_text());assert n['pytest_exit']==0 and n['old_files_unchanged']
for p,h in n['file_hashes'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
v8=json.loads((B/'independent-core-readback-r15.json').read_text());assert v8['whole_node_passed'] and not v8['execution_allowed'] and v8['verifier_permissions']['direct_c'] is False
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],
 completed=a['completed']+['Dedicated real final certificate expiry necessary gate: R14 four genuine validations followed by real PG clock crossing original certificate end, fifth original product validation rejected without clock or checked_at substitution. Savepoint Manifest cleanup and same caller live proved; independent READONLY risk ABORTED/nine tables zero/current twelve hashes. R14 full node FAILED at old Judge deadline retained. Separate fresh DB/Source/Root/approval/certificates R15 complete native PASS146.76s plus independent exact SQL/closed ACL/twelve hashes and actual COMMIT refusal. Product unchanged; same frozen pure337 result reused.'],
 incomplete=a['incomplete']+['Tasks9/10 ACTIVE without Delivery: non-native caller/old domain/withdrawal still pending. Dedicated termination and independent fresh full adjacent are separate proofs, not one extended old approval. R12 missing fixture and R13 erroneous legacy error assertion retained FAILED; R14 bounded expiry passed but whole failed. Formal Root/finaljoint/WALACK/business pending; historical beforeimages and Prime UNKNOWN unchanged.'],
 next_steps=['Continue registered Tasks9/10 non-native physical caller and old signing-domain negative matrix, then visible identity withdrawal/formal Root/finaljoint independently; no unknown result replay, old approval extension or Source ACL widening.']+a['next_steps'],
 source_commits={**a['source_commits'],'shared-parent-native-dedicated-final-expiry-necessary':head},
 evidence=a['evidence']+[dict(type='checkpoint',path=str(B/'final-expiry-review-1679.md'),summary='R14 bounded real final expiry passed with whole failure retained; separate fresh R15 full native passed/readback; formal Task/Root/business pending')])
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010','gt-shared-parent-certificate-identity-20261010','gt-shared-description-origin-reader-20261010','gt-shared-parent-native-executor-set-20261010',B.name]
extra=[str((B/p).relative_to(R)) for p in ['final-expiry-review-1679.md','implementation-plan.md','native-r15/result-r15.json','native-r15/native-same-transaction-prepare-proof.json','native-r15/native-description-proof.json','independent-core-readback-r15.json','pure-result-r6.json','independent-final-expiry-readback-r14.json','final-expiry-plan-1679.md','native-r14/dedicated-final-expiry-proof.json','expiry-terminal-and-adjacent-boundary-r14.json']]
for task in tasks:
 root=R/'.evidence'/task;cp=json.loads((root/'checkpoint.json').read_text());old=cp['evidence_files'][-1]
 path=root/'current-native-certificate-reference-1680.json';refs=[old]+extra
 body=dict(authority_revision=r['project_revision'],task=task,head=head,execution_allowed=False,root_provenance_verified=False,same_caller_metadata_necessary_verified=True,full_task_delivered=False,historical_fixture_restored=False,references=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in refs])
 path.open('x').write(json.dumps(body,indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='dedicated-real-final-expiry-and-independent-fresh-native-necessary-green-other-caller-old-domain-next')
 cp['evidence_files'][-1]=str(path.relative_to(R));(root/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text
m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);v=m.validate_installation();assert v['status']=='GREEN'
(B/'context-sync-1680.json').write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,installation=v,memory_write_skipped=True,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False),indent=2)+'\n')
print(r['project_revision'],v['status'],head)
