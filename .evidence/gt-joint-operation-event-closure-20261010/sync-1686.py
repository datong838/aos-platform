from pathlib import Path
import importlib.util,sys,json,hashlib,subprocess
B=Path(__file__).resolve().parent;R=B.parents[1]
s=importlib.util.spec_from_file_location('mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001685'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
v=json.loads((B/'pure-result-r1.json').read_text());assert v['pytest_exit']==0 and v['database_connections']==0
for p,h in v['file_hashes'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
live=json.loads((B/'current-events-negative-r1.json').read_text());assert live['identity']['readonly']=='on' and live['real_catalog_negative']=='TRIGGER_EFFECT_REQUIRED'
fx=json.loads((B/'manual-effects-candidate-r1.json').read_text());assert fx['application_sql_contract_count']==15 and fx['real_catalog_rejection']=='TRIGGER_EFFECT_REQUIRED' and not fx['formal_installation_approved']
cb=json.loads((B/'fk-callbacks-summary-r1.json').read_text());assert cb['foreign_key_count']==712 and cb['operator_bindings']==6645 and not cb['non_pg_internal_callbacks']
assert hashlib.sha256((B/'fk-callbacks-r1.json').read_bytes()).hexdigest()==cb['exact_callback_file_sha256']
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],
 completed=a['completed']+['Operation-aware joint dependency component: FK check/read locks distinct from writes; actual action/mask propagation and exact reviewed function effects reach fixed point, unknown/drift/disabled/TRUNCATE policy rejects. RED module missing, 19 new+17 catalog+3 original prepare/reader PASS39/0.56s connections0. R22 READONLY exact 638 tables/712FK/3629triggers original candidate15 events direct27triggers9functions. 15 application SQL effect candidates reviewed, four native RI effects intentionally unapproved: installed catalog still TRIGGER_EFFECT_REQUIRED. READONLY6645 operator bindings use five pg_catalog/internal callbacks, no callback executed or binary trust inferred. Component Delivery only.'],
 incomplete=a['incomplete']+['Full original joint installation effects incomplete: kernel binary/provenance, FK types/casts/collations/indirect callbacks and approved exact contracts need audit. Candidate SQL effects, mask/action catalog and possible event closure are not actual database queue or legal joint finalizer. Original Source/budget/Intent/clock/WAL/Root/business remain pending.'],
 next_steps=['Continue registered Task10 full joint audit: read original FK column types/cast/collation bindings and exact installed native provenance; never auto-approve empty native effects. Integrate original Source/budget/unique Intent/final currentness/clock end contract then full native matrix; safe loop continues.']+a['next_steps'],
 source_commits={**a['source_commits'],'joint-operation-event-closure-component':head},
 evidence=a['evidence']+[dict(type='checkpoint',path=str(B/'review.md'),summary='39PASS zero connections; real event/action/mask catalog and manual SQL candidate audit strictly reject missing kernel contract')])
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008','gt-original-target-persisted-reader-20261010','gt-shared-parent-certificate-identity-20261010','gt-shared-description-origin-reader-20261010','gt-shared-parent-native-executor-set-20261010','gt-shared-parent-native-certificate-prepare-20261010']
delivery=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=r['project_revision'],result='JOINT_OPERATION_CLOSURE_COMPONENT_VERIFIED_NO_EXECUTION',changed_files=['aos-platform/'+p for p in json.loads((B/'stage-files.json').read_text())],commits=[head],verification=['19 new logic +17 prior catalogue +3 original adjacent PASS39/0.56s connections0, actual RED preserved','READONLY original exact actions/masks plus15 SQL candidates and6645 operator bindings; four kernel functions not silently approved, real catalog rejects missing effects'],risks=['Reviewed effect semantics/C binary/Owner ACL trust separate; conservative graph not actual event queue','Complete joint finalizer/Source clock/WAL ACK/formal Root/business pending'],blockers=[])
(B/'delivery.json').open('x').write(json.dumps(delivery,indent=2)+'\n')
extra=[str((B/p).relative_to(R)) for p in ['implementation-plan.md','review.md','pure-result-r1.json','current-events-negative-r1.json','manual-effects-candidate-r1.json','fk-callbacks-summary-r1.json','delivery.json']]

for task in tasks:
 root=R/'.evidence'/task;cp=json.loads((root/'checkpoint.json').read_text());old=cp['evidence_files'][-1]
 path=root/'current-native-certificate-reference-1686.json';refs=[old]+extra
 body=dict(authority_revision=r['project_revision'],task=task,head=head,execution_allowed=False,root_provenance_verified=False,same_caller_metadata_necessary_verified=True,full_task_delivered=False,historical_fixture_restored=False,references=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in refs])
 path.open('x').write(json.dumps(body,indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='joint-operation-event-closure-delivered-kernel-cast-collation-full-joint-next')
 cp['evidence_files'][-1]=str(path.relative_to(R));(root/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
orig=m.atomic_write_text
m.atomic_write_text=lambda p,t,**kw:None if str(p).startswith('/Users/ddt/.codex/memories/') else orig(p,t,**kw)
m.sync_projections(apply=True,include_prime=True);v=m.validate_installation();assert v['status']=='GREEN'
(B/'context-sync-1686.json').write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,installation=v,memory_write_skipped=True,execution_allowed=False,full_task_delivered=False,historical_fixture_restored=False),indent=2)+'\n')
print(r['project_revision'],v['status'],head)
