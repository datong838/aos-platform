import importlib.util,sys,json,hashlib,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('joint_mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001607'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();assert head.startswith('dad8f257')
receipt=m.complete_task(m.DEFAULT_PATHS,task_id='gt-newjudge-intent-native-20261009',expected_revision=a['project_revision'],result='OWNED_LAB_NEWJUDGE_PENDING_INTENT_GREEN_FULL_JOINT_FINALIZER_PENDING',changed_files=['aos-platform/.evidence/gt-newjudge-intent-native-20261009'],commits=[head],verification=['actual signed Source/SCRAM/newJudge/Target dependent Intent/replay/negative/actual COMMIT deny: native1PASS81.57s','default Judge native1PASS64.57s; adjacent293PASS0.70s','independent aborted xid2767,0debit/0Target/0Judge Intent,Source1/NOLOGIN,FORCE RLS/noDML/immutable deferred triggers,old resources unchanged'],risks=['test-only original Source/root identity not formal authority','full four-leg Intent/finalizer/transport/Usage and natural firstchain pending','parallel physical upper-bound competition pending'],blockers=[])
(B/'delivery.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/gt-newjudge-intent-native-20261009/review.md',summary='Original newJudge awaiting Target dependency Intent added with actual Source/SCRAM/own approved parent/shared risk/Target exact application and same xid-pid; original approval Proposal hash and approval-event idempotency bound, negative and actual COMMIT23514 deny native1PASS81.57s,defaultJudge1PASS64.57s adjacent293PASS0.70s. Independent aborted0debit0Target0Judge Source1 retained/NOLOGIN/privateFORCERLS/noDML/old resources unchanged. No actual output/transport/full four-leg finalizer or business firstchain. Five parent Tasks ACTIVE; bounded lab only Delivery.')])
orig=m.atomic_write_text
def safe(path,text,**kwargs):
 if str(path).startswith('/Users/ddt/.codex/memories/'):return
 return orig(path,text,**kwargs)
m.atomic_write_text=safe;sync=m.sync_projections(apply=True,include_prime=True)
files=[str(p.relative_to(R)) for p in B.iterdir() if p.is_file() and p.name not in ('context-sync-1608.json','sync_joint_checkpoint.py')]
files+=json.loads((B/'stage-files.json').read_text())
files=list(dict.fromkeys(files))
refs=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in files]
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008']
for task in tasks:
 folder=R/'.evidence'/task;cp=json.loads((folder/'checkpoint.json').read_text());prior='.evidence/'+task+'/source-newjudge-native-reference-1607.json'
 assert prior in cp['evidence_files']
 refname='newjudge-pending-intent-reference-1608.json';refpath='.evidence/'+task+'/'+refname
 (folder/refname).write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,execution_allowed=False,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs),indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='Source-newJudge-pending-Intent-native-green-actual-input-joint-finalizer-pending')
 cp['evidence_files']=[refpath if x==prior else x for x in cp['evidence_files']]
 (folder/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
v=m.validate_installation();status=m.memory_status();assert v['status']=='GREEN'
assert all(x['status']=='CURRENT' for x in status['projections'] if x['consistency']=='strong')
(B/'context-sync-1608.json').write_text(json.dumps(dict(revision=r['project_revision'],head=head,sync=sync,validation=v,status=status),ensure_ascii=False,indent=2)+'\n');print(r['project_revision'],v['status'])
