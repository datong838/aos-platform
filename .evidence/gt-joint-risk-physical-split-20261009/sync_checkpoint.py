import importlib.util,sys,json,hashlib,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('split_mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001608'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();assert head.startswith('8aab0967')
receipt=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='ORIGINAL_FOUR_LEG_RISK_INFLIGHT_CONFLICT_RED_REPRODUCED',changed_files=['aos-platform/.evidence/'+B.name],commits=[head],verification=['native original Source/SCRAM/two approved parents/two cases: actual third leg23514 PHYSICAL_CAPACITY while parents1/10 each; expected fullplan preparation RED1FAILED25.91s','independent xid3328 aborted,allprepared0/Source1/NOLOGIN memberships0,old containers unchanged','R1 diagnostic helper NameError26.24s retained and independently reconciled; R2 fresh DB, no original replay'],risks=['test1minor allocations are not actual price or execution authority','plan body still descriptive refs, not final canonical joint receipt','full plan risk vs actual inflight separation and price semantics/lock graph/joint finalizer/true Target result/Judge input/natural firstchain pending'],blockers=[])
(B/'delivery.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary='Actual original Source/SCRAM/two independent approved parents and two-case four-leg preparation RED: Target0/Judge0 each1/10 parent, physical2/20000; Target1 actual23514 PHYSICAL_CAPACITY despite remaining parent risk. Native1FAILED25.91s,independent xid3328aborted/allprepared0/retainedSource1/NOLOGIN/old resources unchanged. Investigation only Delivery, not productGREEN. Full plan risk and actual inflight must separate; preserve full cases, unknown cost/occupancy and original capacity. Price per-request semantics/full lock graph/actual jointCOMMIT/Target real output/newJudge input/natural chain pending. Five parents ACTIVE, Goalactive.')])
orig=m.atomic_write_text
def safe(path,text,**kwargs):
 if str(path).startswith('/Users/ddt/.codex/memories/'):return
 return orig(path,text,**kwargs)
m.atomic_write_text=safe;sync=m.sync_projections(apply=True,include_prime=True)
files=json.loads((B/'stage-files.json').read_text())
refs=[dict(path=f,sha256=hashlib.sha256((R/f).read_bytes()).hexdigest()) for f in files]
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008']
for task in tasks:
 folder=R/'.evidence'/task;cp=json.loads((folder/'checkpoint.json').read_text());prior='.evidence/'+task+'/newjudge-pending-intent-reference-1608.json';assert prior in cp['evidence_files']
 refname='joint-risk-inflight-red-reference-1609.json';refpath='.evidence/'+task+'/'+refname
 (folder/refname).write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,execution_allowed=False,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs),indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='complete-four-leg-risk-inflight-conflict-native-RED-plan-risk-ledger-next')
 cp['evidence_files']=[refpath if x==prior else x for x in cp['evidence_files']]
 (folder/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
v=m.validate_installation();status=m.memory_status();assert v['status']=='GREEN';assert all(x['status']=='CURRENT' for x in status['projections'] if x['consistency']=='strong')
(B/'context-sync-1609.json').write_text(json.dumps(dict(revision=r['project_revision'],head=head,sync=sync,validation=v,status=status),ensure_ascii=False,indent=2)+'\n');print(r['project_revision'],v['status'])
