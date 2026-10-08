import importlib.util,sys,json,hashlib,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('split_mc',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
a=m.load_authority();assert a['project_revision']=='AOS-001609'
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008']
renewed={}
for t in tasks:
 current=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/(t+'.json')).read_text())
 renewed[t]=m.renew_task(m.DEFAULT_PATHS,task_id=t,owner=current['owner'],expected_revision=a['project_revision'],expected_task=current,lease_expires_at='2026-10-08T23:12:18.820894+00:00',reconciliation='Same sole writer; HEADa94fbe1c and active exact parent scope/Lease matched; native R2 terminal PASS and unknown effects read-only reconciled; no formal runtime change. Continuing registered full joint protocol.')
(B/'renewals.json').write_text(json.dumps(renewed,indent=2)+'\n')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();assert head.startswith('a94fbe1c')
receipt=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=a['project_revision'],result='COMPLETE_ORIGINAL_PLAN_RISK_PREPARATION_NATIVE_GREEN_FULL_FINALIZER_PENDING',changed_files=['aos-platform/.evidence/'+B.name],commits=[head],verification=['actual originalSource/SCRAM/Target+newJudge complete2case4leg plan risk producer native1PASS70.44s; actualphysical0requests0tokens;247adjacentPASS0.67s','actual COMMIT23514 denied,independent aborted/planRisk0/debit0/Intent0/Source1/NOLOGIN/privateFORCERLS/oldresources unchanged'],risks=['original parent risk preparation only; per-leg price and allocation not derived','full actual occupation/unknown retention/lock graph/trusted jointCOMMIT/real Target output/newJudge input/natural firstchain pending'],blockers=[])
(B/'delivery.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
r=m.update_authority(expected_revision=a['project_revision'],current_phase=a['current_phase'],delivery_status=a['delivery_status'],last_green_gate=a['last_green_gate'],next_gate=a['next_gate'],evidence=a['evidence']+[dict(type='checkpoint',path='aos-platform/.evidence/'+B.name+'/review.md',summary='Complete original2case4leg plan risk producer added separately from inflight, actual original Source/SCRAM/two independent approved parents/full actual Suite/Target-newJudge exact original application/Actor/Rule/hash/parentCaps10each. Server physicalPreparedRequests0/Tokens0,exact replay and UUID/null/target/hash/privateACL/earlyconstraints/actualCOMMIT23514 negatives native1PASS70.44s;adjacent247PASS0.67s. Independent aborted planrisk/debit/Intent0,Source1 retained/NOLOGIN/forceRLS/oldresources unchanged. Preparation only; no perleg price assignment or actual admission/finalizer/Usage/Targetrealoutput/Judgeinput/natural firstchain. Five parents ACTIVE; bounded lab Delivery only.')])
orig=m.atomic_write_text
def safe(path,text,**kwargs):
 if str(path).startswith('/Users/ddt/.codex/memories/'):return
 return orig(path,text,**kwargs)
m.atomic_write_text=safe;sync=m.sync_projections(apply=True,include_prime=True)
files=json.loads((B/'stage-files.json').read_text())
refs=[dict(path=f,sha256=hashlib.sha256((R/f).read_bytes()).hexdigest()) for f in files]
tasks=['gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008']
for task in tasks:
 folder=R/'.evidence'/task;cp=json.loads((folder/'checkpoint.json').read_text());prior='.evidence/'+task+'/joint-risk-inflight-red-reference-1609.json';assert prior in cp['evidence_files']
 refname='complete-plan-risk-reference-1610.json';refpath='.evidence/'+task+'/'+refname
 (folder/refname).write_text(json.dumps(dict(authority_revision=r['project_revision'],head=head,execution_allowed=False,references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs),indent=2)+'\n')
 cp.update(authority_revision=r['project_revision'],step='complete-four-leg-risk-native-green-actual-occupation-joint-finalizer-pending')
 cp['evidence_files']=[refpath if x==prior else x for x in cp['evidence_files']]
 (folder/'checkpoint.json').write_text(json.dumps(cp,indent=2)+'\n')
v=m.validate_installation();status=m.memory_status();assert v['status']=='GREEN';assert all(x['status']=='CURRENT' for x in status['projections'] if x['consistency']=='strong')
(B/'context-sync-1610.json').write_text(json.dumps(dict(revision=r['project_revision'],head=head,sync=sync,validation=v,status=status),ensure_ascii=False,indent=2)+'\n');print(r['project_revision'],v['status'])
