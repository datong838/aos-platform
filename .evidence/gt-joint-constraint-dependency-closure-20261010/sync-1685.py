from pathlib import Path
import importlib.util,sys,json,hashlib,subprocess
B=Path(__file__).resolve().parent;R=B.parents[1]
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001684'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
v=json.loads((B/'pure-result-r2.json').read_text());assert v['pytest_exit']==0 and v['database_connections']==0
for p,h in v['file_hashes'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
live=json.loads((B/'current-catalog-negative-summary-r1.json').read_text());assert live['identity']['readonly']=='on' and live['actual_current_catalog_rejection']=='TRIGGER_EFFECT_REQUIRED'
assert hashlib.sha256((B/'current-catalog-negative-r1.json').read_bytes()).hexdigest()==live['exact_catalog_file_sha256']
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],
 completed=a['completed']+['Joint end-protocol dependency closure component implemented: immutable exact catalog, bidirectional multi-hop FK and reviewed exact function-hash write effects iterated to fixed point, unknown/disabled/drift/missing effect rejects; cycles stable and no SQL/execution grant. RED missing module, first default conftest setup connection refused no effect preserved, noconftest forbidden-connect 17 new +3 original adjacent PASS20/0.55s connections0. Current retained R22 READONLY catalog 638 relations/712 FK/3629 triggers strictly TRIGGER_EFFECT_REQUIRED without audited effects; original raw catalog hash bound. Scoped component Delivery only, full joint/event queue/Root/business pending.'],
 incomplete=a['incomplete']+['Exact installed trigger-effect contracts for full related FK component still missing; conservative catalog closure is not actual transaction event queue, binary provenance, semantic review, final currentness or lawful joint COMMIT. Finalizer/Root/WAL ACK/business unchanged pending.'],
 next_steps=['Continue complete joint protocol installation contract: enumerate related original FK component and each real trigger function body/Owner/library identity, review actual written relations/effects and pin immutable hashes. No empty effect approvals or inferred dynamic writes; then integrate Source/budget/Intent/currentness/clock and native end matrix.']+a['next_steps'],
 source_commits={**a['source_commits'],'joint-constraint-dependency-closure-component':head},
 evidence=a['evidence']+[dict(type='checkpoint',path=str(B/'review.md'),summary='Pure exact dependency closure component 20PASS and installed catalogue negative; full joint remains pending')])
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010','gt-shared-parent-certificate-identity-20261010','gt-shared-description-origin-reader-20261010','gt-shared-parent-native-executor-set-20261010','gt-shared-parent-native-certificate-prepare-20261010']
delivery=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=r['project_revision'],result='JOINT_CATALOG_CLOSURE_COMPONENT_VERIFIED_NO_EXECUTION',changed_files=['aos-platform/'+p for p in json.loads((B/'stage-files.json').read_text())],commits=[head],verification=['17 new logic and 3 original adjacent tests PASS20/0.55s, connections0, RED and failed default DB setup preserved','Installed R22 READONLY exact catalog 638 tables/712FK/3629triggers rejects unreviewed effects'],risks=['Reviewed effect semantics/C binary/Owner ACL trust separate; conservative graph not actual event queue','Complete joint finalizer/Source clock/WAL ACK/formal Root/business pending'],blockers=[])
(B/'delivery.json').open('x').write(json.dumps(delivery,indent=2)+'\n')
extra=[str((B/p).relative_to(R)) for p in ['implementation-plan.md','review.md','pure-result-r2.json','current-catalog-negative-summary-r1.json','delivery.json']]

for task in tasks:
 root=R/'.evidence'/task;cp=json.loads((root/'checkpoint.json').read_text());old=cp['evidence_files'][-1]
 path=root/'current-native-certificate-reference-1685.json';refs=[old]+extra
 body=dict(authority_revision=r['project_revision'],task=task,head=head,execution_allowed=False,root_provenance_verified=False,same_caller_metadata_necessary_verified=True,full_task_delivered=False,historical_fixture_restored=False,references=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in refs])
 path.open('x').write(json.dumps(body,indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='joint-catalog-closure-component-delivered-real-trigger-effects-full-joint-next')
 cp['evidence_files'][-1]=str(path.relative_to(R));(root/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text
m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);v=m.validate_installation();assert v['status']=='GREEN'
(B/'context-sync-1685.json').write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,installation=v,memory_write_skipped=True,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False),indent=2)+'\n')
print(r['project_revision'],v['status'],head)
