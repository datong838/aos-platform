"""Exact test-only migration compatibility stage; preserve original fixture diff."""
import json, hashlib, subprocess, importlib.util, sys
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True)
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
m=mod('stage_memory',R/'scripts/memory/memoryctl.py');a=m.load_authority()
assert a['project_revision']=='AOS-001633' and git('rev-parse','HEAD').strip()=='94a8182b5e8bd5c7fc8ddc753d7779d707080094'
assert not git('diff','--cached','--name-only').strip()
p=json.loads((B/'independent-domains-verification.json').read_text());assert p['all_selected_passed'] and p['node_count']==p['database_count']==27 and p['old_resources_unchanged']
for x in json.loads((B/'input-bindings-r3.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
parents=('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008')
for tid in (B.name,'gt-capacity-source-publication-20261006',*parents):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());assert t['status']=='ACTIVE' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
 assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists()
test='services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py';indexed=git('show','HEAD:'+test)
old1='        for profile in (native.CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,native.CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL):\n            owner.execute(profile)'
old2='        for profile in (native.CAPACITY_SOURCE_CANDIDATE_PROFILE_SQL,native.CAPACITY_ORIGINAL_APPLICATION_PROFILE_SQL,\n                        native.CAPACITY_ORIGINAL_CANDIDATES_PROFILE_SQL):owner.execute(profile)'
new='        from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions\n        require_source_transaction_functions(owner)'
for old in (old1,old2):assert indexed.count(old)==1;indexed=indexed.replace(old,new)
anchor="        'test_native_signed_supplier_combination_keeps_original_approved_terms',\n";assert indexed.count(anchor)==1
indexed=indexed.replace(anchor,anchor+"        'test_native_source_window_requires_original_request_allocation_and_basis',\n")
sha=subprocess.check_output(['git','hash-object','-w','--stdin'],cwd=R,input=indexed.encode()).decode().strip()
subprocess.run(['git','update-index','--cacheinfo','100644,'+sha+','+test],cwd=R,check=True)
assert git('diff','--numstat','--',test).split()[:2]==['6','1']
files=[str(x.relative_to(R)) for x in sorted(B.iterdir()) if x.is_file()]+['.evidence/gt-capacity-source-publication-20261006/plan.md']
subprocess.run(['git','add','--',*files],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(files+[test])
subprocess.run(['git','commit','-m','test(aip): audit migrated Source profiles in original domain matrix'],cwd=R,check=True);head=git('rev-parse','HEAD').strip()
delivery=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='BOUNDED_SIGNED_DOMAIN_MATRIX_NATIVE_VERIFIED_FULL_SOURCE_PENDING',changed_files=[x for x in files if x.startswith(str(B.relative_to(R))+'/')],commits=[head],verification=['Final full original three-function matrix 27 passes/27 independent retained databases, original exact signed scope/supplier/window positive and negative assertions','Independent unchanged product hashes, original role/interface cleanup and all31 old resources checked'],risks=['Full Source public issuance/COMMIT/current-consumer all exit requirements remain separate','Actual final COMMIT wall-clock counterexample unresolved','No independent model review result'],blockers=[])
summary='Original S17-S19 cumulative native scope/supplier/window matrix: r1 1pass26fail DuplicateFunction before target SQL, current157 exact installed functions independently audited. Two original tests replace redundant strict CREATE profiles with existing complete function/ACL/lock audit; window added to per-node isolation. r2 27pass but24DB limitation retained; final r3 27pass/27fresh retainedDB independently verified. Original assertions intact, only5add4del test changes selectively committed; prior fixture6add1del remains unstaged. No product/currentDB/runtime/business effects. Bounded matrix evidence Task delivered; original Source and parent Tasks ACTIVE, full S01-S20/actualCOMMIT clock/model-review/first-chain pending.'
u=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary=summary)])
orig=m.atomic_write_text;m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=str(x.relative_to(R)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (B/'review.md',B/'independent-domains-verification.json',B/'test-changes.json',B/'duplicate-profile-readonly-diagnosis.json',B/'scope-review.json')];paths=[]
for tid in parents:
 cpf=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(cpf.read_text());prior=f'.evidence/{tid}/current-source-full-core-reference-1633.json';new=f'.evidence/{tid}/current-source-signed-domains-reference-1634.json';assert prior in cp['evidence_files']
 (R/new).write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2));cp.update(authority_revision=u['project_revision'],step='original-signed-domain-matrix-native-verified-full-source-and-final-clock-pending');cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];cpf.write_text(json.dumps(cp,indent=2));paths.extend([new,str(cpf.relative_to(R))])
assert m.validate_installation()['status']=='GREEN';assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
w=mod('stage_wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');snapshots={tid:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2',f'.evidence/{tid}/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文') for tid in parents}
(B/'context-delivery-sync.json').write_text(json.dumps(dict(authority_revision=u['project_revision'],evidence_commit=head,delivery=delivery,sync=sync,checkpoints=snapshots,original_source_task='ACTIVE',full_source_delivery=False,goal_status_changed=False),indent=2));paths.append(str((B/'context-delivery-sync.json').relative_to(R)))
subprocess.run(['git','add','--',*paths],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): record original signed domain matrix and remaining gates'],cwd=R,check=True)
print(u['project_revision'],'ORIGINAL_DOMAIN_MATRIX_VERIFIED_FULL_SOURCE_PENDING')
