"""Exact test-only migration compatibility stage; preserve original fixture diff."""
import json, hashlib, subprocess, importlib.util, sys
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True)
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
m=mod('stage_memory',R/'scripts/memory/memoryctl.py');a=m.load_authority()
assert a['project_revision']=='AOS-001634' and git('rev-parse','HEAD').strip()=='463b466ee2b0aea169894f7cf141d13a323ad3e8'
assert not git('diff','--cached','--name-only').strip()
p=json.loads((B/'independent-final-verification.json').read_text());assert p['all_selected_passed'] and p['node_count']==44 and p['database_count']>=3 and p['old_resources_unchanged']
for x in json.loads((B/'input-bindings-r9.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
parents=('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008')
for tid in (B.name,'gt-capacity-source-publication-20261006',*parents):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());assert t['status']=='ACTIVE' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
 assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists()
test='services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py';indexed=git('show','HEAD:'+test)
working=(R/test).read_text()
first='def test_private_native_publication_rejects_missing_original_bytes('
next_fn='def test_native_verifier_and_private_scram_share_one_isolated_database('
dec="@pytest.mark.parametrize('native_original_fact_reader',['shared','distinct'],indirect=True)\n"
hs=indexed.index(first);he=indexed.index(next_fn,hs);ws=working.index(dec+first);we=working.index(next_fn,ws)
indexed=indexed[:hs]+working[ws:we]+indexed[he:]
anchor='    registered_cases = {\n';assert indexed.count(anchor)==1
indexed=indexed.replace(anchor,anchor+"        'test_private_native_publication_rejects_missing_original_bytes',\n")
old_helper='    from aos_api.aip_provider_capacity_publication_store import CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL\n    owner.execute(CAPACITY_ORIGINAL_WITHDRAWAL_BOUNDARY_SQL)'
new_helper='    from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions\n    require_source_transaction_functions(owner)'
assert indexed.count(old_helper)==1;indexed=indexed.replace(old_helper,new_helper)
old_count='        assert owner.execute("SELECT count(*) AS n FROM pg_proc WHERE pronamespace=\'aos_capacity_publication_private\'::regnamespace AND proname=ANY(%s)",(names,)).fetchone()[\'n\']==0'
assert indexed.count(old_count)==1;indexed=indexed.replace(old_count,old_count[:-1]+'3\n        _install_original_withdrawal_audit(owner)')
sha=subprocess.check_output(['git','hash-object','-w','--stdin'],cwd=R,input=indexed.encode()).decode().strip()
subprocess.run(['git','update-index','--cacheinfo','100644,'+sha+','+test],cwd=R,check=True)
assert git('diff','--numstat','--',test).split()[:2]==['6','1']
files=[str(x.relative_to(R)) for x in sorted(B.iterdir()) if x.is_file()]+['.evidence/gt-capacity-source-publication-20261006/plan.md']
subprocess.run(['git','add','--',*files],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(files+[test])
subprocess.run(['git','commit','-m','test(aip): exercise real public Source entry and audit migrated withdrawal guards'],cwd=R,check=True);head=git('rev-parse','HEAD').strip()
delivery=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='WHOLE_SUITE_FIRST_GATES_NATIVE_REPAIRED_FULL_SOURCE_PENDING',changed_files=[x for x in files if x.startswith(str(B.relative_to(R))+'/')],commits=[head],verification=['Whole original suite inventory 101 functions/381 initial nodes,382 after explicit first-test layouts; full selection failed first missing public installation then next duplicated audit helper; failures and unexecuted nodes retained','Final 44 original entry/withdrawal adjacent nodes plus earlier unchanged Owner15 nodes, precise input versions; independent publication rollback/roles/interfaces/current definitions/protected31 resources'],risks=['Full Source public issuance/COMMIT/current-consumer all exit requirements remain separate','Actual final COMMIT wall-clock counterexample unresolved','No independent model review result'],blockers=[])
summary='Whole original Source suite current inventory101functions/381initial nodes,382after explicit layouts, complete selection/maxfail1 no hidden skips. First native RED42883 from old fixture defaultprivate migration; original first missingbytes test now actual complete public fixture, exact same original signed materials/SCRAM/checker, legal prepare rollback control and only malformedraw with validpermit/native22023. Two layouts pass; r3 mixed-layout test wiring failure retained/fixed. Next whole4pass1fail duplicate migrated withdrawal audit before fault; shared helper now full existing function/ACL/lock audit, Owner15pass. All remaining affected8 helper callers plus entry2 final44passed; historical rollback-count0 changed to current migrated3 plus full exact re-audit. Whole suite still incomplete, no Source/COMMIT-clock/first-chain PASS. Independent native zero Source residue and31old resources. Original fixture6/1 remains unstaged; no product/defaultmigration/currentDB/runtime/Goal changes.'
u=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary=summary)])
orig=m.atomic_write_text;m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=str(x.relative_to(R)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (B/'review.md',B/'independent-final-verification.json',B/'test-changes.json',B/'r1-independent-diagnosis.json',B/'r6-next-gate-diagnosis.json')];paths=[]
for tid in parents:
 cpf=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(cpf.read_text());prior=f'.evidence/{tid}/current-source-signed-domains-reference-1634.json';new=f'.evidence/{tid}/current-source-whole-suite-first-gates-reference-1635.json';assert prior in cp['evidence_files']
 (R/new).write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2));cp.update(authority_revision=u['project_revision'],step='whole-source-first-gates-native-repaired-full-suite-and-final-clock-pending');cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];cpf.write_text(json.dumps(cp,indent=2));paths.extend([new,str(cpf.relative_to(R))])
assert m.validate_installation()['status']=='GREEN';assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
w=mod('stage_wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');snapshots={tid:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2',f'.evidence/{tid}/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文') for tid in parents}
(B/'context-delivery-sync.json').write_text(json.dumps(dict(authority_revision=u['project_revision'],evidence_commit=head,delivery=delivery,sync=sync,checkpoints=snapshots,original_source_task='ACTIVE',full_source_delivery=False,goal_status_changed=False),indent=2));paths.append(str((B/'context-delivery-sync.json').relative_to(R)))
subprocess.run(['git','add','--',*paths],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): record whole Source suite first gates and pending exits'],cwd=R,check=True)
print(u['project_revision'],'WHOLE_SUITE_FIRST_GATES_VERIFIED_FULL_SOURCE_PENDING')
