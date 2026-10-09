"""Commit exact current consumer fix; keep all original full contracts ACTIVE."""
from pathlib import Path
import hashlib,json,subprocess,sys,importlib.util
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True)
a=json.loads((B/'independent-matrix-verification.json').read_text())
g=json.loads((B/'independent-green-verification.json').read_text())
red=json.loads((B/'independent-red-verification.json').read_text())
assert len(a['databases'])==6 and a['old_resources_unchanged'] and g['three_extra_keys_denied'] and red['three_extra_keys_accepted']
change=json.loads((B/'expected-product-change.json').read_text());test=json.loads((B/'expected-test-change.json').read_text())
assert hashlib.sha256((R/change['path']).read_bytes()).hexdigest()==change['after_sha256']
assert hashlib.sha256(git('show','HEAD:'+change['path']).encode()).hexdigest()==change['before_sha256']
assert hashlib.sha256(git('show',':'+test['path']).encode()).hexdigest()==test['expected_index_sha256']
assert git('diff','--cached','--name-only').splitlines()==[test['path']]
files=[str(p.relative_to(R)) for p in sorted(B.iterdir()) if p.is_file()]
plans=['.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-gt-provider-capacity-publication-20261005/plan.md',
 '.evidence/gt-capacity-source-publication-20261006/plan.md']
# Do not add the entire working test file: its prior fixture edits are protected.
subprocess.run(['git','add','--',*files,*plans,change['path']],cwd=R,check=True)
allowed=set(files+plans+[change['path'],test['path']])
assert set(git('diff','--cached','--name-only').splitlines())==allowed
assert hashlib.sha256(git('show',':'+test['path']).encode()).hexdigest()==test['expected_index_sha256']
subprocess.run(['git','commit','-m','fix(aip): revalidate original current Source consumption commands'],cwd=R,check=True)
head=git('rev-parse','HEAD').strip()
assert git('diff','--numstat','--',test['path']).split()[:2]==['6','1']
sp=importlib.util.spec_from_file_location('m',R/'scripts/memory/memoryctl.py')
m=importlib.util.module_from_spec(sp);sys.modules['m']=m;sp.loader.exec_module(m)
auth=m.load_authority();assert auth['project_revision']=='AOS-001630'
for task in ('gt-provider-capacity-publication-schema-20261005','gt-capacity-source-publication-20261006','gt-capacity-occupation-source-20261007'):
 assert json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{task}.json').read_text())['status']=='ACTIVE'
d=m.complete_task(m.DEFAULT_PATHS,task_id=B.name,expected_revision=auth['project_revision'],
 result='CURRENT_SOURCE_EXTRA_KEY_NATIVE_DIAGNOSTIC_COMPLETE',changed_files=['aos-platform/.evidence/'+B.name],commits=[head],
 verification=['Authentic current independent Owner/native Source positive and unchanged replay; three extra-key variants accepted before fix (native RED27.45s), fixed denials after two-line instance revalidation (native GREEN23.75s)',
 'Original shared/distinct old and independent consumers 4PASS184.42s; persistent three-key original Owner regression both layouts2PASS111.16s/noSKIP',
 'Independent RED/GREEN Source signature/provenance and six regression retained DBs/roles/interfaces/31resources; selective13line test index excludes original6addition1deletion fixture changes'],
 risks=['Bounded diagnostic Delivery only; exact product fix belongs original ACTIVE publication-schema and regression Source-publication Tasks; no full Source/epoch/legacy Delivery',
 'Independent model reviewer previously daemon ownership failure; no model PASS claimed. Original current Source expiry namedSQL22023 assertion was not an original contract requirement and prior RED retained, no SQL/error/TTL change',
 'Formal deployment/identity/COMMIT temporal semantics/first business chain/Goal acceptance remain pending'],blockers=[])
rev=m.update_authority(expected_revision=auth['project_revision'],current_phase=auth['current_phase'],delivery_status=auth['delivery_status'],
 last_green_gate=auth['last_green_gate'],next_gate=auth['next_gate'],evidence=auth['evidence']+[dict(type='checkpoint',
 path='aos-platform/.evidence/'+B.name+'/review.md',summary='Current independent Owner direct Source consumer three extra-key instances accepted native RED. Original Task scope renewed/plan amended, exact two-line direct instance revalidation fixes all three, legal replay intact; native GREEN1PASS23.75s, old+independent shared/distinct4PASS184.42s, persistent original Owner both layouts2PASS111.16s. Independent Source signatures/provenance/six regression DBs/NOLOGIN/interfaces/31resources verified. Exact13line test hunk committed, prior6/1 fixture changes preserved unstaged. Bounded diagnostic Delivery only; original complete Source/epoch/legacy Task ACTIVE, model review local daemon limitation retained. Prior expiry namedSQL assertion not mandated by original contract, no SQL/TTL/error semantics changes. No currentDB/runtime/Provider/Goal change.')])
orig=m.atomic_write_text
m.atomic_write_text=lambda path,text,**kw:None if str(path).startswith('/Users/ddt/.codex/memories/') else orig(path,text,**kw)
sync=m.sync_projections(apply=True,include_prime=True)
refs=[dict(path=f,sha256=hashlib.sha256((R/f).read_bytes()).hexdigest()) for f in files+plans+[change['path']]]
# Working test includes protected prior edits; bind its actual hash explicitly.
refs.append(dict(path=test['path'],sha256=hashlib.sha256((R/test['path']).read_bytes()).hexdigest()))
updates=[]
for task in ('gt-atomic-model-admission-20261008','gt-model-typed-proof-20261008','gt-judge-call-authority-20261008','gt-judge-budget-parent-20261008','gt-shared-budget-fence-order-20261008'):
 cpfile=R/'.evidence'/task/'checkpoint.json';cp=json.loads(cpfile.read_text())
 receipt=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{task}.json').read_text())
 assert receipt['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and receipt['status']=='ACTIVE'
 assert datetime.fromisoformat(receipt['lease_expires_at'])>datetime.now(timezone.utc)
 prior='.evidence/'+task+'/current-source-body-expiry-reference-1630.json';ref='.evidence/'+task+'/current-source-command-fix-reference-1631.json'
 assert prior in cp['evidence_files']
 (R/ref).write_text(json.dumps(dict(authority_revision=rev['project_revision'],head=head,
 references=[dict(path=prior,sha256=hashlib.sha256((R/prior).read_bytes()).hexdigest())]+refs,execution_allowed=False),indent=2))
 cp.update(authority_revision=rev['project_revision'],step='current-source-command-instance-fix-native-and-persistent-green-original-full-contract-review-next')
 cp['evidence_files']=[ref if x==prior else x for x in cp['evidence_files']];cpfile.write_text(json.dumps(cp,indent=2));updates.extend([str(cpfile.relative_to(R)),ref])
assert m.validate_installation()['status']=='GREEN'
assert all(x['status']=='CURRENT' for x in m.memory_status()['projections'] if x['consistency']=='strong')
(B/'context-delivery.json').write_text(json.dumps(dict(delivery=d,revision=rev['project_revision'],sync=sync,
 validation='GREEN',strong_projections='CURRENT',original_feature_tasks='ACTIVE',protected_test_fixture_diff='6 additions/1 deletion unstaged'),ensure_ascii=False,indent=2))
updates.append(str((B/'context-delivery.json').relative_to(R)))
assert not git('diff','--cached','--name-only').strip()
subprocess.run(['git','add','--',*updates],cwd=R,check=True)
assert set(git('diff','--cached','--name-only').splitlines())==set(updates)
subprocess.run(['git','commit','-m','docs(aos): register current Source command fix native acceptance'],cwd=R,check=True)
print(rev['project_revision'],'CURRENT_SOURCE_COMMAND_FIX_STAGE_COMPLETE_ORIGINAL_CONTRACTS_ACTIVE')
