from pathlib import Path
import importlib.util,sys,json,hashlib,subprocess
B=Path(__file__).resolve().parent;R=B.parents[1]
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001682'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
for node,readback,key in [('r21','independent-reader-first-withdrawal-readback-r21.json','reader_first_race_verified'),('r22','independent-pending-writer-withdrawal-readback-r22.json','pending_writer_race_verified')]:
 n=json.loads((B/('native-'+node)/('result-'+node+'.json')).read_text());assert n['pytest_exit']==0 and n['old_files_unchanged']
 for p,h in n['file_hashes'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
 v=json.loads((B/readback).read_text());assert v[key] and v['whole_termination_node_passed'] and v['statuses']['risk']=='aborted' and not v['execution_allowed']
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],
 completed=a['completed']+['Original identity withdrawal bidirectional native race necessary gates PASS: R21 reader-first full v3 prepare/reader then actual pg_blocking_pids observes immutable withdrawal writer waiting; risk COMMIT refused/ABORT releases locks, writer legal COMMIT and fresh private identity rejects. R22 pending-writer-first actual reader blocking observed before writer COMMIT; original canonical v3 SQL strictly 40001, savepoint clean/same caller retained, risk COMMIT refused/ABORT and fresh private identity rejects. Full nodes PASS111.13s and PASS84.09s. Independent READONLY confirms exact preserved legacy immutable history/head2/2/inactive/current risk metadata zero/closed ACL/current twelve hashes. Product unchanged.'],
 incomplete=a['incomplete']+['Tasks9/10 remain ACTIVE/no Delivery despite R21/R22 necessary race gates. Formal trusted Root, complete original joint finalizer, actual COMMIT/WAL ACK interval and natural business chain remain pending. R21/R22 fresh private reads are not fresh full v3 risk attempts; R19 separately proves new-v3 post-withdrawal termination.'],
 next_steps=['Continue original joint finalizer contract audit: exact budget fact bridges, actual write order/deferred queue and final currentness/clock decision; complete scoped plan/Task before code. No trigger bypass or experiment Root trust.']+a['next_steps'],
 source_commits={**a['source_commits'],'shared-parent-native-bidirectional-withdrawal-race-necessary':head},
 evidence=a['evidence']+[dict(type='checkpoint',path=str(B/'identity-withdrawal-race-review-1682.md'),summary='R21/R22 real native withdrawal race orders/full nodes and independent READONLY PASS; formal Root/finaljoint/business pending')])
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010','gt-shared-parent-certificate-identity-20261010','gt-shared-description-origin-reader-20261010','gt-shared-parent-native-executor-set-20261010',B.name]
extra=[str((B/p).relative_to(R)) for p in ['identity-withdrawal-race-review-1682.md','reader-first-withdrawal-plan-1682.md','pending-writer-withdrawal-plan-1682.md','native-r21/result-r21.json','native-r21/reader-first-withdrawal-proof.json','independent-reader-first-withdrawal-readback-r21.json','native-r22/result-r22.json','native-r22/pending-writer-serialization-proof.json','native-r22/pending-writer-withdrawal-proof.json','independent-pending-writer-withdrawal-readback-r22.json']]
for task in tasks:
 root=R/'.evidence'/task;cp=json.loads((root/'checkpoint.json').read_text());old=cp['evidence_files'][-1]
 path=root/'current-native-certificate-reference-1683.json';refs=[old]+extra
 body=dict(authority_revision=r['project_revision'],task=task,head=head,execution_allowed=False,root_provenance_verified=False,same_caller_metadata_necessary_verified=True,full_task_delivered=False,historical_fixture_restored=False,references=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in refs])
 path.open('x').write(json.dumps(body,indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='bidirectional-native-identity-withdrawal-race-necessary-green-original-joint-finalizer-next')
 cp['evidence_files'][-1]=str(path.relative_to(R));(root/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text
m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);v=m.validate_installation();assert v['status']=='GREEN'
(B/'context-sync-1683.json').write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,installation=v,memory_write_skipped=True,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False),indent=2)+'\n')
print(r['project_revision'],v['status'],head)
