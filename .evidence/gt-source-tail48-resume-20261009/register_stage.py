"""Exact test-only migration compatibility stage; preserve original fixture diff."""
import json, hashlib, subprocess, importlib.util, sys
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True)
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
m=mod('stage_memory',R/'scripts/memory/memoryctl.py');a=m.load_authority()
assert a['project_revision']=='AOS-001646' and git('rev-parse','HEAD').strip()=='2c4d584377f59d44f6aa7a123ee69b39cfa46e4d'
assert not git('diff','--cached','--name-only').strip()
p=json.loads((B/'independent-tail44-terminal-verification.json').read_text());assert p['all_selected_passed'] and p['node_count']==44 and p['database_count']==44 and p['sources']==4 and p['old_resources_unchanged'] and not p['full_source_delivery']
for x in json.loads((B/'input-bindings-r3.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
parents=('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008')
from datetime import timedelta
renewals=[]
for tid in parents:
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());assert t['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
 if datetime.fromisoformat(t['lease_expires_at'])<=datetime.now(timezone.utc):
  renewals.append(m.renew_task(m.DEFAULT_PATHS,task_id=tid,owner=t['owner'],expected_revision=a['project_revision'],expected_task=t,lease_expires_at=(datetime.now(timezone.utc)+timedelta(hours=4)).isoformat(),reconciliation='Supported Goal active after user restart pause. Sole original owner; HEAD2c4d58437 exact scopes and fixture preserved, all test handles terminal. r7 delivered; r8 actual44PASS diskguard and independent44DB4nativeSource proof; only parent checkpoint reference update, no runtime/unknown replay. Original Source remains active/noDelivery.'))
(B/'parent-checkpoint-lease-renewals.json').write_text(json.dumps(renewals,indent=2))
for tid in (B.name,'gt-capacity-source-publication-20261006',*parents):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());assert t['status']=='ACTIVE' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
 assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists()
test='services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py';indexed=git('show','HEAD:'+test);working=(R/test).read_text()
import ast
name='test_latest_migration_installs_private_source_boundary'
oldnode=next(ast.get_source_segment(indexed,n) for n in ast.parse(indexed).body if isinstance(n,ast.FunctionDef) and n.name==name)
newnode=next(ast.get_source_segment(working,n) for n in ast.parse(working).body if isinstance(n,ast.FunctionDef) and n.name==name)
assert indexed.count(oldnode)==1;indexed=indexed.replace(oldnode,newnode,1)
sha=subprocess.check_output(['git','hash-object','-w','--stdin'],cwd=R,input=indexed.encode()).decode().strip();subprocess.run(['git','update-index','--cacheinfo','100644,'+sha+','+test],cwd=R,check=True)
assert git('diff','--numstat','--',test).split()[:2]==['6','1']
files=[str(x.relative_to(R)) for x in sorted(B.iterdir()) if x.is_file()]+['.evidence/gt-capacity-source-publication-20261006/plan.md']
subprocess.run(['git','add','--',*files],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(files+[test])
subprocess.run(['git','commit','-m','test(aip): verify current migration heads and retain Source tail gate evidence'],cwd=R,check=True);head=git('rev-parse','HEAD').strip()
delivery=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='SOURCE_TAIL44_PASS_CURRENT_MIGRATION_ORACLE_REPAIRED_FOUR_STORAGE_PENDING',changed_files=[x for x in files if x.startswith(str(B.relative_to(R))+'/')],commits=[head],verification=['Original48tail r1 pathcollection no effect; r2 actual2PASS1FAIL34.51s migrationhead159 versus old157 oracle independently3DBzeroSource diagnosed','Only migrationhead test uses exact codeheads and real157 ancestry; originaltable/role/public-interface controls and allotherAST preserved; r3 knownexpiry setup2PASS1ERROR40.32s independently4DBreconciled no replay','r4 actual44PASS1diskguardSETUPERROR421.94s4pending; independent44DB4nativeC signed committed Source rows1963inputhashes/fullfoundationACLlock/roles/tempcleanup/durability/protectedresources; no full386 green'],risks=['Original remaining4 and full386 single cumulative still pending; Colima20GiB capacity not increased by Desktop migration','Actual final COMMIT expiry counterexample and joint/naturalfirstchain still open; no formal permission or modelreviewPASS'],blockers=[])
summary=(B/'review.md').read_text()
u=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary=summary)])
orig=m.atomic_write_text;m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=str(x.relative_to(R)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (B/'review.md',B/'independent-tail44-terminal-verification.json',B/'migration-head-failure-independent.json',B/'expired-setup-r3-independent.json',B/'remaining-four.json',B/'exact-migration-oracle-change.json')];paths=[]
for tid in parents:
 cpf=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(cpf.read_text());prior=f'.evidence/{tid}/current-source-full337-resource-pause-reference-1646.json';new=f'.evidence/{tid}/current-source-tail44-migration-head-reference-1647.json';assert prior in cp['evidence_files']
 (R/new).write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2));cp.update(authority_revision=u['project_revision'],step='source-tail44-migration-head-repaired-four-storage-pending-final-commit-pending');cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];cpf.write_text(json.dumps(cp,indent=2));paths.extend([new,str(cpf.relative_to(R))])
assert m.validate_installation()['status']=='GREEN';assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
w=mod('stage_wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');snapshots={tid:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2',f'.evidence/{tid}/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文') for tid in parents}
(B/'context-delivery-sync.json').write_text(json.dumps(dict(authority_revision=u['project_revision'],evidence_commit=head,delivery=delivery,sync=sync,checkpoints=snapshots,original_source_task='ACTIVE',full_source_delivery=False,goal_status_changed=False),indent=2));paths.append(str((B/'context-delivery-sync.json').relative_to(R)))
subprocess.run(['git','add','--',*paths],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): record Source tail verification and storage continuation'],cwd=R,check=True)
print(u['project_revision'],'SOURCE_TAIL44_PASS_CURRENT_MIGRATION_ORACLE_REPAIRED_FOUR_STORAGE_PENDING')
