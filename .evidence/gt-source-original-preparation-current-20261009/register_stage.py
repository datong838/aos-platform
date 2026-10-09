"""Exact test-only migration compatibility stage; preserve original fixture diff."""
import json, hashlib, subprocess, importlib.util, sys
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True)
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
m=mod('stage_memory',R/'scripts/memory/memoryctl.py');a=m.load_authority()
assert a['project_revision']=='AOS-001635' and git('rev-parse','HEAD').strip()=='28e0f9194565e5b7215abe303cd3ab0635e61788'
assert not git('diff','--cached','--name-only').strip()
p=json.loads((B/'independent-final-verification.json').read_text());assert p['all_selected_passed'] and p['node_count']==1 and p['database_count']==1 and p['old_resources_unchanged']
for x in json.loads((B/'input-bindings-r3.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
parents=('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008')
for tid in (B.name,'gt-capacity-source-publication-20261006',*parents):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());assert t['status']=='ACTIVE' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
 assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists()
test='services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py';indexed=git('show','HEAD:'+test)
working=(R/test).read_text()
first='def test_registered_original_inputs_prepare_native_v2_before_signing('
next_fn="@pytest.mark.parametrize('outcome'"
dec="@pytest.mark.parametrize('native_original_fact_reader',['shared','distinct'],indirect=True)\n"
hs=indexed.index(first);he=indexed.index(next_fn,hs);ws=working.index(dec+first);we=working.index(next_fn,ws)
indexed=indexed[:hs]+working[ws:we]+indexed[he:]
anchor='    registered_cases = {\n';assert indexed.count(anchor)==1
indexed=indexed.replace(anchor,anchor+"        'test_registered_original_inputs_prepare_native_v2_before_signing',\n")
sha=subprocess.check_output(['git','hash-object','-w','--stdin'],cwd=R,input=indexed.encode()).decode().strip()
subprocess.run(['git','update-index','--cacheinfo','100644,'+sha+','+test],cwd=R,check=True)
assert git('diff','--numstat','--',test).split()[:2]==['6','1']
files=[str(x.relative_to(R)) for x in sorted(B.iterdir()) if x.is_file()]+['.evidence/gt-capacity-source-publication-20261006/plan.md']
subprocess.run(['git','add','--',*files],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(files+[test])
subprocess.run(['git','commit','-m','test(aip): bind original pending preparation to controlled public fixture'],cwd=R,check=True);head=git('rev-parse','HEAD').strip()
delivery=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='ORIGINAL_PREPARATION_SHARED_GREEN_DISTINCT_RESOURCE_PENDING',changed_files=[x for x in files if x.startswith(str(B.relative_to(R))+'/')],commits=[head],verification=['Original registered inputs1pass and pending preparation42883 RED; test-only explicit fixture, r2 transaction rollback error preserved, r3 shared1pass; distinct unexecuted due2.5GB reserve','Independent exact input and retained DB native audit zero Source, protected31 resources unchanged'],risks=['Distinct layout not executed; full Source not delivered','Actual final COMMIT clock counterexample unresolved','No independent model review result'],blockers=[])
summary='Original registration/native pending preparation next gate: registration1pass, preparation42883RED from old defaultprivate fixture. Minimal test-only completepublicfixture same original signed command/transaction bindings, explicit two layouts; new rollback context mistake retained and force_rollback fixed. Shared1pass15.60s, independent native fullfunction ACL/lock audit, zero Source and31old resource identity unchanged. Distinct NOT_EXECUTED because lab2514800640 bytes reserve2500000000 and nextDB80MB unsafe; no delete/reuse/Goal change. Only bounded diagnosis delivered, originalSource remainsACTIVE; fullSource/final COMMIT clock/firstchain pending.'
u=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary=summary)])
orig=m.atomic_write_text;m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=str(x.relative_to(R)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (B/'review.md',B/'independent-final-verification.json',B/'resource-boundary.json')];paths=[]
for tid in parents:
 cpf=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(cpf.read_text());prior=f'.evidence/{tid}/current-source-whole-suite-first-gates-reference-1635.json';new=f'.evidence/{tid}/current-source-original-preparation-reference-1636.json';assert prior in cp['evidence_files']
 (R/new).write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2));cp.update(authority_revision=u['project_revision'],step='source-original-preparation-shared-green-distinct-resource-and-final-clock-pending');cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];cpf.write_text(json.dumps(cp,indent=2));paths.extend([new,str(cpf.relative_to(R))])
assert m.validate_installation()['status']=='GREEN';assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
w=mod('stage_wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');snapshots={tid:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2',f'.evidence/{tid}/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文') for tid in parents}
(B/'context-delivery-sync.json').write_text(json.dumps(dict(authority_revision=u['project_revision'],evidence_commit=head,delivery=delivery,sync=sync,checkpoints=snapshots,original_source_task='ACTIVE',full_source_delivery=False,goal_status_changed=False),indent=2));paths.append(str((B/'context-delivery-sync.json').relative_to(R)))
subprocess.run(['git','add','--',*paths],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): record partial original preparation and disk reserve gate'],cwd=R,check=True)
print(u['project_revision'],'ORIGINAL_PREPARATION_SHARED_GREEN_DISTINCT_PENDING')
