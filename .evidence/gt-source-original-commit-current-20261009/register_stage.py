"""Exact test-only migration compatibility stage; preserve original fixture diff."""
import json, hashlib, subprocess, importlib.util, sys
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True)
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
m=mod('stage_memory',R/'scripts/memory/memoryctl.py');a=m.load_authority()
assert a['project_revision']=='AOS-001637' and git('rev-parse','HEAD').strip()=='bf30b0cb438222f8295ec0ae8336b22337b89e34'
assert not git('diff','--cached','--name-only').strip()
p=json.loads((B/'independent-final-verification.json').read_text());assert p['all_selected_passed'] and p['node_count']==6 and p['database_count']==6 and p['sources']==2 and p['old_resources_unchanged']
for x in json.loads((B/'input-bindings-r2.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
parents=('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008')
for tid in (B.name,'gt-capacity-source-publication-20261006',*parents):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());assert t['status']=='ACTIVE' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
 assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists()
test='services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py';indexed=git('show','HEAD:'+test)
working=(R/test).read_text()
first='def test_complete_native_publication_requires_actual_caller_commit('
next_fn='def test_preparation_transport_uses_verified_authentication'
dec="@pytest.mark.parametrize('native_original_fact_reader',['shared','distinct'],indirect=True)\n"
hs=indexed.index(first);he=indexed.index(next_fn,hs);ws=working.index(dec+first);we=working.index(next_fn,ws)
indexed=indexed[:hs]+working[ws:we]+indexed[he:]
anchor='    registered_cases = {\n';assert indexed.count(anchor)==1
indexed=indexed.replace(anchor,anchor+"        'test_complete_native_publication_requires_actual_caller_commit',\n")
sha=subprocess.check_output(['git','hash-object','-w','--stdin'],cwd=R,input=indexed.encode()).decode().strip()
subprocess.run(['git','update-index','--cacheinfo','100644,'+sha+','+test],cwd=R,check=True)
assert git('diff','--numstat','--',test).split()[:2]==['6','1']
files=[str(x.relative_to(R)) for x in sorted(B.iterdir()) if x.is_file()]+['.evidence/gt-capacity-source-publication-20261006/plan.md']
subprocess.run(['git','add','--',*files],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(files+[test])
subprocess.run(['git','commit','-m','test(aip): bind original actual commit exits to controlled public fixture'],cwd=R,check=True);head=git('rev-parse','HEAD').strip()
delivery=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='ORIGINAL_ACTUAL_CALLER_COMMIT_SIX_EXITS_GREEN',changed_files=[x for x in files if x.startswith(str(B.relative_to(R))+'/')],commits=[head],verification=['Original committed first exit RED42883 preserved; same actual completepublic fixture and signed command,6outcomes both layouts passed69.01s','Independent6DB exact frozen inputs/native signed durable2Sources committed xids and4negative DB zero publication rows,32oldresources unchanged'],risks=['Actual final COMMIT clock counterexample unresolved; no full Source delivery','No independent model review result or formal firstchain'],blockers=[])
summary='Original caller COMMIT threeoutcome function RED42883 defaultprivate fixture. Same completepublic controlled fixture test-only minimal repair, original signed command actualconn.commit durable independentOwner readback preserved; bothlayouts6passed69.01s,6independentDB, twoSources rawhash/nativeEd25519/provenance/session/xidcommitted/globalaccount verified,4negative DBzero rows. Exact7inputs/rootnative volume/fsync/protected32resources unchanged. Original fixture6/1unstaged; originalSource remainsACTIVE, fullSource/final COMMIT clock expiry counterexample/currentconsumer/fullfirstchain/modelreview pending. No productdefaults/currentDB/runtime/Goal change.'
u=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary=summary)])
orig=m.atomic_write_text;m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=str(x.relative_to(R)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (B/'review.md',B/'independent-final-verification.json',B/'native-commit-r2-result.json')];paths=[]
for tid in parents:
 cpf=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(cpf.read_text());prior=f'.evidence/{tid}/current-source-root-native-reference-1637.json';new=f'.evidence/{tid}/current-source-original-commit-reference-1638.json';assert prior in cp['evidence_files']
 (R/new).write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2));cp.update(authority_revision=u['project_revision'],step='original-caller-commit-six-green-final-clock-full-source-pending');cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];cpf.write_text(json.dumps(cp,indent=2));paths.extend([new,str(cpf.relative_to(R))])
assert m.validate_installation()['status']=='GREEN';assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
w=mod('stage_wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');snapshots={tid:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2',f'.evidence/{tid}/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文') for tid in parents}
(B/'context-delivery-sync.json').write_text(json.dumps(dict(authority_revision=u['project_revision'],evidence_commit=head,delivery=delivery,sync=sync,checkpoints=snapshots,original_source_task='ACTIVE',full_source_delivery=False,goal_status_changed=False),indent=2));paths.append(str((B/'context-delivery-sync.json').relative_to(R)))
subprocess.run(['git','add','--',*paths],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): record original signed actual commit exits'],cwd=R,check=True)
print(u['project_revision'],'ORIGINAL_ACTUAL_CALLER_COMMIT_SIX_EXITS_GREEN')
