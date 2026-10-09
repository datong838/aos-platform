"""Exact test-only migration compatibility stage; preserve original fixture diff."""
import json, hashlib, subprocess, importlib.util, sys
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True)
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
m=mod('stage_memory',R/'scripts/memory/memoryctl.py');a=m.load_authority()
assert a['project_revision']=='AOS-001645' and git('rev-parse','HEAD').strip()=='75d287f50b255864b28df9d9404a3e749fffdc00'
assert git('branch','--show-current').strip()=='m1' and not git('diff','--cached','--name-only').strip()
p=json.loads((B/'independent-partial-terminal-verification.json').read_text());assert p['all_selected_passed'] and p['node_count']==337 and p['database_count']==123 and p['sources']==7 and p['old_resources_unchanged'] and not p['full_source_delivery']
q=json.loads((B/'independent-resource-final-verification.json').read_text());assert q['all_selected_passed'] and q['node_count']==1 and q['database_count']==1 and q['sources']==0 and q['old_resources_unchanged'] and not q['full_source_delivery']
for x in json.loads((B/'input-bindings-r1.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
parents=('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008')
for tid in (B.name,'gt-capacity-source-publication-20261006',*parents):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());assert t['status']=='ACTIVE' and t['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
 assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists()
test='services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py';assert git('diff','--numstat','--',test).split()[:2]==['6','1']
files=[str(x.relative_to(R)) for x in sorted(B.iterdir()) if x.is_file()]
subprocess.run(['git','add','--',*files],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(files)
subprocess.run(['git','commit','-m','test(aip): record whole Source partial gate and native resource recovery'],cwd=R,check=True);head=git('rev-parse','HEAD').strip()
delivery=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='WHOLE_SOURCE_337_PASS_RESOURCE_RECOVERED_FULL_PENDING_USER_PAUSE',changed_files=files,commits=[head],verification=['Whole original386nodes337PASS1SETUPERROR1849.82s48unexecuted; independently verified123retainedDBs and7native signed committed Source rows','Exact failed ri_trigger resource probe1PASS17.52s;93ownedconnections settings recorded; independent1DB zeroSource foundation ACL locks rolecleanup durability protectedresources and1963inputs verified'],risks=['Remaining48nodes/full386 Source acceptance pending','Actual final COMMIT expiry counterexample unresolved; no formal firstchain or modelreview PASS','Full rerun capacity headroom requires review after explicit user resume'],blockers=[])
summary=(B/'review.md').read_text()
u=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary=summary)])
orig=m.atomic_write_text;m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=str(x.relative_to(R)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (B/'review.md',B/'independent-partial-terminal-verification.json',B/'independent-resource-final-verification.json',B/'current-clock-completion-audit.json',B/'source-finalize-deferred-catalog-audit.json',B/'pause-handoff.json')];paths=[]
for tid in parents:
 cpf=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(cpf.read_text());prior=f'.evidence/{tid}/current-source-offset-signing-permit-reference-1645.json';new=f'.evidence/{tid}/current-source-full337-resource-pause-reference-1646.json';assert prior in cp['evidence_files']
 (R/new).write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2));cp.update(authority_revision=u['project_revision'],step='whole-source337-resource-recovered-full-suite-final-clock-pending-user-pause-handoff');cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];cpf.write_text(json.dumps(cp,indent=2));paths.extend([new,str(cpf.relative_to(R))])
assert m.validate_installation()['status']=='GREEN';assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
w=mod('stage_wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');snapshots={tid:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2',f'.evidence/{tid}/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文') for tid in parents}
(B/'context-delivery-sync.json').write_text(json.dumps(dict(authority_revision=u['project_revision'],evidence_commit=head,delivery=delivery,sync=sync,checkpoints=snapshots,original_source_task='ACTIVE',full_source_delivery=False,goal_status_changed=False,user_pause_requested=True,goal_pause_tool_readback_pending=True),indent=2));paths.append(str((B/'context-delivery-sync.json').relative_to(R)))
subprocess.run(['git','add','--',*paths],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): hand off Source verification before user restart'],cwd=R,check=True)
print(u['project_revision'],'WHOLE_SOURCE_337_PASS_RESOURCE_RECOVERED_FULL_PENDING_USER_PAUSE')
