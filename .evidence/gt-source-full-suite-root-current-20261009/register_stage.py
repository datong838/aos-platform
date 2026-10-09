"""Exact test-only migration compatibility stage; preserve original fixture diff."""
import json, hashlib, subprocess, importlib.util, sys
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True)
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
m=mod('stage_memory',R/'scripts/memory/memoryctl.py');a=m.load_authority()
assert a['project_revision']=='AOS-001639' and git('rev-parse','HEAD').strip()=='938c5209c90f7cacd9cffd08998aaff9a812979f'
assert not git('diff','--cached','--name-only').strip()
p=json.loads((B/'independent-final-verification.json').read_text());assert p['all_selected_passed'] and p['node_count']==5 and p['database_count']==1 and p['sources']==0 and p['old_resources_unchanged']
for x in json.loads((B/'input-bindings-r2.json').read_text()):assert hashlib.sha256((R/x['path']).read_bytes()).hexdigest()==x['sha256']
parents=('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008')
for tid in (B.name,'gt-capacity-source-publication-20261006',*parents):
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{tid}.json').read_text());assert t['status']=='ACTIVE' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
 assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{tid}.json').exists()
test='services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py';indexed=git('show','HEAD:'+test);working=(R/test).read_text()
import ast
names={'test_original_source_binding_uses_typed_normalization_in_private_reader','test_original_source_time_profile_matches_original_datetime_oracle','test_original_source_candidate_profile_matches_original_shape_oracle'}
old_nodes={n.name:ast.get_source_segment(indexed,n) for n in ast.parse(indexed).body if isinstance(n,ast.FunctionDef) and n.name in names}
new_nodes={n.name:ast.get_source_segment(working,n) for n in ast.parse(working).body if isinstance(n,ast.FunctionDef) and n.name in names}
assert old_nodes.keys()==new_nodes.keys()==names
for name in sorted(names):assert indexed.count(old_nodes[name])==1;indexed=indexed.replace(old_nodes[name],new_nodes[name],1)
sha=subprocess.check_output(['git','hash-object','-w','--stdin'],cwd=R,input=indexed.encode()).decode().strip();subprocess.run(['git','update-index','--cacheinfo','100644,'+sha+','+test],cwd=R,check=True)
assert git('diff','--numstat','--',test).split()[:2]==['6','1']
files=[str(x.relative_to(R)) for x in sorted(B.iterdir()) if x.is_file()]+['.evidence/gt-capacity-source-publication-20261006/plan.md']
subprocess.run(['git','add','--',*files],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(files+[test])
subprocess.run(['git','commit','-m','test(aip): audit migrated source normalization profiles in original oracles'],cwd=R,check=True);head=git('rev-parse','HEAD').strip()
delivery=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='WHOLE_SOURCE_FIRST_NORMALIZATION_GAP_REPAIRED_FULL_PENDING',changed_files=[x for x in files if x.startswith(str(B.relative_to(R))+'/')],commits=[head],verification=['Original101function386node full selection50pass1fail196.50s,335unexecuted; duplicate migrated source field profile native RED independently diagnosed','Original3normalization oracle functions5nodes pass20.04s, full original date/shape/type negative controls retained; independent1963inputs and zeroSource/protected32resources'],risks=['Full Source suite and actual final COMMIT expiry counterexample pending','No modelreview or formal firstchain acceptance'],blockers=[])
summary='Full original101function386nodes maxfail1 nofilter50passed1failed196.50s/335unexecuted. Duplicate permanent157 sourcefield profile before typed reader assertions; failedDB exactexisting functionACLlock audit/zeroSource. Same SourceTask testonly3oracle functions replace repeated install with strict existing audit and rollback4permanent functions+audit;5passed20.04s all original date/shape/type and native/private/naivehash controls retained. Independent1963inputs/one originalsession newDB/protected32resources unchanged. Current commitSQL identical4350f338 actualexpiredSource COMMIT counterexample, finalclock/fullSource/firstchain/modelreview unresolved. Originalfixture6/1unstaged, SourceTask ACTIVE/noGoal/currentDB/runtime changes.'
u=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary=summary)])
orig=m.atomic_write_text;m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=str(x.relative_to(R)),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (B/'review.md',B/'independent-final-verification.json',B/'first-failure-independent.json',B/'clock-completion-audit.json')];paths=[]
for tid in parents:
 cpf=R/'.evidence'/tid/'checkpoint.json';cp=json.loads(cpf.read_text());prior=f'.evidence/{tid}/current-source-original-approval-reference-1639.json';new=f'.evidence/{tid}/current-source-normalization-reference-1640.json';assert prior in cp['evidence_files']
 (R/new).write_text(json.dumps(dict(authority_revision=u['project_revision'],head=head,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2));cp.update(authority_revision=u['project_revision'],step='whole-source-first-normalization-gap-repaired-full-suite-next-final-clock-pending');cp['evidence_files']=[new if x==prior else x for x in cp['evidence_files']];cpf.write_text(json.dumps(cp,indent=2));paths.extend([new,str(cpf.relative_to(R))])
assert m.validate_installation()['status']=='GREEN';assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
w=mod('stage_wake',R/'scripts/long-task-watchdog/aos_wake_progress.py');snapshots={tid:w.checkpoint_snapshot(R,'01a107a2-e9e4-7670-bc44-1144fa9b27e2',f'.evidence/{tid}/checkpoint.json',R.parent/'docs/palantier/AOS项目开发上下文') for tid in parents}
(B/'context-delivery-sync.json').write_text(json.dumps(dict(authority_revision=u['project_revision'],evidence_commit=head,delivery=delivery,sync=sync,checkpoints=snapshots,original_source_task='ACTIVE',full_source_delivery=False,goal_status_changed=False),indent=2));paths.append(str((B/'context-delivery-sync.json').relative_to(R)))
subprocess.run(['git','add','--',*paths],cwd=R,check=True);assert set(git('diff','--cached','--name-only').splitlines())==set(paths)
subprocess.run(['git','commit','-m','docs(aos): record whole Source normalization gap and pending full exits'],cwd=R,check=True)
print(u['project_revision'],'WHOLE_SOURCE_FIRST_NORMALIZATION_GAP_REPAIRED_FULL_PENDING')
